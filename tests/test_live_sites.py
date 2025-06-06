from playwright.sync_api import sync_playwright
import pytest


@pytest.mark.live
def test_cineplanet_homepage():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            response = page.goto("https://www.cineplanet.com.pe/", timeout=10000)
            assert (
                response is not None
            ), "La respuesta fue None, puede que el sitio esté caído"
            assert response.status == 200
            assert page.url.startswith("https://www.cineplanet.com.pe/")
        finally:
            browser.close()
