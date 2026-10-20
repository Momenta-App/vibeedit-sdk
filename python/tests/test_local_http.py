import pytest

from vibeedit.local_http import is_local_browser_url


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:49123/catalog/font.ttf",
    "http://127.0.0.1:49123/project/clip.mp4?at=1",
    "data:image/png;base64,AAAA", "blob:http://127.0.0.1:49123/local", "about:blank",
])
def test_browser_accepts_only_origin_and_nonnetwork_resources(url):
    assert is_local_browser_url(url, "http://127.0.0.1:49123")


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:49123@outside.invalid/private",
    "http://127.0.0.1:49123@127.0.0.1:49124/private",
    "http://@127.0.0.1:49123/private",
    "http://127.0.0.1:49124/private", "https://127.0.0.1:49123/private",
    "http://outside.invalid/?http://127.0.0.1:49123", "file:///private/file",
    "http://127.0.0.1:491230/private", "http://[invalid/private",
])
def test_browser_denies_credentials_other_origins_and_invalid_ports(url):
    assert not is_local_browser_url(url, "http://127.0.0.1:49123")
