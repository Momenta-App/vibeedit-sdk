import json

import pytest

from vibeedit.data import data_path


def test_catalog_site_exposes_search_compatibility_requirements_and_copyable_code():
    playwright = pytest.importorskip("playwright.sync_api")
    item = next(item for item in json.loads(data_path("catalog", "catalog.json").read_text())["items"] if item["id"] == "vibeedit://sfx/impact-procedural")
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(data_path("site", "index.html").as_uri())
        page.locator("#search").fill(item["id"])
        card = page.locator(".card")
        assert card.count() == 1
        card.locator("summary").click()
        assert card.locator(".compatibility").inner_text() == f"{' / '.join(item['platforms'])} · {' / '.join(item['backends'])}".upper()
        assert "ASSETS:" in card.locator(".requirements").inner_text()
        assert card.locator(".python-code").inner_text() == item["examples"]["python"]
        assert card.locator(".javascript-code").inner_text() == item["examples"]["javascript"]
        for selector in [".identifier", ".copy-prompt", ".copy-python", ".copy-javascript"]:
            card.locator(selector).click()
            playwright.expect(card.locator(selector)).to_have_text("COPIED")
        browser.close()
