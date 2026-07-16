from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PREFIX = "packages/app/public/text-effect-catalog/components/html-motion-mogrt"
DESTINATION = PACKAGE_ROOT / "catalog" / "text-runtime"


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone the tracked VibeEdit HTML motion-title runtime without redesigning it")
    parser.add_argument("--source-root", type=Path, required=True, help="path to a VibeEdit source checkout")
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    root = args.source_root.resolve()
    revision = _git(root, "rev-parse", args.revision).decode().strip()
    paths = [
        path
        for path in _git(root, "ls-tree", "-r", "--name-only", revision, SOURCE_PREFIX).decode().splitlines()
        if path.startswith(f"{SOURCE_PREFIX}/")
    ]
    if not paths:
        raise RuntimeError("tracked canonical text runtime is empty")

    shutil.rmtree(DESTINATION, ignore_errors=True)
    records = []
    for path in paths:
        relative = Path(path).relative_to(SOURCE_PREFIX)
        payload = _git(root, "show", f"{revision}:{path}")
        if relative.suffix == ".html":
            payload = _inject_adapter(payload.decode()).encode()
        destination = DESTINATION / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        records.append({"path": relative.as_posix(), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})

    adapter = _adapter().encode()
    (DESTINATION / "vibeedit-adapter.js").write_bytes(adapter)
    records.append({"path": "vibeedit-adapter.js", "bytes": len(adapter), "sha256": hashlib.sha256(adapter).hexdigest()})
    manifest = {
        "schemaVersion": "vibeedit.canonical-text-runtime.v1",
        "source": SOURCE_PREFIX,
        "revision": revision,
        "files": sorted(records, key=lambda item: item["path"]),
    }
    (DESTINATION / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "revision": revision, "files": len(records)}))
    return 0


def _inject_adapter(document: str) -> str:
    injection = '<script src="/vibeedit-adapter.js"></script><style>html,body,.elegant-misc-root{background:transparent!important}</style>'
    if "</head>" not in document:
        raise RuntimeError("canonical HTML output has no head boundary")
    return document.replace("</head>", f"{injection}</head>", 1)


def _adapter() -> str:
    return r'''(() => {
  const requested = new URLSearchParams(location.search).get("text");
  if (!requested) return;
  const apply = (config) => {
    if (!config || typeof config !== "object" || (!config.slug && !config.family)) return config;
    const words = requested.trim().split(/\s+/).filter(Boolean);
    const distribute = (layers) => {
      if (!Array.isArray(layers) || !layers.length) return;
      const explicit = requested.split(/\s*[|\n]\s*/).filter(Boolean);
      const values = explicit.length === layers.length
        ? explicit
        : layers.map((_, index) => index === layers.length - 1
          ? words.slice(Math.floor(index * words.length / layers.length)).join(" ")
          : words.slice(Math.floor(index * words.length / layers.length), Math.floor((index + 1) * words.length / layers.length)).join(" "));
      layers.forEach((layer, index) => {
        if (layer && typeof layer === "object" && values[index]) layer.text = values[index];
      });
    };
    config.text = requested;
    distribute(config.text_lines);
    const recipes = [config.recipe, config.componentRecipe].filter((value) => value && typeof value === "object");
    recipes.forEach((recipe) => {
      recipe.text = requested;
      distribute(recipe.lines);
      distribute(recipe.layers);
      distribute(recipe.texts);
      distribute(recipe.crossing_texts);
    });
    return config;
  };
  const parse = JSON.parse.bind(JSON);
  JSON.parse = (value, reviver) => apply(parse(value, reviver));
  const fetchRequest = fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await fetchRequest(...args);
    const read = response.json.bind(response);
    response.json = async () => apply(await read());
    return response;
  };
})();
'''


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace").strip() or f"git {' '.join(args)} failed")
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
