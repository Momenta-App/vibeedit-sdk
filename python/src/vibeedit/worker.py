"""Bounded Pi RPC workers with durable intent, local allowance enforcement and no shell tools.

A successful RPC prompt acknowledgement is admission, not completion. Process/network
ambiguity retains its original operation and allowance; it never starts a substitute call.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import hmac
import http.server
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal, ROUND_CEILING
from jsonschema.exceptions import ValidationError
from pathlib import Path

from vibeedit.goals import SCHEMA, Store, canonical, detach, project_path

PI_VERSION = "1.3.0"
PI_INTEGRITY = "sha512-V/WoCjA2hQSe3QLWIUB24cTRdtEdeLiIzkDqU5RMXV6VWuD+KGZnzVBMhglwdnQTySkehZsjt8a3g6Jd2g4nnw=="
OPENROUTER = "https://openrouter.ai/api/v1"
TOOLS = {"project_read", "project_image", "artifact_write", "render_ffmpeg", "analyze", "analysis_status"}
PROFILES = {"economical-v1": "z-ai/glm-5.3-flash", "visual-v1": "z-ai/glm-5.3-flashx", "reviewer-v1": "z-ai/glm-5.3-prime"}
PROVIDERS = {"economical-v1": "open-inference/fp4", "visual-v1": "z-ai/fp8", "reviewer-v1": "alibaba"}
PROVIDER_MODELS = {"economical-v1": "OpenInference | z-ai/glm-5.3-flash-20260826", "visual-v1": "Z.AI | z-ai/glm-5.3-flashx-20260918", "reviewer-v1": "Alibaba | z-ai/glm-5.3-prime-20260921"}
MAX_JSON_BYTES = 2 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("credential-bearing provider redirects are refused")


def provider_open(request, timeout):
    return urllib.request.build_opener(NoRedirect).open(request, timeout=timeout)


def companion_path():
    from vibeedit.data import data_path
    development = Path(__file__).resolve().parents[3] / "companion"
    return development if development.is_dir() else data_path("companion")


def config_home():
    return Path(os.environ.get("VIBEEDIT_CONFIG_HOME", Path.home() / ".config" / "vibeedit"))


def _read_private(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("protected credential configuration missing; configure explicitly, no internal-key fallback")
    if os.name != "nt" and (path.stat().st_mode & 0o077 or path.parent.stat().st_mode & 0o077):
        raise ValueError("credential config must be mode 0600 in a mode 0700 directory")
    config = json.loads(path.read_text(encoding="utf-8"))
    if os.name == "nt":
        if config.get("apiKey") or not config.get("apiKeyDpapi"):
            raise ValueError("Windows plaintext credential config refused; configure OS-protected BYOK")
        config["apiKey"] = _windows_protect(base64.b64decode(config["apiKeyDpapi"], validate=True), decrypt=True).decode()
    return config


def _windows_protect(data, *, decrypt=False):
    """User-scoped Windows DPAPI: no plaintext customer key in config files."""
    if os.name != "nt":
        raise ValueError("Windows DPAPI is only available on Windows")
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    destination = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    # CRYPTPROTECT_UI_FORBIDDEN; omit LOCAL_MACHINE so ciphertext is user-bound.
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(destination)):
        raise ValueError("Windows OS credential protection failed")
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel.LocalFree(destination.pbData)


def configure_byok(key):
    if not key.strip() or len(key.strip()) > 1024 or any(c.isspace() for c in key.strip()):
        raise ValueError("invalid OpenRouter customer key")
    directory = config_home()
    if directory.is_symlink():
        raise ValueError("credential directory cannot be a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    temporary = directory / f".worker-{uuid.uuid4().hex}.json"
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        credential = {"apiKeyDpapi": base64.b64encode(_windows_protect(key.strip().encode())).decode()} if os.name == "nt" else {"apiKey": key.strip()}
        stream.write(canonical({"schemaVersion": SCHEMA, "funding": "byok", **credential}))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(directory / "worker.json")
    return {"schemaVersion": SCHEMA, "ok": True, "funding": "byok", "provider": "OpenRouter", "credentialStored": True}


def validate_task(spec):
    if not isinstance(spec, dict) or not str(spec.get("task", "")).strip():
        raise ValueError("worker task required")
    if spec.get("funding") not in {"byok", "managed"}:
        raise ValueError("funding must be explicit: byok or managed")
    if spec.get("profile") not in PROFILES:
        raise ValueError("unknown versioned worker profile")
    for key, low, high in (("maxModelCalls", 1, 100), ("maxToolCalls", 1, 500), ("maxOutputTokens", 1, 32768), ("maxRetailMicrousd", 1, 1_000_000_000), ("maxSeconds", 1, 86400)):
        if type(spec.get(key)) is not int or not low <= spec[key] <= high:
            raise ValueError(f"{key} must be an integer in [{low}, {high}]")
    if type(spec.get("platformBudgetMicros", 0)) is not int or not 0 <= spec.get("platformBudgetMicros", 0) <= spec["maxRetailMicrousd"] // 2:
        raise ValueError("platformBudgetMicros must explicitly allocate real infrastructure within the total retail ceiling")
    if type(spec.get("maxNoProgressCalls", 3)) is not int or not 1 <= spec.get("maxNoProgressCalls", 3) <= 20:
        raise ValueError("maxNoProgressCalls must be an integer in [1,20] (default3)")
    if spec.get("delegationLimit", 0) != 0:
        raise ValueError("nested delegation is disabled in bounded workers")
    if not isinstance(spec.get("tools"), list) or not set(spec["tools"]).issubset(TOOLS):
        raise ValueError("only explicitly allowed scoped project tools are supported; shell is not a sandbox")
    if not isinstance(spec.get("references"), list) or not all(isinstance(r, str) for r in spec["references"]):
        raise ValueError("references must enumerate project-relative files readable by the worker")
    if spec["references"] and (not isinstance(spec.get("referenceDigests"), dict) or set(spec["references"]) != set(spec["referenceDigests"])):
        raise ValueError("referenceDigests must pin every allowed source/reference SHA-256")
    if any(not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) for digest in spec.get("referenceDigests", {}).values()):
        raise ValueError("reference digests must be lowercase SHA-256")
    if not isinstance(spec.get("outputSchema"), dict):
        raise ValueError("outputSchema is required")
    from jsonschema import Draft202012Validator
    Draft202012Validator.check_schema(spec["outputSchema"])
    if not isinstance(spec.get("artifacts"), list):
        raise ValueError("artifact contracts required (may be empty only for structured review tasks)")
    if set(spec["tools"]) & {"analyze", "analysis_status"}:
        permissions = spec.get("analysisPermissions")
        if not isinstance(permissions, list) or not 1 <= len(permissions) <= 32:
            raise ValueError("paid analysis tools require explicit bounded analysisPermissions")
        ids = set()
        for permission in permissions:
            required = {"operationId", "service", "source", "sourceSha256", "maxRetailMicrousd"}
            if not isinstance(permission, dict) or not required <= set(permission) <= required | {"options", "maxDownloadBytes"}:
                raise ValueError("analysis permission requires exact operation/service/source/SHA and retail ceiling")
            operation = permission["operationId"]
            if not isinstance(operation, str) or not 1 <= len(operation) <= 120 or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-" for char in operation) or operation in ids:
                raise ValueError("analysis operations must have unique bounded explicit IDs")
            ids.add(operation)
            if permission["service"] not in {"video", "faces", "speakers"} or permission["source"] not in spec["references"] or spec["referenceDigests"][permission["source"]] != permission["sourceSha256"]:
                raise ValueError("analysis permission must bind an authorized source/reference and named public service")
            if type(permission["maxRetailMicrousd"]) is not int or not 0 < permission["maxRetailMicrousd"] <= spec["maxRetailMicrousd"] or not isinstance(permission.get("options", {}), dict) or len(canonical(permission.get("options", {})).encode()) > 65536:
                raise ValueError("analysis permission exceeds bounded retail/options scope")
            if set(permission.get("options", {})) & {"uploadId", "maxRetailUsd", "fundingAllowanceId"}:
                raise ValueError("analysis funding/source admission fields are controlled by the trusted client")
            if type(permission.get("maxDownloadBytes", 128*1024*1024)) is not int or not 0 < permission.get("maxDownloadBytes", 128*1024*1024) <= 128*1024*1024:
                raise ValueError("analysis download limit exceeds128 MiB")
    return spec


def confined(root, path, *, must_exist=True):
    if not isinstance(path, str) or not path or Path(path).is_absolute() or "\\" in path:
        raise ValueError("artifact paths must be project-relative POSIX paths")
    parts = Path(path).parts
    if any(p in {"..", "."} for p in parts):
        raise ValueError("path traversal refused")
    candidate = root / path
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlink paths are not allowed in worker scope")
    resolved = candidate.resolve(strict=must_exist)
    if not resolved.is_relative_to(root):
        raise ValueError("path leaves project scope")
    return resolved


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_artifacts(root, contracts):
    """Verify exact bytes, typed JSON and playable media, rather than accepting a model claim."""
    root = project_path(root)
    receipts = []
    for contract in contracts:
        path = confined(root, contract["path"])
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"missing/nonempty artifact required: {contract['path']}")
        digest = _digest(path)
        if contract.get("sha256") and contract["sha256"] != digest:
            raise ValueError("artifact digest does not match completion contract")
        kind = contract.get("kind", "file")
        if kind in {"json", "composition", "review"}:
            value = json.loads(path.read_text(encoding="utf-8"))
            if kind == "composition":
                from vibeedit.validation import validate_composition
                validate_composition(value)
            if contract.get("schema"):
                from jsonschema import Draft202012Validator
                Draft202012Validator(contract["schema"]).validate(value)
            if kind == "review" and not (isinstance(value, dict) and value.get("findings") is not None and value.get("sourceSha256")):
                raise ValueError("review artifact must identify inspected source and findings")
        if kind == "render":
            from vibeedit.ffmpeg import ffprobe_path
            result = subprocess.run([ffprobe_path(), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, timeout=30, check=True)
            metadata = json.loads(result.stdout)
            if not any(s.get("codec_type") == "video" and s.get("width", 0) > 0 for s in metadata["streams"]) or float(metadata.get("format", {}).get("duration", 0)) <= 0:
                raise ValueError("render contract requires a playable nonzero video")
        receipts.append({"path": contract["path"], "sha256": digest, "byteLength": path.stat().st_size, "kind": kind})
    render_digests = {receipt["sha256"] for receipt in receipts if receipt["kind"] == "render"}
    for receipt in receipts:
        if receipt["kind"] == "review" and render_digests:
            report = json.loads(confined(root, receipt["path"]).read_text(encoding="utf-8"))
            if report["sourceSha256"] not in render_digests:
                raise ValueError("final review must reference the verified rendered bytes")
    return receipts


class RpcClient:
    """One binary-LF reader per process; responses correlate by ID, never by order."""
    def __init__(self, command, cwd, env):
        options = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        self.process = subprocess.Popen(command, cwd=cwd, env={**env, "PYTHONIOENCODING": "utf-8"}, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
        self.records = queue.Queue()
        self.pending = {}
        self.write_lock = threading.Lock()
        self.errors = queue.Queue()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.diagnostics = threading.Thread(target=self._drain_stderr, daemon=True)
        self.reader.start()
        self.diagnostics.start()

    def _read(self):
        try:
            while line := self.process.stdout.readline(MAX_JSON_BYTES+1):
                if len(line) > MAX_JSON_BYTES or not line.endswith(b"\n"):
                    raise ValueError("invalid or oversized Pi JSONL record")
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("Pi protocol record must be object")
                if record.get("type") == "response" and record.get("id") in self.pending:
                    self.pending[record["id"]].put(record)
                self.records.put(record)
        except (OSError, ValueError) as error:
            self.errors.put(type(error).__name__)
        finally:
            self.records.put({"type": "vibeedit_rpc_exit", "returncode": self.process.poll()})

    def _drain_stderr(self):
        # Consume continuously; raw diagnostic text can contain provider secrets or private media.
        while self.process.stderr.read(4096):
            pass

    def send(self, command, identity=None):
        identity = identity or str(uuid.uuid4())
        if identity in self.pending:
            raise ValueError("duplicate in-flight RPC command ID")
        self.pending[identity] = queue.Queue(maxsize=1)
        with self.write_lock:
            self.process.stdin.write((canonical({**command, "id": identity})+"\n").encode())
            self.process.stdin.flush()
        return identity

    def response(self, identity, timeout=10):
        try:
            result = self.pending[identity].get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError("Pi observation timeout; original command remains indeterminate") from None
        if not result.get("success"):
            raise ValueError(f"Pi rejected {result.get('command')}; inspect private session, no automatic resubmission")
        return result

    def close(self):
        with contextlib.suppress(OSError):
            self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                os.killpg(self.process.pid, signal.SIGTERM)
            else:
                subprocess.run(["taskkill", "/PID", str(self.process.pid), "/T", "/F"], capture_output=True, check=False)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    os.killpg(self.process.pid, signal.SIGKILL)
                else:
                    self.process.kill()
                self.process.wait(timeout=3)


def refresh_profiles():
    request = urllib.request.Request(OPENROUTER+"/models", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)
    models = {m["id"]: m for m in data["data"]}
    profiles = {}
    for profile, identity in PROFILES.items():
        model = models.get(identity)
        if not model or not {"tools", "response_format"}.issubset(model.get("supported_parameters", [])):
            raise ValueError("pinned model capability missing; no silent fallback")
        with urllib.request.urlopen(OPENROUTER+"/models/"+identity+"/endpoints", timeout=20) as response:
            endpoints = json.load(response)["data"]["endpoints"]
        endpoint = next((e for e in endpoints if e.get("tag") == PROVIDERS[profile]), None)
        if not endpoint or endpoint.get("name") != PROVIDER_MODELS[profile] or not {"tools", "response_format"}.issubset(endpoint.get("supported_parameters", [])):
            raise ValueError("pinned provider route unavailable; no unapproved fallback")
        prompt = Decimal(endpoint["pricing"]["prompt"])
        completion = Decimal(endpoint["pricing"]["completion"])
        if not prompt.is_finite() or not completion.is_finite() or min(prompt, completion) < 0:
            raise ValueError("unknown/invalid provider pricing; inference admission disabled")
        profiles[profile] = {"model": identity, "contextWindow": min(model["context_length"], endpoint["context_length"]), "providerRoute": endpoint["tag"], "providerModelName": endpoint["name"], "input": [m for m in model["architecture"]["input_modalities"] if m in {"text", "image"}], "inputUsdPerToken": str(prompt), "outputUsdPerToken": str(completion), "checkedAtUnix": time.time(), "expiresAtUnix": time.time()+86400, "inferenceQualified": False, "provider": "OpenRouter"}
    return profiles


def _funding(spec):
    if spec["funding"] == "managed":
        from vibeedit.myriograph import Myriograph, MyriographError, read_config
        try:
            customer = Myriograph(read_config())
            customer.bind_customer()
            return customer
        except (OSError, ValueError, MyriographError):
            raise ValueError("managed inference unavailable: explicitly configure the public Myriograph customer account/key; no internal/provider-key fallback") from None
    config = _read_private(config_home()/"worker.json")
    if config.get("funding") != "byok" or not config.get("apiKey"):
        raise ValueError("configure an explicit customer OpenRouter key using worker configure --key-stdin")
    return config["apiKey"]


def require_parent_admission(store, identity, spec):
    if not spec.get("parentGoalId"):
        return
    parent = store.get(spec["parentGoalId"])
    allowances = [o for o in store.operations(parent["id"]) if o["kind"] == "child_allowance" and o["intent"].get("workerId") == identity]
    if parent["status"] != "active" or not allowances or allowances[0]["reserved_microusd"] < spec["maxRetailMicrousd"]:
        raise ValueError("parent goal stopped or child retail allowance not durably admitted")


def require_progress_budget(store, identity, spec):
    """Durable no-progress bound: reads and repeated prose are not new artifact evidence."""
    operations = store.operations(identity)
    seen, checkpoint = set(), 0
    for op in operations:
        if op["kind"] != "tool" or op["state"] != "settled" or op["intent"].get("name") not in {"artifact_write", "render_ffmpeg", "submit_result"}:
            continue
        digest = (op["receipt"] or {}).get("sha256")
        if digest and digest not in seen:
            checkpoint = max(checkpoint, op["updated"])
            seen.add(digest)
    attempts = [op for op in operations if op["kind"] == "inference" and op["created"] > checkpoint]
    if len(attempts) >= spec.get("maxNoProgressCalls", 3):
        raise ValueError("no-progress model-call limit reached; new validated artifact evidence or explicit revised task required")


class FundingProxy:
    """Loopback-only inference gate; key stays here, never in Pi argv/env/project.

    Each HTTP request reserves the full declared context plus maximum output before
    forwarding once. Provider-reported cost releases unused allowance. Ambiguous
    network sends retain their original request hash, native generation ID and hold.
    This is conservative local BYOK enforcement, not a provider account spending cap.
    """
    def __init__(self, project, identity, spec, profile, key, owner, fence, *, upstream=OPENROUTER):
        self.project, self.identity, self.spec, self.profile = project, identity, spec, profile
        if upstream != OPENROUTER and urllib.parse.urlsplit(upstream).hostname not in {"127.0.0.1", "::1"}:
            raise ValueError("only fixed OpenRouter or loopback protocol fixtures may receive BYOK requests")
        self.upstream = upstream
        self.key, self.owner, self.fence = key, owner, fence
        self.token = uuid.uuid4().hex+uuid.uuid4().hex
        self.lock = threading.Lock()
        parent = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                if self.path != "/v1/chat/completions" or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer "+parent.token):
                    self.send_error(403)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_JSON_BYTES:
                    self.send_error(413)
                    return
                try:
                    value = json.loads(self.rfile.read(length))
                    parent.forward(self, value)
                except (OSError, RuntimeError, ValueError, KeyError, TypeError):
                    with contextlib.suppress(OSError):
                        self.send_error(409, "Inference admission refused or acknowledgement unknown; inspect original durable operation")

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def forward(self, client, value):
        with self.lock, contextlib.closing(Store(self.project)) as store:
            record = store.get(self.identity)
            if record["status"] != "active" or record["owner"] != self.owner or record["fence"] != self.fence or record["lease_until"] < time.time():
                raise ValueError("worker paused, canceled or fenced")
            require_parent_admission(store, self.identity, self.spec)
            if store.db.execute("SELECT 1 FROM controls WHERE record_id=? AND kind='cancel' AND state IN ('pending','sending')", (self.identity,)).fetchone():
                raise ValueError("cancellation pending; no new inference admissions")
            prior = [o for o in store.operations(self.identity) if o["kind"] == "inference"]
            if any(o["state"] != "settled" for o in prior):
                raise ValueError("unreconciled original inference blocks new admission")
            require_progress_budget(store, self.identity, self.spec)
            if len(prior) >= self.spec["maxModelCalls"] or time.time() > self.profile["expiresAtUnix"]:
                raise ValueError("model call allowance exhausted or pricing expired")
            if value.get("model") != self.profile["model"] or not value.get("stream"):
                raise ValueError("unapproved model or non-stream transport")
            # Ignore caller-controlled pricing, fallback and token parameters.
            value["max_tokens"] = self.spec["maxOutputTokens"]
            value.pop("max_completion_tokens", None)
            value["provider"] = {"only": [self.profile["providerRoute"]], "allow_fallbacks": False, "require_parameters": True}
            value["usage"] = {"include": True}
            value["stream_options"] = {"include_usage": True}
            reserve = int(((Decimal(self.profile["inputUsdPerToken"])*self.profile["contextWindow"] + Decimal(self.profile["outputUsdPerToken"])*self.spec["maxOutputTokens"])*1_000_000).to_integral_value(rounding=ROUND_CEILING))
            operation = f"{self.identity}:inference:{len(prior)+1}"
            body = canonical(value).encode()
            store.intent(self.identity, operation, "inference", {"requestSha256": hashlib.sha256(body).hexdigest(), "model": self.profile["model"], "funding": "byok", "credentialSha256": hashlib.sha256(self.key.encode()).hexdigest(), "call": len(prior)+1, "price": self.profile}, reserve=reserve, cap=self.spec["maxRetailMicrousd"], owner=self.owner, fence=self.fence)
            store.settle(operation, "sending", {"requestSha256": hashlib.sha256(body).hexdigest()})
            request = urllib.request.Request(self.upstream+"/chat/completions", data=body, headers={"Authorization": "Bearer "+self.key, "Content-Type": "application/json", "Accept": "text/event-stream"})
            native_id, usage, done = None, None, False
            try:
                with provider_open(request, timeout=min(self.spec["maxSeconds"], 120)) as response:
                    client.send_response(response.status)
                    client.send_header("Content-Type", "text/event-stream")
                    client.send_header("Connection", "close")
                    client.end_headers()
                    while line := response.readline(MAX_JSON_BYTES+1):
                        if len(line) > MAX_JSON_BYTES:
                            raise ValueError("oversized provider event")
                        if line.startswith(b"data:"):
                            data = line[5:].strip()
                            if data == b"[DONE]":
                                done = True
                            elif data:
                                event = json.loads(data)
                                previous_id = native_id
                                native_id = event.get("id", native_id)
                                usage = event.get("usage") or usage
                                if native_id and native_id != previous_id:
                                    store.settle(operation, "streaming", {"nativeGenerationId": native_id, "reason": "original handle observed; settlement pending"})
                        client.wfile.write(line)
                        client.wfile.flush()
                    if done and usage and usage.get("cost") is not None:
                        cost = Decimal(str(usage["cost"]))
                        if not cost.is_finite() or cost < 0:
                            raise ValueError("invalid provider cost")
                        microusd = int((cost*1_000_000).to_integral_value(rounding=ROUND_CEILING))
                        store.settle(operation, "settled", {"nativeGenerationId": native_id, "usage": usage, "transport": "complete"}, microusd)
                    else:
                        store.settle(operation, "unknown", {"nativeGenerationId": native_id, "usage": usage, "reason": "no independently reported final provider cost; original hold retained"})
            except (OSError, ValueError, urllib.error.URLError):
                store.settle(operation, "unknown", {"nativeGenerationId": native_id, "usage": usage, "reason": "transport acknowledgement/settlement indeterminate; do not resend"})
                raise ValueError("provider acknowledgement indeterminate") from None

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)



def _managed_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _managed_id(store, identity, purpose):
    project = json.loads((store.root / "project.vibeedit.json").read_text(encoding="utf-8"))
    return "ve-" + purpose + "-" + _managed_hash({"projectId": project["id"], "recordId": identity})[:48]


def managed_profile(client, spec, capabilities=None):
    capabilities = capabilities if capabilities is not None else client.call("/v1/companion/capabilities")
    if capabilities.get("schemaVersion") != "myriograph.companion.v1" or capabilities.get("enabled") is not True or capabilities.get("funding") != "metered-prepaid" or capabilities.get("automaticPaidRetries") != 0 or capabilities.get("retailCeiling", {}).get("enforced") is not True or capabilities.get("requestPath") != "/v1/companion/requests" or capabilities.get("allowancePath") != "/v1/companion/allowances" or "durable-request-poll" not in capabilities.get("transport", "") or capabilities.get("videoTransport") is not False:
        raise ValueError("managed inference unavailable: deployed prepaid/retail reservation and original-request contract is not enabled")
    profile = capabilities.get("profiles", {}).get(spec["profile"])
    if not isinstance(profile, dict) or profile.get("id") != spec["profile"] or profile.get("model") != PROFILES[spec["profile"]] or profile.get("providerRoute") != PROVIDERS[spec["profile"]] or profile.get("providerModelName") != PROVIDER_MODELS[spec["profile"]] or profile.get("retailMultiplier") != 2 or profile.get("expiresAtUnix", 0) <= time.time():
        raise ValueError("managed profile identity, retail rate or expiry not approved; no fallback")
    if profile.get("pricingDigest") != _managed_hash({key: value for key, value in profile.items() if key != "pricingDigest"}):
        raise ValueError("managed profile pricing digest mismatch")
    if type(profile.get("contextWindow")) is not int or not 1 <= profile["contextWindow"] <= 2_000_000:
        raise ValueError("managed context bound unavailable")
    for key in ["inputUsdPerToken", "outputUsdPerToken"]:
        value = Decimal(str(profile.get(key)))
        if not value.is_finite() or value <= 0:
            raise ValueError("managed price unavailable")
    if spec.get("managedPricingDigest") and spec["managedPricingDigest"] != profile["pricingDigest"]:
        raise ValueError("managed pricing changed from the explicitly pinned task digest")
    return profile


def _managed_same_scope(original, current):
    # The gateway authorizes the actual account. Rotating a customer key must not
    # replace its native jobs/allowance; a different account still receives404.
    return isinstance(original, dict) and all(original.get(key) == current.get(key) for key in ("apiUrl", "organizationId", "projectId", "accountId", "mode"))


def ensure_managed_allowance(store, identity, spec, client):
    client.bind_customer()
    parent_id = spec.get("parentGoalId", identity)
    parent = store.get(parent_id)
    if parent["status"] != "active":
        raise ValueError("parent allowance admissions require an active goal/worker")
    remote_id = _managed_id(store, parent_id, "allowance")
    local_id = parent_id + ":managed-allowance"
    payload = {"remoteOperationId": remote_id, "maxRetailMicros": parent["spec"]["maxRetailMicrousd"], "customerIdentity": client.identity}
    platform = parent["spec"].get("platformBudgetMicros", 0)
    if platform:
        payload["platformBudgetMicros"] = platform
    existing = next((op for op in store.operations(parent_id) if op["id"] == local_id), None)
    if existing:
        if not _managed_same_scope(existing["intent"].get("customerIdentity"), client.identity) or existing["intent"].get("maxRetailMicros") != payload["maxRetailMicros"] or existing["intent"].get("remoteOperationId") != remote_id or existing["intent"].get("platformBudgetMicros", 0) != platform:
            raise ValueError("original managed allowance scope/cap differs from configured customer")
        payload = existing["intent"]
    fresh = store.intent(parent_id, local_id, "managed_allowance", payload)
    prior = next(op for op in store.operations(parent_id) if op["id"] == local_id)
    if fresh:
        store.settle(local_id, "sending", {"remoteOperationId": remote_id})
        try:
            body = {"maxRetailMicros": payload["maxRetailMicros"]}
            if platform:
                body["platformBudgetMicros"] = platform
            response = client.call("/v1/companion/allowances", body, key=remote_id)
        except Exception:
            store.settle(local_id, "unknown", {"remoteOperationId": remote_id, "reason": "original allowance acknowledgement unknown; observe original ID before any retry"})
            raise
    else:
        # An observation never creates a replacement allowance or resets a goal cap.
        response = client.call("/v1/companion/allowances/" + remote_id)
    if fresh:
        response = client.call("/v1/companion/allowances/" + remote_id)
    funding_status = response.get("fundingStatus") or {}
    if funding_status.get("schemaVersion") != "myriograph.customerAllowance.v1" or funding_status.get("state") != "admitted" or not isinstance(funding_status.get("reservationId"), str) or type(funding_status.get("retailCeilingMicros")) is not int or not 0 < funding_status["retailCeilingMicros"] <= payload["maxRetailMicros"]:
        raise ValueError("managed parent reservation identity/retail status unavailable")
    if response.get("allowanceId") != remote_id or response.get("operationId") != remote_id or response.get("state") != "active" or response.get("retailCapMicros") != payload["maxRetailMicros"] or response.get("platformBudgetMicros", 0) != platform:
        raise ValueError("original managed allowance identity/cap unavailable or closed")
    if prior["state"] != "settled":
        store.settle(local_id, "settled", {"remoteOperationId": remote_id, "allowanceId": remote_id, "state": "active", "maxRetailMicros": payload["maxRetailMicros"], "platformBudgetMicros": platform, "parentReservationId": funding_status["reservationId"], "fundingStatus": funding_status, "customerIdentity": client.identity}, 0)
    return remote_id


def close_managed_allowance(store, identity):
    operations = [op for op in store.operations(identity) if op["kind"] == "managed_allowance"]
    if not operations:
        return None
    from vibeedit.myriograph import Myriograph, read_config
    client = Myriograph(read_config())
    client.bind_customer()
    original = operations[0]
    if not _managed_same_scope(original["intent"].get("customerIdentity"), client.identity):
        raise ValueError("original customer identity required to close managed allowance")
    remote_id = original["intent"]["remoteOperationId"]
    op_id = identity + ":managed-allowance-close"
    if not store.intent(identity, op_id, "managed_allowance_close", {"allowanceId": remote_id}):
        response = client.call("/v1/companion/allowances/" + remote_id)
        prior = next(op for op in store.operations(identity) if op["id"] == op_id)
        if response.get("state") == "closed" and prior["state"] != "settled":
            store.settle(op_id, "settled", {"allowanceId": remote_id, "state": "closed", "settlement": response.get("settlement"), "unknownHoldsPreserved": True}, 0)
        if response.get("state") != "closed":
            raise ValueError("original managed allowance closure not acknowledged; original holds remain visible")
        return response
    store.settle(op_id, "sending", {"allowanceId": remote_id})
    try:
        response = client.call("/v1/companion/allowances/" + remote_id + "/close", {}, key=remote_id + ":close")
    except Exception:
        store.settle(op_id, "unknown", {"allowanceId": remote_id, "reason": "original close acknowledgement unknown; held usage remains observable"})
        raise
    if response.get("allowanceId") != remote_id or response.get("state") != "closed":
        store.settle(op_id, "unknown", {"allowanceId": remote_id, "state": response.get("state"), "unknownHoldsPreserved": True})
        raise ValueError("original managed allowance close pending; observe original holds")
    store.settle(op_id, "settled", {"allowanceId": remote_id, "state": "closed", "settlement": response.get("settlement"), "unknownHoldsPreserved": True}, 0)
    return response


def cancel_managed_operations(store, identity):
    """Stop original managed requests even after their local observer timed out."""
    pending = [op for op in store.operations(identity) if op["kind"] == "inference" and op["state"] != "settled" and op["intent"].get("funding") == "managed"]
    if not pending:
        return []
    from vibeedit.myriograph import Myriograph, read_config
    customer = Myriograph(read_config())
    customer.bind_customer()
    results = []
    for original in pending:
        if not _managed_same_scope(original["intent"].get("customerIdentity"), customer.identity):
            raise ValueError("original customer scope required to cancel managed request")
        remote = original["intent"]["remoteOperationId"]
        cancel_id = original["id"] + ":cancel"
        if store.intent(identity, cancel_id, "managed_cancel", {"remoteOperationId": remote}):
            store.settle(cancel_id, "sending", {"remoteOperationId": remote})
            try:
                response = customer.call("/v1/companion/requests/" + remote + "/cancel", {}, key=remote + ":cancel")
            except Exception:
                store.settle(cancel_id, "unknown", {"remoteOperationId": remote, "reason": "cancel acknowledgement unknown; original request remains observable"})
                raise
            store.settle(cancel_id, "settled", {"remoteOperationId": remote, "state": response.get("state")}, 0)
        else:
            response = customer.call("/v1/companion/requests/" + remote)
        if response.get("operationId") != remote or response.get("requestSha256") != original["intent"]["requestSha256"]:
            raise ValueError("original cancellation response identity mismatch")
        if (response.get("settlement") or {}).get("state") == "settled":
            _managed_settlement(store, original["id"], response)
        results.append({"operationId": remote, "state": response.get("state"), "holdsRetainedUntilAuthoritativeSettlement": True})
    return results


def _managed_settlement(store, operation, response):
    settlement = response.get("settlement") or {}
    if response.get("state") not in {"settled", "cancelled", "rejected"} or settlement.get("schemaVersion") != "myriograph.customerSettlement.v1" or settlement.get("state") != "settled" or type(settlement.get("retailMicros")) is not int or settlement["retailMicros"] < 0:
        raise ValueError("original managed request has no authoritative retail settlement; hold retained")
    operation_row = store.db.execute("SELECT record_id FROM operations WHERE id=?", (operation,)).fetchone()
    record = store.get(operation_row["record_id"])
    parent_id = record["spec"].get("parentGoalId", record["id"])
    allowance = next((op for op in store.operations(parent_id) if op["kind"] == "managed_allowance"), None)
    parent_reservation = ((allowance or {}).get("receipt") or {}).get("parentReservationId")
    if not parent_reservation or settlement.get("parentReservationId") != parent_reservation:
        raise ValueError("managed settlement does not acknowledge the original shared parent reservation")
    receipt = {"managedOperationId": response["operationId"], "allowanceId": response.get("allowanceId"), "nativeGenerationId": (response.get("response") or {}).get("id"), "settlement": settlement, "transport": "durable server request; completed reply buffered as local SSE"}
    store.settle(operation, "settled", receipt, settlement["retailMicros"])
    return receipt


class ManagedFundingProxy(FundingProxy):
    """Myriograph owns the prepaid hold/provider send; Pi only sees buffered local SSE."""
    def __init__(self, project, identity, spec, profile, client, owner, fence):
        self.customer = client
        self.deadline = time.monotonic() + spec["maxSeconds"]
        super().__init__(project, identity, spec, profile, "", owner, fence)

    def forward(self, client, value):
        with self.lock, contextlib.closing(Store(self.project)) as store:
            record = store.get(self.identity)
            if record["status"] != "active" or record["owner"] != self.owner or record["fence"] != self.fence or record["lease_until"] <= time.time():
                raise ValueError("worker paused, canceled or fenced")
            require_parent_admission(store, self.identity, self.spec)
            if store.db.execute("SELECT 1 FROM controls WHERE record_id=? AND kind='cancel' AND state IN ('pending','sending')", (self.identity,)).fetchone():
                raise ValueError("cancellation pending; no new managed admissions")
            prior_cancel_ids = {row[0] for row in store.db.execute("SELECT id FROM controls WHERE record_id=? AND kind='cancel'", (self.identity,))}
            prior = [op for op in store.operations(self.identity) if op["kind"] == "inference"]
            if any(op["state"] != "settled" for op in prior):
                raise ValueError("original managed inference must reconcile before another admission")
            require_progress_budget(store, self.identity, self.spec)
            if len(prior) >= self.spec["maxModelCalls"] or self.profile["expiresAtUnix"] <= time.time():
                raise ValueError("managed model-call bound exhausted or approved pricing expired")
            if value.get("model") != self.profile["model"] or not value.get("stream"):
                raise ValueError("unapproved managed model or transport")
            allowance = ensure_managed_allowance(store, self.identity, self.spec, self.customer)
            provider_cap = int(((Decimal(self.profile["inputUsdPerToken"]) * self.profile["contextWindow"] + Decimal(self.profile["outputUsdPerToken"]) * self.spec["maxOutputTokens"]) * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
            reserve = provider_cap * self.profile["retailMultiplier"]
            local_id = f"{self.identity}:inference:{len(prior)+1}"
            remote_id = _managed_id(store, local_id, "request")
            body = {key: value[key] for key in ("messages", "tools", "tool_choice", "temperature", "response_format") if key in value}
            body.update(profile=self.spec["profile"], pricingDigest=self.profile["pricingDigest"], maxRetailMicros=reserve, allowanceId=allowance, max_tokens=self.spec["maxOutputTokens"])
            request_hash = _managed_hash(body)
            store.intent(self.identity, local_id, "inference", {"funding": "managed", "remoteOperationId": remote_id, "allowanceId": allowance, "requestSha256": request_hash, "model": self.profile["model"], "price": self.profile, "customerIdentity": self.customer.identity}, reserve=reserve, cap=self.spec["maxRetailMicrousd"], owner=self.owner, fence=self.fence)
            store.settle(local_id, "sending", {"managedOperationId": remote_id, "allowanceId": allowance})
            response, settled = None, False
            try:
                response = self.customer.call("/v1/companion/requests", body, key=remote_id)
                if response.get("operationId") != remote_id or response.get("requestSha256") != request_hash:
                    raise ValueError("managed admission acknowledgement identity mismatch")
                response = self.customer.call("/v1/companion/requests/" + remote_id)
                while True:
                    if response.get("operationId") != remote_id or response.get("requestSha256") != request_hash or response.get("allowanceId") != allowance:
                        raise ValueError("managed response identity differs from original intent")
                    if response.get("state") in {"settled", "cancelled", "rejected"}:
                        _managed_settlement(store, local_id, response)
                        settled = True
                        if response["state"] != "settled":
                            raise ValueError("managed request canceled/rejected with authoritative settlement; no reply to replay")
                        break
                    if response.get("state") == "held":
                        raise ValueError("original managed request not settled; retain hold and observe original operation")
                    current = store.get(self.identity)
                    new_cancellations = {row[0] for row in store.db.execute("SELECT id FROM controls WHERE record_id=? AND kind='cancel' AND state IN ('pending','sending','acknowledged')", (self.identity,))} - prior_cancel_ids
                    expired = time.monotonic() >= self.deadline
                    stopped = current["status"] != "active" or current["fence"] != self.fence or current["lease_until"] <= time.time() or bool(new_cancellations) or expired
                    cancel_id = local_id + ":cancel"
                    if stopped and store.intent(self.identity, cancel_id, "managed_cancel", {"remoteOperationId": remote_id}):
                        store.settle(cancel_id, "sending", {"remoteOperationId": remote_id})
                        cancellation = self.customer.call("/v1/companion/requests/" + remote_id + "/cancel", {}, key=remote_id + ":cancel")
                        store.settle(cancel_id, "settled", {"remoteOperationId": remote_id, "state": cancellation.get("state")}, 0)
                    if expired:
                        raise ValueError("managed observation deadline reached; original request cancellation/hold remains observable")
                    time.sleep(.25)
                    response = self.customer.call("/v1/companion/requests/" + remote_id)
            except Exception:
                if not settled:
                    store.settle(local_id, "unknown", {"managedOperationId": remote_id, "allowanceId": allowance, "reason": "original server request/retail settlement indeterminate; never replace it"})
                raise
            reply = response.get("response") or {}
            if reply.get("model") != self.profile["model"] or not isinstance(reply.get("choices"), list) or not reply.get("id"):
                raise ValueError("settled managed reply is not the selected OpenAI model response; no inference replay")
            client.send_response(200)
            client.send_header("Content-Type", "text/event-stream")
            client.send_header("Connection", "close")
            client.end_headers()
            envelope = {key: reply[key] for key in ("id", "created", "model") if key in reply}
            envelope["object"] = "chat.completion.chunk"
            chunks = []
            for choice in reply["choices"]:
                message = dict(choice.get("message") or {})
                if message.get("tool_calls"):
                    message["tool_calls"] = [{**tool, "index": index} for index, tool in enumerate(message["tool_calls"])]
                chunks.append({**envelope, "choices": [{"index": choice.get("index", 0), "delta": message, "finish_reason": None}]})
                chunks.append({**envelope, "choices": [{"index": choice.get("index", 0), "delta": {}, "finish_reason": choice.get("finish_reason", "stop")}]})
            usage = dict(reply.get("usage", {}))
            usage["provider_cost"] = usage.get("cost")
            usage["cost"] = response["settlement"]["retailMicros"] / 1_000_000
            usage["myriograph_retail_micros"] = response["settlement"]["retailMicros"]
            chunks.append({**envelope, "choices": [], "usage": usage})
            for chunk in chunks:
                client.wfile.write(("data: " + json.dumps(chunk, allow_nan=False) + "\n\n").encode())
            client.wfile.write(b"data: [DONE]\n\n")
            client.wfile.flush()

def _pi_command(directory, *, require_ready=False):
    if require_ready:
        marker = json.loads((directory/"ready.json").read_text(encoding="utf-8"))
        lock_digest = hashlib.sha256((companion_path()/"package-lock.json").read_bytes()).hexdigest()
        if marker != {"piVersion": PI_VERSION, "lockSha256": lock_digest}:
            raise ValueError("worker runtime is incomplete or has a different package lock; rerun worker setup")
    path = directory / "node_modules" / "@earendil-works" / "pi-coding-agent"
    metadata = json.loads((path/"package.json").read_text(encoding="utf-8"))
    if metadata["version"] != PI_VERSION:
        raise ValueError("installed Pi version differs from immutable VibeEdit pin")
    node = shutil.which("node")
    if not node:
        raise ValueError("Node >=22.19.0 required; run worker setup")
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=True).stdout.strip().lstrip("v")
    if tuple(map(int, version.split(".")[:3])) < (22, 19, 0):
        raise ValueError("Node >=22.19.0 required by pinned Pi")
    return [node, str(path/metadata["bin"]["pi"])]


def worker_runtime():
    return config_home() / "runtime" / f"pi-{PI_VERSION}"


def setup_worker():
    directory = worker_runtime()
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise ValueError("npm and Node >=22.19.0 required; no global toolchain replacement is performed")
    if any(p.is_symlink() for p in (config_home(), directory.parent, directory)):
        raise ValueError("worker runtime directory cannot be symlinked")
    lock = json.loads((companion_path()/"package-lock.json").read_text(encoding="utf-8"))
    if lock["packages"]["node_modules/@earendil-works/pi-coding-agent"]["integrity"] != PI_INTEGRITY:
        raise ValueError("Pi archive integrity differs from the pinned release")
    marker = {"piVersion": PI_VERSION, "lockSha256": hashlib.sha256((companion_path()/"package-lock.json").read_bytes()).hexdigest()}
    if directory.exists():
        _pi_command(directory, require_ready=True)
        return {"schemaVersion": SCHEMA, "ok": True, **marker, "runtime": str(directory), "reused": True, "providerCalls": 0}
    directory.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    stage = directory.parent / (directory.name+".staging-"+uuid.uuid4().hex)
    stage.mkdir(mode=0o700)
    try:
        shutil.copyfile(companion_path()/"package.json", stage/"package.json")
        shutil.copyfile(companion_path()/"package-lock.json", stage/"package-lock.json")
        result = subprocess.run([npm, "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=stage, capture_output=True, timeout=300)
        if result.returncode:
            raise ValueError("pinned Pi dependency installation failed; retry worker setup after repairing Node/network/disk")
        _pi_command(stage)
        (stage/"ready.json").write_text(canonical(marker), encoding="utf-8")
        stage.rename(directory)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {"schemaVersion": SCHEMA, "ok": True, **marker, "integrity": PI_INTEGRITY, "runtime": str(directory), "providerCalls": 0}


def _sanitize_event(event):
    kind = event.get("type")
    if kind == "message_update":
        delta = event.get("assistantMessageEvent", {})
        return {"type": kind, "deltaType": delta.get("type"), "delta": delta.get("delta") if delta.get("type") == "text_delta" else None}
    if kind == "message_end":
        message = event.get("message", {})
        return {"type": kind, "role": message.get("role"), "stopReason": message.get("stopReason"), "usage": message.get("usage")}
    return {k: event[k] for k in ("type", "id", "command", "success", "toolName", "toolCallId", "isError", "aborted", "willRetry") if k in event}


def run_worker(project, identity, *, runtime=None, profile=None, upstream=OPENROUTER):
    store = Store(project)
    owner = str(uuid.uuid4())
    fence = store.claim(identity, owner)
    if fence is None:
        return
    client, proxy = None, None
    try:
        record = store.get(identity)
        spec = validate_task(record["spec"])
        prior = store.operations(identity)
        if any(o["kind"] in {"inference", "rpc_prompt"} and o["state"] != "settled" for o in prior):
            store.update(identity, "waiting", {"reason": "previous send indeterminate; original session/operation retained, no automatic retry", "operations": [o["id"] for o in prior]}, owner=owner, fence=fence)
            return
        for reference in spec["references"]:
            if _digest(confined(store.root, reference)) != spec["referenceDigests"][reference]:
                raise ValueError("source/reference changed since task admission; explicit revision required")
        key = _funding(spec)
        if profile is not None and urllib.parse.urlsplit(upstream).hostname not in {"127.0.0.1", "::1"}:
            raise ValueError("profile injection is limited to nonbilling loopback protocol qualification")
        profile = profile or (managed_profile(key, spec) if spec["funding"] == "managed" else refresh_profiles()[spec["profile"]])
        supplied_runtime = runtime is not None
        runtime = runtime or worker_runtime()
        command = _pi_command(runtime, require_ready=not supplied_runtime)
        folder = confined(store.root, f".vibeedit/workers/{identity}", must_exist=False)
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        agent = confined(store.root, f".vibeedit/workers/{identity}/agent", must_exist=False)
        agent.mkdir(exist_ok=True, mode=0o700)
        confined(store.root, f".vibeedit/workers/{identity}/agent/models.json", must_exist=False)
        confined(store.root, f".vibeedit/workers/{identity}/agent/settings.json", must_exist=False)
        confined(store.root, f".vibeedit/workers/{identity}/sessions", must_exist=False)
        proxy = ManagedFundingProxy(store.root, identity, spec, profile, key, owner, fence) if spec["funding"] == "managed" else FundingProxy(store.root, identity, spec, profile, key, owner, fence, upstream=upstream)
        provider = {"baseUrl": f"http://127.0.0.1:{proxy.server.server_port}/v1", "api": "openai-completions", "apiKey": "${VIBEEDIT_LOCAL_GATEWAY_TOKEN}", "models": [{"id": profile["model"], "name": profile["model"], "reasoning": False, "input": profile["input"], "contextWindow": profile["contextWindow"], "maxTokens": spec["maxOutputTokens"], "cost": {"input": float(Decimal(profile["inputUsdPerToken"])*profile.get("retailMultiplier", 1)*1_000_000), "output": float(Decimal(profile["outputUsdPerToken"])*profile.get("retailMultiplier", 1)*1_000_000), "cacheRead": float(Decimal(profile["inputUsdPerToken"])*profile.get("retailMultiplier", 1)*1_000_000), "cacheWrite": float(Decimal(profile["inputUsdPerToken"])*profile.get("retailMultiplier", 1)*1_000_000)}}]}
        (agent/"models.json").write_text(canonical({"providers": {"vibeedit-bounded": provider}}), encoding="utf-8")
        (agent/"settings.json").write_text(canonical({"retry": {"enabled": False, "provider": {"maxRetries": 0}}, "compaction": {"enabled": False}, "cacheWarming": {"enabled": False}}), encoding="utf-8")
        tools = [*spec["tools"], "submit_result"]
        command += ["--mode", "rpc", "--no-extensions", "--no-mcp", "--no-skills", "--no-prompt-templates", "--no-context-files", "--no-themes", "--extension", str(companion_path()/"extensions"/"worker.ts"), "--tools", ",".join(tools), "--provider", "vibeedit-bounded", "--model", profile["model"], "--session-dir", str(folder/"sessions"), "--session-id", identity, "--system-prompt", "You are a bounded VibeEdit worker. Use only authorized references and scoped tools. Preserve source files. Produce the requested artifacts, then call submit_result with a JSON object matching the supplied schema. Do not treat model text as successful completion. Do not perform new delegation, purchases, network calls or unrelated edits."]
        env = {k: os.environ[k] for k in ("PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "TEMP", "TMP", "LANG") if k in os.environ}
        env.update({"PI_CODING_AGENT_DIR": str(agent), "PI_OFFLINE": "1", "PI_SKIP_VERSION_CHECK": "1", "PI_TELEMETRY": "0", "VIBEEDIT_LOCAL_GATEWAY_TOKEN": proxy.token, "VIBEEDIT_WORKER_PROJECT": str(store.root), "VIBEEDIT_WORKER_ID": identity, "VIBEEDIT_WORKER_FENCE": str(fence), "VIBEEDIT_WORKER_OWNER": owner, "VIBEEDIT_PYTHON": sys.executable, "PYTHONPATH": str(Path(__file__).resolve().parents[1])})
        client = RpcClient(command, folder, env)
        store.event(identity, "worker_started", {"pid": client.process.pid, "supervisorPid": os.getpid(), "startIdentity": owner, "fence": fence, "piVersion": PI_VERSION, "profile": profile, "funding": spec["funding"], "customerScope": key.identity if spec["funding"] == "managed" else {"provider": "OpenRouter"}, "budgetEnforcement": "Myriograph prepaid parent/child retail reservation; buffered reply" if spec["funding"] == "managed" else "conservative local per-call reservation; not provider-account cap", "tools": tools})
        prompt_id = f"{identity}:prompt:{len([o for o in prior if o['kind']=='rpc_prompt'])+1}"
        prompt = {"task": spec["task"], "references": spec["references"], "referenceDigests": spec.get("referenceDigests", {}), "derivedFrom": spec.get("derivedFrom", []), "outputSchema": spec["outputSchema"], "artifacts": spec["artifacts"], "artifactDirectory": f"workers/{identity}/artifacts", "priorCompletedOperations": [o["receipt"] for o in prior if o["state"] == "settled" and o["kind"] == "tool"]}
        store.intent(identity, prompt_id, "rpc_prompt", {"promptSha256": hashlib.sha256(canonical(prompt).encode()).hexdigest()}, owner=owner, fence=fence)
        client.send({"type": "prompt", "message": canonical(prompt)}, prompt_id)
        started, canceled, prompt_accepted, settled = time.monotonic(), False, False, False
        while True:
            store.heartbeat(identity, owner, fence)
            row = store.get(identity)
            controls = list(store.db.execute("SELECT * FROM controls WHERE record_id=? AND state='pending' ORDER BY rowid", (identity,)))
            for control in controls:
                # Persist sending before pipe write; a crash never replays a steer automatically.
                store.db.execute("UPDATE controls SET state='sending' WHERE id=? AND state='pending'", (control["id"],))
                if control["kind"] == "steer":
                    client.send({"type": "steer", "message": json.loads(control["payload"])["message"]}, control["id"])
                if control["kind"] == "cancel":
                    client.send({"type": "clear_queue"})
                    client.send({"type": "abort"}, control["id"])
                    canceled = True
            if not canceled and (time.monotonic()-started >= spec["maxSeconds"] or row["status"] != "active"):
                client.send({"type": "clear_queue"})
                client.send({"type": "abort"})
                canceled = True
                store.event(identity, "deadline_or_stop", {"reason": "wall-time or lifecycle bound", "settlementStillRequired": True})
            try:
                event = client.records.get(timeout=.2)
            except queue.Empty:
                if canceled and time.monotonic()-started >= spec["maxSeconds"]+10:
                    break
                continue
            store.event(identity, "pi", _sanitize_event(event))
            if event.get("type") == "response":
                if event.get("id") == prompt_id:
                    if not event.get("success"):
                        store.settle(prompt_id, "settled", {"accepted": False}, 0)
                        store.update(identity, "failed", {"reason": "Pi rejected prompt; no automatic resubmission"}, owner=owner, fence=fence)
                        return
                    prompt_accepted = True
                    if event.get("data", {}).get("disposition") == "handled":
                        store.settle(prompt_id, "settled", {"accepted": True, "disposition": "handled"}, 0)
                        break
                store.db.execute("UPDATE controls SET state=? WHERE id=?", ("acknowledged" if event.get("success") else "rejected", event.get("id", "")))
            if event.get("type") == "agent_settled":
                settled = True
                store.settle(prompt_id, "settled", {"accepted": prompt_accepted, "aborted": event.get("aborted", False), "sessionId": identity}, 0)
                break
            if event.get("type") == "vibeedit_rpc_exit":
                break
        with proxy.lock:
            inference = [o for o in store.operations(identity) if o["kind"] == "inference"]
        if not settled or any(o["state"] != "settled" for o in inference):
            store.update(identity, "waiting", {"reason": "Pi/provider acknowledgement or settlement indeterminate; original operations and holds retained", "sessionId": identity}, owner=owner, fence=fence)
            return
        if canceled:
            if not spec.get("parentGoalId"):
                try:
                    close_managed_allowance(store, identity)
                except (OSError, RuntimeError, ValueError):
                    store.event(identity, "managed_close_pending", {"reason": "cancellation stops new work; original prepaid holds remain observable"})
            store.update(identity, "canceled", {"reason": "cancellation observed; actual incurred usage retained", "sessionId": identity}, owner=owner, fence=fence)
            return
        checkpoint = committed_artifacts(store, identity)
        result, artifacts = checkpoint["result"], checkpoint["artifacts"]
        pending_analysis = [op for op in store.operations(identity) if op["kind"] == "analysis" and op["state"] != "settled"]
        if pending_analysis and not spec.get("parentGoalId"):
            for operation in pending_analysis:
                analysis_status(store, identity, operation["intent"]["operationId"])
            pending_analysis = [op for op in store.operations(identity) if op["kind"] == "analysis" and op["state"] != "settled"]
            if all(analysis_execution_ready(op) for op in pending_analysis):
                try:
                    close_managed_allowance(store, identity)
                except (OSError, RuntimeError, ValueError):
                    store.event(identity, "managed_close_pending", {"reason": "verified execution awaits original parent/platform settlement; full native holds retained"})
                for operation in pending_analysis:
                    analysis_status(store, identity, operation["intent"]["operationId"])
                pending_analysis = [op for op in store.operations(identity) if op["kind"] == "analysis" and op["state"] != "settled"]
        if pending_analysis:
            store.update(identity, "waiting", {"reason": "execution artifacts verified; original paid analysis retail settlement still pending", "executionCheckpoint": checkpoint, "analysis": [op["receipt"] for op in pending_analysis]}, owner=owner, fence=fence)
            return
        if not spec.get("parentGoalId"):
            close_managed_allowance(store, identity)
        store.update(identity, "complete", {"result": result, "artifacts": artifacts, "sessionId": identity, "usageMicrousd": sum(op["settled_microusd"] or 0 for op in store.operations(identity) if op["kind"] in {"inference", "analysis"})}, owner=owner, fence=fence)
    except (OSError, RuntimeError, ValueError, KeyError, ValidationError, subprocess.SubprocessError) as error:
        # Never print provider diagnostics or credential-bearing request objects.
        row = store.get(identity)
        if row["owner"] == owner and row["fence"] == fence and row["lease_until"] > time.time():
            store.update(identity, "blocked", {"reason": str(error) if not isinstance(error, ValidationError) else "structured output failed its declared schema"}, owner=owner, fence=fence)
    finally:
        if client:
            client.close()
        if proxy:
            proxy.close()
        store.db.execute("UPDATE records SET lease_until=0 WHERE id=? AND owner=? AND fence=?", (identity, owner, fence))
        store.close()



def analysis_permission(spec, operation):
    permission = next((row for row in spec.get("analysisPermissions", []) if row["operationId"] == operation), None)
    if not permission:
        raise ValueError("analysis operation was not explicitly authorized by the parent")
    return permission


def analysis_status(store, identity, operation, *, download=False):
    from vibeedit.myriograph import Myriograph, observe, read_config
    spec = store.get(identity)["spec"]
    permission = analysis_permission(spec, operation)
    local_id = identity + ":analysis:" + operation
    original = next((op for op in store.operations(identity) if op["id"] == local_id and op["kind"] == "analysis"), None)
    if not original:
        raise ValueError("original analysis admission has not been durably recorded")
    customer = Myriograph(read_config())
    customer.bind_customer()
    if not _managed_same_scope(original["intent"].get("customerIdentity"), customer.identity):
        raise ValueError("original analysis customer scope required")
    observed = observe(customer, store.root, operation)
    native = observed.get("native") or {}
    if native.get("sourceSha256", permission["sourceSha256"]) != permission["sourceSha256"] or native.get("jobId", native.get("id", observed.get("jobId"))) != observed.get("jobId"):
        raise ValueError("original native job/source identity mismatch")
    settlement = native.get("settlement") or {}
    parent_id = spec.get("parentGoalId", identity)
    allowance = next((op for op in store.operations(parent_id) if op["kind"] == "managed_allowance"), None)
    parent_reservation = ((allowance or {}).get("receipt") or {}).get("parentReservationId")
    if (settlement.get("state") == "settled" or settlement.get("readyForParentSettlement") is True) and (not parent_reservation or settlement.get("parentReservationId") != parent_reservation):
        raise ValueError("native analysis settlement does not acknowledge the original shared goal parent")
    result = {"operationId": operation, "service": permission["service"], "sourceSha256": permission["sourceSha256"], "jobId": observed.get("jobId"), "state": observed["state"], "fundingAllowanceId": original["intent"]["fundingAllowanceId"], "settlement": settlement if settlement.get("schemaVersion") == "myriograph.customerSettlement.v1" else {"state": "held", "retailMicros": None}, "originalHandleRequired": True}
    if original["state"] != "settled":
        if settlement.get("schemaVersion") == "myriograph.customerSettlement.v1" and settlement.get("state") == "settled" and type(settlement.get("retailMicros")) is int and settlement["retailMicros"] >= 0 and observed["state"] in {"completed", "succeeded", "failed", "cancelled", "canceled"}:
            store.settle(local_id, "settled", result, settlement["retailMicros"])
        else:
            store.settle(local_id, "waiting", result)
    if download:
        if observed["state"] not in {"completed", "succeeded"}:
            raise ValueError("original analysis result is not complete; keep its existing handle")
        from vibeedit import myriograph
        destination = confined(store.root, f"workers/{identity}/analysis/{operation}", must_exist=False)
        downloaded = myriograph.download(customer, store.root, operation, destination, max_bytes=permission.get("maxDownloadBytes", 128 * 1024 * 1024))
        result["artifacts"] = [{**{key: value for key, value in row.items() if key != "path"}, "path": str(Path(row["path"]).relative_to(store.root))} for row in downloaded["native"]["artifacts"]]
    # Adopt a crashed analyze tool only after this exact original job has been observed.
    for op in store.operations(identity):
        if op["kind"] == "tool" and op["state"] != "settled" and op["intent"].get("name") == "analyze" and op["intent"].get("analysisOperationId") == operation:
            store.settle(op["id"], "settled", {key: value for key, value in result.items() if key != "artifacts"}, 0)
    return result


def submit_analysis(store, identity, owner, fence, args):
    from vibeedit.myriograph import Myriograph, read_config, submit
    spec = store.get(identity)["spec"]
    if set(args) != {"operationId", "service", "source", "sourceSha256", "maxRetailMicrousd"}:
        raise ValueError("analysis requires explicit operation/service/source/SHA and retail cap only; options come from parent permission")
    permission = analysis_permission(spec, args["operationId"])
    if any(args[key] != permission[key] for key in args):
        raise ValueError("analysis request differs from the parent's exact source/service/operation/retail permission")
    source = confined(store.root, permission["source"])
    if _digest(source) != permission["sourceSha256"]:
        raise ValueError("analysis source bytes changed from the parent's SHA identity")
    customer = Myriograph(read_config())
    customer.bind_customer()
    allowance = ensure_managed_allowance(store, identity, spec, customer)
    local_id = identity + ":analysis:" + permission["operationId"]
    payload = {"operationId": permission["operationId"], "service": permission["service"], "source": permission["source"], "sourceSha256": permission["sourceSha256"], "settingsSha256": _managed_hash(permission.get("options", {})), "fundingAllowanceId": allowance, "customerIdentity": customer.identity, "maxRetailMicrousd": permission["maxRetailMicrousd"]}
    if not store.intent(identity, local_id, "analysis", payload, reserve=permission["maxRetailMicrousd"], cap=spec["maxRetailMicrousd"], owner=owner, fence=fence):
        return analysis_status(store, identity, permission["operationId"])
    store.settle(local_id, "sending", {"operationId": permission["operationId"], "fundingAllowanceId": allowance})
    try:
        receipt = submit(customer, store.root, permission["service"], source, permission.get("options", {}), permission["maxRetailMicrousd"] / 1_000_000, permission["operationId"], funding_allowance_id=allowance)
    except Exception:
        store.settle(local_id, "unknown", {"operationId": permission["operationId"], "fundingAllowanceId": allowance, "reason": "original native admission/settlement uncertain; inspect original SDK jobs journal and never replace it"})
        raise
    result = {"operationId": permission["operationId"], "service": permission["service"], "sourceSha256": permission["sourceSha256"], "jobId": receipt.get("jobId"), "state": receipt["state"], "fundingAllowanceId": allowance, "settlement": {"state": "held", "retailMicros": None}, "originalHandleRequired": True}
    store.settle(local_id, "waiting", result)
    return result


def cancel_analysis_operations(store, identity):
    from vibeedit.myriograph import Myriograph, observe, read_config
    pending = [op for op in store.operations(identity) if op["kind"] == "analysis" and op["state"] != "settled"]
    if not pending:
        return
    customer = Myriograph(read_config())
    customer.bind_customer()
    for original in pending:
        if not _managed_same_scope(original["intent"].get("customerIdentity"), customer.identity):
            raise ValueError("original analysis customer scope required for cancellation")
        operation = original["intent"]["operationId"]
        cancel_id = original["id"] + ":cancel"
        if store.intent(identity, cancel_id, "analysis_cancel", {"operationId": operation}):
            store.settle(cancel_id, "sending", {"operationId": operation})
            try:
                result = observe(customer, store.root, operation, "cancel")
            except Exception:
                store.settle(cancel_id, "unknown", {"operationId": operation, "reason": "original native cancellation remains observable; financial holds retained"})
                raise
            store.settle(cancel_id, "settled", {"operationId": operation, "jobId": result.get("jobId"), "state": result["state"]}, 0)
        analysis_status(store, identity, operation)

def execute_tool(project, identity, owner, fence, call_id, name, args):
    """Trusted bridge with fixed tools and exact parent-approved paid analysis permissions."""
    with contextlib.closing(Store(project)) as store:
        row = store.get(identity)
        spec = row["spec"]
        if row["status"] != "active" or row["owner"] != owner or row["fence"] != fence or row["lease_until"] < time.time():
            raise ValueError("worker is stopped or tool ownership is stale")
        require_parent_admission(store, identity, spec)
        if name not in [*spec["tools"], "submit_result"]:
            raise ValueError("tool outside parent allowlist")
        operations = [o for o in store.operations(identity) if o["kind"] == "tool"]
        op_id = f"{identity}:tool:{call_id}"
        prior = next((o for o in operations if o["id"] == op_id), None)
        intent = {"name": name, "argumentsSha256": hashlib.sha256(canonical(args).encode()).hexdigest()}
        if name in {"analyze", "analysis_status"}:
            intent["analysisOperationId"] = args.get("operationId")
        if prior:
            if prior["intent"] != intent:
                raise ValueError("conflicting tool retry")
            if prior["state"] != "settled":
                raise ValueError("tool intent indeterminate; reconcile artifact receipt before retry")
            receipt = prior["receipt"]
            if name == "project_image":
                content = confined(store.root, receipt["path"]).read_bytes()
                if hashlib.sha256(content).hexdigest() != receipt["sha256"]:
                    raise ValueError("image changed since original tool receipt")
                return {**receipt, "imageData": base64.b64encode(content).decode()}
            return receipt
        if len(operations) >= spec["maxToolCalls"]:
            raise ValueError("tool allowance exhausted")
        store.intent(identity, op_id, "tool", intent, owner=owner, fence=fence)
        artifacts_dir = f"workers/{identity}/artifacts"
        if name == "analyze":
            result = submit_analysis(store, identity, owner, fence, args)
        elif name == "analysis_status":
            if not {"operationId"} <= set(args) <= {"operationId", "download"} or type(args.get("download", False)) is not bool:
                raise ValueError("analysis_status requires an authorized operation ID and optional bounded download")
            result = analysis_status(store, identity, args["operationId"], download=args.get("download", False))
        elif name == "project_image":
            if args["path"] not in spec["references"]:
                raise ValueError("image outside parent references")
            path = confined(store.root, args["path"])
            if path.stat().st_size > MAX_JSON_BYTES:
                raise ValueError("image exceeds 2 MiB bounded tool transport")
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest != spec["referenceDigests"][args["path"]]:
                raise ValueError("image digest changed")
            mime = "image/png" if content.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if content.startswith(b"\xff\xd8\xff") else None
            if not mime:
                raise ValueError("bounded image tool supports PNG/JPEG source-linked frames")
            result = {"path": args["path"], "sha256": digest, "mimeType": mime, "imageData": base64.b64encode(content).decode()}
        elif name == "project_read":
            if args["path"] not in spec["references"] and not args["path"].startswith(artifacts_dir+"/"):
                raise ValueError("file outside parent references")
            path = confined(store.root, args["path"])
            if args["path"] in spec["references"] and _digest(path) != spec["referenceDigests"][args["path"]]:
                raise ValueError("source/reference digest changed since admission")
            if path.stat().st_size > 65536:
                raise ValueError("read limited to 64 KiB compact text artifacts; prepare selected ranges first")
            result = {"path": args["path"], "content": path.read_text(encoding="utf-8"), "sha256": _digest(path)}
        elif name in {"artifact_write", "submit_result"}:
            value = args["value"]
            if name == "submit_result":
                from jsonschema import Draft202012Validator
                Draft202012Validator(spec["outputSchema"]).validate(value)
                relative = f"workers/{identity}/result.json"
            else:
                if not args.get("name") or Path(args["name"]).name != args["name"] or args["name"] in {".", ".."}:
                    raise ValueError("artifact name must be a filename")
                relative = artifacts_dir+"/"+args["name"]
            content = (canonical(value)+"\n").encode()
            if len(content) > MAX_JSON_BYTES:
                raise ValueError("artifact exceeds 2 MiB bound")
            path = confined(store.root, relative, must_exist=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if path.read_bytes() != content:
                    raise ValueError("immutable artifact exists with different content; use a new revision name")
            else:
                with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600), "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            result = {"path": relative, "sha256": hashlib.sha256(content).hexdigest(), "byteLength": len(content)}
        elif name == "render_ffmpeg":
            from vibeedit.render import render
            from vibeedit.validation import validate_composition
            source_path = args["compositionPath"]
            if not source_path.startswith(artifacts_dir+"/"):
                raise ValueError("render only accepts immutable worker-authored composition")
            composition = json.loads(confined(store.root, source_path).read_text(encoding="utf-8"))
            validate_composition(composition)
            if composition["render"]["backend"] not in {"ffmpeg", "auto"} or composition.get("motion") or composition.get("artifacts", {}).get("masks") or composition.get("artifacts", {}).get("tracking"):
                raise ValueError("worker renderer allows bounded FFmpeg compositions; executable HTML/model effects remain parent operations")
            for source in composition.get("sources", []):
                if source["kind"] not in {"video", "audio", "image"}:
                    raise ValueError("source kind outside worker renderer scope")
                reference = source["uri"]
                if reference not in spec["references"]:
                    raise ValueError("render source must be an explicit parent reference")
                resolved = confined(store.root, reference)
                if source.get("identity") != {"algorithm": "sha256", "value": spec["referenceDigests"][reference]}:
                    raise ValueError("composition must retain the original source SHA-256 identity")
                if _digest(resolved) != spec["referenceDigests"][reference]:
                    raise ValueError("render source digest changed")
                source["uri"] = str(resolved)
            if composition["durationFrames"] > 18000 or composition["canvas"]["width"]*composition["canvas"]["height"] > 3840*2160:
                raise ValueError("worker render exceeds 10-minute/4K resource bounds")
            name_out = args["outputName"]
            if Path(name_out).name != name_out or not name_out.endswith(".mp4"):
                raise ValueError("render output must be a plain MP4 filename")
            relative = artifacts_dir+"/"+name_out
            output = confined(store.root, relative, must_exist=False)
            if output.exists():
                raise ValueError("render output exists; reconcile its original operation, do not overwrite")
            output.parent.mkdir(parents=True, exist_ok=True)
            render(composition, output)
            result = verify_artifacts(store.root, [{"path": relative, "kind": "render"}])[0]
        else:
            raise ValueError("unknown scoped tool")
        store.settle(op_id, "settled", {k: v for k, v in result.items() if k != "imageData"}, 0)
        return result


def reconcile_inference(store, identity, operation):
    row = next((o for o in store.operations(identity) if o["id"] == operation and o["kind"] in {"inference", "analysis"}), None)
    if not row:
        raise ValueError("unknown original inference operation")
    if row["state"] == "settled":
        return row["receipt"]
    if row["kind"] == "analysis":
        return analysis_status(store, identity, row["intent"]["operationId"])
    if row["intent"].get("funding") == "managed":
        customer = _funding(store.get(identity)["spec"])
        if not _managed_same_scope(row["intent"].get("customerIdentity"), customer.identity):
            raise ValueError("original Myriograph customer identity required for reconciliation")
        response = customer.call("/v1/companion/requests/" + row["intent"]["remoteOperationId"])
        if response.get("operationId") != row["intent"]["remoteOperationId"] or response.get("requestSha256") != row["intent"]["requestSha256"]:
            raise ValueError("original managed request identity mismatch; hold retained")
        return _managed_settlement(store, operation, response)
    native_id = (row["receipt"] or {}).get("nativeGenerationId")
    if not native_id:
        raise ValueError("original native generation handle was never observed; keep hold and seek provider reconciliation, never make a replacement call")
    key = _funding(store.get(identity)["spec"])
    if row["intent"].get("credentialSha256") != hashlib.sha256(key.encode()).hexdigest():
        raise ValueError("original explicitly configured customer credential required for reconciliation")
    request = urllib.request.Request(OPENROUTER+"/generation?"+urllib.parse.urlencode({"id": native_id}), headers={"Authorization": "Bearer "+key})
    try:
        with provider_open(request, timeout=20) as response:
            data = json.load(response)["data"]
    except (OSError, ValueError, KeyError):
        raise ValueError("original generation not yet reconcilable; hold retained") from None
    if data.get("id") != native_id or data.get("total_cost") is None:
        raise ValueError("generation identity/cost missing; hold retained")
    cost = Decimal(str(data["total_cost"]))
    if not cost.is_finite() or cost < 0:
        raise ValueError("generation cost invalid; hold retained")
    receipt = {"nativeGenerationId": native_id, "usage": {k: data[k] for k in ("total_cost", "tokens_prompt", "tokens_completion", "native_tokens_prompt", "native_tokens_completion", "cancelled", "finish_reason") if k in data}, "transport": "reconciled original provider receipt"}
    store.settle(operation, "settled", receipt, int((cost*1_000_000).to_integral_value(rounding=ROUND_CEILING)))
    return receipt


def committed_artifacts(store, identity):
    """Validate exact durable submission bytes without asserting financial completion."""
    record = store.get(identity)
    submissions = [op for op in store.operations(identity) if op["kind"] == "tool" and op["intent"].get("name") == "submit_result" and op["state"] == "settled"]
    if not submissions or len({(op["receipt"].get("path"), op["receipt"].get("sha256")) for op in submissions}) != 1:
        raise ValueError("artifact recovery requires a durably settled, unambiguous structured submission")
    relative = f"workers/{identity}/result.json"
    path = confined(store.root, relative)
    receipt = submissions[0]["receipt"]
    if receipt.get("path") != relative or _digest(path) != receipt.get("sha256"):
        raise ValueError("structured submission bytes changed since original tool receipt")
    result = json.loads(path.read_text(encoding="utf-8"))
    from jsonschema import Draft202012Validator
    Draft202012Validator(record["spec"]["outputSchema"]).validate(result)
    artifacts = verify_artifacts(store.root, record["spec"]["artifacts"])
    prior = (record["result"] or {}).get("executionCheckpoint")
    checkpoint = {"result": result, "artifacts": artifacts, "submissionOperationId": submissions[0]["id"]}
    if prior is not None and prior != checkpoint:
        raise ValueError("verified execution checkpoint bytes changed while financial holds remain")
    return checkpoint


def analysis_execution_ready(operation):
    receipt = operation["receipt"] or {}
    settlement = receipt.get("settlement") or {}
    return operation["kind"] == "analysis" and receipt.get("state") in {"completed", "succeeded", "failed", "cancelled", "canceled"} and settlement.get("schemaVersion") == "myriograph.customerSettlement.v1" and settlement.get("state") == "held" and all(settlement.get(field) is True for field in ("terminalExecutionProven", "providerChildrenSettled", "platformCensusKnown", "readyForParentSettlement"))


def execution_checkpoint(store, identity, *, refresh_analysis=False):
    """Ready artifacts may advance declared steps while original retail holds stay held."""
    record = store.get(identity)
    if record["status"] == "complete":
        return record["result"]
    if record["status"] not in {"waiting", "paused"} or record["lease_until"] > time.time():
        return None
    operations = store.operations(identity)
    pending = [op for op in operations if op["state"] != "settled"]
    if not pending or any(op["kind"] != "analysis" for op in pending):
        return None
    if refresh_analysis:
        for op in pending:
            analysis_status(store, identity, op["intent"]["operationId"])
        operations = store.operations(identity)
        pending = [op for op in operations if op["state"] != "settled"]
    if not all(analysis_execution_ready(op) for op in pending):
        return None
    checkpoint = committed_artifacts(store, identity)
    if not pending:
        return recover_artifacts(store, identity)["result"]
    # This is execution-only evidence. Neither the worker nor its financial
    # child allowance becomes complete until the original ledger acknowledges.
    return {**checkpoint, "financialState": "held-until-original-parent-settlement"}


def recover_artifacts(store, identity):
    """Adopt exact committed worker artifacts after a supervisor/RPC crash; no model replay."""
    record = store.get(identity)
    if record["kind"] != "worker":
        raise ValueError("handle is not a worker")
    if record["status"] == "complete":
        return record
    if record["lease_until"] > time.time():
        raise ValueError("worker still has a live lease; observe/cancel it before artifact recovery")
    operations = store.operations(identity)
    if any(op["kind"] == "managed_allowance_close" and op["state"] != "settled" for op in operations):
        close_managed_allowance(store, identity)
        operations = store.operations(identity)
    pending = [op for op in operations if op["state"] != "settled" and op["kind"] != "rpc_prompt"]
    if pending and not record["spec"].get("parentGoalId") and all(op["kind"] == "analysis" for op in pending):
        committed_artifacts(store, identity)
        for operation in pending:
            analysis_status(store, identity, operation["intent"]["operationId"])
        pending = [op for op in store.operations(identity) if op["state"] != "settled" and op["kind"] != "rpc_prompt"]
        if all(analysis_execution_ready(op) for op in pending):
            close_managed_allowance(store, identity)
            for operation in pending:
                analysis_status(store, identity, operation["intent"]["operationId"])
        operations = store.operations(identity)
    if any(op["state"] != "settled" for op in operations if op["kind"] != "rpc_prompt"):
        raise ValueError("original provider/tool acknowledgement remains unknown; reconcile it before artifact recovery")
    checkpoint = committed_artifacts(store, identity)
    # Fence stale ownership before adoption; interrupted recovery stays paused.
    store.update(identity, "paused", {"reason": "explicit artifact recovery; original sends retained"}, expected_revision=record["revision"])
    spec = record["spec"]
    result, artifacts = checkpoint["result"], checkpoint["artifacts"]
    for op in operations:
        if op["kind"] == "rpc_prompt" and op["state"] != "settled":
            store.settle(op["id"], "settled", {"transport": "original RPC disposition unknown", "recovery": "exact committed submission and required artifacts independently validated; no model replay", "submissionOperationId": checkpoint["submissionOperationId"]}, 0)
    if not spec.get("parentGoalId"):
        close_managed_allowance(store, identity)
    current = store.get(identity)
    return store.update(identity, "complete", {"result": result, "artifacts": artifacts, "sessionId": identity, "usageMicrousd": sum(op["settled_microusd"] or 0 for op in operations if op["kind"] in {"inference", "analysis"}), "recovery": "artifact-adopted; original RPC conversation disposition not claimed"}, expected_revision=current["revision"])


def register_commands(subparsers):
    group = subparsers.add_parser("worker", help="bounded optional Pi companion")
    sub = group.add_subparsers(dest="worker_command", required=True)
    setup = sub.add_parser("setup")
    setup.add_argument("--json", action="store_true")
    setup.set_defaults(handler=_command)
    config = sub.add_parser("configure")
    config.add_argument("--key-stdin", action="store_true", required=True)
    config.add_argument("--json", action="store_true")
    config.set_defaults(handler=_command)
    profiles = sub.add_parser("profiles")
    profiles.add_argument("--refresh", action="store_true")
    profiles.add_argument("--funding", choices=("byok", "managed"), default="byok")
    profiles.add_argument("--json", action="store_true")
    profiles.set_defaults(handler=_command)
    for action in ("run", "status", "events", "steer", "cancel", "resume", "reconcile", "recover"):
        parser = sub.add_parser(action)
        parser.add_argument("--project", required=True)
        parser.add_argument("--id", required=True)
        parser.add_argument("--json", action="store_true")
        if action == "run":
            parser.add_argument("--spec", required=True)
            parser.add_argument("--no-detach", action="store_true")
        if action == "events":
            parser.add_argument("--after", type=int, default=0)
        if action in {"steer", "reconcile"}:
            parser.add_argument("--operation-id", required=True)
        if action == "steer":
            parser.add_argument("--message", required=True)
        parser.set_defaults(handler=_command)


def _command(args):
    action = args.worker_command
    if action == "setup":
        print(json.dumps(setup_worker()))
        return 0
    if action == "configure":
        print(json.dumps(configure_byok(sys.stdin.read(2048))))
        return 0
    if action == "profiles":
        if args.funding == "managed":
            customer = _funding({"funding": "managed"})
            capabilities = customer.call("/v1/companion/capabilities")
            profiles = {name: managed_profile(customer, {"profile": name}, capabilities) for name in PROFILES}
            print(json.dumps({"schemaVersion": SCHEMA, "ok": True, "funding": "managed", "profiles": profiles, "transport": capabilities["transport"], "qualification": "deployed capability metadata only; real inference/customer settlement qualification is separate"}))
            return 0
        print(json.dumps({"schemaVersion": SCHEMA, "ok": True, "funding": "byok", "profiles": refresh_profiles() if args.refresh else PROFILES, "managed": "query explicitly using profiles --funding managed; no fallback", "qualification": "catalog only; actual tool/image/video/cancellation inference awaits authorized test budget"}))
        return 0
    with contextlib.closing(Store(args.project)) as store:
        if action == "run":
            spec = validate_task(json.loads(Path(args.spec).read_text(encoding="utf-8")))
            record = store.create("worker", args.id, spec)
            if not args.no_detach and record["status"] == "active":
                detach(__name__, store.root, args.id)
        else:
            record = store.get(args.id)
            if record["kind"] != "worker":
                raise ValueError("handle is not a worker")
            if action == "recover":
                recover_artifacts(store, args.id)
            if action == "reconcile":
                reconcile_inference(store, args.id, args.operation_id)
            if action in {"cancel", "steer"} and record["status"] == "active":
                store.control(args.id, action, {"message": args.message} if action == "steer" else {}, getattr(args, "operation_id", None))
            if action == "cancel" and record["status"] in {"waiting", "blocked", "paused", "canceled"}:
                store.control(args.id, "cancel", {}, getattr(args, "operation_id", None))
                if record["status"] != "canceled":
                    store.update(args.id, "canceled", {"reason": "explicit cancellation; original job handles and unsettled holds retained"}, expected_revision=record["revision"])
                try:
                    cancel_managed_operations(store, args.id)
                    cancel_analysis_operations(store, args.id)
                    if not record["spec"].get("parentGoalId"):
                        close_managed_allowance(store, args.id)
                except (OSError, RuntimeError, ValueError):
                    store.event(args.id, "managed_cancel_pending", {"reason": "original request/allowance cancellation remains observable; no new work admitted"})
            if action == "resume":
                if record["status"] in {"complete", "failed"}:
                    raise ValueError("terminal worker replay is read-only")
                operations = store.operations(args.id)
                committed = any(operation["kind"] == "tool" and operation["state"] == "settled" and operation["intent"].get("name") == "submit_result" for operation in operations)
                if committed:
                    recover_artifacts(store, args.id)
                else:
                    if any(operation["state"] != "settled" for operation in operations):
                        raise ValueError("resume requires reconciliation of original indeterminate operations; never replace their handles")
                    store.update(args.id, "active", {"reason": "explicit resume of same task/session"}, expected_revision=record["revision"])
                    detach(__name__, store.root, args.id)
        result = {"schemaVersion": SCHEMA, "ok": True, "worker": store.get(args.id), "continuation": f"vibeedit worker status --project {json.dumps(str(store.root))} --id {args.id} --json"}
        if action == "events":
            result["events"] = store.events(args.id, args.after)
        if action == "status":
            result["operations"] = store.operations(args.id)
        print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--handle", required=True)
    parser.add_argument("--tool")
    parser.add_argument("--call-id")
    arguments = parser.parse_args()
    if arguments.tool:
        try:
            value = json.loads(sys.stdin.buffer.read(MAX_JSON_BYTES+1))
            result = execute_tool(arguments.project, arguments.handle, os.environ["VIBEEDIT_WORKER_OWNER"], int(os.environ["VIBEEDIT_WORKER_FENCE"]), arguments.call_id, arguments.tool, value)
            print(canonical({"ok": True, "result": result}))
        except (OSError, ValueError, RuntimeError, KeyError, ValidationError, subprocess.SubprocessError) as error:
            print(canonical({"ok": False, "error": "scoped tool rejected invalid input or execution; inspect durable operation"}))
            sys.exit(1)
    else:
        run_worker(arguments.project, arguments.handle)
