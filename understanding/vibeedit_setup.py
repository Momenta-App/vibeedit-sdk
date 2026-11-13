#!/usr/bin/env python3
"""VibeEdit agent setup: email verification, scoped keys and private local config.

Python 3.11+, standard library only. No browser session or administrator key.
Run --help, or read https://vibeedit.com/agents.md before authenticating.
"""
import argparse
import contextlib
import getpass
import json
import os
import pathlib
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ORIGIN = "https://vibeedit.com"
AUTH_ORIGIN = "https://cnvibkgxcaaohnxbsxoi.supabase.co"
VERSION = "vibeedit.agentSetup.v1"
SERVICES = {"visual": "video", "faces": "faces", "speakers": "voices",
            "active-speakers": "active-speakers", "voice-identity": "voice-identity", "characters": "characters"}


class SetupError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, origin=ORIGIN, auth_origin=AUTH_ORIGIN):
        self.origin = origin
        self.auth_origin = auth_origin
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, path, *, body=None, headers=None, method=None, provider=False):
        origin = self.auth_origin if provider else self.origin
        request = urllib.request.Request(origin + path, method=method,
            headers={"Accept": "application/json", **({"Content-Type": "application/json"} if body is not None else {}), **(headers or {})},
            data=json.dumps(body).encode() if body is not None else None)
        try:
            with self.opener.open(request, timeout=45) as response:
                raw = response.read(1_048_577)
        except urllib.error.HTTPError as error:
            try:
                value = json.loads(error.read(65536))
                code = value.get("error_code") or (value.get("error", {}).get("code") if isinstance(value.get("error"), dict) else value.get("error"))
            except (ValueError, AttributeError):
                code = None
            code = code if isinstance(code, str) and re.fullmatch(r"[a-z0-9_]{1,80}", code) else "request_failed"
            hint = " Wait before requesting another email code." if error.code == 429 else " Keep your state and retry the original operation."
            raise SetupError(f"Request failed ({error.code}, {code})." + hint) from None
        except (OSError, TimeoutError):
            raise SetupError("Connection interrupted. Keep your private state; retry the original operation without changing its inputs.") from None
        if len(raw) > 1_048_576:
            raise SetupError("Response is too large. Keep your original state.")
        try:
            value = json.loads(raw)
        except ValueError:
            raise SetupError("Response is not JSON. Keep your original state and request identity.") from None
        if not isinstance(value, dict):
            raise SetupError("Unexpected response. Keep your original state.")
        return value

    def auth_headers(self):
        discovery = self.request("/v1/video/auth")
        if discovery.get("supabaseUrl") != self.auth_origin or not isinstance(discovery.get("publishableKey"), str):
            raise SetupError("Account authority changed. Review current VibeEdit setup instructions before signing in.")
        return {"apikey": discovery["publishableKey"]}


def read_private(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor) as file:
            info = os.fstat(file.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 1_048_576:
                raise SetupError("Private state/config must be a small regular file.")
            if os.name == "posix" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
                raise SetupError("Private state/config must be owned by you with permissions 600. Correct its permissions before continuing.")
            value = json.load(file)
    except (OSError, ValueError):
        raise SetupError("Cannot read private state/config. Check its path and permissions; do not paste its contents.") from None
    if not isinstance(value, dict):
        raise SetupError("Private state/config must contain a JSON object.")
    return value


def save_private(path, value, *, replace=False):
    path = pathlib.Path(path).expanduser().absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise SetupError("Refusing to replace a symlink with private credentials.")
    if not replace and path.exists():
        if read_private(path) == value:
            return
        raise SetupError("Config already exists. Choose a new path; existing credentials were preserved.")
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600), "w") as file:
            json.dump(value, file, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        if replace:
            os.replace(temporary, path)
            return
        os.link(temporary, path)
    except OSError:
        raise SetupError("Private file could not be saved. Keep your setup state and retry the same operation; do not create a replacement key.") from None
    finally:
        temporary.unlink(missing_ok=True)


def load_state(path):
    state = read_private(path)
    if state.get("schemaVersion") != VERSION or state.get("apiUrl") != ORIGIN:
        raise SetupError("This is not a VibeEdit setup state. Existing SDK configs and job state must remain separate.")
    return state


@contextlib.contextmanager
def lock_state(path):
    # Stable flock file avoids stale locks after a crash and double admission
    # when two agent processes use the same setup state.
    import fcntl
    path = pathlib.Path(path).expanduser().absolute()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with os.fdopen(os.open(str(path) + ".lock", os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600), "w") as file:
        try:
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SetupError("Another setup command is using this state. Wait for it to finish; keep the same state path.") from None
        yield


def session_headers(client, state):
    if not state.get("accessToken") or state.get("expiresAt", 0) <= time.time() + 10:
        raise SetupError("Sign in again with request-code and verify-code using the same state/email. Keep any pending key identity unchanged.")
    headers = {"Authorization": "Bearer " + state["accessToken"]}
    user = client.request("/auth/v1/user", headers={**client.auth_headers(), **headers}, provider=True)
    if not user.get("email_confirmed_at") or user.get("email", "").lower() != state["email"]:
        raise SetupError("The verified user does not match this setup. No key was created.")
    return headers


def account_rows(client, state):
    rows = client.request("/v1/video/accounts", headers=session_headers(client, state)).get("accounts")
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("accountId", row.get("id")), str) for row in rows):
        raise SetupError("Account response was incomplete. Keep your verified state and retry accounts; do not create a new account.")
    if not rows:
        raise SetupError("No owned/administered account is available. Use VibeEdit account support; do not create parallel accounts.")
    return [{"id": row.get("accountId", row.get("id")), "name": row.get("name", "VibeEdit account")} for row in rows]


