"""Real portable script proofs; synthetic alpha proves composition only."""
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"


def run(script, *args, check=True):
    return subprocess.run([sys.executable, str(script), *map(str, args)], check=check, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(ROOT / "python/src")})


def video(path, *, alpha=False):
    graph = "color=black:s=160x90:r=30:d=1,drawbox=x=70:y=30:w=20:h=30:color=white:t=fill" if alpha else "testsrc2=s=160x90:r=30:d=3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", graph, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)


def test_curtain_explicit_project_receipts_and_scope(tmp_path):
    video(tmp_path / "source.mp4")
    folder = SKILLS / "vibeedit-reverse-curtain-reveal/scripts"
    for orientation in ["horizontal", "vertical"]:
        result = run(folder / "render_reverse_curtain_reveal_effect.py", "--project", tmp_path, "--input", "source.mp4", "--source-start", 0, "--duration", 1.2, "--open-duration", .6, "--width", 160, "--height", 90, "--orientation", orientation, "--output-name", orientation + ".mp4")
        receipt = json.loads(result.stdout)
        assert receipt["status"] == "needs-editorial-review" and len(receipt["sourceSha256"]) == 64
        checked = run(folder / "quick_validate.py", "--project", tmp_path, "--receipt", "artifacts/curtain/" + orientation + "/receipt.json")
        assert json.loads(checked.stdout)["ok"]
    denied = run(folder / "render_reverse_curtain_reveal_effect.py", "--project", tmp_path, "--input", "../source.mp4", "--source-start", 0, check=False)
    assert denied.returncode != 0 and "project-relative" in denied.stderr
    exhausted = run(folder / "render_reverse_curtain_reveal_effect.py", "--project", tmp_path, "--input", "source.mp4", "--source-start", 2.5, "--duration", 2, check=False)
    assert exhausted.returncode != 0 and "final-frame hold" in exhausted.stderr


def test_subject_curtain_external_alpha_and_no_hold(tmp_path):
    video(tmp_path / "source.mp4")
    video(tmp_path / "alpha.mp4", alpha=True)
    folder = SKILLS / "vibeedit-reverse-curtain-subject-reveal/scripts"
    args = ["--project", tmp_path, "--input", "source.mp4", "--source-start", 0, "--source-end", 1, "--background-start", 1, "--background-end", 3, "--external-alpha", "alpha.mp4", "--duration", 1.2, "--open-duration", .6, "--width", 160, "--height", 90]
    for mode in ["subject_over_curtain", "subject_under_curtain"]:
        result = run(folder / "render_reverse_curtain_subject_reveal_effect.py", *args, "--layer-mode", mode, "--background-mode", "random_frame_stutter", "--output-name", mode + ".mp4")
        receipt = json.loads(result.stdout)
        assert receipt["config"]["externalAlpha"] == "alpha.mp4" and receipt["validation"]["subjectHasNoEndHold"]
        checked = run(folder / "quick_validate.py", "--project", tmp_path, "--receipt", "artifacts/curtain/" + mode + "/receipt.json")
        assert json.loads(checked.stdout)["ok"]
    short = run(folder / "render_reverse_curtain_subject_reveal_effect.py", *args, "--source-end", .1, "--output-name", "too-short.mp4", check=False)
    assert short.returncode != 0 and "no final-frame hold" in short.stderr


def test_portable_fonts_and_optional_voice_probe(tmp_path):
    run(SKILLS / "clean-text-animation/scripts/render_clean_text.py", "--text", "Follow for more", "--output", tmp_path / "clean.mp4", "--contact-sheet", tmp_path / "clean.jpg", "--size", "320x180", "--font-size", 24, "--duration", .4, "--hold", .1, "--shimmer", "last")
    assert (tmp_path / "clean.mp4").stat().st_size > 1000
    run(SKILLS / "negative/scripts/run_negative_gauntlet.py", "--out-dir", tmp_path / "negative", "--no-video")
    assert json.loads((tmp_path / "negative/gauntlet-report.json").read_text(encoding="utf-8"))["pass"]
    probe = run(SKILLS / "vibeedit-bs-roformer-voice-isolation/scripts/isolate_voice_bs_roformer.py", "--probe")
    receipt = json.loads(probe.stdout)
    assert receipt["requiredVersion"] == "0.47.0" and receipt["inferenceQualified"] is False


def test_router_dry_plan_no_private_harness(tmp_path):
    script = SKILLS / "vibeedit-viral-source-edit-router/scripts/package_viral_source_edit_plans.py"
    run(script, "--out-dir", tmp_path / "plans", "--package-id", "local-fixture")
    plan = next((tmp_path / "plans").glob("*/edit-plan.json"))
    result = subprocess.run(["bun", str(script.with_name("validate_viral_source_edit_router.ts")), str(plan)], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout)["ok"]
