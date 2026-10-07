from vibeedit.browser_setup import native_paths
from vibeedit.data import data_path
from vibeedit.examples import create_example
from vibeedit.browser_render import load_job
from vibeedit.version import VERSION


def test_browser_example_is_an_ordinary_job(tmp_path):
    example = create_example("browser-composition", tmp_path)
    manifest, root, entry, fps, frames = load_job(example / "job.json")
    assert entry.name == "index.html"
    assert root == example.resolve()
    assert frames == 12
    assert str(fps) == "30000/1001"
    assert "renderFrame" in entry.read_text()


def test_native_runtime_uses_versioned_user_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("VIBEEDIT_CACHE_DIR", str(tmp_path))
    host, bridge = native_paths()
    assert host.is_relative_to(tmp_path / "cef" / VERSION)
    assert bridge.is_relative_to(tmp_path / "cef" / VERSION)
    assert data_path("browser-renderer", "host", "host.mm").is_file()
    assert data_path("browser-renderer", "surface-bridge", "src", "encoder.mm").is_file()
