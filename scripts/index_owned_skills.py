"""Index SDK-authored skills without rewriting the pinned canonical donor set."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent.parent
version = json.loads((root / "package.json").read_text())["version"]
names = ["vibeedit-setup", "vibeedit-acquisition", "vibeedit-companion"]
skills = []
for name in names:
    directory = root / "skills" / name
    digest = hashlib.sha256()
    files = sorted(p for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    for file in files:
        digest.update(file.relative_to(directory).as_posix().encode() + b"\0" + file.read_bytes() + b"\0")
    checksum = digest.hexdigest()
    skills.append({"id": f"vibeedit://skill/{name}", "name": name, "version": version, "path": name, "harnesses": ["agents", "codex", "claude", "opencode"], "checksum": checksum, "source": {"kind": "sdk-owned", "path": f"skills/{name}", "sha256": checksum}, "validation": {"status": "integrity-only", "files": len(files), "note": "Tree digest pins content; customer journey qualification is separate."}})
(root / "skills" / "owned.json").write_text(json.dumps({"schemaVersion": "vibeedit.ownedSkills.v1", "skills": skills}, indent=2) + "\n")
