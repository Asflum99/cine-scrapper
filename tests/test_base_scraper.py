from scrapers.base_scraper import BaseScraper
from unittest.mock import MagicMock, AsyncMock, patch
from scrapers.base_scraper import console
from playwright.async_api import Locator
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


# Test para comprobar que se aplica el filtro
@pytest.mark.asyncio
async def test_apply_filters(scraper):
    # Interviniendo función
    def side_effect(*args, **kwargs):
        if args[1] == "Cine":
            return ("test-cine", True)
        elif args[1] == "Día":
            return ("test-dia", True)

    # Testeando
    with patch.object(
        scraper, "apply_specific_filter", side_effect=side_effect
    ) as apply_filter_mock:
        result = await scraper.apply_filters(
            MagicMock(),
            ["Cine", "Día"],
            "title-selector-test",
            "accordion-test",
            "item_selector-test",
        )

        assert result == ["test-cine", "test-dia"]
        assert apply_filter_mock.await_count == 2


# Test para comprobar filtro
@pytest.mark.asyncio
async def test_apply_specific_filter_success(scraper):
    # Creando mocks
    page_mock = MagicMock()
    title_element_mock = MagicMock()
    accordion_locator_mock = MagicMock()
    items_mock = MagicMock()

    def side_effect(selector):
        if selector == "title-selector-test":
            return title_element_mock
        elif selector == "accordion-selector-test":
            return accordion_locator_mock

    page_mock.locator.side_effect = side_effect

    # Mockeando funciones
    title_element_mock.count = AsyncMock(return_value=1)
    title_element_mock.nth.return_value.inner_text = AsyncMock(
        return_value="   test-name "
    )
    accordion_locator_mock.nth.return_value.get_attribute = AsyncMock(
        return_value="accordion_expanded"
    )
    accordion_locator_mock.nth.return_value.locator.return_value = items_mock

    # Testeando
    with patch.object(
        scraper, "select_filter", AsyncMock(return_value=("test", True))
    ) as mock_filter:
        result = await scraper.apply_specific_filter(
            page_mock,
            "test-name",
            "title-selector-test",
            "accordion-selector-test",
            "item-test",
        )

        assert result == ("test", True)
        mock_filter.assert_called_with(items_mock, page_mock, "test-name")
        page_mock.locator.assert_any_call("title-selector-test")
        page_mock.locator.assert_any_call("accordion-selector-test")
        title_element_mock.count.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_specific_filter_first_failure(scraper):
    # Creando mocks
    page_mock = MagicMock()

    # Mockeando funciones
    page_mock.locator.return_value = None

    # Testeando
    result = await scraper.apply_specific_filter(
        page_mock,
        "filter-name-test",
        "title-selector-test",
        "accordion-selector-test",
        "item-selector-test",
    )

    assert result == ("Missing filter title", False)


@pytest.mark.asyncio
async def test_apply_specific_filter_second_failure(scraper):
    # Creando mocks
    page_mock = MagicMock()
    title_element_mock = MagicMock()
    accordion_locator_mock = MagicMock()

    def side_effect(selector):
        if selector == "title-selector":
            return title_element_mock
        elif selector == "accordion-selector":
            return accordion_locator_mock

    # Mockeando funciones
    page_mock.locator.side_effect = side_effect
    title_element_mock.count = AsyncMock(return_value=1)
    title_element_mock.nth.return_value.inner_text = AsyncMock(return_value="  no-test ")

    # Testeando
    result = await scraper.apply_specific_filter(
        page_mock, "yes-test", "title-selector", "accordion-selector", "item-selector"
    )

    assert result == ("Filters don't matches", False)


# Test para comprobar la selección del filtro
@pytest.mark.asyncio
async def test_select_filter(scraper):
    # Creando mocks
    items_mock = MagicMock()
    page_mock = MagicMock()
    filter_mock = "ciudad"
    selected_item_mock = AsyncMock()

    items_mock.nth = MagicMock(return_value=selected_item_mock)
    selected_item_mock.inner_text = AsyncMock(return_value="  test ")
    selected_item_mock.click = AsyncMock()
    page_mock.wait_for_function = AsyncMock()

    with patch.object(scraper, "print_locators") as mock_print, patch.object(
        scraper, "ask_user_for_input", AsyncMock(return_value=1)
    ) as mock_ask:
        result = await scraper.select_filter(items_mock, page_mock, filter_mock)

        # Verifica llamadas
        mock_print.assert_called_once_with(items_mock)
        mock_ask.assert_called_once_with(items_mock, filter_mock)
        selected_item_mock.inner_text.assert_awaited_once()
        selected_item_mock.click.assert_awaited_once()
        page_mock.wait_for_function.assert_awaited_once()

        # Verifica resultado
        assert result == ("test", True)


# Test para comprobar la transformación de ElementHandle a str
@pytest.mark.asyncio
async def test_print_locators(scraper):
    # Creando mocks
    mock_items = MagicMock()
    mock_items.count = AsyncMock(return_value=2)

    mock_item_0 = AsyncMock()
    mock_item_0.inner_text = AsyncMock(return_value=" Hola ")

    mock_item_1 = AsyncMock()
    mock_item_1.inner_text = AsyncMock(return_value=" Chau   ")

    mock_items.nth = MagicMock(side_effect=[mock_item_0, mock_item_1])

    # Testeando
    with patch.object(scraper, "print_list_of_items") as mock_print:
        await scraper.print_locators(mock_items)

        # Haciendo comprobaciones
        mock_print.assert_called_once_with(["Hola", "Chau"])
        mock_items.count.assert_awaited()
        mock_items.nth.assert_any_call(0)
        mock_items.nth.assert_any_call(1)
        assert mock_items.nth.call_count == 2
        mock_item_0.inner_text.assert_awaited_once()
        mock_item_1.inner_text.assert_awaited_once()


# Tests para comprobar que se captura correctamente el input del usuario
@pytest.mark.asyncio
async def test_ask_user_for_input_locator(scraper, monkeypatch):
    # Creando mocks
    items_mock = MagicMock(spec=Locator)
    items_mock.count = AsyncMock(return_value=2)

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: " 1 ")

    result = await scraper.ask_user_for_input(items_mock, "test")

    assert result == 1


@pytest.mark.asyncio
async def test_ask_user_for_input_list(scraper, monkeypatch):
    # Creando mocks
    items_mock = ["Lima", "Arequipa"]

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "1  ")

    result = await scraper.ask_user_for_input(items_mock, "test")

    assert result == 1


@pytest.mark.asyncio
async def test_ask_user_for_input_fail_then_success(scraper, monkeypatch):
    inputs = iter(["5", "2"])

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(inputs))

    # Creando mocks
    items_mock = MagicMock(spec=Locator)
    items_mock.count = AsyncMock(return_value=3)

    result = await scraper.ask_user_for_input(items_mock, "test")

    assert result == 2
