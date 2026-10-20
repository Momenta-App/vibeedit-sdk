from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean-install and exercise exact VibeEdit release archives")
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--npm", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-revision", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--checksums", type=Path)
    parser.add_argument("--canonical-artifact-id")
    parser.add_argument("--canonical-artifact-digest")
    parser.add_argument("--expected-python", help="Required launcher major.minor, selected by the platform matrix")
    args = parser.parse_args(argv)
    for path in (args.wheel, args.npm):
        if not path.is_file():
            parser.error(f"archive is missing: {path}")
    uv = shutil.which("uv")
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not uv or not npm or not node:
        parser.error("uv, npm, and node are required")

    result = {
        "schemaVersion": "1.0.0",
        "status": "failed",
        "sourceRevision": args.source_revision,
        "launcher": interpreter_record(),
        "archives": {
            "wheel": archive_record(args.wheel),
            "npm": archive_record(args.npm),
        },
    }
    try:
        if args.expected_python and args.expected_python != ".".join(map(str, sys.version_info[:2])):
            raise ValueError("smoke launcher differs from the selected matrix Python")
        if args.manifest:
            result["releaseVerification"] = verify_release_inputs(args)
        elif any((args.manifest_sha256, args.checksums, args.canonical_artifact_id, args.canonical_artifact_digest)):
            raise ValueError("canonical artifact verification requires --manifest and its exact build identity")
        with tempfile.TemporaryDirectory(prefix="vibeedit-release-smoke-") as temporary:
            root = Path(temporary)
            python, result["installedInterpreter"] = prepare_python(uv, args.wheel.resolve(), root)
            result["python"] = smoke_python(python, root)
            result["node"] = smoke_node(npm, node, args.npm.resolve(), root)
        result["status"] = "passed"
    except Exception as error:
        result["failure"] = {"type": type(error).__name__, "message": str(error)}
        write_result(result, args.output)
        raise
    write_result(result, args.output)
    return 0


INTERPRETER_PROBE = """import json,platform,struct,sys;print(json.dumps({'executable':sys.executable,'version':sys.version,'versionInfo':list(sys.version_info[:3]),'implementation':platform.python_implementation(),'system':platform.system(),'machine':platform.machine(),'bits':struct.calcsize('P')*8,'platform':platform.platform()}))"""


def interpreter_record() -> dict[str, object]:
    return run_json([sys.executable, "-c", INTERPRETER_PROBE])


