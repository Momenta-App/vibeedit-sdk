import json
import re
from pathlib import Path


root = Path(__file__).resolve().parent.parent
path = root / "catalog" / "catalog.json"
catalog = json.loads(path.read_text(encoding="utf-8"))

for item in catalog["items"]:
    if item["category"] == "skill":
        name = item["id"].rsplit("/", 1)[-1]
        item["examples"] = {
            "python": f"install_skill({name!r}, harness='codex')",
            "javascript": f"installSkill({json.dumps(name)}, {{ harness: 'codex' }})",
        }
    if item["category"] == "template":
        match = re.fullmatch(r"examples/([^/]+)/composition\.json", item["provenance"]["implementation"])
        if not match:
            raise RuntimeError(f"template does not reference a packaged example: {item['id']}")
        name = match.group(1)
        item["examples"] = {
            "python": f"create_example({name!r})",
            "javascript": f"createExample({json.dumps(name)})",
        }

path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
