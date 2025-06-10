from scrapers.base_scraper import BaseScraper
from unittest.mock import MagicMock, AsyncMock, patch
from scrapers.base_scraper import console
import pytest, asyncio


class DummyScraper(BaseScraper):
    def scrape(self):
        pass


@pytest.fixture
def scraper():
    return DummyScraper()


# Test para comprobar la impresión de la lista de elementos
def test_print_list_with_3_items_should_print_one_row(scraper, monkeypatch):
    # Lista a interceptar lo que se imprimiría
    printed = []

    def fake_print(fila):
        printed.append(fila.plain)  # Guardamos el Text completo

    # Interviniendo console.print
    monkeypatch.setattr(console, "print", fake_print)

    # Datos de prueba
    test_items = ["hola", "chau", "adiós"]

    # Ejecutar
    scraper.print_list_of_items(test_items)

    # Asegurarse de que algo se imprimió
    assert printed == ["1) hola      2) chau      3) adiós     "]


def test_print_list_with_3_items_should_print_two_row(scraper, monkeypatch):
    # Creando lista de items
    test_items = [
        "comida",
        "refrigeradora",
        "emancipación",
        "construcción",
        "destellos",
        "inmaculada",
    ]

    printed = []

    def fake_print(fila):
        printed.append(fila.plain)

    monkeypatch.setattr(console, "print", fake_print)

    scraper.print_list_of_items(test_items)

    assert (
        printed[0] == "1) comida            2) refrigeradora     3) emancipación      "
    )
    assert (
        printed[1] == "4) construcción      5) destellos         6) inmaculada        "
    )


@pytest.mark.asyncio
async def test_setup_browser(scraper):
    # Creando mocks
    chromium_mock = MagicMock()
    browser_mock = MagicMock()
    p_mock = MagicMock()
    p_mock.chromium = chromium_mock

    # Mockeando funciones
    chromium_mock.launch = AsyncMock(return_value=browser_mock)

    # Ejecutar
    result = await scraper.setup_browser(p_mock)

    # Verificar
    chromium_mock.launch.assert_awaited_once_with(headless=False)
    assert result is browser_mock


@pytest.mark.asyncio
async def test_load_page(scraper):
    # Creando mocks
    browser_mock = MagicMock()
    page_mock = MagicMock()
    page_selector_mock = MagicMock()

    # Mockeando funciones
    browser_mock.new_page = AsyncMock(return_value=page_mock)
    page_mock.goto = AsyncMock()
    page_mock.locator = MagicMock(return_value=page_selector_mock)
    page_selector_mock.wait_for = AsyncMock()

    # Testeando función
    result = await scraper.load_page(browser_mock, "https://url.com", ".test-selector")

    # Haciendo comprobaciones
    browser_mock.new_page.assert_called_once()
    page_mock.goto.assert_awaited_once_with("https://url.com")
    page_mock.locator.assert_called_once_with(".test-selector")
    page_selector_mock.wait_for.assert_awaited_once_with(timeout=3000)

    # Comprobando resultados
    assert result == page_mock


@pytest.mark.asyncio
async def test_fail_load_page(scraper):
    # Creando mock
    browser_mock = MagicMock()
    page_mock = MagicMock()
    page_selector_mock = MagicMock()

    # Definiendo la función
    browser_mock.new_page = AsyncMock(return_value=page_mock)
    page_mock.goto = AsyncMock()
    page_mock.locator = MagicMock(return_value=page_selector_mock)

    # Forzando error
    page_selector_mock.wait_for = AsyncMock(
        side_effect=[Exception("fail"), Exception("fail"), None]
    )
    page_mock.reload = AsyncMock()

    with patch.object(asyncio, "sleep", new_callable=AsyncMock) as sleep_mock:
        await scraper.load_page(browser_mock, "https://url.com", ".test-selector")

        # Verifica que hubo reintentos
        assert page_selector_mock.wait_for.call_count == 3
        assert page_mock.reload.call_count == 2
        assert sleep_mock.call_count == 2


@pytest.mark.asyncio
async def test_extract_general_information(scraper):
    # Creando mocks
    movie_mock = MagicMock()
    title_mock = MagicMock()
    movie_extra_info_mock = MagicMock()
    image_mock = MagicMock()
    movie_data = {}

    def side_effect(selector):
        if selector == "title-selector":
            return title_mock
        elif selector == "movie_extra_info_selector":
            return movie_extra_info_mock
        elif selector == "image_selector":
            return image_mock

    # Mockeando funciones
    movie_mock.locator = MagicMock(side_effect=side_effect)
    title_mock.inner_text = AsyncMock(return_value="  title-test ")
    movie_extra_info_mock.inner_text = AsyncMock(
        return_value="   Terror, 1h 30min, +14.   "
    )
    image_mock.get_attribute = AsyncMock(return_value="src-test")

    # Testeando
    await scraper.extract_general_information(
        movie_mock,
        movie_data,
        "title-selector",
        "movie_extra_info_selector",
        "image_selector",
        ", ",
    )

    assert movie_mock.locator.call_count == 3


@pytest.mark.asyncio
async def test_enter_movie_details_page(scraper):
    # Creando mocks
    movie_mock = MagicMock()
    button_mock = MagicMock()
    page_mock = MagicMock()

    # Mockeando funciones
    movie_mock.locator = MagicMock(return_value=button_mock)
    button_mock.click = AsyncMock()
    page_mock.locator = MagicMock(return_value=AsyncMock())

    # Testeando
    await scraper.enter_movie_details_page(movie_mock, page_mock, "button-test", "test")

    page_mock.locator.assert_called_once_with("test")
    button_mock.click.assert_awaited_once()
    movie_mock.locator.assert_called_once_with("button-test")
