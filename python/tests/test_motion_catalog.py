import hashlib
import json
from pathlib import Path

import pytest

from vibeedit import list_motion_components
from vibeedit.data import data_path
from vibeedit.motion import _apply_persistent_frame, _load_persistent_page, _motion_asset_server, _requires_webgpu, _settle_web_frames, document_for_frame, motion_render_plan


def _spec(identifier):
    return {
        "canvas": {"width": 640, "height": 360},
        "timeline": {"tracks": [{"order": 0, "items": [{"id": "motion", "kind": "motion", "placement": {"startFrame": 0, "durationFrames": 60}, "componentId": identifier, "props": {}}]}]},
    }


def test_all_portable_motion_components_seek_deterministically():
    components = list_motion_components()
    assert len(components) == 50
    assert len({component["id"] for component in components}) == 50
    for component in components:
        early = document_for_frame(_spec(component["id"]), 2)
        late = document_for_frame(_spec(component["id"]), 42)
        assert early == document_for_frame(_spec(component["id"]), 2)
        assert early != late
        assert "data-vibeedit-component=" in early
        assert "<script" not in early
        assert "http://" not in early and "https://" not in early


def test_motion_validation_report_records_both_runtimes():
    report = json.loads(data_path("catalog", "motion-validation.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert report["cases"] == 50
    assert len(report["javascriptSha256"]) == 64
    assert len(report["pythonSha256"]) == 64


def test_canonical_text_runtime_is_manifest_bound():
    components = list_motion_components()
    assert len([component for component in components if component.get("canonical")]) == 30
    root = data_path("catalog", "text-runtime")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == "vibeedit.canonical-text-runtime.v1"
    assert len(manifest["files"]) == 151
    for record in manifest["files"]:
        payload = (root / record["path"]).read_bytes()
        assert len(payload) == record["bytes"], record["path"]
        assert hashlib.sha256(payload).hexdigest() == record["sha256"], record["path"]


def test_canonical_seeking_uses_canvas_frame_rate():
    spec = _spec("vibeedit://text/mogrt-elegant")
    spec["canvas"]["frameRate"] = {"numerator": 24, "denominator": 1}
    assert 'data-vibeedit-time="0.500000"' in document_for_frame(spec, 12, "http://127.0.0.1:1234/")


def test_every_registered_text_effect_has_a_verified_hash_bound_preview():
    catalog = json.loads(data_path("catalog", "catalog.json").read_text(encoding="utf-8"))
    assets = json.loads(data_path("catalog", "assets.json").read_text(encoding="utf-8"))
    text = [item for item in catalog["items"] if item["id"].startswith("vibeedit://text/")]
    by_path = {asset["path"]: asset for asset in assets["assets"]}

    assert len(text) == 52
    assert len({item["id"] for item in text}) == 52
    for item in text:
        assert item["preview"]["status"] == "verified", item["id"]
        assert item["preview"]["mediaType"] == "video/mp4", item["id"]
        asset_path = f"catalog/{item['preview']['uri']}"
        assert asset_path in by_path, item["id"]
        asset = by_path[asset_path]
        payload = data_path(asset_path).read_bytes()
        assert len(payload) == asset["bytes"], item["id"]
        assert hashlib.sha256(payload).hexdigest() == asset["sha256"], item["id"]
        assert asset["redistribution"] == "verified", item["id"]
        assert asset["decodable"] is True, item["id"]


def test_persistent_html_runtime_seeks_css_and_loads_project_fonts():
    playwright = pytest.importorskip("playwright.sync_api")
    spec = {
        "canvas": {"width": 640, "height": 360, "frameRate": {"numerator": 30, "denominator": 1}, "backgroundColor": "#101217"},
        "durationFrames": 30,
        "timeline": {
            "tracks": [
                {
                    "order": 10,
                    "items": [
                        {
                            "id": "agent-html",
                            "kind": "motion",
                            "placement": {"startFrame": 0, "durationFrames": 30},
                            "componentId": "vibeedit://motion/html",
                            "props": {
                                "html": '<div id="title">AGENT HTML</div>',
                                "css": "@font-face{font-family:TestPoppins;src:url('catalog/text-runtime/assets/fonts/Poppins-Bold.ttf');font-weight:700}#title{font:700 72px TestPoppins;animation:enter 1s linear both}@keyframes enter{from{transform:translateX(-200px);opacity:0}to{transform:translateX(100px);opacity:1}}",
                            },
                        }
                    ],
                }
            ]
        },
    }
    with playwright.sync_playwright() as runtime, _motion_asset_server(Path.cwd()) as urls:
        browser = runtime.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 640, "height": 360})
        page = context.new_page()
        _load_persistent_page(page, spec, urls)
        _apply_persistent_frame(page, spec, 0, urls["catalog"])
        _settle_web_frames(page, spec, 0)
        child = page.locator("iframe[data-vibeedit-web]").element_handle().content_frame()
        early = child.locator("#title").evaluate("element => ({transform:getComputedStyle(element).transform, font:getComputedStyle(element).fontFamily})")
        _apply_persistent_frame(page, spec, 15, urls["catalog"])
        _settle_web_frames(page, spec, 15)
        late = child.locator("#title").evaluate("element => ({transform:getComputedStyle(element).transform, font:getComputedStyle(element).fontFamily})")
        assert early["transform"] != late["transform"]
        assert "TestPoppins" in late["font"]
        assert child.evaluate("document.fonts.check('700 72px TestPoppins')") is True
        assert child.evaluate("isSecureContext") is True
        context.close()
        browser.close()