def write_result(result: dict[str, object], output: Path | None) -> None:
    value = json.dumps(result, indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(value, encoding="utf-8")
    print(value, end="")


def verify_release_inputs(args: argparse.Namespace) -> dict[str, object]:
    """Fail before installation unless the canonical build's complete identity agrees."""
    if not args.manifest_sha256 or not re.fullmatch(r"[a-f0-9]{64}", args.manifest_sha256):
        raise ValueError("pin --manifest-sha256 from the canonical build job")
    if not args.source_revision or not re.fullmatch(r"[a-f0-9]{40}", args.source_revision):
        raise ValueError("pin the complete expected source revision")
    if not args.canonical_artifact_id or not re.fullmatch(r"[0-9]+", args.canonical_artifact_id):
        raise ValueError("pin the immutable canonical workflow artifact ID")
    if not args.canonical_artifact_digest or not re.fullmatch(r"[a-f0-9]{64}", args.canonical_artifact_digest):
        raise ValueError("pin the canonical workflow artifact digest")
    if not args.checksums:
        raise ValueError("canonical verification requires --checksums")
    manifest = archive_record(args.manifest)
    if manifest["sha256"] != args.manifest_sha256:
        raise ValueError("release manifest differs from the canonical build SHA-256")
    value = json.loads(args.manifest.read_text(encoding="utf-8"))
    if value.get("schemaVersion") != "vibeedit.release.v1" or value.get("source") != {"repository": "https://github.com/Momenta-App/vibeedit-sdk", "revision": args.source_revision}:
        raise ValueError("release manifest schema/source revision is not the expected canonical build")
    versions = value.get("versions", {})
    if value.get("id") != "v" + versions.get("npm", ""):
        raise ValueError("release tag differs from its npm package version")
    directory = args.manifest.parent.resolve()
    files = {
        "pythonWheel": args.wheel,
        "pythonSource": directory / "python" / ("vibeedit-" + versions.get("python", "") + ".tar.gz"),
        "npm": args.npm,
        "coreRequirements": directory / "requirements-core.lock",
        "setupScript": directory / "setup.py",
    }
    if args.wheel.name != "vibeedit-" + versions.get("python", "") + "-py3-none-any.whl" or args.npm.name != "vibeedit-" + versions.get("npm", "") + ".tgz":
        raise ValueError("archive filenames differ from the manifest package versions")
    if set(value.get("artifacts", {})) != set(files):
        raise ValueError("release manifest must declare exactly the five bootstrap/package artifacts")
    verified = {}
    for name, path in files.items():
        if path.is_symlink() or directory not in path.resolve().parents:
            raise ValueError("canonical artifact must be a regular local file inside the downloaded build")
        record = archive_record(path)
        expected = value["artifacts"][name]
        if expected != {"url": "https://github.com/Momenta-App/vibeedit-sdk/releases/download/" + value["id"] + "/" + path.name, "sha256": record["sha256"], "byteLength": record["bytes"]}:
            raise ValueError(f"canonical {name} bytes, length, or release URL differ from the manifest")
        verified[name] = record
    flat = {verified[name]["name"]: verified[name]["sha256"] for name in ("pythonWheel", "pythonSource", "npm")}
    tree = {("npm/" if name == "npm" else "python/") + verified[name]["name"]: verified[name]["sha256"] for name in ("pythonWheel", "pythonSource", "npm")}
    if read_checksums(args.checksums) != flat or read_checksums(directory / "SHA256SUMS.tree") != tree:
        raise ValueError("checksum manifests must exactly match all three canonical archives")
    return {
        "status": "passed-before-install",
        "manifest": manifest,
        "checksums": archive_record(args.checksums),
        "treeChecksums": archive_record(directory / "SHA256SUMS.tree"),
        "artifacts": verified,
        "workflowArtifact": {"id": args.canonical_artifact_id, "sha256": args.canonical_artifact_digest, "runId": os.environ.get("GITHUB_RUN_ID"), "runAttempt": os.environ.get("GITHUB_RUN_ATTEMPT")},
        "transportDigestContract": "The pinned official workflow download step enforces digest-mismatch:error separately. This value identifies the upload ZIP; this helper verifies the extracted manifest and package files.",
    }


def read_checksums(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([a-f0-9]{64})  ([A-Za-z0-9_./-]+)", line)
        if not match or match[2] in values or any(part in {"", ".", ".."} for part in match[2].split("/")):
            raise ValueError("invalid or duplicate release checksum entry")
        values[match[2]] = match[1]
    if not values:
        raise ValueError("release checksum manifest is empty")
    return values


def prepare_python(uv: str, wheel: Path, root: Path) -> tuple[Path, dict[str, object]]:
    environment = root / "python"
    run([uv, "venv", "--python", sys.executable, str(environment)])
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    interpreter = run_json([str(python), "-c", INTERPRETER_PROBE])
    launcher = interpreter_record()
    for field in ("versionInfo", "implementation", "system", "machine", "bits"):
        if interpreter[field] != launcher[field]:
            raise RuntimeError(f"isolated wheel interpreter changed selected {field}")
    run([uv, "pip", "install", "--python", str(python), f"{wheel}[browser]"])
    return python, interpreter


def smoke_python(python: Path, root: Path) -> dict[str, object]:
    if sys.platform.startswith("linux"):
        run([str(python), "-m", "playwright", "install-deps", "chromium"])
    setup = run_json([str(python), "-m", "vibeedit.cli", "setup", "--browser", "--json"])
    doctor = run_json([str(python), "-m", "vibeedit.cli", "doctor", "--json"])
    if not setup.get("complete") or not doctor.get("ready"):
        raise RuntimeError("clean wheel setup or doctor did not report ready")

    examples = root / "examples"
    basic = Path(run_json([str(python), "-m", "vibeedit.cli", "examples", "create", "basic-generated", str(examples), "--json"])["path"])
    basic_output = root / "basic.mp4"
    run_json([str(python), "-m", "vibeedit.cli", "render", str(basic / "composition.json"), "--output", str(basic_output), "--json"])
    basic_report = run_json([str(python), "-m", "vibeedit.cli", "verify", str(basic_output), "--spec", str(basic / "composition.json"), "--json"])

    mixed = Path(run_json([str(python), "-m", "vibeedit.cli", "examples", "create", "mixed-python-html", str(examples), "--json"])["path"])
    run([str(python), str(mixed / "render.py")], cwd=mixed)
    mixed_report = run_json([str(python), "-m", "vibeedit.cli", "verify", str(mixed / "mixed-python-html.mp4"), "--spec", str(mixed / "composition.json"), "--json"])
    if not basic_report.get("passed") or not mixed_report.get("passed"):
        raise RuntimeError("clean wheel render verification failed")

    browser_project = Path(run_json([str(python), "-m", "vibeedit.cli", "examples", "create", "browser-composition", str(examples), "--json"])["path"])
    browser_report = run_json([str(python), "-m", "vibeedit.cli", "render-browser", str(browser_project / "job.json"), "--output", str(root / "browser.mp4"), "--backend", "screenshot", "--json"])
    if browser_report.get("frames") != 12 or browser_report.get("backend") != "screenshot":
        raise RuntimeError("clean wheel ordinary browser composition failed")
    run([str(python), "-c", "from vibeedit.data import data_path; from vibeedit.browser_setup import native_paths; assert data_path('browser-renderer/host/host.mm').is_file(); assert data_path('browser-renderer/surface-bridge/src/lib.rs').is_file(); import vibeedit.browser_render; print(native_paths())"])

    requests = "\n".join(
        json.dumps(value)
        for value in (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_catalog", "arguments": {"query": "procedural"}}},
        )
    ) + "\n"
    mcp = run([str(python), "-m", "vibeedit.cli", "mcp"], input_value=requests).stdout.splitlines()
    responses = [json.loads(line) for line in mcp]
    tools = responses[1]["result"]["tools"]
    if "agent_command" not in {tool["name"] for tool in tools} or not responses[2]["result"]["structuredContent"]:
        raise RuntimeError("clean wheel MCP smoke failed")

    catalog = run_json([str(python), "-m", "vibeedit.cli", "catalog", "open", "--no-browser", "--json"])
    skills_root = root / "skills"
    skills_root.mkdir()
    installed = run_json(
        [str(python), "-m", "vibeedit.cli", "skills", "install", "vibeedit-effects", "--harness", "codex", "--scope", "project", "--json"],
        cwd=skills_root,
    )
    checked = run_json(
        [str(python), "-m", "vibeedit.cli", "skills", "check", "vibeedit-effects", "--harness", "codex", "--scope", "project", "--json"],
        cwd=skills_root,
    )
    if catalog.get("opened") or installed.get("action") != "installed" or not checked.get("installed") or checked.get("modified"):
        raise RuntimeError("clean wheel catalog or skill lifecycle smoke failed")
    project_proof = smoke_project_review(python, root)
    caption_proofs = []
    for name in ("dialogue-quote", "talking-head-captions"):
        directory = Path(run_json([str(python), "-m", "vibeedit.cli", "examples", "create", name, str(examples), "--json"])["path"])
        run([str(python), str(directory / "render.py")], cwd=directory)
        report = run_json([str(python), "-m", "vibeedit.cli", "verify", str(directory / (name + ".mp4")), "--spec", str(directory / "composition.json"), "--json"])
        if not report.get("passed"):
            raise RuntimeError("clean caption/quote template omitted expected picture or original audio")
        caption_proofs.append(render_record(name, report))

    return {
        "browserComposition": browser_report,
        "version": run([str(python), "-m", "vibeedit.cli", "--version"]).stdout.strip(),
        "doctorReady": True,
        "browserSetupComplete": True,
        "catalogResolved": True,
        "skillInstalledUnmodified": True,
        "mcpTools": len(tools),
        "mcpCatalogCallPassed": True,
        "projectReviewAndTransfer": project_proof,
        "captionTemplates": caption_proofs,
        "renders": [render_record("basic-generated", basic_report), render_record("mixed-python-html", mixed_report)],
    }


def smoke_project_review(python: Path, root: Path) -> dict[str, object]:
    """Exercise the installed wheel's saved state and real render, not source imports."""
    code = r'''
import json, pathlib, subprocess, sys, threading, urllib.error, urllib.request
from vibeedit.data import data_path
from vibeedit.project import Project, create_project, file_digest
from vibeedit.portable import bundle_project, restore_project
from vibeedit.render import render
from vibeedit.review import ReviewServer
from vibeedit.verify import verify_output
root=pathlib.Path(sys.argv[1]);root.mkdir()
spec=json.loads(data_path('schema','fixtures','minimal.json').read_text(encoding='utf-8'))
spec['durationFrames']=30;spec['verification'].update(durationFrames=30,hasAudio=True)
spec['timeline']['tracks']=[]
(root/'seed.json').write_text(json.dumps(spec),encoding='utf-8')
create_project(root/'project',root/'seed.json');project=Project(root/'project')
subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=0.2',str(root/'source.wav')],check=True)
project.register_source(root/'source.wav',expected_revision=0);source=project.read()['sources'][0]
spec['sources']=[{'id':source['id'],'kind':'audio','uri':source['path'],'identity':{'algorithm':'sha256','value':source['sha256']}}]
spec['timeline']['tracks']=[{'id':'audio','kind':'audio','order':0,'items':[{'id':'hit','kind':'audio','placement':{'startFrame':0,'durationFrames':4},'source':{'sourceId':source['id'],'inFrame':0,'durationFrames':4},'metadata':{'reviewBeat':{'sourceId':source['id'],'index':0}}}]}]
(project.root/'revision.json').write_text(json.dumps(spec),encoding='utf-8');project.use_composition('revision.json',expected_revision=1)
server=ReviewServer(project,'beats',source['id']);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
try:
 try:urllib.request.urlopen(server.origin+'/api/state',timeout=3);raise RuntimeError('review exposed unauthenticated state')
 except urllib.error.HTTPError as error:assert error.code==401
 command={'operationId':'archive-beat-choice','expectedRevision':2,'author':'human:artifact-fixture','sourceId':source['id'],'sourceSha256':source['sha256'],'domain':'beats','action':'set','targetId':'beatmap','payload':{'beats':[{'timeSec':0.1,'strength':1}]}}
 request=urllib.request.Request(server.origin+'/api/corrections',data=json.dumps(command).encode(),headers={'Authorization':'Bearer '+server.token,'Origin':server.origin,'Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=3) as response:assert json.load(response)['event']['revision']==3
 assert Project(project.root).correct(command)['revision']==3
finally:server.shutdown();server.server_close();thread.join()
revised=project.apply_review(source['id'],'beats',expected_revision=3);assert revised['ok']
output=render(project.root/revised['composition'],root/'reviewed.mp4');assert verify_output(output,spec['verification']).passed
raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(output),'-vn','-ac','1','-ar','8000','-f','s16le','pipe:1'])
import array
samples=array.array('h',raw)
if sys.byteorder!='little':samples.byteswap()
assert max(abs(n) for n in samples[:400])<100 and max(abs(n) for n in samples[900:1200])>500
bundle=bundle_project(project.root,root/'edit.zip');restore_project(root/'edit.zip',root/'restored',expected_sha256=bundle['sha256'])
restored=Project(root/'restored');assert restored.corrections()==project.corrections();assert file_digest(restored.root/source['path'])==source['sha256']
print(json.dumps({'savedCorrectionSurvivesRestart':True,'exactRetrySingleEvent':True,'correctionChangesAudiblePlacement':True,'loopbackCapabilityRequired':True,'portableBundleRestored':True,'sourceSha256':source['sha256'],'corrections':len(restored.corrections())}))
'''
    return run_json([str(python), "-c", code, str(root / "project-review")])


def smoke_node(npm: str, node: str, archive: Path, root: Path) -> dict[str, object]:
    directory = root / "node"
    directory.mkdir()
    run([npm, "init", "-y"], cwd=directory)
    run([npm, "install", str(archive), "--ignore-scripts"], cwd=directory)
    package = directory / "node_modules" / "vibeedit"
    run([node, str(package / "bin" / "vibeedit.js"), "validate", str(package / "schema" / "fixtures" / "minimal.json")], cwd=directory)
    run(
        [
            node,
            "--input-type=module",
            "-e",
            "import('vibeedit').then(m=>{if(new m.Composition({id:'artifact-smoke'}).id!=='artifact-smoke')process.exit(1)})",
        ],
        cwd=directory,
    )
    audit_process = run([npm, "audit", "--omit=dev", "--json"], cwd=directory, check=False)
    audit = json.loads(audit_process.stdout)
    vulnerabilities = audit.get("metadata", {}).get("vulnerabilities", {}).get("total")
    if audit_process.returncode or vulnerabilities != 0:
        raise RuntimeError("clean npm archive audit failed")
    return {
        "version": run([node, str(package / "bin" / "vibeedit.js"), "--version"], cwd=directory).stdout.strip(),
        "apiImported": True,
        "compositionConstructed": True,
        "schemaValidated": True,
        "productionVulnerabilities": vulnerabilities,
    }


def render_record(example: str, report: dict[str, object]) -> dict[str, object]:
    checks = {value["id"]: value for value in report["checks"]}
    return {
        "example": example,
        "passed": report["passed"],
        "width": checks["width"]["actual"],
        "height": checks["height"]["actual"],
        "durationFrames": checks["durationFrames"]["actual"],
        "durationDriftFrames": checks["durationFrames"]["drift"],
        "hasVideo": checks["hasVideo"]["actual"],
        "hasAudio": checks["hasAudio"]["actual"],
    }


def archive_record(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return {"name": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def run_json(command: list[str], *, cwd: Path | None = None) -> dict[str, object]:
    return json.loads(run(command, cwd=cwd).stdout)


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    input_value: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
    environment.update(PYTHONIOENCODING="utf-8", PYTHONNOUSERSITE="1")
    result = subprocess.run(command, cwd=cwd, input=input_value, capture_output=True, text=True, encoding="utf-8", env=environment, check=False)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"command failed: {command[0]}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
