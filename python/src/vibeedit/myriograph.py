"""Thin customer clients; native jobs and Myriograph remain authoritative.

There is deliberately no operator-credential discovery or private-worker route.
A new paid admission requires an advertised server-enforced retail ceiling.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
import webbrowser

PUBLIC_ORIGIN = "https://u83j0k7e5m.execute-api.ca-central-1.amazonaws.com"
SERVICE_PATHS = {"video": "/v1/video", "speakers": "/v1/voices", "faces": "/v1/faces"}
_WINDOWS = os.name == "nt"
TERMINAL = {"completed", "succeeded", "failed", "cancelled", "canceled"}


class MyriographError(RuntimeError):
    def __init__(self, code: str, status: int | None = None):
        self.code = code
        self.status = status
        super().__init__(f"Myriograph {code}" + (f" (HTTP {status})" if status else ""))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise MyriographError("redirect_refused")


def config_path() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "vibeedit" / "myriograph.json"


def _origin(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Myriograph apiUrl must be an HTTPS origin without credentials, path or query.")
    return value.rstrip("/")


def read_config(path: Path | None = None, *, allow_unprotected_import: bool = False) -> dict:
    path = path or config_path()
    if not path.is_file():
        raise MyriographError("login_required")
    if not _WINDOWS and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("Myriograph credential file must have owner-only permissions (chmod 600).")
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and "apiKeyDpapi" in value:
        if not _WINDOWS or "apiKey" in value or value.get("credentialProtection") != "windows-user-dpapi.v1":
            raise ValueError("Protected Myriograph credential must be opened by its original Windows user.")
        value = {**{key: item for key, item in value.items() if key not in {"apiKeyDpapi", "credentialProtection"}},
                 "apiKey": _windows_credential(base64.b64decode(value["apiKeyDpapi"], validate=True), protect=False).decode()}
    elif _WINDOWS and not allow_unprotected_import:
        raise ValueError("Import the customer config with myriograph login --import-config to protect its key for this Windows user.")
    if not isinstance(value, dict) or not isinstance(value.get("apiKey"), str) or not value["apiKey"].strip():
        raise ValueError("Customer config needs apiUrl and a nonempty apiKey.")
    return {**value, "apiUrl": _origin(value["apiUrl"])}


def _windows_credential(value: bytes, *, protect: bool) -> bytes:
    if not _WINDOWS:
        raise ValueError("Windows user credential protection is unavailable.")
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
    source, target = Blob(len(value), buffer), Blob()
    try:
        # UI forbidden, current-user scope; never machine-wide protection.
        if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
            raise ValueError("Windows user credential protection failed.")
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.memset(buffer, 0, len(value))
        if target.pbData:
            kernel.LocalFree(target.pbData)


def _save_private(path: Path, value: dict) -> None:
    if _WINDOWS:
        value = {**{key: item for key, item in value.items() if key != "apiKey"}, "credentialProtection": "windows-user-dpapi.v1",
                 "apiKeyDpapi": base64.b64encode(_windows_credential(value["apiKey"].encode(), protect=True)).decode()}
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Myriograph:
    def __init__(self, config: dict):
        self.origin = _origin(config["apiUrl"])
        self.headers = {"Authorization": "Bearer " + config["apiKey"], "Content-Type": "application/json"}
        self.headers.update({header: config[key] for key, header in [("organizationId", "X-Organization-Id"), ("projectId", "X-Project-Id")] if config.get(key)})
        self.identity = {"apiUrl": self.origin, "keySha256": hashlib.sha256(config["apiKey"].encode()).hexdigest(), **{k: config[k] for k in ("organizationId", "projectId") if config.get(k)}}
        self.opener = urllib.request.build_opener(_NoRedirect())

    def call(self, path: str, body: dict | None = None, *, method: str | None = None, key: str | None = None, authenticated: bool = True) -> dict:
        if not path.startswith("/") or path.startswith("//") or "/internal/" in path or "?" in path or "#" in path:
            raise ValueError("Use a public Myriograph route.")
        headers = dict(self.headers) if authenticated else {"Content-Type": "application/json"}
        if key:
            headers["Idempotency-Key"] = key
        request = urllib.request.Request(self.origin + path, data=json.dumps(body, allow_nan=False).encode() if body is not None else None, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=65) as response:
                data = response.read(16 * 1024 * 1024 + 1)
                if len(data) > 16 * 1024 * 1024:
                    raise MyriographError("response_requires_download")
                value = json.loads(data)
                if not isinstance(value, dict):
                    raise MyriographError("invalid_response")
                return value
        except urllib.error.HTTPError as error:
            with error:
                data = error.read(65536)
            try:
                detail = json.loads(data).get("error", {})
            except (ValueError, AttributeError):
                detail = {}
            # Do not echo remote messages, tokens, signed URLs or request bodies.
            code = detail.get("code", "request_failed") if isinstance(detail, dict) else "request_failed"
            raise MyriographError(code if re.fullmatch(r"[a-zA-Z0-9_.:-]{1,128}", str(code)) else "request_failed", error.code) from None
        except (urllib.error.URLError, TimeoutError):
            raise MyriographError("transport_unknown" if body is not None else "transport_unavailable") from None

    def bind_customer(self) -> None:
        if "accountId" in self.identity:
            return
        billing = self.call("/v1/video/billing")
        if billing.get("mode") not in ("live", "test") or not isinstance(billing.get("accountId"), str):
            raise MyriographError("customer_account_binding_required")
        # Native visual jobs are account-owned. Bind to the verified account,
        # allowing a rotated customer key to recover that account's original jobs.
        self.identity = {"apiUrl": self.origin, "accountId": billing["accountId"], "mode": billing["mode"],
                         **{k: self.identity[k] for k in ("organizationId", "projectId") if k in self.identity}}

    def capabilities(self, service: str) -> dict:
        return self.call(SERVICE_PATHS[service] + "/capabilities")

    def check_retail_ceiling(self, service: str) -> None:
        """Only a deployed native contract can promise admission enforcement."""
        capabilities = self.capabilities(service)
        if not isinstance(capabilities.get("retailCeiling"), dict) or any(capabilities["retailCeiling"].get(k) != v for k, v in {"field": "maxRetailUsd", "enforced": True, "currency": "USD"}.items()):
            raise MyriographError("server_retail_ceiling_unavailable")


@contextmanager
def _database(project: Path):
    root = project.resolve() / ".vibeedit"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    db_path = root / "myriograph.sqlite3"
    connection = sqlite3.connect(db_path, timeout=10)
    if os.name != "nt":
        db_path.chmod(0o600)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute("CREATE TABLE IF NOT EXISTS jobs (operation TEXT PRIMARY KEY, service TEXT NOT NULL, identity TEXT NOT NULL, intent TEXT NOT NULL, request TEXT, idempotency_key TEXT NOT NULL, native_id TEXT, state TEXT NOT NULL, response TEXT, updated REAL NOT NULL)")
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def export_recovery(project: Path) -> dict:
    """Export passive original-operation records, excluding observations and credentials."""
    with _database(project) as db:
        jobs = [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY operation")]
    for row in jobs:
        row["response"] = None  # Native observations can contain temporary signed links.
    data = {"schemaVersion": "vibeedit.myriographRecovery.v1", "jobs": jobs}
    _validate_recovery(data)
    return data


def import_recovery(project: Path, data: dict) -> None:
    """Restore validated JSON into an empty journal without network or paid admission."""
    jobs = _validate_recovery(data)
    with _database(project) as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT 1 FROM jobs LIMIT 1").fetchone():
            raise MyriographError("recovery_destination_not_empty")
        db.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)", [tuple(row[k] for k in ("operation", "service", "identity", "intent", "request", "idempotency_key", "native_id", "state", "response", "updated")) for row in jobs])


def _validate_recovery(data: dict) -> list[dict]:
    if not isinstance(data, dict) or set(data) != {"schemaVersion", "jobs"} or data["schemaVersion"] != "vibeedit.myriographRecovery.v1" or not isinstance(data["jobs"], list) or len(data["jobs"]) > 100000:
        raise MyriographError("recovery_schema")
    seen = set()
    for row in data["jobs"]:
        if not isinstance(row, dict) or set(row) != {"operation", "service", "identity", "intent", "request", "idempotency_key", "native_id", "state", "response", "updated"}:
            raise MyriographError("recovery_schema")
        _safe_id(row["operation"])
        _safe_id(row["idempotency_key"])
        if row["native_id"] is not None:
            _safe_id(row["native_id"])
        if row["operation"] in seen or row["service"] not in SERVICE_PATHS or not isinstance(row["state"], str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,128}", row["state"]) or row["response"] is not None or type(row["updated"]) not in (int, float) or not math.isfinite(row["updated"]):
            raise MyriographError("recovery_record")
        seen.add(row["operation"])
        for field in ("identity", "intent", "request"):
            if row[field] is None and field == "request":
                continue
            if not isinstance(row[field], str) or len(row[field]) > 1024 * 1024:
                raise MyriographError("recovery_record")
            value = json.loads(row[field])
            if not isinstance(value, dict) or row[field] != _canonical(value):
                raise MyriographError("recovery_record")
            if field == "identity" and (not set(value) <= {"apiUrl", "accountId", "mode", "keySha256", "organizationId", "projectId"} or "apiUrl" not in value or _origin(value["apiUrl"]) != value["apiUrl"]):
                raise MyriographError("recovery_identity")
            # Identity's public origin is expected. Durable admission bodies must
            # contain stable native references, never temporary network grants.
            if field != "identity" and (re.search(r"https?://", row[field], re.IGNORECASE) or re.search(r'"(?:apiKey|authorization|accessToken|refreshToken|secret)"\s*:', row[field], re.IGNORECASE)):
                raise MyriographError("recovery_contains_credentials_or_urls")
        if row["state"] == "admission_unknown" and row["request"] is None:
            raise MyriographError("recovery_missing_original_admission")
    return data["jobs"]


def _safe_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
        raise ValueError("Use a 1–128 character operation/job ID containing letters, digits, dot, colon, underscore or hyphen.")
    return value


def _source(path: Path) -> dict:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"sha256": digest, "byteLength": path.stat().st_size, "contentType": mimetypes.guess_type(path.name)[0] or "application/octet-stream"}


def submit(api: Myriograph, project: Path, service: str, media: Path, options: dict, max_retail_usd: float, operation: str, *, funding_allowance_id: str | None = None) -> dict:
    _safe_id(operation)
    api.bind_customer()
    if not math.isfinite(max_retail_usd) or max_retail_usd <= 0:
        raise ValueError("max-retail-usd must be a finite positive USD amount.")
    if set(options) & {"uploadId", "maxRetailUsd", "fundingAllowanceId"}:
        raise ValueError("uploadId, maxRetailUsd and fundingAllowanceId are controlled by durable admission.")
    intent = {"source": _source(media), "settings": options, "maxRetailUsd": max_retail_usd}
    if funding_allowance_id is not None:
        intent["fundingAllowanceId"] = _safe_id(funding_allowance_id)
    # Keep a transaction across network work so concurrent observers cannot submit.
    # SQLite releases it on process death; a committed send fence survives the death.
    with _database(project) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM jobs WHERE operation=?", (operation,)).fetchone()
        if row and (row["identity"] != _canonical(api.identity) or row["intent"] != _canonical(intent) or row["service"] != service):
            raise MyriographError("operation_conflict")
        if row and row["native_id"]:
            return _receipt(dict(row), project)
        if row and row["state"] == "admission_unknown":
            raise MyriographError("admission_unknown_reconcile_original")
        if not row:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)", (operation, service, _canonical(api.identity), _canonical(intent), None, uuid.uuid4().hex, None, "prepared", None, time.time()))
            db.commit()
        api.check_retail_ceiling(service)
        if funding_allowance_id is not None:
            capability = api.capabilities(service).get("fundingAllowance", {})
            if capability.get("field") != "fundingAllowanceId" or capability.get("sharedGoal") is not True:
                raise MyriographError("server_shared_goal_allowance_unavailable")
        db.execute("BEGIN IMMEDIATE") if not db.in_transaction else None
        row = db.execute("SELECT * FROM jobs WHERE operation=?", (operation,)).fetchone()
        if row["native_id"]:
            return _receipt(dict(row), project)
        if row["state"] == "admission_unknown":
            raise MyriographError("admission_unknown_reconcile_original")
        request = json.loads(row["request"]) if row["request"] else None
        if request is None:
            request = {**options, **_upload_source(api, service, media, intent["source"], funding_allowance_id=funding_allowance_id), "maxRetailUsd": max_retail_usd,
                       **({"fundingAllowanceId": funding_allowance_id} if funding_allowance_id is not None else {})}
        # A send may succeed remotely before any reply. Never clear this fence
        # merely because this client dies, times out or loses its acknowledgement.
        db.execute("UPDATE jobs SET request=?,state='admission_unknown',updated=? WHERE operation=?", (_canonical(request), time.time(), operation))
        db.commit()
        response = api.call(SERVICE_PATHS[service] + "/jobs", request, key=row["idempotency_key"])
        native_id = response.get("jobId", response.get("id"))
        if not isinstance(native_id, str):
            raise MyriographError("missing_original_job_handle")
        _safe_id(native_id)
        db.execute("UPDATE jobs SET native_id=?,state=?,response=?,updated=? WHERE operation=?", (native_id, response.get("state", response.get("status", "accepted")), _canonical(response), time.time(), operation))
        return _receipt(dict(db.execute("SELECT * FROM jobs WHERE operation=?", (operation,)).fetchone()), project)


def _upload_source(api: Myriograph, service: str, media: Path, identity: dict, *, funding_allowance_id: str | None = None) -> dict:
    base = SERVICE_PATHS[service]
    upload_body = {**identity, **({"fundingAllowanceId": funding_allowance_id} if funding_allowance_id is not None else {})}
    upload_key = "vibeedit-upload-" + hashlib.sha256(_canonical({"customer": api.identity, "service": service, "source": upload_body}).encode()).hexdigest()
    upload = api.call(base + "/uploads", upload_body, key=upload_key)
    if service == "faces":
        if upload.get("source"):
            if upload["source"].get("artifactSha256") != identity["sha256"] or upload["source"].get("byteLength") != identity["byteLength"]:
                raise MyriographError("multipart_source_binding")
            return {"source": upload["source"]}
        if upload.get("state") != "uploading" or not isinstance(upload.get("partBytes"), int) or not 0 < upload["partBytes"] <= 64 * 1024 * 1024:
            raise MyriographError("multipart_upload_reconciliation_required")
        count = math.ceil(identity["byteLength"] / upload["partBytes"])
        with media.open("rb") as stream:
            for start in range(1, count + 1, 16):
                parts = api.call(base + "/uploads/" + identity["sha256"] + "/parts", {"partNumbers": list(range(start, min(count + 1, start + 16)))})
                for part in parts["parts"]:
                    ordinal = part["partNumber"]
                    if type(ordinal) is not int or not start <= ordinal < min(count + 1, start + 16):
                        raise MyriographError("invalid_multipart_descriptor")
                    stream.seek((ordinal - 1) * upload["partBytes"])
                    data = stream.read(min(upload["partBytes"], identity["byteLength"] - stream.tell()))
                    if len(data) != part["byteLength"]:
                        raise MyriographError("multipart_source_changed")
                    _put_source(api, part["url"], data, {"Content-Length": str(len(data))})
        complete = api.call(base + "/uploads/" + identity["sha256"] + "/complete", {})
        source = complete.get("source")
        if not source or source.get("artifactSha256") != identity["sha256"] or source.get("byteLength") != identity["byteLength"]:
            raise MyriographError("multipart_completion_reconciliation_required")
        return {"source": source}
    if not upload.get("uploaded"):
        with media.open("rb") as stream:
            _put_source(api, upload["url"], stream, {**upload.get("headers", upload.get("requiredHeaders", {})), "Content-Length": str(identity["byteLength"])})
    return {"uploadId": upload["uploadId"]}


def _put_source(api: Myriograph, url: str, data, headers: dict) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise MyriographError("invalid_upload_capability")
    request = urllib.request.Request(url, data=data, headers=headers, method="PUT")
    with api.opener.open(request, timeout=600) as response:
        if response.status not in (200, 201, 204):
            raise MyriographError("upload_incomplete")


def _receipt(row: dict, project: Path) -> dict:
    return {"schemaVersion": "vibeedit.myriographJob.v1", "ok": True, "operation": row["operation"], "service": row["service"], "jobId": row["native_id"], "state": row["state"], "continuation": ["vibeedit", "jobs", "status", row["operation"], "--project", str(project.resolve()), "--json"]}


def observe(api: Myriograph, project: Path, operation: str, action: str = "status") -> dict:
    api.bind_customer()
    with _database(project) as db:
        row = db.execute("SELECT * FROM jobs WHERE operation=?", (_safe_id(operation),)).fetchone()
        if row is None:
            raise MyriographError("local_job_not_found")
        if row["identity"] != _canonical(api.identity):
            raise MyriographError("original_customer_credentials_required")
        if not row["native_id"]:
            if action != "resume" or row["state"] != "admission_unknown" or row["service"] not in SERVICE_PATHS:
                raise MyriographError("admission_unknown_reconcile_original" if row["state"] == "admission_unknown" else "admission_not_sent")
            # Faces first read and validate the original alias. Explicit resume
            # may then continue only a server-proven unsent original admission;
            # unknown physical queue sends stay fenced. Video/voice admission
            # replays its exact original key/body.
            result = _recover_face_admission(api, row) if row["service"] == "faces" else api.call(
                SERVICE_PATHS[row["service"]] + "/jobs", json.loads(row["request"]), key=row["idempotency_key"])
            native_id = result.get("jobId", result.get("id"))
            if not isinstance(native_id, str):
                raise MyriographError("missing_original_job_handle")
            _safe_id(native_id)
            db.execute("UPDATE jobs SET native_id=?,state=?,response=?,updated=? WHERE operation=?", (native_id, result.get("state", result.get("status", "accepted")), _canonical(result), time.time(), operation))
            return {**_receipt(dict(db.execute("SELECT * FROM jobs WHERE operation=?", (operation,)).fetchone()), project), "native": result, "reconciledOriginalAdmission": True}
        base = SERVICE_PATHS[row["service"]] + "/jobs/" + _safe_id(row["native_id"])
        suffix = {"status": "", "cancel": "/cancel", "resume": "/recover", "download": "/download"}[action]
        body = {} if action in ("cancel", "resume") else None
        if row["service"] == "faces" and action == "resume":
            current = api.call(base)
            if current.get("state") == "completed":
                return {**_receipt(dict(row), project), "state": "completed", "native": current}
            revision = current.get("statusRevisionSha256")
            if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{64}", revision):
                raise MyriographError("face_resume_revision_required")
            suffix, body = "/resume", {"expectedStatusSha256": revision}
        result = api.call(base + suffix, body)
        if action != "download":
            db.execute("UPDATE jobs SET state=?,response=?,updated=? WHERE operation=?", (result.get("state", result.get("status", row["state"])), _canonical(result), time.time(), operation))
        return {**_receipt(dict(db.execute("SELECT * FROM jobs WHERE operation=?", (operation,)).fetchone()), project), "native": result}


def _recover_face_admission(api: Myriograph, row: sqlite3.Row) -> dict:
    path = SERVICE_PATHS["faces"] + "/operations/" + _safe_id(row["idempotency_key"])
    try:
        result = api.call(path)
    except MyriographError as error:
        if error.status == 404:
            raise MyriographError("original_face_operation_not_found", 404) from None
        raise
    _validate_face_operation(row, result)
    if result.get("resumeOriginalAllowed") is True and result.get("admissionState") in ("prepared", "funding_unknown", "funded_unsent"):
        # Explicit resume may wake only this proven-unsent original intent.
        # Status/watch never enter this path; indeterminate queue sends stay fenced.
        continued = api.call(path + "/recover", {"expectedRequestIntentSha256": result["requestIntentSha256"]})
        _validate_face_operation(row, continued)
        if continued["jobId"] != result["jobId"]:
            raise MyriographError("original_face_operation_binding")
        return continued
    return result


def _validate_face_operation(row: sqlite3.Row, result: dict) -> None:
    original = json.loads(row["request"])
    source = original.get("source")
    intent = result.get("requestIntent")
    # Native canonical JSON permits integers only, so the API freezes the price
    # as its exact JSON-number text. All source/library/frame terms stay intact.
    price = intent.get("maxRetailUsd") if isinstance(intent, dict) else None
    if (result.get("schemaVersion") != "myriograph.faceOperationStatus.v1"
            or result.get("originalIdempotencyKey") != row["idempotency_key"]
            or not isinstance(result.get("jobId"), str) or not re.fullmatch(r"[a-f0-9]{64}", result["jobId"])
            or not isinstance(intent, dict) or not isinstance(price, str) or len(price) > 128
            or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?", price)
            or float(price) != original.get("maxRetailUsd")
            or {key: value for key, value in intent.items() if key != "maxRetailUsd"} != {key: value for key, value in original.items() if key != "maxRetailUsd"}
            or result.get("requestIntentSha256") != hashlib.sha256((_canonical(intent) + "\n").encode()).hexdigest()
            or not isinstance(source, dict) or not isinstance(source.get("artifactSha256"), str)
            or result.get("sourceSha256") not in (None, source["artifactSha256"])):
        raise MyriographError("original_face_operation_binding")


def download(api: Myriograph, project: Path, operation: str, destination: Path, max_bytes: int = 128 * 1024 * 1024) -> dict:
    descriptor = observe(api, project, operation, "download")
    native = descriptor["native"]
    artifacts = native.get("artifacts", [{"kind": "result", **native}])
    if descriptor["service"] == "faces":
        package = native.get("package", {})
        artifacts = [{"kind": "faces", "url": native.get("url"), "sha256": package.get("artifactSha256"), "byteLength": package.get("byteLength"), "format": "zip"}]
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    saved = []
    for artifact in artifacts:
        kind, expected = artifact.get("kind"), artifact.get("sha256")
        if not isinstance(kind, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", kind) or not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            raise MyriographError("invalid_artifact_descriptor")
        url = urllib.parse.urlsplit(artifact["url"])
        if url.scheme != "https" or url.username or url.password:
            raise MyriographError("invalid_download_capability")
        target = destination / (kind + (".zip" if artifact.get("format") == "zip" else ".json"))
        if target.exists():
            with target.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() == expected:
                    saved.append({"kind": kind, "path": str(target), "sha256": expected})
                    continue
            raise MyriographError("existing_artifact_conflict")
        fd, temporary = tempfile.mkstemp(dir=destination)
        try:
            digest, total = hashlib.sha256(), 0
            # Signed downloads never receive Myriograph authorization headers.
            with os.fdopen(fd, "wb") as stream, api.opener.open(urllib.request.Request(artifact["url"]), timeout=120) as response:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise MyriographError("artifact_download_limit")
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if digest.hexdigest() != expected or artifact.get("byteLength", total) != total:
                raise MyriographError("artifact_integrity")
            with _database(project) as db:
                intent = json.loads(db.execute("SELECT intent FROM jobs WHERE operation=?", (operation,)).fetchone()[0])
            value = _verify_face_archive(Path(temporary), descriptor["jobId"], intent["source"]["sha256"], max_bytes) if artifact.get("format") == "zip" else json.loads(Path(temporary).read_text(encoding="utf-8"))
            if kind in ("result", "baseline", "faces") and value.get("sourceSha256") != intent["source"]["sha256"]:
                raise MyriographError("artifact_source_mismatch")
            os.replace(temporary, target)
            saved.append({"kind": kind, "path": str(target), "sha256": expected, "byteLength": total, "schemaVersion": value.get("schemaVersion")})
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return {**descriptor, "native": {"artifacts": saved}}


def _verify_face_archive(path: Path, job_id: str, source_sha256: str, max_bytes: int) -> dict:
    """Validate public native manifest without extracting or importing private code."""
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(n.startswith("/") or ".." in PurePosixPath(n).parts or "\\" in n for n in names):
            raise MyriographError("unsafe_face_package_members")
        if sum(i.file_size for i in archive.infolist()) > max_bytes or any(stat.S_ISLNK(i.external_attr >> 16) for i in archive.infolist()):
            raise MyriographError("face_package_expansion_limit")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("schemaVersion") not in ("myriograph.faceIdentityResult.v1", "myriograph.faceIdentityResult.v2") or manifest.get("sourceSha256") != source_sha256 or manifest.get("jobId") != job_id:
            raise MyriographError("face_package_binding")
        files = manifest.get("files", [])
        if len(files) != len(names) - 1 or set(names) != {"manifest.json", *(f["path"] for f in files)}:
            raise MyriographError("unbound_face_package_member")
        for item in files:
            with archive.open(item["path"]) as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"] or archive.getinfo(item["path"]).file_size != item["byteLength"]:
                    raise MyriographError("face_package_member_integrity")
        return manifest


def register_commands(subparsers) -> None:
    account = subparsers.add_parser("myriograph", help="Myriograph customer login, account and credit")
    commands = account.add_subparsers(dest="myriograph_action", required=True)
    for name in ("login", "logout", "status", "account", "billing"):
        command = commands.add_parser(name)
        command.add_argument("--json", action="store_true")
        command.add_argument("--config", type=Path)
        if name == "login":
            command.add_argument("--import-config", type=Path, help="import the customer JSON downloaded from Myriograph; never pass a key on the command line")
            command.add_argument("--browser", action="store_true")
        command.set_defaults(handler=_account_command)
    analyze = subparsers.add_parser("analyze", help="Submit paid intelligence with an enforceable retail ceiling")
    services = analyze.add_subparsers(dest="service", required=True)
    for name in SERVICE_PATHS:
        command = services.add_parser(name)
        command.add_argument("media", type=Path)
        command.add_argument("--project", required=True, type=Path)
        command.add_argument("--operation", required=True, help="retain this operation ID for exact retry")
        command.add_argument("--max-retail-usd", required=True, type=float)
        command.add_argument("--funding-allowance-id", help="retain the original server goal allowance; native service capability required")
        command.add_argument("--options", type=Path, help="native service options as JSON")
        command.add_argument("--config", type=Path)
        command.add_argument("--json", action="store_true")
        command.set_defaults(handler=_analyze_command)
    jobs = subparsers.add_parser("jobs", help="Observe and recover original native Myriograph jobs")
    commands = jobs.add_subparsers(dest="job_action", required=True)
    for name in ("list", "status", "watch", "cancel", "resume", "download"):
        command = commands.add_parser(name)
        if name != "list":
            command.add_argument("operation")
        command.add_argument("--project", required=True, type=Path)
        command.add_argument("--config", type=Path)
        command.add_argument("--json", action="store_true")
        if name == "watch":
            command.add_argument("--wait-seconds", type=float, default=30)
        if name == "download":
            command.add_argument("--destination", required=True, type=Path)
            command.add_argument("--max-download-bytes", type=int, default=128 * 1024 * 1024, help="explicit compressed and expanded per-artifact limit")
        command.set_defaults(handler=_jobs_command)


def _print(value: dict) -> int:
    print(json.dumps({"schemaVersion": "vibeedit.myriograph.v1", "ok": True, **value}, ensure_ascii=False, allow_nan=False))
    return 0


def _account_command(args: argparse.Namespace) -> int:
    path = args.config or config_path()
    if args.myriograph_action == "logout":
        path.unlink(missing_ok=True)
        return _print({"loggedIn": False, "revocationRequired": True, "billingUrl": PUBLIC_ORIGIN + "/billing"})
    if args.myriograph_action == "login":
        if args.import_config:
            config = read_config(args.import_config, allow_unprotected_import=True)
            # This denies research/operator credentials before adopting them.
            billing = Myriograph(config).call("/v1/video/billing")
            if billing.get("mode") not in ("live", "test", "sandbox") or not billing.get("accountId"):
                raise MyriographError("customer_account_binding_required")
            _save_private(path, config)
            return _print({"loggedIn": True, "mode": billing["mode"], "config": str(path)})
        if args.browser:
            webbrowser.open(PUBLIC_ORIGIN + "/billing")
        return _print({"loggedIn": path.is_file(), "signupUrl": PUBLIC_ORIGIN + "/billing", "keyFlow": "Sign in on Myriograph, create a customer key, save its JSON privately, then login --import-config FILE."})
    api = Myriograph(read_config(path))
    if args.myriograph_action in ("account", "billing"):
        return _print({"billing": api.call("/v1/video/billing"), "billingUrl": api.origin + "/billing"})
    capabilities = {}
    for service in SERVICE_PATHS:
        try:
            capabilities[service] = {"available": True, "native": api.capabilities(service)}
        except MyriographError as error:
            capabilities[service] = {"available": False, "code": error.code, "status": error.status}
    return _print({"loggedIn": True, "apiUrl": api.origin, "services": capabilities})


def _analyze_command(args: argparse.Namespace) -> int:
    options = json.loads(args.options.read_text(encoding="utf-8")) if args.options else {}
    if not isinstance(options, dict):
        raise ValueError("options must be a JSON object.")
    return _print(submit(Myriograph(read_config(args.config)), args.project, args.service, args.media, options, args.max_retail_usd, args.operation,
                         funding_allowance_id=args.funding_allowance_id))


def _jobs_command(args: argparse.Namespace) -> int:
    if args.job_action == "list":
        with _database(args.project) as db:
            return _print({"jobs": [_receipt(dict(row), args.project) for row in db.execute("SELECT * FROM jobs ORDER BY updated")]})
    api = Myriograph(read_config(args.config))
    if args.job_action == "download":
        if args.max_download_bytes <= 0:
            raise ValueError("max-download-bytes must be positive.")
        return _print(download(api, args.project, args.operation, args.destination, args.max_download_bytes))
    if args.job_action != "watch":
        result = observe(api, args.project, args.operation, args.job_action)
        # Status receipts omit native payloads that can contain private source refs.
        return _print({k: v for k, v in result.items() if k != "native"})
    if not math.isfinite(args.wait_seconds) or not 0 <= args.wait_seconds <= 3600:
        raise ValueError("wait-seconds must be between 0 and 3600.")
    deadline = time.monotonic() + args.wait_seconds
    while True:
        result = observe(api, args.project, args.operation)
        if result["state"] in TERMINAL or time.monotonic() >= deadline:
            return _print({**{k: v for k, v in result.items() if k != "native"}, "observerTimedOut": result["state"] not in TERMINAL})
        time.sleep(min(2, max(0, deadline - time.monotonic())))
