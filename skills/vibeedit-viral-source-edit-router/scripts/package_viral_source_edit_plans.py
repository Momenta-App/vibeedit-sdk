#!/usr/bin/env python3
"""
Generate dry-run viral source edit plan packages.

The generator writes local wiki packages only. It never renders, edits raw media,
or mutates project files. Creed corpus indexes are used as optional learned
evidence when present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_CORPUS = Path("fan_Edit_Data/workspace/reference-corpora/creed-analysis-dataset")
DEFAULT_OUT = DEFAULT_CORPUS / "derived/viral-source-edit-gauntlet"
PROOF_STATES = [
    "learned",
    "inferred",
    "candidate",
    "preferred",
    "confirmed",
    "planned",
    "tested",
    "reviewed",
    "accepted",
]
LANE_PRESETS = [
    {
        "slug": "legacy-pressure",
        "label": "legacy pressure",
        "themes": ["legacy_identity", "combat_proof", "self_proof"],
        "song_section": "hook-to-drop",
        "target_duration_sec": 24.0,
    },
    {
        "slug": "rivalry-breakpoint",
        "label": "rivalry breakpoint",
        "themes": ["rivalry", "combat_proof", "identity_pressure"],
        "song_section": "pre-drop-to-peak",
        "target_duration_sec": 18.0,
    },
    {
        "slug": "training-resolve",
        "label": "training resolve",
        "themes": ["training", "self_proof", "family_aftershock"],
        "song_section": "build-to-aftershock",
        "target_duration_sec": 28.0,
    },
    {
        "slug": "quiet-aftershock",
        "label": "quiet aftershock",
        "themes": ["family_aftershock", "consequence", "mentor_stakes"],
        "song_section": "break-to-loop",
        "target_duration_sec": 20.0,
    },
]


def main() -> int:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    generated = (
        generate_sample_packages(args, out_dir)
        if args.sample_creed
        else [generate_input_package(args, out_dir)]
    )
    packages = collect_package_summaries(out_dir, generated)

    manifest = {
        "schema_version": "vibeedit.viral_source_edit_gauntlet.manifest.v1",
        "generated_at": now(),
        "mode": "sample_creed" if args.sample_creed else "input",
        "generated_this_run_count": len(generated),
        "package_count": len(packages),
        "generated_this_run": generated,
        "packages": packages,
        "proof_boundary": "Dry-run planning packages only; no render, source mutation, project mutation, preview, review, or acceptance is claimed.",
    }
    write_json(out_dir / "index.json", manifest)
    print(f"generated {len(generated)} package(s)")
    for item in generated:
        print(item["package_path"])
    print(f"manifest {out_dir / 'index.json'}")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="Generate dry-run viral source edit planning packages.")
    parser.add_argument("--source", help="Optional source/movie manifest JSON.")
    parser.add_argument("--song", help="Optional song manifest JSON.")
    parser.add_argument("--creed-corpus", default=str(DEFAULT_CORPUS), help="Optional Creed corpus root.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT), help="Output directory for generated packages.")
    parser.add_argument("--package-id", help="Optional package id for input mode.")
    parser.add_argument("--sample-creed", action="store_true", help="Generate several dry-run sample packages from Creed learned evidence.")
    parser.add_argument("--limit", type=int, default=4, help="Sample package count.")
    return parser.parse_args()


def generate_sample_packages(args, out_dir: Path):
    corpus = load_creed_corpus(Path(args.creed_corpus))
    selected = LANE_PRESETS[: max(1, args.limit)]
    return [write_package(out_dir, build_sample_plan(corpus, lane, index)) for index, lane in enumerate(selected)]


def generate_input_package(args, out_dir: Path):
    source = load_optional_json(args.source) or {
        "title": "Untitled source",
        "source_id": "future-source",
        "aspect_ratio": "source",
        "moments": [],
    }
    song = load_optional_json(args.song) or {
        "title": "Untitled song",
        "artist": "unknown",
        "duration_sec": 24.0,
        "sections": default_song_sections(24.0),
    }
    plan = build_input_plan(source, song, args.package_id)
    return write_package(out_dir, plan)


def load_creed_corpus(root: Path):
    return {
        "root": str(root),
        "source_moments": load_items(root / "crosswalks/fanedit_general_source_moment_index.json"),
        "source_sequences": load_items(root / "crosswalks/fanedit_general_source_sequence_index.json"),
        "story": load_items(root / "crosswalks/story_structure_index.json"),
        "quotes": load_items(root / "crosswalks/quote_audio_visual_alignment_index.json"),
        "recipes": load_items(root / "crosswalks/skill_recipe_evidence_index.json"),
        "songs": load_items(root / "audio_beat_song_index.json"),
    }


def load_items(path: Path):
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        return data.get("items", [])
    if isinstance(data, list):
        return data
    return []


def load_optional_json(path):
    if not path:
        return None
    return json.loads(Path(path).read_text())


def build_sample_plan(corpus, lane, index):
    story_rows = rank_story_rows(corpus["story"], lane)
    story_row = story_rows[index % len(story_rows)] if story_rows else {}
    fanedit_id = story_row.get("fanedit_id", f"sample-{lane['slug']}")
    moments = select_moments(corpus["source_sequences"] or corpus["source_moments"], fanedit_id, lane)
    song = song_profile(next((item for item in corpus["songs"] if item.get("fanedit_id") == fanedit_id), {}), lane)
    quotes = [item for item in corpus["quotes"] if item.get("fanedit_id") == fanedit_id][:3]
    recipes = [item for item in corpus["recipes"] if item.get("fanedit_id") == fanedit_id][:2]
    package_id = f"sample-{lane['slug']}-{fanedit_id}"
    return build_plan(
        package_id=package_id,
        mode="sample_creed_dry_run",
        source_profile={
            "title": "Creed corpus learned evidence sample",
            "source_id": "creed-corpus",
            "aspect_ratio": "source",
            "source_aspect_ratio_policy": "preserve source aspect ratio by default",
            "input_kind": "optional learned evidence",
        },
        song=song,
        lane=lane,
        story_row=story_row,
        source_candidates=moments,
        quotes=quotes,
        recipes=recipes,
        learned_from=[corpus["root"]],
    )


def build_input_plan(source, song, package_id):
    lane = {
        "slug": slugify(source.get("lane") or source.get("title") or "future-source"),
        "label": source.get("lane") or "future source edit",
        "themes": source.get("themes", ["source_identity", "emotional_turn", "payoff"]),
        "song_section": "provided-song-map",
        "target_duration_sec": float(song.get("duration_sec") or source.get("target_duration_sec") or 24.0),
    }
    source_candidates = [
        normalize_source_candidate(moment, index, source.get("source_id", "future-source"))
        for index, moment in enumerate(source.get("moments", []))
    ]
    return build_plan(
        package_id=package_id or f"future-{lane['slug']}-{stable_id(source.get('title', 'source'))}",
        mode="input_dry_run",
        source_profile={
            "title": source.get("title", "Untitled source"),
            "source_id": source.get("source_id", "future-source"),
            "aspect_ratio": source.get("aspect_ratio", "source"),
            "source_aspect_ratio_policy": "preserve source aspect ratio by default",
            "input_kind": "user supplied manifest" if source.get("moments") else "placeholder manifest",
        },
        song=song_profile(song, lane),
        lane=lane,
        story_row={},
        source_candidates=source_candidates,
        quotes=source.get("quotes", []),
        recipes=source.get("sfx", []),
        learned_from=[],
    )


def build_plan(package_id, mode, source_profile, song, lane, story_row, source_candidates, quotes, recipes, learned_from):
    sections = build_sections(lane["target_duration_sec"], song)
    clip_plan = align_clips_to_sections(source_candidates, sections)
    transition_plan = build_transition_plan(clip_plan, sections, song)
    effects_plan = build_effects_plan(sections, transition_plan, song)
    proof = build_proof_ledger(mode, source_profile, song, lane, story_row, clip_plan, quotes, recipes, learned_from)
    return {
        "schema_version": "vibeedit.viral_source_edit_package.v1",
        "package_id": package_id,
        "generated_at": now(),
        "mode": mode,
        "defaults": {
            "aspect_ratio": "source",
            "text_overlays": False,
            "render": False,
            "mutate_source": False,
            "mutate_project": False,
        },
        "source_profile": source_profile,
        "story_lane": {
            "slug": lane["slug"],
            "label": lane["label"],
            "themes": lane["themes"],
            "thesis": f"the edit where {lane['label']} turns source recognition into an earned payoff",
            "source_story_summary": story_row.get("summary", {}).get("grammar_summary") if story_row else None,
        },
        "song_profile": song,
        "sections": sections,
        "clip_plan": clip_plan,
        "transition_plan": transition_plan,
        "effects_plan": effects_plan,
        "quote_plan": build_quote_plan(quotes),
        "sfx_plan": build_sfx_plan(recipes, sections),
        "text_policy": {
            "overlays_enabled": False,
            "boundary": "No renderable text overlays by default; section names and quote roles remain metadata.",
        },
        "renderability": {
            "state": "planned",
            "blocked_claims": ["tested", "reviewed", "accepted", "rendered", "previewed"],
            "notes": "Package is execution-ready planning data only.",
        },
        "proof_ledger": proof,
    }


def rank_story_rows(rows, lane):
    def score(row):
        summary = row.get("summary", {})
        themes = set(summary.get("themes", []))
        return len(themes.intersection(lane["themes"])), summary.get("confidence") == "medium"

    ranked = sorted(rows, key=score, reverse=True)
    return ranked or rows


def select_moments(rows, fanedit_id, lane):
    selected = [normalize_creed_candidate(item) for item in rows if item.get("fanedit_id") == fanedit_id]
    if selected:
        return selected[:8]
    scored = sorted(
        rows,
        key=lambda item: sum(token in json.dumps(item).lower() for token in lane["themes"]),
        reverse=True,
    )
    return [normalize_creed_candidate(item) for item in scored[:8]]


def normalize_creed_candidate(item):
    window = item.get("approx_source_window", {})
    return {
        "id": item.get("id"),
        "source_id": item.get("source_id"),
        "source_shot_id": item.get("source_shot_id"),
        "start_sec": window.get("start_sec"),
        "end_sec": window.get("end_sec"),
        "story_function": item.get("story_function", "source_moment"),
        "vibe": item.get("moment_vibe"),
        "source_event_preview": item.get("source_event_preview", []),
        "proof_state": item.get("proof_tier", "candidate"),
        "confidence": item.get("confidence"),
        "proof_boundary": item.get("proof_boundary"),
    }


def normalize_source_candidate(item, index, source_id):
    return {
        "id": item.get("id", f"{source_id}-moment-{index:03d}"),
        "source_id": item.get("source_id", source_id),
        "source_shot_id": item.get("source_shot_id"),
        "start_sec": item.get("start_sec"),
        "end_sec": item.get("end_sec"),
        "story_function": item.get("story_function", "source_moment"),
        "vibe": item.get("vibe") or item.get("description"),
        "source_event_preview": item.get("source_event_preview", []),
        "proof_state": item.get("proof_state", "candidate"),
        "confidence": item.get("confidence"),
        "proof_boundary": item.get("proof_boundary", "Future input candidate; confirm against source before execution."),
    }


def song_profile(item, lane):
    evidence = item.get("evidence", {}) if isinstance(item.get("evidence"), dict) else {}
    duration = float(item.get("duration_sec") or evidence.get("duration_sec") or lane["target_duration_sec"])
    return {
        "title": item.get("title", "Provided or learned song section"),
        "artist": item.get("artist", "unknown"),
        "duration_sec": duration,
        "bpm": item.get("bpm") or evidence.get("bpm"),
        "beats": item.get("beats") or evidence.get("beats") or [],
        "energy": item.get("energy") or evidence.get("energy"),
        "song_section_strategy": lane["song_section"],
        "sections": item.get("sections") or default_song_sections(duration),
        "proof_boundary": item.get("proof_boundary", "Song sections are planner assumptions unless supplied by analyzed beat/song metadata."),
    }


def default_song_sections(duration):
    points = [0, duration * 0.14, duration * 0.34, duration * 0.58, duration * 0.82, duration]
    names = ["hook", "setup", "build", "drop_peak", "aftershock"]
    return [
        {
            "name": names[index],
            "start_sec": round(points[index], 3),
            "end_sec": round(points[index + 1], 3),
            "energy": ["medium", "low", "rising", "high", "falling"][index],
        }
        for index in range(len(names))
    ]


def build_sections(duration, song):
    roles = ["hook", "setup", "build", "drop", "peak", "aftershock", "loop"]
    weights = [0.12, 0.16, 0.2, 0.14, 0.18, 0.14, 0.06]
    start = 0.0
    sections = []
    for index, role in enumerate(roles):
        end = duration if index == len(roles) - 1 else start + duration * weights[index]
        song_ref = song["sections"][min(index, len(song["sections"]) - 1)] if song.get("sections") else {}
        sections.append(
            {
                "role": role,
                "timeline": {"start_sec": round(start, 3), "end_sec": round(end, 3)},
                "song_reference": song_ref,
                "sync_target": sync_target_for(role),
                "proof_state": "planned",
            }
        )
        start = end
    return sections


def align_clips_to_sections(candidates, sections):
    if not candidates:
        return [
            {
                "section": section["role"],
                "timeline": section["timeline"],
                "source_candidate": None,
                "selection_state": "candidate",
                "rationale": "Needs future source candidate selection.",
                "proof_boundary": "No source moment supplied; do not render.",
            }
            for section in sections
        ]
    return [
        {
            "section": section["role"],
            "timeline": section["timeline"],
            "source_candidate": candidates[index % len(candidates)],
            "selection_state": "preferred" if index < len(candidates) else "candidate",
            "rationale": f"Maps {section['role']} to source vibe while preserving non-chronological payoff order.",
            "proof_boundary": "Preferred planning choice only; confirm exact source range before edit execution.",
        }
        for index, section in enumerate(sections)
    ]


def build_quote_plan(quotes):
    if not quotes:
        return {
            "architecture": "music-led or source-sound-led",
            "quote_slots": [],
            "proof_state": "candidate",
            "boundary": "No quote is required by default; add only confirmed source dialogue or supplied quote ranges.",
        }
    return {
        "architecture": "hybrid quote-led",
        "quote_slots": [
            {
                "id": item.get("id", f"quote-{index:03d}"),
                "timeline": item.get("edit_time"),
                "role": item.get("role", "quote accent"),
                "status": item.get("status", "candidate"),
                "proof_state": "candidate",
                "boundary": item.get("proof_boundary") or "Transcript match may exist; visual/audio source confirmation remains unresolved.",
            }
            for index, item in enumerate(quotes)
        ],
        "proof_state": "candidate",
        "boundary": "Quote timing must become confirmed audio before render.",
    }


def build_sfx_plan(recipes, sections):
    motifs = ["impact accent", "air pull", "hit stop", "silence pocket", "sub drop"]
    learned = [
        {
            "source": item.get("id", f"recipe-{index:03d}"),
            "status": item.get("status", "partial"),
            "candidate_source_ids": item.get("candidate_source_ids", []),
            "proof_boundary": item.get("proof_boundary", "Recipe evidence is planning-only."),
        }
        for index, item in enumerate(recipes)
    ]
    return {
        "default_density": "selective",
        "learned_recipe_evidence": learned,
        "spots": [
            {
                "section": section["role"],
                "timeline": section["timeline"],
                "motif": motifs[index % len(motifs)],
                "proof_state": "planned",
                "boundary": "SFX spot is planned only; asset selection and mix review are not done.",
            }
            for index, section in enumerate(sections)
            if section["role"] in {"hook", "drop", "peak", "aftershock"}
        ],
    }


def build_transition_plan(clip_plan, sections, song):
    posture = transition_posture(song, sections)
    cuts = [
        build_transition_decision(clip_plan[index - 1], clip_plan[index], sections[index], posture, index)
        for index in range(1, len(clip_plan))
    ]
    return {
        "role": "viral_transition_reviewer",
        "proof_state": "planned",
        "skill": "vibeedit-viral-transition-reviewer",
        "posture": posture,
        "cuts_reviewed": cuts,
        "downstream_skill_library": [
            "vibeedit-transition-editor",
            "vibeedit-flash-subject-transition",
            "vibeedit-sam31-mlx-flash-subject-transition",
            "vibeedit-masking-router",
            "vibeedit-segmentation-cutouts",
            "vibeedit-sam21-video-segmentation",
            "vibeedit-reverse-curtain-reveal",
            "vibeedit-reverse-curtain-subject-reveal",
            "vibeedit-tile-object-reveal",
            "vibeedit-random-frame-stutter",
            "vibeedit-effects",
        ],
        "boundary": "Transition review is planned only; no preview, render, mask run, or timeline mutation happened.",
    }


def transition_posture(song, sections):
    high_energy_count = sum(1 for section in sections if energy_weight(section.get("song_reference", {}).get("energy")) >= 3)
    bpm = song.get("bpm")
    weight = "heavy" if bpm and bpm >= 140 and high_energy_count >= 2 else "medium" if high_energy_count >= 2 else "light"
    return {
        "weight": weight,
        "frequency": {
            "light": "mostly clean cuts with one or two transition accents",
            "medium": "selected section turns and strong beats",
            "heavy": "frequent transitions on high-energy cuts while preserving readability",
        }[weight],
        "rationale": "Transition weight is inferred from supplied song energy and dry-run cut density.",
    }


def build_transition_decision(previous_clip, next_clip, section, posture, index):
    section_energy = energy_weight(section.get("song_reference", {}).get("energy"))
    use_transition = section["role"] in {"drop", "peak"} or section_energy >= 3
    family = "subject_flash" if use_transition and section["role"] in {"drop", "peak"} else "motion_bridge" if use_transition else "clean_cut"
    return {
        "cut_id": f"cut-{index:02d}",
        "timeline_time": section["timeline"]["start_sec"],
        "from_clip": candidate_id(previous_clip),
        "to_clip": candidate_id(next_clip),
        "song_anchor": section["sync_target"],
        "decision": "transition" if use_transition else "clean_cut",
        "weight": posture["weight"] if use_transition else "none",
        "transition_family": family,
        "downstream_skills": transition_skills_for_family(family),
        "timeline_or_clip_change_allowed": family == "subject_flash",
        "requested_timeline_adjustment": "Confirm or shift clip B to a strong segmentable first-frame subject." if family == "subject_flash" else "",
        "mask_route": "needed" if family == "subject_flash" else "none",
        "proof_state": "planned",
        "boundary": "Per-cut decision only; downstream transition skill has not executed.",
    }


def transition_skills_for_family(family):
    if family == "subject_flash":
        return ["vibeedit-viral-transition-reviewer", "vibeedit-flash-subject-transition", "vibeedit-masking-router", "vibeedit-segmentation-cutouts"]
    if family == "motion_bridge":
        return ["vibeedit-viral-transition-reviewer", "vibeedit-transition-editor"]
    return ["vibeedit-viral-transition-reviewer"]


def build_effects_plan(sections, transition_plan, song):
    density = effect_density(song, transition_plan)
    anchors = build_effect_anchors(sections, transition_plan, song, density)
    selected = [anchor for anchor in anchors if anchor["selected_for_effect"]]
    return {
        "role": "viral_effects_reviewer",
        "proof_state": "planned",
        "skill": "vibeedit-viral-effects-reviewer",
        "density": density,
        "unused_audio_anchors": anchors,
        "events": [effect_event(anchor, index) for index, anchor in enumerate(selected)],
        "downstream_skill_library": [
            "vibeedit-effects",
            "vibeedit-effects-punctuation",
            "vibeedit-subject-effects",
            "vibeedit-sam31-mlx-subject-effects",
            "vibeedit-masking-router",
            "vibeedit-segmentation-cutouts",
            "vibeedit-sam21-video-segmentation",
            "vibeedit-color-style-recipes",
            "vibeedit-random-frame-stutter",
            "vibeedit-reverse-curtain-reveal",
            "vibeedit-tile-object-reveal",
        ],
        "structure_change_allowed": False,
        "boundary": "Effects review is additive planning only; it selects song anchors not already served by cuts or transitions, and no structure, preview, render, or mask execution changed.",
    }


def effect_density(song, transition_plan):
    transition_weight = transition_plan["posture"]["weight"]
    bpm = song.get("bpm") or 0
    if transition_weight == "heavy" or bpm >= 140:
        weight = "medium"
    elif transition_weight == "medium":
        weight = "light"
    else:
        weight = "light"
    return {
        "weight": weight,
        "rationale": "Effects fill unused musical anchors after transition decisions; density stays below or equal to transition intensity.",
    }


def build_effect_anchors(sections, transition_plan, song, density):
    cut_times = [item["timeline_time"] for item in transition_plan["cuts_reviewed"]]
    beats = song.get("beats") or []
    if beats:
        return [
            build_beat_effect_anchor(beat, cut_times, density, index)
            for index, beat in enumerate(beats[:12])
        ]
    return [
        build_section_effect_anchor(section, cut_times, density, index)
        for index, section in enumerate(sections)
        if section["role"] in {"hook", "build", "aftershock"}
    ]


def build_beat_effect_anchor(beat, cut_times, density, index):
    served_by_cut = any(abs(float(beat) - float(cut_time)) <= 0.08 for cut_time in cut_times)
    return {
        "anchor_id": f"beat-{index:02d}",
        "timeline_time": round(float(beat), 3),
        "song_reason": "supplied beat not used as a shot change" if not served_by_cut else "beat already served by cut or transition",
        "already_served_by": "transition_or_cut" if served_by_cut else "",
        "selected_for_effect": not served_by_cut,
        "proof_state": "planned",
    }


def build_section_effect_anchor(section, cut_times, density, index):
    time = section["timeline"]["start_sec"]
    served_by_cut = any(abs(float(time) - float(cut_time)) <= 0.08 for cut_time in cut_times)
    return {
        "anchor_id": f"anchor-{index:02d}",
        "timeline_time": time,
        "song_reason": section["sync_target"] if not served_by_cut else "section start already served by cut or transition",
        "already_served_by": "transition_or_cut" if served_by_cut else "",
        "selected_for_effect": not served_by_cut and density["weight"] in {"light", "medium", "heavy"},
        "proof_state": "planned",
    }


def effect_event(anchor, index):
    family = "subject_flash" if anchor["anchor_id"].startswith("beat-") else "shimmer"
    return {
        "effect_id": f"effect-{index + 1:02d}",
        "timeline_time": anchor["timeline_time"],
        "song_anchor": anchor["song_reason"],
        "source_subject": "selected source subject",
        "effect_family": family,
        "downstream_skills": effect_skills_for_family(family),
        "duration_frames": 1 if family == "subject_flash" else 12,
        "intensity": "medium" if family == "subject_flash" else "light",
        "mask_route": "needed" if family == "subject_flash" else "none",
        "structure_change_allowed": False,
        "proof_state": "planned",
        "boundary": "Additive effect only; downstream effect skill has not executed.",
    }


def effect_skills_for_family(family):
    if family == "subject_flash":
        return ["vibeedit-viral-effects-reviewer", "vibeedit-subject-effects", "vibeedit-masking-router"]
    if family == "shimmer":
        return ["vibeedit-viral-effects-reviewer", "vibeedit-effects-punctuation", "vibeedit-effects"]
    return ["vibeedit-viral-effects-reviewer", "vibeedit-effects"]


def energy_weight(value):
    return {
        "low": 1,
        "falling": 1,
        "medium": 2,
        "rising": 3,
        "high": 4,
        "drop": 4,
    }.get(str(value).lower(), 2)


def build_proof_ledger(mode, source_profile, song, lane, story_row, clip_plan, quotes, recipes, learned_from):
    entries = [
        ledger("package mode", mode, "planned", "Generator wrote a dry-run package."),
        ledger("aspect ratio policy", source_profile["aspect_ratio"], "planned", "Default is source aspect ratio."),
        ledger("text overlay policy", "disabled", "planned", "No on-screen text overlays by default."),
        ledger("story lane", lane["label"], "inferred", "Lane selected from preset or input metadata."),
        ledger("song structure", song.get("song_section_strategy"), "candidate", song.get("proof_boundary")),
    ]
    entries.extend(ledger("learned corpus", item, "learned", "Optional learned evidence source.") for item in learned_from)
    if story_row:
        entries.append(ledger("story grammar", story_row.get("id"), "learned", story_row.get("summary", {}).get("proof_boundary")))
    entries.extend(
        ledger(f"clip {item['section']}", candidate_id(item), item["selection_state"], item["proof_boundary"])
        for item in clip_plan
    )
    entries.extend(
        ledger("quote evidence", item.get("id", f"quote-{index}"), "candidate", item.get("proof_boundary") or item.get("status"))
        for index, item in enumerate(quotes)
    )
    entries.extend(
        ledger("recipe evidence", item.get("id", f"recipe-{index}"), "learned", item.get("proof_boundary"))
        for index, item in enumerate(recipes)
    )
    entries.extend(
        ledger(f"{state} boundary", "not claimed", "planned", "No operation promoted this package to this state.")
        for state in ["tested", "reviewed", "accepted"]
    )
    return {"allowed_states": PROOF_STATES, "state_boundaries": state_boundaries(), "entries": entries}


def ledger(subject, claim, state, evidence):
    return {
        "subject": subject,
        "claim": claim,
        "state": state if state in PROOF_STATES else "candidate",
        "evidence": evidence or "No direct evidence supplied.",
    }


def state_boundaries():
    return {
        "learned": "Observed in optional reference evidence, not proof for a future source.",
        "inferred": "Derived by planner from supplied metadata or reusable grammar.",
        "candidate": "Possible source, quote, SFX, or timing choice requiring confirmation.",
        "preferred": "Ranked planning choice among candidates before confirmation.",
        "confirmed": "Requires direct source/media inspection or authoritative user input.",
        "planned": "Written into this dry-run package.",
        "tested": "Requires executed test or preview workflow evidence.",
        "reviewed": "Requires recorded human or review-model inspection evidence.",
        "accepted": "Requires explicit final approval.",
    }


def candidate_id(item):
    candidate = item.get("source_candidate")
    if not candidate:
        return None
    return candidate.get("id") or candidate.get("source_shot_id") or candidate.get("source_id")


def write_package(out_dir: Path, plan):
    package_dir = out_dir / slugify(plan["package_id"])
    package_dir.mkdir(parents=True, exist_ok=True)
    file_map = {
        "index": "index.json",
        "memory": "memory.json",
        "edit_plan": "edit-plan.json",
        "proof_ledger": "proof-ledger.json",
        "source": "source.md",
        "story": "story.md",
        "song": "song.md",
        "quote": "quote.md",
        "transitions": "transitions.md",
        "effects": "effects.md",
        "sfx": "sfx.md",
        "qa": "qa.md",
        "readme": "README.md",
    }
    write_json(package_dir / "edit-plan.json", plan)
    write_json(package_dir / "proof-ledger.json", plan["proof_ledger"])
    write_json(package_dir / "memory.json", build_memory(plan, file_map))
    write_json(package_dir / "index.json", build_index(plan, file_map))
    write_markdown_docs(package_dir, plan)
    return {
        "package_id": plan["package_id"],
        "package_path": str(package_dir),
        "files": file_map,
    }


def collect_package_summaries(out_dir: Path, generated):
    generated_by_path = {item["package_path"]: item for item in generated}
    summaries = []
    for package_dir in sorted(item for item in out_dir.iterdir() if item.is_dir()):
        index_path = package_dir / "index.json"
        if str(package_dir) in generated_by_path:
            summaries.append(generated_by_path[str(package_dir)])
            continue
        if not index_path.exists():
            continue
        index = json.loads(index_path.read_text())
        summaries.append(
            {
                "package_id": index.get("package_id", package_dir.name),
                "package_path": str(package_dir),
                "files": index.get("file_map", {}),
            }
        )
    return summaries


def build_index(plan, file_map):
    return {
        "schema_version": "vibeedit.viral_source_edit_package.index.v1",
        "package_id": plan["package_id"],
        "generated_at": plan["generated_at"],
        "mode": plan["mode"],
        "file_map": file_map,
        "defaults": plan["defaults"],
        "proof_boundary": plan["renderability"]["notes"],
    }


def build_memory(plan, file_map):
    return {
        "schema_version": "vibeedit.local_edit_wiki_memory.v1",
        "package_id": plan["package_id"],
        "summary": plan["story_lane"]["thesis"],
        "source": plan["source_profile"],
        "song": plan["song_profile"],
        "text_overlays": False,
        "proof_states": PROOF_STATES,
        "local_docs": file_map,
        "next_steps": [
            "Confirm exact source/movie ranges.",
            "Confirm quote audio if using quote-led structure.",
            "Run transition review before effects and resolve any subject-flash clip-B or mask blockers.",
            "Run effects review additively after transition decisions without changing structure.",
            "Select real SFX assets and test mix.",
            "Only then promote planned items to tested, reviewed, or accepted.",
        ],
    }


def write_markdown_docs(package_dir: Path, plan):
    write_text(package_dir / "README.md", markdown_readme(plan))
    write_text(package_dir / "source.md", markdown_source(plan))
    write_text(package_dir / "story.md", markdown_story(plan))
    write_text(package_dir / "song.md", markdown_song(plan))
    write_text(package_dir / "quote.md", markdown_quote(plan))
    write_text(package_dir / "transitions.md", markdown_transitions(plan))
    write_text(package_dir / "effects.md", markdown_effects(plan))
    write_text(package_dir / "sfx.md", markdown_sfx(plan))
    write_text(package_dir / "qa.md", markdown_qa(plan))


def markdown_readme(plan):
    return f"""# {plan['package_id']}