def config_headers(config):
    if config.get("apiUrl") != ORIGIN or not re.fullmatch(r"mv_[A-Za-z0-9_-]{30,150}", config.get("apiKey", "")):
        raise SetupError("Expected a canonical VibeEdit scoped config. Preserve old SDK job configs at their original origin for resume.")
    return {"Authorization": "Bearer " + config["apiKey"], "X-Project-Id": config["projectId"], "X-Organization-Id": config["organizationId"]}


def run(args, client):
    if args.command == "discover":
        return client.request("/.well-known/vibeedit.json")
    if args.command in {"check", "revoke"}:
        config = read_private(args.config)
        headers = config_headers(config)
        if args.command == "revoke":
            value = client.request("/v1/video/keys/current", method="DELETE", headers=headers)
            if value.get("revoked") is not True:
                raise SetupError("Revocation was not acknowledged. Retain this config and retry revocation.")
            return {"status": "revoked", "configPath": str(pathlib.Path(args.config).expanduser().absolute())}
        checks = []
        for service in args.service or SERVICES:
            client.request("/v1/" + SERVICES[service] + "/capabilities", headers=headers)
            checks.append({"service": service, "status": "authorized"})
        return {"status": "connected", "apiUrl": ORIGIN, "projectId": config["projectId"], "checks": checks, "paidWorkStarted": False}
    state_path = pathlib.Path(args.state).expanduser().absolute()
    if args.command == "request-code":
        email = args.email.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise SetupError("Enter the user's authorized email address.")
        previous = load_state(state_path) if state_path.exists() else {}
        if previous.get("pendingKey") and previous.get("email") != email:
            raise SetupError("An unresolved key belongs to the original email. Reconcile it before changing users.")
        if previous.get("requestedAt", 0) + 60 > time.time():
            raise SetupError("Wait at least 60 seconds before another code request. A lost acknowledgement does not mean no email was sent.")
        state = {"schemaVersion": VERSION, "apiUrl": ORIGIN, "email": email, "requestedAt": time.time(),
                 "phase": "code-requested", **({"pendingKey": previous["pendingKey"]} if previous.get("pendingKey") else {})}
        save_private(state_path, state, replace=True)
        client.request("/auth/v1/otp?redirect_to=" + urllib.parse.quote(ORIGIN + "/auth/callback", safe=""),
            body={"email": email, "create_user": args.signup}, headers=client.auth_headers(), provider=True)
        return {"status": "code_requested", "statePath": str(state_path), "next": "verify-code", "humanStep": "User authorizes email access or supplies the one-time code; never infer it."}
    state = load_state(state_path)
    if args.command == "verify-code":
        if state.get("accessToken") and state.get("expiresAt", 0) > time.time() + 10:
            return {"status": "verified", "accounts": account_rows(client, state)}
        code = sys.stdin.readline().strip() if args.code_stdin else getpass.getpass("VibeEdit email code: ")
        if not re.fullmatch(r"[0-9]{6,10}", code):
            raise SetupError("Supply the email code through the prompt or --code-stdin; never put it in command-line arguments.")
        session = client.request("/auth/v1/verify", body={"email": state["email"], "token": code, "type": "email"}, headers=client.auth_headers(), provider=True)
        if not isinstance(session.get("access_token"), str) or not isinstance(session.get("expires_in"), (int, float)):
            raise SetupError("Authentication response was incomplete. Keep your state and sign in again.")
        state.update(accessToken=session["access_token"], expiresAt=time.time() + session["expires_in"], phase="authenticated")
        save_private(state_path, state, replace=True)
        return {"status": "verified", "accounts": account_rows(client, state), "next": "create-key"}
    if "read" not in args.access:
        raise SetupError("Include read access so the issued key can verify its project/account. No key was created.")
    if state.get("phase") == "configured":
        prior = read_private(state["configPath"])
        expected = {"accountId": args.account or prior["organizationId"], "projectIds": [args.project], "customerServices": sorted(set(args.services)),
                    "customerAccess": sorted(set(args.access)), "customerBillingAccess": args.billing_access}
        if state["configPath"] != str(pathlib.Path(args.config).expanduser().absolute()) or state.get("scopes") != expected:
            raise SetupError("This setup already saved its config. Use that config; begin a separately authorized new setup with a new state path for different access.")
        client.request("/v1/customer/context?" + urllib.parse.urlencode({"service": expected["customerServices"][0], "projectId": args.project, "access": "read"}), headers=config_headers(prior))
        return {"status": "configured", "configPath": state["configPath"], "reusedAcknowledgement": True, "loginSessionCleared": True, "paidWorkStarted": False}
    accounts = account_rows(client, state)
    account = args.account or (accounts[0]["id"] if len(accounts) == 1 else None)
    if account not in {row["id"] for row in accounts}:
        raise SetupError("Select an owned account with --account from the accounts command. No key was created.")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", args.project):
        raise SetupError("Project ID must use 1–128 letters, numbers, dots, colons, underscores or hyphens, starting with a letter or number.")
    output = pathlib.Path(args.config).expanduser().absolute()
    if output == state_path:
        raise SetupError("Config and temporary login state need separate file paths.")
    body = {"accountId": account, "projectIds": [args.project], "customerServices": sorted(set(args.services)),
            "customerAccess": sorted(set(args.access)), "customerBillingAccess": args.billing_access}
    pending = state.get("pendingKey")
    if pending and (pending["body"] != body or pending["configPath"] != str(output)):
        raise SetupError("An earlier key request is unresolved. Restore its exact account/project/scopes/config path and retry; do not replace its identity.")
    if not pending:
        if output.exists() or output.is_symlink():
            raise SetupError("Config path already exists. Choose a new path before creating a key.")
        pending = {"requestId": str(uuid.uuid4()), "body": body, "configPath": str(output)}
        state["pendingKey"] = pending
        save_private(state_path, state, replace=True)
    value = client.request("/v1/video/keys", body=pending["body"], headers={**session_headers(client, state), "Idempotency-Key": pending["requestId"]})
    if value.get("organizationId") != account or not isinstance(value.get("apiKey"), str):
        raise SetupError("Key acknowledgement did not match the selected account. Keep your state and reconcile the original request.")
    config = {"apiUrl": ORIGIN, "apiKey": value["apiKey"], "organizationId": account, "projectId": args.project}
    identity = client.request("/v1/customer/context?" + urllib.parse.urlencode({"service": body["customerServices"][0], "projectId": args.project, "access": "read"}), headers=config_headers(config))
    if identity.get("organizationId") != account or identity.get("projectId") != args.project:
        raise SetupError("The issued key did not verify its account/project. Keep your original state for reconciliation.")
    save_private(output, config)
    save_private(state_path, {"schemaVersion": VERSION, "apiUrl": ORIGIN, "phase": "configured", "configPath": str(output), "requestId": pending["requestId"], "scopes": body}, replace=True)
    return {"status": "configured", "configPath": str(output), "accountId": account, "projectId": args.project,
            "mode": identity.get("mode"), "scopes": body, "loginSessionCleared": True, "paidWorkStarted": False}


