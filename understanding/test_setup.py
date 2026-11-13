"""Exercise the shipped setup client against a real local HTTP server."""
import fcntl
import http.server
import json
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.parse

SOURCE = pathlib.Path(__file__).resolve().parent / "vibeedit_setup.py"
ACCOUNT = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
TOKEN = "mv_" + "fixture_only_" * 5


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.state = self.root / "setup.json"
        self.config = self.root / "vibeedit.json"
        self.calls = []
        self.keys = {}
        self.accounts = [{"id": ACCOUNT, "name": "Existing account"}]
        self.uncertain = False
        self.redirect = False
        self.foreign_auth = False
        self.revoked = False
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, value, status=200):
                raw = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self):
                outer.calls.append(("GET", self.path, dict(self.headers), None))
                if self.path == "/v1/video/auth":
                    return self.respond({"supabaseUrl": "https://example.invalid" if outer.foreign_auth else outer.origin, "publishableKey": "public_fixture"})
                if self.path == "/auth/v1/user":
                    return self.respond({"email": "operator@example.invalid", "email_confirmed_at": "2026-11-12T00:00:00Z"})
                if self.path == "/v1/video/accounts":
                    return self.respond({"accounts": outer.accounts})
                if self.path.startswith("/v1/customer/context?"):
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                    return self.respond({"organizationId": self.headers.get("X-Organization-Id"), "projectId": query["projectId"][0], "mode": "test"})
                if self.path.endswith("/capabilities"):
                    if outer.redirect:
                        self.send_response(302)
                        self.send_header("Location", outer.origin + "/credential-capture")
                        self.end_headers()
                        return
                    return self.respond({"schemaVersion": "fixture"}, 401 if outer.revoked else 200)
                return self.respond({"error": {"code": "not_found"}}, 404)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.calls.append(("POST", self.path, dict(self.headers), body))
                if self.path.startswith("/auth/v1/otp?"):
                    return self.respond({})
                if self.path == "/auth/v1/verify":
                    if body.get("token") != "123456":
                        return self.respond({"error_code": "otp_expired"}, 403)
                    return self.respond({"access_token": "fixture_session", "expires_in": 3600, "refresh_token": "must_never_be_saved"})
                if self.path == "/v1/video/keys":
                    identity = self.headers["Idempotency-Key"]
                    if identity in outer.keys and outer.keys[identity] != body:
                        return self.respond({"error": {"code": "idempotency_conflict"}}, 409)
                    outer.keys[identity] = body
                    if outer.uncertain:
                        outer.uncertain = False
                        return self.respond({"error": {"code": "acknowledgement_lost"}}, 503)
                    return self.respond({"apiKey": TOKEN, "organizationId": body["accountId"], "mode": "test"}, 201)
                return self.respond({}, 404)

            def do_DELETE(self):
                outer.calls.append(("DELETE", self.path, dict(self.headers), None))
                outer.revoked = True
                self.respond({"revoked": True})

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.origin = "http://127.0.0.1:" + str(self.server.server_port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def cli(self, *args, code=None, expected=0):
        script = "import importlib.util,sys; s=importlib.util.spec_from_file_location('setup',sys.argv[2]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); sys.exit(m.main(sys.argv[3:],m.Client(sys.argv[1],sys.argv[1])))"
        result = subprocess.run([sys.executable, "-c", script, self.origin, str(SOURCE), *map(str, args)], input=code, text=True, capture_output=True)
        self.assertEqual(result.returncode, expected, result.stderr)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)
        self.assertNotIn("fixture_session", result.stdout + result.stderr)
        self.assertNotIn("must_never_be_saved", result.stdout + result.stderr)
        return json.loads(result.stdout if expected == 0 else result.stderr)

    def login(self):
        self.cli("request-code", "--email", "operator@example.invalid", "--state", self.state)
        self.cli("verify-code", "--code-stdin", "--state", self.state, code="123456\n")

    def create(self, *extra, expected=0):
        return self.cli("create-key", "--state", self.state, "--project", "test-project", "--config", self.config, *extra, expected=expected)

    def test_email_key_private_config_capabilities_repeated_ack_and_revoke(self):
        self.login()
        self.assertNotIn("refresh", self.state.read_text())
        result = self.create()
        self.assertTrue(result["loginSessionCleared"])
        config = json.loads(self.config.read_text())
        self.assertEqual(config["apiKey"], TOKEN)
        self.assertEqual(config["apiUrl"], "https://vibeedit.com")
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("accessToken", self.state.read_text())
        self.assertNotIn(TOKEN, self.state.read_text())
        self.assertEqual(len(self.cli("check", "--config", self.config)["checks"]), 6)
        self.assertTrue(self.create()["reusedAcknowledgement"])
        self.assertEqual(len(self.keys), 1)
        self.assertFalse(next(iter(self.keys.values()))["customerBillingAccess"])
        self.assertEqual(next(iter(self.keys.values()))["customerAccess"], ["download", "read"])
        self.cli("revoke", "--config", self.config)
        self.cli("check", "--config", self.config, expected=1)

    def test_uncertain_admission_retains_identity_and_refuses_changed_scope(self):
        self.login()
        self.uncertain = True
        self.create(expected=1)
        intent = json.loads(self.state.read_text())["pendingKey"]
        self.assertFalse(self.config.exists())
        self.create("--billing-access", expected=1)
        self.assertEqual(len(self.keys), 1)
        self.create()
        admissions = [c for c in self.calls if c[0:2] == ("POST", "/v1/video/keys")]
        self.assertEqual(len(admissions), 2)
        self.assertEqual({c[2]["Idempotency-Key"] for c in admissions}, {intent["requestId"]})
        self.assertEqual(admissions[0][3], admissions[1][3])

    def test_multiple_accounts_require_explicit_selection(self):
        self.accounts.append({"id": SECOND, "name": "Second existing account"})
        self.login()
        self.create(expected=1)
        self.assertFalse(self.keys)
        self.assertEqual(self.create("--account", SECOND)["accountId"], SECOND)

    def test_existing_config_is_preserved_before_admission(self):
        self.login()
        self.config.write_text("existing private data")
        self.config.chmod(0o600)
        self.create(expected=1)
        self.assertFalse(self.keys)
        self.assertEqual(self.config.read_text(), "existing private data")

    def test_public_permissions_and_foreign_auth_are_refused(self):
        self.login()
        self.state.chmod(0o644)
        self.create(expected=1)
        self.assertFalse(self.keys)
        self.state.unlink()
        self.foreign_auth = True
        before = len([c for c in self.calls if c[1].startswith("/auth/v1/otp?")])
        self.cli("request-code", "--email", "operator@example.invalid", "--state", self.state, expected=1)
        self.assertEqual(len([c for c in self.calls if c[1].startswith("/auth/v1/otp?")]), before)

    def test_credentials_never_follow_http_redirect(self):
        self.login()
        self.create()
        self.redirect = True
        self.cli("check", "--config", self.config, "--service", "visual", expected=1)
        self.assertFalse(any(c[1] == "/credential-capture" for c in self.calls))

    def test_same_state_is_locked_before_email_transmission(self):
        with open(str(self.state) + ".lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.cli("request-code", "--email", "operator@example.invalid", "--state", self.state, expected=1)
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
