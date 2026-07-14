#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

REQUIRED_TYPES = {"click", "tap", "tick", "pop", "hit", "whoosh", "layered"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and print the micro SFX choice map.")
    parser.add_argument("--print", action="store_true", dest="print_map")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "references" / "sfx_choice_map.json").read_text())
    found = set(payload["sfx_types"])
    missing = sorted(REQUIRED_TYPES - found)
    if missing:
        raise SystemExit(f"missing sfx_types: {missing}")
    for name, item in payload["sfx_types"].items():
        for key in ("primary_use", "tags", "attack_ms", "tail_ms", "gain_db", "layer_recipe"):
            if key not in item:
                raise SystemExit(f"{name} missing {key}")
    for event, choice in payload["event_map"].items():
        if choice not in found:
            raise SystemExit(f"{event} maps to unknown type {choice}")
    if args.print_map:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print("quick_validate ok: micro-sfx-choice")


if __name__ == "__main__":
    main()
