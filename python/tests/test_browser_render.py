import json
import os
import urllib.error
import urllib.request
from fractions import Fraction

import pytest
from vibeedit.browser_render import (
    HOST,
    BrowserRenderError,
    CEFService,
    load_job,
    project_server,
    render_browser_job,
)


def test_byte_ranges_and_symlink_escape(tmp_path):
    (tmp_path / "media.webm").write_bytes(bytes(range(100)))
    (tmp_path / "escape").symlink_to("/etc/hosts")
    with project_server(tmp_path) as url:
        with urllib.request.urlopen(
            urllib.request.Request(url + "media.webm", headers={"Range": "bytes=13-27"})
        ) as response:
            assert response.status == 206
            assert response.headers["Content-Range"] == "bytes 13-27/100"
            assert response.read() == bytes(range(13, 28))
        with urllib.request.urlopen(
            urllib.request.Request(url + "media.webm", headers={"Range": "bytes=-4"})
        ) as response:
            assert response.read() == bytes(range(96, 100))
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(url + "escape")
        assert error.value.code == 404


def test_manifest_rational_duration_and_boundary(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Example</h1>")
    manifest = {
        "entry": "index.html",
        "width": 320,
        "height": 180,
        "frameRate": {"numerator": 30000, "denominator": 1001},
        "duration": "1.001",
    }
    path = tmp_path / "job.json"
    path.write_text(json.dumps(manifest))
    assert load_job(path)[3:] == (Fraction(30000, 1001), 30)
    manifest["duration"] = "1"
    path.write_text(json.dumps(manifest))
    with pytest.raises(BrowserRenderError, match="exact integer"):
        load_job(path)
    manifest["entry"] = "../outside.html"
    path.write_text(json.dumps(manifest))
    with pytest.raises(BrowserRenderError, match="existing HTML"):
        load_job(path)


@pytest.mark.skipif(
    os.environ.get("VIBEEDIT_CEF_INTEGRATION") != "1",
    reason="explicit built CEF integration gate",
)
def test_built_host_static_async_capture_and_warm_recovery(tmp_path):
    import numpy as np
    from PIL import Image

    assert HOST.is_file()
    page = tmp_path / "index.html"
    page.write_text(
        """<!doctype html><style>body{margin:0;background:#123456;color:white}h1{font:40px Arial}</style><h1>OFFLINE</h1><canvas width="40" height="40" style="position:absolute;right:0;bottom:0"></canvas><script>window.renderFrame=async(frame)=>{if(frame===2)await new Promise(r=>setTimeout(r,80));document.querySelector('h1').textContent=frame<3?'STATIC':'READY '+frame;const c=document.querySelector('canvas').getContext('2d');c.fillStyle=`rgb(${frame<3?20:50+frame},100,180)`;c.fillRect(0,0,40,40)}</script>"""
    )
    job = tmp_path / "job.json"
    job.write_text(
        json.dumps(
            {
                "entry": "index.html",
                "width": 320,
                "height": 180,
                "frames": 6,
                "frameRate": {"numerator": 30000, "denominator": 1001},
            }
        )
    )
    with CEFService(timeout=10) as service:
        assert service.capabilities["windows"] == 0
        assert not service.capabilities["active"]
        for repeat in range(2):
            raw = tmp_path / f"frames{repeat}.bgra"
            screenshots = tmp_path / f"shots{repeat}"
            report = render_browser_job(
                job,
                tmp_path / f"video{repeat}.mp4",
                service=service,
                backend="cef",
                raw=raw,
                screenshots=screenshots,
            )
            assert report["frames"] == 6
            frames = np.memmap(raw, mode="r", dtype=np.uint8, shape=(6, 180, 320, 4))
            for index in range(6):
                reference = np.array(
                    Image.open(screenshots / f"{index:06d}.png").convert("RGBA")
                )
                assert np.array_equal(frames[index][:, :, [2, 1, 0, 3]], reference)
                assert tuple(frames[index, 160, 300, [2, 1, 0]]) == (
                    20 if index < 3 else 50 + index,
                    100,
                    180,
                )


@pytest.mark.skipif(
    os.environ.get("VIBEEDIT_CEF_INTEGRATION") != "1",
    reason="explicit built CEF integration gate",
)
def test_dynamic_waapi_uses_creation_time(tmp_path):
    import numpy as np

    (tmp_path / "index.html").write_text(
        """<style>body{margin:0;background:black}div{width:160px;height:90px;background:black}</style><div></div><script>window.renderFrame=(frame)=>{if(frame===3)document.querySelector('div').animate([{backgroundColor:'#000'},{backgroundColor:'#fff'}],{duration:100,fill:'forwards'})}</script>"""
    )
    job = tmp_path / "job.json"
    job.write_text(
        json.dumps({"entry": "index.html", "width": 160, "height": 90, "frames": 9})
    )
    with CEFService() as service:
        render_browser_job(
            job,
            tmp_path / "video.mp4",
            service=service,
            backend="cef",
            raw=tmp_path / "frames.bgra",
        )
    frames = np.memmap(
        tmp_path / "frames.bgra", mode="r", dtype=np.uint8, shape=(9, 90, 160, 4)
    )
    assert (
        np.abs(
            frames[:, 45, 80, 0].astype(int)
            - np.array([0, 0, 0, 0, 85, 170, 255, 255, 255])
        ).max()
        <= 1
    )


@pytest.mark.skipif(
    os.environ.get("VIBEEDIT_CEF_INTEGRATION") != "1",
    reason="explicit built CEF integration gate",
)
def test_gsap_delay_and_repeated_render_are_deterministic(tmp_path):
    import shutil

    import numpy as np
    from vibeedit.browser_render import ROOT

    shutil.copyfile(
        ROOT / "browser-renderer/examples/vendor/gsap.min.js",
        tmp_path / "gsap.js",
    )
    (tmp_path / "index.html").write_text(
        """<style>body{margin:0;background:black}div{width:160px;height:90px;background:white}</style><div></div><script src="gsap.js"></script><script>gsap.fromTo('div',{opacity:.2},{opacity:1,duration:1,delay:.2,ease:'none'});window.renderFrame=async(frame)=>{if(frame===0)await new Promise(resolve=>setTimeout(resolve,80))}</script>"""
    )
    job = tmp_path / "job.json"
    job.write_text(
        json.dumps({"entry": "index.html", "width": 160, "height": 90, "frames": 12})
    )
    captures = []
    with CEFService() as service:
        for repeat in range(2):
            raw = tmp_path / f"{repeat}.bgra"
            render_browser_job(
                job, tmp_path / f"{repeat}.mp4", service=service, backend="cef", raw=raw
            )
            captures.append(
                np.memmap(raw, mode="r", dtype=np.uint8, shape=(12, 90, 160, 4))
            )
    expected = np.array(
        [round(255 * (0.2 + 0.8 * max(0, frame / 30 - 0.2))) for frame in range(12)]
    )
    assert np.abs(captures[0][:, 45, 80, 0].astype(int) - expected).max() <= 1
    assert np.array_equal(captures[0], captures[1])


def test_fetch_keeps_original_media_bytes(tmp_path):
    import subprocess

    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=red:size=160x90:rate=30",
            "-frames:v",
            "3",
            "-c:v",
            "libx264",
            str(tmp_path / "movie.mp4"),
        ],
        check=True,
    )
    original = (tmp_path / "movie.mp4").read_bytes()
    conversions = {}
    with project_server(
        tmp_path, normalize=True, browser_version={}, conversions=conversions
    ) as url:
        assert urllib.request.urlopen(url + "movie.mp4").read() == original
        prepared = urllib.request.urlopen(
            urllib.request.Request(
                url + "movie.mp4", headers={"Sec-Fetch-Dest": "video"}
            )
        ).read()
        assert prepared != original
        assert conversions["movie.mp4"]["originalCodec"] == "h264"
        assert urllib.request.urlopen(url + "movie.mp4").read() == original


