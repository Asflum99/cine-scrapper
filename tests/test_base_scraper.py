from scrapers.base_scraper import BaseScraper
from unittest.mock import MagicMock, AsyncMock, patch
from playwright.async_api import async_playwright
import pytest


class DummyScraper(BaseScraper):
    def scrape(self):
        pass


scraper = DummyScraper()


# Test para comprobar la impresión de la lista de elementos
@patch("scrapers.base_scraper.console.print")
@pytest.mark.refactor
def test_print_list_with_3_items_should_print_one_row(mock_print):
    # Creando lista de items
    test_items = ["hola", "chau", "adiós"]

    # Testeando
    scraper.print_list_of_items(test_items)

    # Obtener textos que se imprimieron
    args, _ = mock_print.call_args
    fila = args[0]

    # Haciendo comprobaciones
    assert mock_print.call_count == 1
    texto = fila.plain
    assert "1)" in texto and "hola" in texto
    assert "2)" in texto and "chau" in texto
    assert "3)" in texto and "adiós" in texto


@patch("scrapers.base_scraper.console.print")
@pytest.mark.refactor
def test_print_list_with_3_items_should_print_two_row(mock_print):
    # Creando lista de items
    test_items = [
        "comida",
        "refrigeradora",
        "emancipación",
        "construcción",
        "destellos",
        "inmaculada",
    ]

    # Testeando
    scraper.print_list_of_items(test_items)

    # Obtener argumentos
    printed = []
    for call in mock_print.call_args_list:
        args, _ = call
        fila = args[0]
        printed.append(fila.plain)

    total_text = "\n".join(printed)

    # Haciendo comprobaciones
    assert mock_print.call_count == 2
    for idx, item in enumerate(test_items, 1):
        assert f"{idx})" in total_text
        assert item in total_text


@pytest.mark.asyncio
async def test_setup_browser():
    async with async_playwright() as p:
        browser = await scraper.setup_browser(p)
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
    result = await scraper.load_page(browser_mock, "https://url.com", ".test-selector")
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
        await scraper.load_page(browser_mock, "https://url.com", ".test-selector")

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
    await scraper.extract_general_information(
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

    await scraper.enter_movie_details_page(
        movie_mock, page_mock, button_selector, movie_details_selector
    )
    button_mock.click.assert_called_once()
    page_mock.wait_for_selector.assert_called_with(movie_details_selector)
