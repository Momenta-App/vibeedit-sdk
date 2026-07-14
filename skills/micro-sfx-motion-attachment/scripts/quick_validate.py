#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

REQUIRED_TARGETS = {
    "text_characters",
    "modules",
    "boxes",
    "buttons",
    "cursors",
    "grids",
    "panels",
    "connectors",
    "object_reveals",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and print the motion attachment map.")
    parser.add_argument("--print", action="store_true", dest="print_map")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "references" / "motion_attachment_map.json").read_text())
    found = set(payload["attachment_targets"])
    missing = sorted(REQUIRED_TARGETS - found)
    if missing:
        raise SystemExit(f"missing attachment_targets: {missing}")
    for name, item in payload["attachment_targets"].items():
        for key in ("sfx", "anchor", "offset_ms", "motion_coupling", "avoid"):
            if key not in item:
                raise SystemExit(f"{name} missing {key}")
    if args.print_map:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print("quick_validate ok: micro-sfx-motion-attachment")


if __name__ == "__main__":
    main()
