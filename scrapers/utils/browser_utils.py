from playwright.async_api import ElementHandle, Playwright, Browser, Page
from typing import List, Tuple


async def setup_browser_and_load_page(p: Playwright, url: str) -> Tuple[Browser, Page]:
    browser = await p.chromium.launch(headless=False)
    page = await browser.new_page()
    await page.goto(url)
    return browser, page


async def extract_general_information(
    movie: ElementHandle,
    movie_data: dict,
    title_html: str,
    movie_extra_info_html: str,
    image_html: str,
    splitter: str,
):
    title = await movie.query_selector(title_html)
    movie_data["title"] = (await title.inner_text()).strip()

    # Extraer género, duración y restricción de edad
    keys = ["genre", "running_time", "age_restriction"]
    movie_extra_info = await movie.query_selector(movie_extra_info_html)
    extras: List[ElementHandle] = (await movie_extra_info.inner_text()).strip().split(splitter)

    for key, extra in zip(keys, extras):
        movie_data[key] = extra

    # Extraer url de imagen
    image = await movie.query_selector(image_html)
    movie_data["image_url"] = await image.get_attribute("src")


async def enter_movie_details_page(
    movie: ElementHandle, page: Page, button_html: str, movie_details_html: str
):
    button = await movie.query_selector(button_html)
    await button.click()
    await page.wait_for_selector(movie_details_html)