#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROVENANCE_SOURCE = "release-package workflow examples"


def main() -> int:
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "examples").glob("*/manifest.json"))]
    catalog_path = ROOT / "catalog" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog["items"] = [item for item in catalog["items"] if item.get("provenance", {}).get("source") != PROVENANCE_SOURCE] + [_item(manifest) for manifest in manifests]
    catalog["items"].sort(key=lambda item: item["id"])
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "examples": len(manifests), "catalogItems": len(catalog["items"])}))
    return 0


def _item(manifest):
    slug = manifest["id"].rsplit("/", 1)[-1]
    unsupported = bool(manifest.get("conditional"))
    extras = manifest["requirements"]["extras"]
    return {
        "id": manifest["id"],
        "name": manifest["name"],
        "description": manifest["description"],
        "category": "template",
        "tags": list(dict.fromkeys(["template", "executable", *manifest["families"]])),
        "version": "0.1.0",
        "inputs": {"media": ["generated"], "minimumClips": 0},
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        "platforms": ["macos", "windows", "linux"],
        "backends": ["python", "ffmpeg", *( ["html", "chromium"] if "browser" in extras else [])],
        "preview": {"status": "unsupported" if unsupported else "missing", "note": "Requires a configured checksum-declared SAM provider." if unsupported else "Run the packaged example or preview builder to create local evidence."},
        "examples": {"python": f"create_example({slug!r})", "javascript": f"createExample({json.dumps(slug)})"},
        "prompts": [f"Create the {manifest['name']} example and preserve its integer-frame artifact provenance."],
        "requirements": {"assets": [], "models": manifest["requirements"]["models"]},
        "license": {"owner": "Attention Engine Inc.", "terms": "SEE LICENSE IN LICENSE.md", "redistribution": "verified"},
        "provenance": {"kind": "vibeedit-owned", "source": PROVENANCE_SOURCE, "implementation": f"examples/{slug}/composition.json", "thirdParty": ["FFmpeg", *( ["Playwright", "Chromium"] if "browser" in extras else [])]},
        "validation": [{"id": "conditional-provider" if unsupported else "end-to-end", "status": "unsupported" if unsupported else "passed", "command": f"python examples/{slug}/render.py", "evidence": "The lightweight package writes an actionable unavailable report; a configured checksum-declared provider is tested separately." if unsupported else "The packaged recipe is exercised by the end-to-end example test matrix."}],
    }


if __name__ == "__main__":
    raise SystemExit(main())