@pytest.mark.skipif(
    os.environ.get("VIBEEDIT_CEF_INTEGRATION") != "1",
    reason="explicit built CEF integration gate",
)
def test_render_frame_introduces_image_and_font(tmp_path):
    import shutil

    import numpy as np
    from PIL import Image
    from vibeedit.browser_render import ROOT

    shutil.copyfile(
        ROOT / "browser-renderer/examples/features/media/Roboto.ttf",
        tmp_path / "font.ttf",
    )
    Image.new("RGB", (160, 90), (40, 180, 220)).save(tmp_path / "image.png")
    (tmp_path / "index.html").write_text(
        """<style>@font-face{font-family:Late;src:url(font.ttf)}body{margin:0;background:black}img{position:absolute;left:0;top:0;width:160px;height:90px}h1{position:absolute;left:0;top:90px;margin:0;color:white;font:32px Late}</style><script>window.renderFrame=(frame)=>{if(frame===0)document.body.innerHTML='<img src="image.png"><h1>Roboto ready</h1>'}</script>"""
    )
    job = tmp_path / "job.json"
    job.write_text(
        json.dumps({"entry": "index.html", "width": 320, "height": 180, "frames": 3})
    )
    with CEFService() as service:
        report = render_browser_job(
            job,
            tmp_path / "movie.mp4",
            service=service,
            backend="cef",
            raw=tmp_path / "frames.bgra",
        )
    frames = np.memmap(
        tmp_path / "frames.bgra", mode="r", dtype=np.uint8, shape=(3, 180, 320, 4)
    )
    assert tuple(frames[0, 45, 80, [2, 1, 0]]) == (40, 180, 220)
    assert any(
        font["custom"] and "Roboto" in font["family"]
        for font in report["fontDiagnostics"]["platformFonts"]
    )


