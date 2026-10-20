"""Pin reviewed portable adaptations while retaining each donor's historical identity."""
import json

from import_skills import TARGET_ROOT, _tree_checksum, _validate_skill, _write_catalog

index_path = TARGET_ROOT / "index.json"
report_path = TARGET_ROOT / "migration-report.json"
index = json.loads(index_path.read_text())
report = json.loads(report_path.read_text())
selected = {item["name"]: item for item in report["selected"]}
for record in index["skills"]:
    checksum = _tree_checksum(TARGET_ROOT / record["path"])
    record["validation"] = _validate_skill(TARGET_ROOT / record["path"])
    if checksum != record["source"]["sha256"]:
        record["adaptation"] = {"kind": "portable-sdk", "parentSha256": record["source"]["sha256"], "reason": "Remove desktop/private-library dependencies; use project-relative inputs, owned public runtime adapters and pinned OFL fonts. Creative workflow and skill identity retained. Runtime qualification is tracked separately."}
        record["version"] = "0.2.0"
    record["checksum"] = checksum
    selected[record["name"]].update(packageSha256=checksum, files=record["validation"]["files"])
    if record.get("adaptation"):
        selected[record["name"]]["adaptation"] = record["adaptation"]
report["policy"] = "Each skill retains its original canonical source revision and sourceSha256. Unchanged trees are byte-identical clones; explicitly recorded portable adaptations have an independent packageSha256. Package trees are authoritative installed content; historical source identity is not a claim of package byte equivalence."
index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
_write_catalog(index["skills"])
print(json.dumps({"skills": len(index["skills"]), "adapted": sum(bool(r.get("adaptation")) for r in index["skills"])}))
