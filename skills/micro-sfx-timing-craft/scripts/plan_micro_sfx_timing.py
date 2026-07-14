#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys


PROFILES = {
    "low": {"gap": (0.140, 0.240), "max_layers": 2, "duck": (2.0, 3.5), "variation": 0.5},
    "medium": {"gap": (0.085, 0.160), "max_layers": 3, "duck": (2.5, 4.5), "variation": 1.0},
    "medium-high": {"gap": (0.060, 0.120), "max_layers": 3, "duck": (2.8, 5.0), "variation": 1.25},
    "high": {"gap": (0.045, 0.100), "max_layers": 4, "duck": (3.0, 5.5), "variation": 1.5},
    "ultra": {"gap": (0.028, 0.070), "max_layers": 5, "duck": (3.5, 6.0), "variation": 2.0},
}

ROLES = {
    "click": {"offset": (-0.004, 0.004), "pre": (0.000, 0.010), "post": (0.020, 0.060), "layers": 1, "gain": (-10.0, -6.0), "pitch": 1.2},
    "tap": {"offset": (-0.008, 0.006), "pre": (0.000, 0.014), "post": (0.030, 0.080), "layers": 1, "gain": (-11.0, -6.5), "pitch": 1.5},
    "tick": {"offset": (-0.003, 0.006), "pre": (0.000, 0.008), "post": (0.020, 0.055), "layers": 1, "gain": (-13.0, -8.0), "pitch": 1.4},
    "pop": {"offset": (-0.014, -0.002), "pre": (0.006, 0.022), "post": (0.045, 0.110), "layers": 2, "gain": (-12.0, -7.0), "pitch": 1.8},
    "hit": {"offset": (-0.018, -0.004), "pre": (0.010, 0.035), "post": (0.080, 0.220), "layers": 3, "gain": (-9.0, -4.5), "pitch": 2.0},
    "whoosh": {"offset": (-0.030, -0.008), "pre": (0.090, 0.260), "post": (0.030, 0.120), "layers": 2, "gain": (-16.0, -9.0), "pitch": 2.5},
    "layered": {"offset": (-0.024, -0.004), "pre": (0.080, 0.220), "post": (0.100, 0.300), "layers": 4, "gain": (-14.0, -6.0), "pitch": 2.2},
    "riser": {"offset": (-0.020, 0.000), "pre": (0.180, 0.480), "post": (0.020, 0.080), "layers": 2, "gain": (-18.0, -10.0), "pitch": 3.0},
    "glitch": {"offset": (-0.010, 0.010), "pre": (0.010, 0.050), "post": (0.030, 0.130), "layers": 3, "gain": (-14.0, -7.0), "pitch": 3.0},
    "tail": {"offset": (0.000, 0.020), "pre": (0.000, 0.015), "post": (0.120, 0.350), "layers": 1, "gain": (-22.0, -13.0), "pitch": 1.0},
}

ROLE_ALIASES = {
    "text-pop": "pop",
    "text_pop": "pop",
    "impact": "hit",
    "layer": "layered",
}
COMPLEXITY_ALIASES = {"max": "ultra"}
PRIMARY_ROLES = {"click", "tap", "tick", "pop", "hit", "glitch"}


