from playwright.async_api import ElementHandle, Playwright, Browser, Page
from typing import List, Tuple
import asyncio


async def setup_browser(p: Playwright) -> Browser:
    return await p.chromium.launch(headless=False)


async def load_page(
    browser: Browser, url: str, selector_check: str
) -> Tuple[Browser, Page]:
    page = await browser.new_page()
    await page.goto(url)

    for _ in range(3):
        try:
            await page.wait_for_selector(selector_check, timeout=3000)
            break
        except:
            print("Contenido no cargó, refrescando página...")
            await page.reload()
            await asyncio.sleep(2)
    return page


async def extract_general_information(
    movie: ElementHandle,
    movie_data: dict,
    title_selector: str,
    movie_extra_info_selector: str,
    image_selector: str,
    splitter: str,
):
    title = await movie.query_selector(title_selector)
    movie_data["title"] = (await title.inner_text()).strip()

    # Extraer género, duración y restricción de edad
    keys = ["genre", "running_time", "age_restriction"]
    movie_extra_info = await movie.query_selector(movie_extra_info_selector)
    extras: List[ElementHandle] = (
        (await movie_extra_info.inner_text()).strip().split(splitter)
    )

    for key, extra in zip(keys, extras):
        movie_data[key] = extra

    # Extraer url de imagen
    image = await movie.query_selector(image_selector)
    movie_data["image_url"] = await image.get_attribute("src")


async def enter_movie_details_page(
    movie: ElementHandle, page: Page, button_selector: str, movie_details_selector: str
):
    button = await movie.query_selector(button_selector)
    await button.click()
    await page.wait_for_selector(movie_details_selector)
