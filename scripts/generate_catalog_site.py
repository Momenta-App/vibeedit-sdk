import json
from pathlib import Path


root = Path(__file__).resolve().parent.parent
catalog = json.loads((root / "catalog" / "catalog.json").read_text(encoding="utf-8"))
(root / "site" / "catalog-data.js").write_text(
    "globalThis.VIBEEDIT_CATALOG = " + json.dumps(catalog, separators=(",", ":"), ensure_ascii=False) + ";\n",
    encoding="utf-8",
)