@pytest.mark.skipif(
    os.environ.get("VIBEEDIT_CEF_INTEGRATION") != "1",
    reason="explicit actual browser integration gate",
)
def test_screenshot_transport_deadline_and_fresh_recovery():
    import time

    from vibeedit.browser_render import ScreenshotService

    with ScreenshotService(timeout=2) as service:
        started = time.monotonic()
        with pytest.raises(BrowserRenderError, match="request exceeded"):
            service.call(
                "Runtime.evaluate",
                params={"expression": "new Promise(()=>{})", "awaitPromise": True},
            )
        assert time.monotonic() - started < 6
        assert service.closed
        assert not service.thread.is_alive()
    with ScreenshotService(timeout=10) as service:
        assert service.evaluate("1+1")["result"]["value"] == 2


@pytest.mark.skipif(
    os.environ.get("VIBEEDIT_CEF_INTEGRATION") != "1",
    reason="explicit built CEF integration gate",
)
def test_nested_browser_project_modules_fonts_and_capture(tmp_path):
    import shutil

    import numpy as np
    from PIL import Image
    from vibeedit.browser_render import ROOT

    shutil.copytree(
        ROOT / "browser-renderer/examples/features", tmp_path / "nested/site"
    )
    job = json.loads((tmp_path / "nested/site/job.json").read_text())
    job.update(entry="nested/site/index.html", frames=3)
    (tmp_path / "job.json").write_text(json.dumps(job))
    with CEFService() as service:
        report = render_browser_job(
            tmp_path / "job.json",
            tmp_path / "movie.mp4",
            backend="cef",
            service=service,
            raw=tmp_path / "frames.bgra",
            screenshots=tmp_path / "screenshots",
        )
    assert "nested/site/motion.js" in report["dependencyIdentities"]
    assert any(
        font["custom"] and font["family"] == "Roboto"
        for font in report["fontDiagnostics"]["platformFonts"]
    )
    frames = np.memmap(
        tmp_path / "frames.bgra",
        mode="r",
        dtype=np.uint8,
        shape=(3, job["height"], job["width"], 4),
    )
    for index in range(3):
        reference = np.array(
            Image.open(tmp_path / "screenshots" / f"{index:06d}.png").convert("RGBA")
        )
        assert np.array_equal(frames[index][:, :, [2, 1, 0, 3]], reference)
    assert not np.array_equal(frames[0], frames[2])


def test_media_preparation_error_survives_http_failure(tmp_path):
    (tmp_path / "invalid.mp4").write_bytes(b"invalid video")
    with pytest.raises(BrowserRenderError, match="Media preparation failed"):
        with project_server(tmp_path, normalize=True, browser_version={}) as url:
            urllib.request.urlopen(urllib.request.Request(url + "invalid.mp4", headers={"Sec-Fetch-Dest": "video"}))
