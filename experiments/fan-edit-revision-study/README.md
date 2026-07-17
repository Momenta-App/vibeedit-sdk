# Fan-edit revision study

This experiment renders one five-moment fan edit through eight human-style revisions. It covers hook/effect changes, transition retiming, effect removal, SFX addition/removal, music changes, safe aftershock removal with retained audio, and a no-op submission.

Run from the repository root:

```bash
PYTHONPATH=python/src uv run --extra test python experiments/fan-edit-revision-study/run.py
```

The generated `review/` directory is deliberately flat: numbered videos, matching CompositionSpecs, provenance records, contact sheets, review notes, and the machine-readable report sit together. Generated media and source fixtures are excluded from package archives.

Text add/change/remove coverage lives in the companion `experiments/revision-stress-test/review/` sequence. The fan-edit sequence intentionally follows the no-text default unless a reference or story requirement supports typography.