Dry-run viral source edit package.

- Thesis: {plan['story_lane']['thesis']}
- Aspect ratio: {plan['source_profile']['aspect_ratio']}
- Text overlays: {str(plan['defaults']['text_overlays']).lower()}
- Render state: planned only

See `proof-ledger.json` before promoting any package claim.
"""


def markdown_source(plan):
    clips = "\n".join(
        f"- {item['section']}: {candidate_id(item) or 'unresolved'} | {item['selection_state']} | {item['proof_boundary']}"
        for item in plan["clip_plan"]
    )
    return f"""# Source

Source: {plan['source_profile']['title']}

Aspect-ratio policy: {plan['source_profile']['source_aspect_ratio_policy']}

## Candidate Moments

{clips}
"""


def markdown_story(plan):
    sections = "\n".join(
        f"- {item['role']} {item['timeline']['start_sec']:.3f}-{item['timeline']['end_sec']:.3f}s: {item['sync_target']}"
        for item in plan["sections"]
    )
    return f"""# Story

{plan['story_lane']['thesis']}

Themes: {', '.join(plan['story_lane']['themes'])}

Learned story summary: {plan['story_lane'].get('source_story_summary') or 'none'}

## Structure

{sections}
"""


def markdown_song(plan):
    song = plan["song_profile"]
    sections = "\n".join(
        f"- {item.get('name')}: {item.get('start_sec')} - {item.get('end_sec')}s | energy {item.get('energy')}"
        for item in song.get("sections", [])
    )
    return f"""# Song

