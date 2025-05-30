from scrapers.utils.browser_utils import (
    setup_browser,
    load_page,
    extract_general_information,
    enter_movie_details_page,
)
from playwright.async_api import async_playwright
from unittest.mock import MagicMock, AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_setup_browser():
    async with async_playwright() as p:
        browser = await setup_browser(p)
        assert browser is not None
        await browser.close()


@pytest.mark.asyncio
async def test_load_page():
    # Creando mock
    browser_mock = MagicMock()
    page_mock = AsyncMock()

    # Definiendo la función
    browser_mock.new_page = AsyncMock(return_value=page_mock)

    # Testeando función
    result = await load_page(browser_mock, "https://url.com", ".test-selector")
    browser_mock.new_page.assert_called_once()
    page_mock.goto.assert_called_once_with("https://url.com")
    page_mock.wait_for_selector.assert_called_with(".test-selector", timeout=3000)

    # Comprobando resultados
    assert result == page_mock


@pytest.mark.asyncio
async def test_fail_load_page():
    # Creando mock
    browser_mock = MagicMock()
    page_mock = AsyncMock()

    # Definiendo la función
    browser_mock.new_page = AsyncMock(return_value=page_mock)

    # Forzando error
    page_mock.wait_for_selector = AsyncMock(
        side_effect=[Exception("fail"), Exception("fail"), None]
    )
    page_mock.reload = AsyncMock()

    with patch("asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        await load_page(browser_mock, "https://url.com", ".test-selector")

        # Verifica que hubo reintentos
        assert page_mock.wait_for_selector.call_count == 3
        assert page_mock.reload.call_count == 2
        assert sleep_mock.call_count == 2


@pytest.mark.asyncio
async def test_extract_general_information():
    # Creando argumentos para la función
    movie_data = {}
    title_selector = ".test-title-selector"
    movie_extra_info_selector = ".test-movie-extra-info-selector"
    image_selector = ".test-image-selector"
    splitter = ", "

    # Mocks que serán retornados por query_selector
    title_mock = AsyncMock()
    title_mock.inner_text = AsyncMock(return_value="Matrix")

    movie_extra_info_mock = AsyncMock()
    movie_extra_info_mock.inner_text = AsyncMock(return_value="Acción, 1h 45min, +14.")

    image_mock = AsyncMock()
    image_mock.get_attribute = AsyncMock(return_value="https://www.imagen.com")

    # Función query_selector
    async def fake_query_selector(selector):
        if selector == title_selector:
            return title_mock
        elif selector == movie_extra_info_selector:
            return movie_extra_info_mock
        elif selector == image_selector:
            return image_mock
        else:
            return "No matches found"

    # Mock principal
    movie_mock = MagicMock()
    movie_mock.query_selector = AsyncMock(side_effect=fake_query_selector)

    # Testeando función
    await extract_general_information(
        movie_mock,
        movie_data,
        title_selector,
        movie_extra_info_selector,
        image_selector,
        splitter,
    )

    # Corroborando resultados
    assert movie_data["title"] == "Matrix"
    assert movie_data["genre"] == "Acción"
    assert movie_data["running_time"] == "1h 45min"
    assert movie_data["age_restriction"] == "+14."
    assert movie_data["image_url"] == "https://www.imagen.com"


@pytest.mark.asyncio
async def test_enter_movie_details_page():
    movie_mock = MagicMock()
    button_mock = AsyncMock()
    page_mock = AsyncMock()

    button_selector = ".test-button-selector"
    movie_details_selector = ".test-movie-details-selector"
    movie_mock.query_selector = AsyncMock(return_value=button_mock)

    await enter_movie_details_page(movie_mock, page_mock, button_selector, movie_details_selector)
    button_mock.click.assert_called_once()
    page_mock.wait_for_selector.assert_called_with(movie_details_selector)
