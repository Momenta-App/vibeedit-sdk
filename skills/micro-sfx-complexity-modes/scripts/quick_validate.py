#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

REQUIRED_MODES = ["low", "medium", "medium-high", "high", "ultra"]
REQUIRED_KEYS = {
    "hit_count_per_second",
    "layering_depth",
    "event_density",
    "timing_jitter_ms",
    "volume_envelope",
    "motion_coupling",
    "verification_strictness",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and print the micro SFX complexity modes.")
    parser.add_argument("--print", action="store_true", dest="print_map")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    payload = json.loads((root / "references" / "complexity_modes.json").read_text())
    modes = payload["modes"]
    if list(modes) != REQUIRED_MODES:
        raise SystemExit(f"mode order must be {REQUIRED_MODES}")
    previous_max = 0
    for name, item in modes.items():
        missing = sorted(REQUIRED_KEYS - set(item))
        if missing:
            raise SystemExit(f"{name} missing {missing}")
        count_min, count_max = item["hit_count_per_second"]
        if count_min < previous_max and name != "low":
            raise SystemExit(f"{name} hit_count_per_second overlaps too far backward")
        previous_max = count_max
    if args.print_map:
        print(json.dumps(payload, indent=2, sort_keys=True))
    print("quick_validate ok: micro-sfx-complexity-modes")


if __name__ == "__main__":
    main()