Song: {song.get('title')} by {song.get('artist')}

BPM: {song.get('bpm')}

Strategy: {song.get('song_section_strategy')}

Proof boundary: {song.get('proof_boundary')}

## Sections

{sections}
"""


def markdown_quote(plan):
    slots = plan["quote_plan"].get("quote_slots", [])
    body = "\n".join(
        f"- {item['id']}: {item.get('timeline')} | {item['proof_state']} | {item['boundary']}"
        for item in slots
    ) or "- No quote slot required by default."
    return f"""# Quote

Architecture: {plan['quote_plan']['architecture']}

Boundary: {plan['quote_plan']['boundary']}

## Slots

{body}
"""


def markdown_transitions(plan):
    transition_plan = plan["transition_plan"]
    cuts = "\n".join(
        f"- {item['cut_id']} at {item['timeline_time']}s: {item['decision']} | {item['transition_family']} | {item['weight']} | skills {', '.join(item['downstream_skills'])}"
        for item in transition_plan["cuts_reviewed"]
    )
    return f"""# Transitions

Role: {transition_plan['role']}

Skill: {transition_plan['skill']}

Posture: {transition_plan['posture']['weight']} - {transition_plan['posture']['frequency']}

Boundary: {transition_plan['boundary']}

## Cuts Reviewed

