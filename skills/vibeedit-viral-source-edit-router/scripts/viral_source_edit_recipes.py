#!/usr/bin/env python3
"""Read-only lookup recipes for source-backed viral edit planning datasets."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path


DEFAULT_DATASET_ROOT = Path(
    "fan_Edit_Data/workspace/reference-corpora/creed-analysis-dataset"
)


INDEX_PATHS = {
    "moments": "crosswalks/fanedit_general_source_moment_index.json",
    "recurring_moments": "crosswalks/recurring_source_moments.json",
    "recurring_patterns": "crosswalks/recurring_story_patterns.json",
    "sequences": "crosswalks/fanedit_general_source_sequence_index.json",
    "broad_lookup": "crosswalks/source_usage_broad_lookup.json",
    "recipe_evidence": "crosswalks/skill_recipe_evidence_index.json",
    "beat_patterns": "crosswalks/beat_pattern_index.json",
    "audio_beat_song": "audio_beat_song_index.json",
    "action_events": "derived/creed-action-events/human_punch_action_event_index.json",
    "action_audio_events": "derived/creed-action-audio/human_punch_action_event_index.json",
}


PROOF_BOUNDARY = (
    "This router reads existing dataset indexes only. Confirmed rows preserve "
    "confirmed proof, candidate rows remain provisional, and preferred rows are "
    "derived planning recommendations rather than promoted proof."
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query source-edit evidence and emit reusable learned-style memory."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Dataset root. Defaults to the local Creed analysis dataset.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    edit_moments = subparsers.add_parser(
        "edit-moments", help="Query edit-to-source moment rows."
    )
    add_common_filters(edit_moments)
    edit_moments.add_argument("--fanedit-id")
    edit_moments.add_argument("--story-function")

    recurring = subparsers.add_parser(
        "recurring-moments", help="Query recurring/iconic source moments."
    )
    add_common_filters(recurring)
    recurring.add_argument("--min-recurrence", type=int, default=2)

    proof = subparsers.add_parser(
        "proof-tiers", help="Summarize candidate, confirmed, and preferred planning tiers."
    )
    add_common_filters(proof)

    sequences = subparsers.add_parser(
        "story-sequences", help="Summarize source sequence/story-function patterns."
    )
    add_common_filters(sequences)
    sequences.add_argument("--fanedit-id")

    timing = subparsers.add_parser(
        "timing-candidates", help="Inspect song, beat, and action timing candidates."
    )
    add_common_filters(timing)
    timing.add_argument("--fanedit-id")

    memory = subparsers.add_parser(
        "emit-learned-memory", help="Write shared learned-style memory JSON."
    )
    add_common_filters(memory)
    memory.add_argument(
        "--output",
        type=Path,
        help="Output JSON path. Defaults under derived/viral-source-edit-learning.",
    )

    args = parser.parse_args()
    dataset_root = args.dataset_root.resolve()
    if args.command == "edit-moments":
        emit(
            query_edit_moments(
                dataset_root,
                query=args.query,
                fanedit_id=args.fanedit_id,
                source_id=args.source_id,
                proof_tier=args.proof_tier,
                story_function=args.story_function,
                limit=args.limit,
            )
        )
        return
    if args.command == "recurring-moments":
        emit(
            query_recurring_moments(
                dataset_root,
                query=args.query,
                source_id=args.source_id,
                proof_tier=args.proof_tier,
                min_recurrence=args.min_recurrence,
                limit=args.limit,
            )
        )
        return
    if args.command == "proof-tiers":
        emit(
            query_proof_tiers(
                dataset_root,
                query=args.query,
                source_id=args.source_id,
                proof_tier=args.proof_tier,
                limit=args.limit,
            )
        )
        return
    if args.command == "story-sequences":
        emit(
            summarize_story_sequences(
                dataset_root,
                query=args.query,
                fanedit_id=args.fanedit_id,
                source_id=args.source_id,
                proof_tier=args.proof_tier,
                limit=args.limit,
            )
        )
        return
    if args.command == "timing-candidates":
        emit(
            inspect_timing_candidates(
                dataset_root,
                query=args.query,
                fanedit_id=args.fanedit_id,
                source_id=args.source_id,
                proof_tier=args.proof_tier,
                limit=args.limit,
            )
        )
        return
    if args.command == "emit-learned-memory":
        emit(
            emit_learned_memory(
                dataset_root,
                query=args.query,
                source_id=args.source_id,
                proof_tier=args.proof_tier,
                limit=args.limit,
                output_path=args.output,
            )
        )


def add_common_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--query", help="Case-insensitive text filter.")
    parser.add_argument("--source-id", help="Source id such as creed-1, creed-2, creed-3.")
    parser.add_argument(
        "--proof-tier",
        choices=["candidate", "confirmed", "preferred"],
        help="Filter proof tier. Preferred is a derived planning tier.",
    )
    parser.add_argument("--limit", type=int, default=10)


def query_edit_moments(
    dataset_root: Path,
    *,
    query: str | None,
    fanedit_id: str | None,
    source_id: str | None,
    proof_tier: str | None,
    story_function: str | None,
    limit: int,
) -> dict:
    rows = [
        summarize_moment(row)
        for row in load_items(dataset_root, "moments")
        if matches_common(row, query=query, source_id=source_id, proof_tier=proof_tier)
        if not fanedit_id or row.get("fanedit_id") == fanedit_id
        if not story_function or row.get("story_function") == story_function
    ]
    return result(
        dataset_root,
        "edit_moments",
        rows[:limit],
        total_matches=len(rows),
        source_artifacts=[INDEX_PATHS["moments"]],
    )


def query_recurring_moments(
    dataset_root: Path,
    *,
    query: str | None,
    source_id: str | None,
    proof_tier: str | None,
    min_recurrence: int,
    limit: int,
) -> dict:
    source_rows = [
        summarize_recurring_moment(row)
        for row in load_items(dataset_root, "recurring_moments")
        if matches_common(row, query=query, source_id=source_id, proof_tier=proof_tier)
        if int(row.get("recurrence_count") or 0) >= min_recurrence
    ]
    pattern_rows = [
        summarize_story_pattern(row)
        for row in load_items(dataset_root, "recurring_patterns")
        if matches_text(row, query)
        if int(row.get("recurrence_count") or 0) >= min_recurrence
    ]
    return result(
        dataset_root,
        "recurring_moments",
        {
            "source_moments": source_rows[:limit],
            "story_patterns": pattern_rows[:limit],
        },
        total_matches={
            "source_moments": len(source_rows),
            "story_patterns": len(pattern_rows),
        },
        source_artifacts=[
            INDEX_PATHS["recurring_moments"],
            INDEX_PATHS["recurring_patterns"],
        ],
    )


def query_proof_tiers(
    dataset_root: Path,
    *,
    query: str | None,
    source_id: str | None,
    proof_tier: str | None,
    limit: int,
) -> dict:
    moments = [
        row
        for row in load_items(dataset_root, "moments")
        if matches_common(row, query=query, source_id=source_id, proof_tier=proof_tier)
    ]
    broad_rows = [
        row
        for row in broad_lookup_rows(dataset_root)
        if matches_common(row, query=query, source_id=source_id, proof_tier=proof_tier)
    ]
    preferred = [row for row in broad_rows if selection_tier(row) == "preferred"]
    return result(
        dataset_root,
        "proof_tiers",
        {
            "counts": {
                "moments_by_proof_tier": dict(Counter(row.get("proof_tier", "unknown") for row in moments)),
                "broad_usage_by_proof_tier": dict(Counter(row.get("proof_tier", "unknown") for row in broad_rows)),
                "preferred_planning_rows": len(preferred),
            },
            "preferred_examples": [summarize_broad_usage(row) for row in preferred[:limit]],
            "confirmed_examples": [
                summarize_moment(row)
                for row in moments
                if row.get("proof_tier") == "confirmed"
            ][:limit],
            "candidate_examples": [
                summarize_moment(row)
                for row in moments
                if row.get("proof_tier") == "candidate"
            ][:limit],
        },
        total_matches={"moments": len(moments), "broad_usage": len(broad_rows)},
        source_artifacts=[INDEX_PATHS["moments"], INDEX_PATHS["broad_lookup"]],
    )


def summarize_story_sequences(
    dataset_root: Path,
    *,
    query: str | None,
    fanedit_id: str | None,
    source_id: str | None,
    proof_tier: str | None,
    limit: int,
) -> dict:
    rows = [
        row
        for row in load_items(dataset_root, "sequences")
        if matches_common(row, query=query, source_id=source_id, proof_tier=proof_tier)
        if not fanedit_id or row.get("fanedit_id") == fanedit_id
    ]
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get("story_function") or "unknown"].append(row)
    patterns = [
        {
            "story_function": story_function,
            "sequence_count": len(items),
            "proof_tier_counts": dict(Counter(item.get("proof_tier", "unknown") for item in items)),
            "confidence_counts": dict(Counter(item.get("confidence", "unknown") for item in items)),
            "source_counts": dict(Counter(item.get("source_id", "unknown") for item in items)),
            "examples": [summarize_sequence(item) for item in items[: min(3, limit)]],
        }
        for story_function, items in sorted(
            grouped.items(), key=lambda item: len(item[1]), reverse=True
        )
    ]
    return result(
        dataset_root,
        "story_sequences",
        patterns[:limit],
        total_matches=len(rows),
        source_artifacts=[INDEX_PATHS["sequences"]],
    )


def inspect_timing_candidates(
    dataset_root: Path,
    *,
    query: str | None,
    fanedit_id: str | None,
    source_id: str | None,
    proof_tier: str | None,
    limit: int,
) -> dict:
    beat_rows = [
        summarize_beat(row)
        for row in load_items(dataset_root, "beat_patterns")
        if matches_common(row, query=query, source_id=source_id, proof_tier=proof_tier)
        if not fanedit_id or row.get("fanedit_id") == fanedit_id
    ]
    audio_rows = [
        summarize_audio(row)
        for row in load_items(dataset_root, "audio_beat_song")
        if matches_text(row, query)
        if not fanedit_id or row.get("fanedit_id") == fanedit_id
    ]
    action_rows = [
        summarize_action(row)
        for row in load_items(dataset_root, "action_events")
        if matches_text(row, query)
        if not source_id or row.get("movie_key") == source_id
    ]
    action_audio_rows = [
        summarize_action(row)
        for row in load_items(dataset_root, "action_audio_events")
        if matches_text(row, query)
        if not source_id or row.get("movie_key") == source_id
    ]
    return result(
        dataset_root,
        "timing_candidates",
        {
            "song_and_beat_candidates": audio_rows[:limit],
            "beat_pattern_candidates": beat_rows[:limit],
            "human_action_candidates": action_rows[:limit],
            "action_audio_candidates": action_audio_rows[:limit],
        },
        total_matches={
            "song_and_beat": len(audio_rows),
            "beat_patterns": len(beat_rows),
            "human_action": len(action_rows),
            "action_audio": len(action_audio_rows),
        },
        source_artifacts=[
            INDEX_PATHS["audio_beat_song"],
            INDEX_PATHS["beat_patterns"],
            INDEX_PATHS["action_events"],
            INDEX_PATHS["action_audio_events"],
        ],
    )


def emit_learned_memory(
    dataset_root: Path,
    *,
    query: str | None,
    source_id: str | None,
    proof_tier: str | None,
    limit: int,
    output_path: Path | None,
) -> dict:
    memory = {
        "schema_version": "vibeedit.viral_source_edit_learning.v1",
        "generated_at": now(),
        "dataset_root": str(dataset_root),
        "route": "vibeedit-viral-source-edit-router",
        "status": "ready_for_planning",
        "learned_from": "existing source-moment, recurrence, sequence, timing, and action indexes",
        "proof_boundary": PROOF_BOUNDARY,
        "filters": compact(
            {"query": query, "source_id": source_id, "proof_tier": proof_tier, "limit": limit}
        ),
        "proof_tier_summary": query_proof_tiers(
            dataset_root,
            query=query,
            source_id=source_id,
            proof_tier=proof_tier,
            limit=limit,
        )["items"],
        "recurring_source_memory": query_recurring_moments(
            dataset_root,
            query=query,
            source_id=source_id,
            proof_tier=proof_tier,
            min_recurrence=2,
            limit=limit,
        )["items"],
        "story_sequence_patterns": summarize_story_sequences(
            dataset_root,
            query=query,
            fanedit_id=None,
            source_id=source_id,
            proof_tier=proof_tier,
            limit=limit,
        )["items"],
        "timing_candidates": inspect_timing_candidates(
            dataset_root,
            query=query,
            fanedit_id=None,
            source_id=source_id,
            proof_tier=proof_tier,
            limit=limit,
        )["items"],
        "reuse_rules": [
            "Use confirmed rows for exact source claims.",
            "Use candidate rows only as source-search leads or vibe/story suggestions.",
            "Use preferred rows as planning priorities only; they do not promote proof.",
            "Keep reference edit timestamps and source timestamps separate.",
            "Do not mutate raw media, source transcripts, human labels, or existing analysis runs.",
        ],
    }
    path = output_path or dataset_root / "derived/viral-source-edit-learning/learned_style_memory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, indent=2, ensure_ascii=False) + "\n")
    return {
        "command": "emit_learned_memory",
        "output_path": str(path),
        "proof_boundary": PROOF_BOUNDARY,
        "bytes_written": path.stat().st_size,
    }


def summarize_moment(row: dict) -> dict:
    return compact(
        {
            "id": row.get("id"),
            "fanedit_id": row.get("fanedit_id"),
            "fanedit_shot_id": row.get("fanedit_shot_id"),
            "edit_time": row.get("edit_time"),
            "proof_tier": row.get("proof_tier"),
            "selection_tier": selection_tier(row),
            "confidence": row.get("confidence"),
            "source_id": row.get("source_id"),
            "source_shot_id": row.get("source_shot_id"),
            "approx_source_window": row.get("approx_source_window"),
            "story_function": row.get("story_function"),
            "moment_vibe": row.get("moment_vibe"),
            "evidence": row.get("evidence"),
            "proof_boundary": row.get("proof_boundary"),
        }
    )


def summarize_recurring_moment(row: dict) -> dict:
    return compact(
        {
            "id": row.get("id"),
            "source_id": row.get("source_id"),
            "movie_title": row.get("movie_title"),
            "source_time": row.get("source_time")
            or compact(
                {
                    "start_sec": row.get("source_start_sec"),
                    "end_sec": row.get("source_end_sec"),
                }
            ),
            "source_text": row.get("source_text"),
            "recurrence_count": row.get("recurrence_count"),
            "fanedit_ids": row.get("fanedit_ids"),
            "confidence": row.get("confidence"),
            "selection_tier": selection_tier(row),
            "story_pattern_tags": row.get("story_pattern_tags"),
            "needs_review": row.get("needs_review"),
        }
    )


def summarize_story_pattern(row: dict) -> dict:
    return compact(
        {
            "id": row.get("id"),
            "pattern": row.get("pattern"),
            "label": row.get("label"),
            "recurrence_count": row.get("recurrence_count"),
            "source_moment_count": row.get("source_moment_count"),
            "fanedit_ids": row.get("fanedit_ids"),
            "representative_quotes": row.get("representative_quotes", [])[:3],
            "confidence": row.get("confidence"),
            "story_function": row.get("story_function"),
            "when_to_use": row.get("when_to_use"),
            "avoid_if": row.get("avoid_if"),
            "proof_boundary": row.get("proof_boundary"),
        }
    )


def summarize_sequence(row: dict) -> dict:
    return compact(
        {
            "id": row.get("id"),
            "fanedit_id": row.get("fanedit_id"),
            "sequence_index": row.get("sequence_index"),
            "shot_count": row.get("shot_count"),
            "edit_time": row.get("edit_time"),
            "proof_tier": row.get("proof_tier"),
            "selection_tier": selection_tier(row),
            "confidence": row.get("confidence"),
            "source_id": row.get("source_id"),
            "source_shot_id": row.get("source_shot_id"),
            "approx_source_window": row.get("approx_source_window"),
            "story_function": row.get("story_function"),
            "moment_vibe": row.get("moment_vibe"),
            "proof_tier_counts": row.get("proof_tier_counts"),
        }
    )


def summarize_broad_usage(row: dict) -> dict:
    return compact(
        {
            "id": row.get("id"),
            "source_id": row.get("source_id"),
            "source_shot_id": row.get("source_shot_id"),
            "source_time": compact(
                {
                    "start_sec": row.get("source_start_sec"),
                    "end_sec": row.get("source_end_sec"),
                    "center_sec": row.get("source_center_sec"),
                }
            ),
            "primary_story_function": row.get("primary_story_function"),
            "representative_moment_vibe": row.get("representative_moment_vibe"),
            "fanedit_count": row.get("fanedit_count"),
            "sequence_count": row.get("sequence_count"),
            "proof_tier": row.get("proof_tier"),
            "selection_tier": selection_tier(row),
            "confidence": row.get("confidence"),
            "fanedit_ids": row.get("fanedit_ids"),
        }
    )


def summarize_beat(row: dict) -> dict:
    return compact(
        {
            "id": row.get("id"),
            "fanedit_id": row.get("fanedit_id"),
            "status": row.get("status"),
            "confidence": row.get("confidence"),
            "bpm": row.get("bpm"),
            "beat_count": row.get("beat_count"),
            "downbeat_count": row.get("downbeat_count"),
            "strongest_beat": row.get("strongest_beat"),
            "first_beats": row.get("first_beats", [])[:8],
            "proof_boundary": row.get("proof_boundary"),
        }
    )


def summarize_audio(row: dict) -> dict:
    return compact(
        {
            "fanedit_id": row.get("fanedit_id"),
            "status": row.get("status"),
            "evidence": row.get("evidence"),
            "audio_layers": row.get("audio_layers"),
            "beats": row.get("beats"),
            "song_semantics": row.get("song_semantics"),
            "proof_boundary": row.get("proof_boundary"),
        }
    )


def summarize_action(row: dict) -> dict:
    return compact(
        {
            "event_id": row.get("event_id"),
            "movie": row.get("movie"),
            "movie_key": row.get("movie_key"),
            "scene_id": row.get("scene_id"),
            "timestamp_sec": row.get("timestamp_sec"),
            "frame_number": row.get("frame_number"),
            "rank": row.get("rank"),
            "normalized_action": row.get("normalized_action"),
            "punch_type": row.get("punch_type"),
            "impact_type": row.get("impact_type"),
            "puncher": row.get("puncher") or dig(row, "actors", "puncher"),
            "recipient": row.get("recipient") or dig(row, "actors", "recipient"),
            "human_reviewed": row.get("human_reviewed") or dig(row, "review", "human_reviewed"),
            "review_status": row.get("review_status") or dig(row, "review", "status"),
            "notes": row.get("notes") or dig(row, "review", "notes"),
        }
    )


def load_items(dataset_root: Path, key: str) -> list[dict]:
    path = dataset_root / INDEX_PATHS[key]
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)]
    if isinstance(data.get("events"), list):
        return [item for item in data["events"] if isinstance(item, dict)]
    return []


def broad_lookup_rows(dataset_root: Path) -> list[dict]:
    path = dataset_root / INDEX_PATHS["broad_lookup"]
    if not path.exists():
        return []
    items = json.loads(path.read_text()).get("items", [])
    rows: list[dict] = []
    for item in items:
        lookup = item.get("lookup", {}) if isinstance(item, dict) else {}
        for value in lookup.values():
            if isinstance(value, list):
                rows.extend(row for row in value if isinstance(row, dict))
    unique = {}
    for row in rows:
        unique[row.get("id", json.dumps(row, sort_keys=True))] = row
    return sorted(
        unique.values(),
        key=lambda row: (
            int(row.get("fanedit_count") or 0),
            int(row.get("sequence_count") or 0),
        ),
        reverse=True,
    )


def matches_common(
    row: dict,
    *,
    query: str | None,
    source_id: str | None,
    proof_tier: str | None,
) -> bool:
    if source_id and row.get("source_id") != source_id and row.get("movie_key") != source_id:
        return False
    if proof_tier == "preferred" and selection_tier(row) != "preferred":
        return False
    if proof_tier and proof_tier != "preferred" and row.get("proof_tier") != proof_tier:
        return False
    return matches_text(row, query)


def matches_text(row: dict, query: str | None) -> bool:
    if not query:
        return True
    return query.casefold() in json.dumps(row, ensure_ascii=False).casefold()


def selection_tier(row: dict) -> str:
    if row.get("proof_tier") != "confirmed":
        return "candidate"
    if row.get("confidence") == "high" and int(row.get("fanedit_count") or 0) >= 2:
        return "preferred"
    if row.get("confidence") == "high" and int(row.get("recurrence_count") or 0) >= 2:
        return "preferred"
    return "confirmed"


def result(
    dataset_root: Path,
    command: str,
    items,
    *,
    total_matches,
    source_artifacts: list[str],
) -> dict:
    return {
        "command": command,
        "generated_at": now(),
        "dataset_root": str(dataset_root),
        "total_matches": total_matches,
        "items": items,
        "source_artifacts": [str(dataset_root / artifact) for artifact in source_artifacts],
        "proof_boundary": PROOF_BOUNDARY,
    }


def compact(value: dict) -> dict:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, [], {}, "")
    }


def dig(value: dict, *keys: str):
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def now() -> str:
    return datetime.now(UTC).isoformat()


def emit(value: dict) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
