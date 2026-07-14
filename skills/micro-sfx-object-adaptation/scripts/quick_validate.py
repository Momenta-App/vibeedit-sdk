#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

REQUIRED_CLASSES = {"ui", "text", "physical", "graphic"}
REQUIRED_MODES = {"small_fast", "small_slow", "large_fast", "large_slow"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and print the object adaptation map.")
    parser.add_argument("--print", action="store_true", dest="print_map")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "references" / "object_adaptation_map.json").read_text())
    classes = payload["object_classes"]
    missing_classes = sorted(REQUIRED_CLASSES - set(classes))
    if missing_classes:
        raise SystemExit(f"missing object_classes: {missing_classes}")
    for class_name, modes in classes.items():
        missing_modes = sorted(REQUIRED_MODES - set(modes))
        if missing_modes:
            raise SystemExit(f"{class_name} missing modes: {missing_modes}")
        for mode_name, item in modes.items():
            for key in ("sfx", "hit_count_multiplier", "layer_depth", "offset_ms", "gain_db", "tail_ms"):
                if key not in item:
                    raise SystemExit(f"{class_name}.{mode_name} missing {key}")
    if args.print_map:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print("quick_validate ok: micro-sfx-object-adaptation")


if __name__ == "__main__":
    main()