{cuts}
"""


def markdown_effects(plan):
    effects_plan = plan["effects_plan"]
    anchors = "\n".join(
        f"- {item['anchor_id']} at {item['timeline_time']}s: selected={str(item['selected_for_effect']).lower()} | {item['song_reason']}"
        for item in effects_plan["unused_audio_anchors"]
    )
    events = "\n".join(
        f"- {item['effect_id']} at {item['timeline_time']}s: {item['effect_family']} | skills {', '.join(item['downstream_skills'])} | structure_change_allowed={str(item['structure_change_allowed']).lower()}"
        for item in effects_plan["events"]
    )
    return f"""# Effects

Role: {effects_plan['role']}

Skill: {effects_plan['skill']}

Density: {effects_plan['density']['weight']} - {effects_plan['density']['rationale']}

Boundary: {effects_plan['boundary']}

## Unused Audio Anchors

{anchors}

## Planned Additive Events

{events}
"""


def markdown_sfx(plan):
    spots = "\n".join(
        f"- {item['section']} {item['timeline']['start_sec']:.3f}-{item['timeline']['end_sec']:.3f}s: {item['motif']} | {item['boundary']}"
        for item in plan["sfx_plan"]["spots"]
    )
    return f"""# SFX

Default density: {plan['sfx_plan']['default_density']}

