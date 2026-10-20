import json
import threading
import urllib.error
import urllib.request

import pytest

from vibeedit.review import ReviewServer, waveform
from test_project import project, correction


@pytest.fixture
def server(project):
    source_id = project.read()["sources"][0]["id"]
    server = ReviewServer(project, "beats", source_id)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def request(server, path, body=None, authorized=True, origin=None, **headers):
    if authorized:
        headers["Authorization"] = "Bearer " + server.token
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Origin"] = origin or server.origin
    req = urllib.request.Request(server.origin + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers


def test_capability_origin_and_project_isolation(server):
    assert request(server, "/api/state", authorized=False)[0] == 401
    assert request(server, "/api/corrections", correction(server.project), origin="https://attacker.invalid")[0] == 403
    assert request(server, "/api/corrections", correction(server.project), authorized=False)[0] == 401
    assert request(server, "/api/state", Host="evil.invalid")[0] == 403
    assert request(server, "/media/unknown")[0] == 400
    assert request(server, "/%2e%2e/project.vibeedit.json")[0] == 404
    assert request(server, "/api/corrections", correction(server.project))[0] == 200
    assert request(server, "/api/corrections", correction(server.project, operationId="stale", expectedRevision=1))[0] == 409
    state = json.loads(request(server, "/api/state")[1])
    assert state["beats"][0]["timeSec"] == 0.1


def test_media_ranges_and_waveform(server):
    source = server.project.source(server.source_id)
    status, body, headers = request(server, "/media/" + source["id"], Range="bytes=10-19")
    assert status == 206 and len(body) == 10
    assert headers["Content-Range"].startswith("bytes 10-19/")
    assert request(server, "/media/" + source["id"], Range="bytes=999999999-")[0] == 416
    assert request(server, "/media/" + source["id"], Range="bytes=-8")[1] == (server.project.root / source["path"]).read_bytes()[-8:]
    result = waveform(server.project, server.source_id)
    assert result["sourceSha256"] == source["sha256"] and len(result["bands"]["volume"]) > 100


def test_session_cookie_does_not_expose_token_to_page(server):
    status, _, headers = request(server, "/api/session", {})
    assert status == 200
    assert "HttpOnly" in headers["Set-Cookie"] and "SameSite=Strict" in headers["Set-Cookie"]
    assert server.token.encode() not in request(server, "/")[1]
