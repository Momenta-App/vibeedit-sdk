# Fan-edit revision study

This experiment renders one five-moment fan edit through fourteen human-style revisions. It covers hook/effect changes, transition retiming, effect removal, SFX addition/removal, music changes, safe aftershock removal with retained audio, micro-aftershock restoration and trimming, final-impact and loudness passes, and no-op approval submissions.

Run from the repository root:

```bash
PYTHONPATH=python/src uv run --extra test python experiments/fan-edit-revision-study/run.py
```

The generated `review/` directory is deliberately flat: numbered videos, matching CompositionSpecs, provenance records, contact sheets, review notes, and the machine-readable report sit together. Generated media and source fixtures are excluded from package archives.

The runner clears only its own generated review artifacts before each pass, records whether it used an installed package or the source checkout, measures final integrated loudness and true peak, and compares every output with a clean reference. Arbitrary final-clip trims remain clean-rendered because encoded B-frame boundaries cannot yet guarantee an exact stream-copied prefix.

Text add/change/remove coverage lives in the companion `experiments/revision-stress-test/review/` sequence. The fan-edit sequence intentionally follows the no-text default unless a reference or story requirement supports typography.