def test_motion_plan_keeps_arbitrary_webgpu_in_browser_until_conformant():
    spec = _spec("vibeedit://motion/web-project")
    spec["timeline"]["tracks"][0]["items"][0]["renderer"] = "auto"
    spec["timeline"]["tracks"][0]["items"][0]["props"] = {"entry": "dist/index.html", "javascript": "const adapter = await navigator.gpu.requestAdapter()"}
    plan = motion_render_plan(spec)
    assert plan["nativeRoutingEnabled"] is False
    assert plan["layers"][0]["selectedBackend"] == "chromium-persistent"
    assert plan["layers"][0]["nativeEligibility"] == "browser-required"
    assert plan["layers"][0]["libraries"] == ["webgpu"]
    assert _requires_webgpu(spec) is True


def test_local_webgpu_project_can_compile_wgsl_when_adapter_is_available():
    playwright = pytest.importorskip("playwright.sync_api")
    spec = _spec("vibeedit://motion/html")
    item = spec["timeline"]["tracks"][0]["items"][0]
    item["renderer"] = "webgpu"
    item["props"] = {"html": "<canvas></canvas>", "javascript": "window.vibeedit={seek(){}} // WGSL"}
    with playwright.sync_playwright() as runtime, _motion_asset_server(Path.cwd()) as urls:
        browser = runtime.chromium.launch(headless=True, args=["--enable-unsafe-webgpu"])
        page = browser.new_page(viewport={"width": 640, "height": 360})
        _load_persistent_page(page, spec, urls)
        child = page.locator("iframe[data-vibeedit-web]").element_handle().content_frame()
        result = child.evaluate(
            """async () => {
              const adapter = await navigator.gpu?.requestAdapter();
              if (!adapter) return {available: false};
              const device = await adapter.requestDevice();
              const module = device.createShaderModule({code: `
                @vertex fn vertex_main(@builtin(vertex_index) index: u32) -> @builtin(position) vec4f {
                  var points = array(vec2f(-1, -1), vec2f(3, -1), vec2f(-1, 3));
                  return vec4f(points[index], 0, 1);
                }
                @fragment fn fragment_main() -> @location(0) vec4f { return vec4f(0.3, 0.8, 1.0, 1.0); }
              `});
              const errors = (await module.getCompilationInfo()).messages.filter((message) => message.type === "error");
              return {available: true, errors: errors.map((error) => error.message)};
            }"""
        )
        browser.close()
    if not result["available"]:
        pytest.skip("pinned Chromium exposed WebGPU but no adapter on this host")
    assert result["errors"] == []