## Spots

{spots}
"""


def markdown_qa(plan):
    return f"""# QA

- [ ] Confirm source ranges before execution.
- [ ] Confirm quote audio before quote-led render.
- [ ] Confirm transition review ran before effects and every cut has a clean-cut or transition decision.
- [ ] Confirm subject-flash transitions have a strong clip-B subject and mask route before execution.
- [ ] Confirm effects are additive and do not change structure, clip selection, or transition decisions.
- [ ] Confirm SFX assets and mix.
- [ ] Keep story labels as metadata unless a text pass materializes final overlays.
- [ ] Preserve source aspect ratio unless explicitly overridden.
- [ ] Do not claim tested, reviewed, accepted, previewed, or rendered until evidence is recorded.

Current state: {plan['renderability']['state']}
"""


def write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_text(path: Path, text):
    path.write_text(text)


def sync_target_for(role):
    return {
        "hook": "recognition or quote pressure by 0.7s",
        "setup": "premise clarity and geography",
        "build": "motion or emotional escalation",
        "drop": "downbeat, impact, reveal, or source-sound punch",
        "peak": "strongest action or emotional proof",
        "aftershock": "breath, silence, consequence, or reaction",
        "loop": "restart-compatible unresolved image or hard ending",
    }[role]


def slugify(value):
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", str(value).lower()))[:96] or "package"


def stable_id(value):
    return hashlib.sha1(str(value).encode()).hexdigest()[:8]


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