def main():
    parser = argparse.ArgumentParser(description="Plan and validate micro-SFX event timings.")
    parser.add_argument("--events", required=True, help="Input event JSON path.")
    parser.add_argument("--out", required=True, help="Output planned timeline JSON path.")
    parser.add_argument("--complexity", help="Override input complexity.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if warnings are emitted.")
    args = parser.parse_args()

    try:
        source = json.load(open(args.events, "r", encoding="utf-8"))
        planned = plan_timeline(source, args.complexity)
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(planned, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except (OSError, ValueError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if planned["warnings"]:
        for warning in planned["warnings"]:
            print(f"warning: {warning}", file=sys.stderr)
        return 1 if args.strict else 0
    return 0


def plan_timeline(source, complexity_override=None):
    if not isinstance(source, dict):
        raise ValueError("input must be a JSON object")

    duration = require_number(source, "duration")
    if duration <= 0:
        raise ValueError("duration must be positive")

    complexity = normalize_complexity(complexity_override or source.get("complexity", "medium"))

    fps = float(source.get("fps", 30))
    if fps <= 0:
        raise ValueError("fps must be positive")

    events = source.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("events must be a non-empty array")

    warnings = []
    planned_events = [
        plan_event(event, index, duration, complexity, warnings)
        for index, event in enumerate(events)
    ]
    planned_events.sort(key=lambda event: (event["transient_time"], event["id"]))
    warnings.extend(validate_density(planned_events, duration, fps, complexity))

    return {
        "version": 1,
        "duration": round(duration, 6),
        "fps": fps,
        "complexity": complexity,
        "summary": summarize(planned_events, duration),
        "events": planned_events,
        "warnings": warnings,
    }


def plan_event(event, index, duration, complexity, warnings):
    if not isinstance(event, dict):
        raise ValueError(f"events[{index}] must be an object")

    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError(f"events[{index}].id must be a non-empty string")

    anchor_time = require_number(event, "time", f"events[{index}]")
    if anchor_time < 0 or anchor_time > duration:
        warnings.append(f"{event_id}: anchor time {anchor_time:.3f}s is outside timeline duration {duration:.3f}s")

    role = normalize_role(event.get("role", "tap"))
    if role not in ROLES:
        warnings.append(f"{event_id}: unknown role {role!r}; using tap")
        role = "tap"

    weight = clamp(float(event.get("weight", 0.6)), 0.0, 1.0)
    role_rule = ROLES[role]
    profile = PROFILES[complexity]
    seed = stable_unit(event_id)
    offset = choose(role_rule["offset"], seed)
    pre_roll = choose(role_rule["pre"], stable_unit(event_id + ":pre"))
    post_roll = choose(role_rule["post"], stable_unit(event_id + ":post")) * (0.75 + weight * 0.5)
    transient_time = anchor_time + offset
    start_time = max(0.0, transient_time - pre_roll)
    end_time = min(duration, transient_time + post_roll)
    requested_layers = int(event.get("layers", role_rule["layers"]))
    layer_count = max(1, min(requested_layers, role_rule["layers"], profile["max_layers"]))

    if requested_layers > layer_count:
        warnings.append(f"{event_id}: requested {requested_layers} layers capped to {layer_count} for {role}/{complexity}")
    if transient_time < 0 or transient_time > duration:
        warnings.append(f"{event_id}: planned transient {transient_time:.3f}s falls outside timeline")
    if start_time == 0.0 and transient_time - pre_roll < 0:
        warnings.append(f"{event_id}: pre-roll clipped at timeline start")
    if end_time == duration and transient_time + post_roll > duration:
        warnings.append(f"{event_id}: post-roll clipped at timeline end")

    layers = [
        plan_layer(event_id, role, layer_index, layer_count, role_rule, weight, profile)
        for layer_index in range(layer_count)
    ]

    return {
        "id": event_id,
        "role": role,
        "group": event.get("group"),
        "anchor_time": rounded(anchor_time),
        "transient_time": rounded(transient_time),
        "start_time": rounded(start_time),
        "end_time": rounded(end_time),
        "pre_roll": rounded(transient_time - start_time),
        "post_roll": rounded(end_time - transient_time),
        "weight": rounded(weight),
        "layers": layers,
        "ducking": plan_ducking(event_id, role, transient_time, duration, weight, profile),
        "source": {key: value for key, value in event.items() if key not in {"id", "time", "role", "weight", "layers", "group"}},
    }


def plan_layer(event_id, role, layer_index, layer_count, role_rule, weight, profile):
    layer_roles = ["transient", "body", "air", "tail", "tonal"]
    unit = stable_unit(f"{event_id}:layer:{layer_index}")
    gain_min, gain_max = role_rule["gain"]
    base_gain = choose((gain_min, gain_max), weight)
    gain_step = layer_index * (2.2 + profile["variation"])
    pitch_span = role_rule["pitch"] + profile["variation"] * 0.35
    pitch = (unit * 2.0 - 1.0) * pitch_span

    return {
        "layer": layer_index + 1,
        "purpose": layer_roles[min(layer_index, len(layer_roles) - 1)],
        "gain_db": rounded(base_gain - gain_step),
        "pitch_semitones": rounded(pitch),
        "automation": {
            "attack": rounded(choose((0.003, 0.020), stable_unit(event_id + ":attack"))),
            "hold": rounded(choose((0.010, 0.060), stable_unit(event_id + ":hold"))),
            "release": rounded(choose((0.030, 0.180), stable_unit(event_id + ":release"))),
        },
        "note": "keep layer distinct" if layer_count > 1 else "single focused hit",
    }


def plan_ducking(event_id, role, transient_time, duration, weight, profile):
    if role not in PRIMARY_ROLES:
        return None
    amount = choose(profile["duck"], weight)
    pre = 0.018 + 0.012 * weight
    post = 0.045 + 0.135 * weight
    return {
        "target": "beds_and_previous_tails",
        "amount_db": rounded(amount),
        "start_time": rounded(max(0.0, transient_time - pre)),
        "end_time": rounded(min(duration, transient_time + post)),
    }


def validate_density(events, duration, fps, complexity):
    warnings = []
    profile = PROFILES[complexity]
    min_gap = profile["gap"][0]
    frame = 1.0 / fps
    transients = [event["transient_time"] for event in events]

    for previous, current in zip(events, events[1:]):
        gap = current["transient_time"] - previous["transient_time"]
        if gap < 0:
            continue
        if gap < frame and complexity != "ultra":
            warnings.append(f"{previous['id']}->{current['id']}: transients are closer than one frame ({gap:.3f}s)")
        if gap < min_gap:
            warnings.append(f"{previous['id']}->{current['id']}: gap {gap:.3f}s is below {complexity} target {min_gap:.3f}s")

    for event in events:
        window_count = sum(1 for transient in transients if abs(transient - event["transient_time"]) <= 0.090)
        if window_count > 3 and event["role"] in PRIMARY_ROLES:
            warnings.append(f"{event['id']}: more than three primary events in a 180ms window")
            break

    for point in sorted(set(transients)):
        active_layers = sum(len(event["layers"]) for event in events if event["start_time"] <= point <= event["end_time"])
        if active_layers > profile["max_layers"]:
            warnings.append(f"{point:.3f}s: {active_layers} active layers exceed {complexity} max {profile['max_layers']}")
            break

    if events and (events[0]["start_time"] < 0 or events[-1]["end_time"] > duration):
        warnings.append("planned event range exceeds timeline bounds")
    return warnings


def summarize(events, duration):
    total_layers = sum(len(event["layers"]) for event in events)
    return {
        "event_count": len(events),
        "layer_count": total_layers,
        "first_transient": rounded(events[0]["transient_time"]) if events else None,
        "last_event_end": rounded(max(event["end_time"] for event in events)) if events else None,
        "average_events_per_second": rounded(len(events) / duration),
    }


def require_number(source, key, label="input"):
    value = source.get(key)
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label}.{key} must be a number")
    return float(value)


def normalize_complexity(value):
    complexity = COMPLEXITY_ALIASES.get(str(value), str(value))
    if complexity not in PROFILES:
        raise ValueError(f"complexity must be one of: {', '.join(PROFILES)}")
    return complexity


def normalize_role(value):
    return ROLE_ALIASES.get(str(value), str(value))


def stable_unit(text):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)


def choose(bounds, unit):
    return bounds[0] + (bounds[1] - bounds[0]) * clamp(unit, 0.0, 1.0)


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def rounded(value):
    return round(float(value), 6)


if __name__ == "__main__":
    raise SystemExit(main())
