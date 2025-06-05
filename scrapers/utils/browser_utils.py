from playwright.async_api import Playwright, Browser, Page, Locator
from typing import List
import asyncio


async def setup_browser(p: Playwright) -> Browser:
    return await p.chromium.launch(headless=False)


async def load_page(
    browser: Browser, url: str, selector_check: str
) -> Page:
    page = await browser.new_page()
    await page.goto(url)
    page_selector = page.locator(selector_check)

    for _ in range(3):
        try:
            await page_selector.wait_for(timeout=3000)
            break
        except:
            print("Contenido no cargó, refrescando página...")
            await page.reload()
            await asyncio.sleep(2)
    return page


async def extract_general_information(
    movie: Locator,
    movie_data: dict,
    title_selector: str,
    movie_extra_info_selector: str,
    image_selector: str,
    splitter: str,
):
    title = movie.locator(title_selector)
    movie_data["title"] = (await title.inner_text()).strip()

    # Extraer género, duración y restricción de edad
    keys = ["genre", "running_time", "age_restriction"]
    movie_extra_info = movie.locator(movie_extra_info_selector)
    extras: List[Locator] = (
        (await movie_extra_info.inner_text()).strip().split(splitter)
    )

    for key, extra in zip(keys, extras):
        movie_data[key] = extra

    # Extraer url de imagen
    image = movie.locator(image_selector)
    movie_data["image_url"] = await image.get_attribute("src")


async def enter_movie_details_page(
    movie: Locator, page: Page, button_selector: str, movie_details_selector: str
):
    button = movie.locator(button_selector)
    await button.click()
    await page.locator(movie_details_selector).wait_for(timeout=3000)