def main(argv=None, client=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("discover", help="Read the public setup manifest; no sign-in.")
    request = commands.add_parser("request-code", help="Send a code only to a user-authorized email address.")
    request.add_argument("--email", required=True)
    request.add_argument("--signup", action="store_true", help="Allow account creation only when the user requested signup.")
    verify = commands.add_parser("verify-code", help="Verify a real email code without putting it in shell history.")
    verify.add_argument("--code-stdin", action="store_true")
    commands.add_parser("accounts", help="List the user's existing owned/administered accounts.")
    create = commands.add_parser("create-key", help="Issue a scoped key and atomically write a private SDK config.")
    create.add_argument("--project", required=True)
    create.add_argument("--account")
    create.add_argument("--config", required=True)
    create.add_argument("--services", nargs="+", choices=["video", "faces", "speakers"], default=["video", "faces", "speakers"])
    create.add_argument("--access", nargs="+", choices=["read", "download", "upload", "submit", "cancel", "library"], default=["read", "download"])
    create.add_argument("--billing-access", action="store_true", help="Grant credit management only with explicit user authorization; no purchase is made.")
    for command in [request, verify, commands.choices["accounts"], create]:
        command.add_argument("--state", required=True, help="Private local setup state; transient login token is removed after config save.")
    check = commands.add_parser("check", help="Read capabilities; no uploads, analysis or payment.")
    check.add_argument("--config", required=True)
    check.add_argument("--service", choices=SERVICES, action="append")
    revoke = commands.add_parser("revoke", help="Revoke only the key in this config.")
    revoke.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    try:
        selected = client or Client()
        if os.name != "posix":
            raise SetupError("This setup CLI requires macOS or Linux for private file permissions and process locking. The documented HTTP API is platform-independent.")
        with lock_state(args.state) if hasattr(args, "state") else contextlib.nullcontext():
            result = {"accounts": account_rows(selected, load_state(args.state))} if args.command == "accounts" else run(args, selected)
        print(json.dumps(result, indent=2))
        return 0
    except (SetupError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, SetupError) else "Setup state/response is incomplete. Preserve it and review current instructions."
        print(json.dumps({"status": "needs_attention", "message": message}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
