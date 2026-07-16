import hashlib
import json
from pathlib import Path

import pytest

from vibeedit import list_motion_atoms, list_motion_components
from vibeedit.data import data_path
from vibeedit.motion import MotionRenderError, _apply_persistent_frame, _html_css_document, _load_persistent_page, _motion_asset_server, _requires_webgpu, _settle_web_frames, document_for_frame, motion_render_plan


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


def test_raw_html_css_contract_is_discoverable_and_native_candidate():
    atoms = list_motion_atoms()
    assert atoms["componentId"] == "vibeedit://motion/html-css"
    assert atoms["javascript"] == "forbidden"
    assert {atom["name"] for atom in atoms["atoms"]} >= {"text", "enter", "shimmer", "blend", "tilt"}
    spec = _spec("vibeedit://motion/html-css")
    spec["timeline"]["tracks"][0]["items"][0]["props"] = {"html": '<h1 class="ve-text ve-enter">RAW CSS</h1>', "css": ".ve-text{color:papayawhip}"}
    plan = motion_render_plan(spec)
    assert plan["layers"][0]["authoringContract"] == "html-css-only"
    assert plan["layers"][0]["seekContract"] == "automatic-css-animations"
    assert plan["layers"][0]["nativeEligibility"] == "candidate-unverified"


def test_raw_html_css_accepts_full_documents_and_rejects_script_surfaces():
    document = _html_css_document(
        {
            "html": "<!doctype html><html lang=\"en\"><head><title>Raw</title></head><body><svg viewBox=\"0 0 10 10\"><circle cx=\"5\" cy=\"5\" r=\"4\"/></svg></body></html>",
            "css": "svg{filter:drop-shadow(0 0 2px white)}",
        },
        "http://127.0.0.1:1234/project/",
        "http://127.0.0.1:1234/atoms/v1.css",
    )
    assert document.count("<html") == 1
    assert document.count("<head") == 1
    assert 'href="http://127.0.0.1:1234/atoms/v1.css"' in document
    assert "script-src 'none'" in document
    assert "<svg" in document
    with pytest.raises(MotionRenderError, match="does not allow javascript"):
        _html_css_document({"html": "<h1>NO</h1>", "javascript": "alert(1)"}, "http://127.0.0.1/", None)
    with pytest.raises(MotionRenderError, match="<script>"):
        _html_css_document({"html": "<script>alert(1)</script>"}, "http://127.0.0.1/", None)
    with pytest.raises(MotionRenderError, match="event handlers"):
        _html_css_document({"html": '<div onclick="alert(1)">NO</div>'}, "http://127.0.0.1/", None)


def test_raw_html_css_atoms_render_and_seek_without_authored_javascript():
    playwright = pytest.importorskip("playwright.sync_api")
    spec = _spec("vibeedit://motion/html-css")
    spec["durationFrames"] = 30
    spec["canvas"].update({"frameRate": {"numerator": 30, "denominator": 1}, "backgroundColor": "#111"})
    spec["timeline"]["tracks"][0]["items"][0]["placement"]["durationFrames"] = 30
    spec["timeline"]["tracks"][0]["items"][0]["props"] = {
        "html": '<main class="ve-stage ve-center"><h1 id="title" class="ve-text ve-enter ve-gradient ve-shimmer ve-perspective ve-tilt" data-ve-from="bottom">ATOMS</h1><p id="blur" class="ve-text ve-blur-in ve-shadow">COMPOSED</p></main>',
        "css": ":root{--ve-duration:1s;--ve-rotate-y:18deg;--ve-gradient:linear-gradient(90deg,#fff,#8cf)}#title::after{content:' CSS';color:white}",
    }
    with playwright.sync_playwright() as runtime, _motion_asset_server(Path.cwd()) as urls:
        browser = runtime.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 640, "height": 360})
        _load_persistent_page(page, spec, urls)
        _apply_persistent_frame(page, spec, 0, urls["catalog"])
        _settle_web_frames(page, spec, 0)
        child = page.locator("iframe[data-vibeedit-html-css]").element_handle().content_frame()
        early = child.locator("#title").evaluate("element => ({transform:getComputedStyle(element).transform, translate:getComputedStyle(element).translate, background:getComputedStyle(element).backgroundImage, position:getComputedStyle(element).backgroundPosition, after:getComputedStyle(element, '::after').content})")
        early_blur = child.locator("#blur").evaluate("element => getComputedStyle(element).filter")
        _apply_persistent_frame(page, spec, 20, urls["catalog"])
        _settle_web_frames(page, spec, 20)
        late = child.locator("#title").evaluate("element => ({transform:getComputedStyle(element).transform, translate:getComputedStyle(element).translate, background:getComputedStyle(element).backgroundImage, position:getComputedStyle(element).backgroundPosition, after:getComputedStyle(element, '::after').content})")
        late_blur = child.locator("#blur").evaluate("element => getComputedStyle(element).filter")
        assert early["translate"] != late["translate"]
        assert early["position"] != late["position"]
        assert early["transform"] == late["transform"]
        assert early_blur != late_blur
        assert "drop-shadow" in late_blur
        assert "gradient" in late["background"]
        assert late["after"] == '" CSS"'
        assert child.locator("script").count() == 0
        browser.close()


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
