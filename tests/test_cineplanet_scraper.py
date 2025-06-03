from scrapers.cineplanet_scraper import CineplanetScraper, console
from playwright.sync_api import sync_playwright
from unittest.mock import MagicMock, AsyncMock
import pytest

scraper = CineplanetScraper()


# Test para comprobar que se aceptan las cookies
@pytest.mark.asyncio
async def test_accept_cookies():
    # Creando mocks
    page_mock = MagicMock()
    button_mock = AsyncMock()

    # Definiendo la acción de query_selector
    page_mock.query_selector = AsyncMock(return_value=button_mock)
    button_mock.is_visible = AsyncMock(return_value=True)

    # Testeando función
    await scraper.accept_cookies(page_mock)
    button_mock.click.assert_called_once()


@pytest.mark.asyncio
async def test_fail_accept_cookies(capfd):
    # Creando mocks
    page_mock = MagicMock()

    # Forzando el error de query_selector
    page_mock.query_selector = AsyncMock(side_effect=Exception("fail"))

    # Llamando a la función
    await scraper.accept_cookies(page_mock)

    # Verificando que se imprimió el mensaje de la excepción
    out, _ = capfd.readouterr()
    assert "No se encontró botón de cookies o hubo un problema: " in out


# Test para comprobar que se captura correctamente el input del usuario
@pytest.mark.asyncio
async def test_ask_user_for_input(monkeypatch):
    # Inputs
    inputs = iter(["0", "2"])

    # Configurando input()
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))

    # Creando lista
    items_mock = ["Elemento 1", "Elemento 2"]

    # Testeando
    result = await scraper._ask_user_for_input(items_mock, "Filtro test")
    assert result == 2


# Test para comprobar la ejecución del input del usuario
@pytest.mark.asyncio
async def test_execute_user_input():
    # Creando mocks individuales para la lista
    item_mock_1 = AsyncMock()
    item_mock_1.inner_text = AsyncMock(return_value="1")
    item_mock_1.click = AsyncMock()

    item_mock_2 = AsyncMock()
    item_mock_2.inner_text = AsyncMock(return_value="2")
    item_mock_2.click = AsyncMock()

    items_mock = [item_mock_1, item_mock_2]

    # Mock de la página principal
    page_mock = AsyncMock()

    # Configurando funciones
    item_mock_text = await item_mock_1.inner_text()

    # Testeando
    result = await scraper._execute_user_input(items_mock, page_mock, 1)
    item_mock_1.click.assert_awaited_once()
    item_mock_2.click.assert_not_called()
    args, _ = page_mock.wait_for_function.call_args
    assert item_mock_text in args[0]
    assert result == (item_mock_text, True)


# Test para comprobar la impresión de la lista de elementos
def test_print_list_of_items(monkeypatch):
    # Creando lista de items
    test_items = ["hola", "chau", "adiós", "comida", "refrigeradora", "computadora"]
    captured_output = []

    # Configurando print() y pasando lista de items
    monkeypatch.setattr(console, "print", lambda text: captured_output.append(text))

    # Testeando
    scraper._print_list_of_items(test_items)

    # Haciendo comprobaciones
    assert len(captured_output) == 2
    assert "1) hola" in captured_output[0].plain
    assert "4) comida" in captured_output[1].plain


# Test para comprobar la transformación de ElementHandle a str
@pytest.mark.asyncio
async def test_print_elementhandles(monkeypatch):
    # Creando mocks individuales para la lista
    item_mock_1 = AsyncMock()
    item_mock_1.inner_text = AsyncMock(return_value="1")

    item_mock_2 = AsyncMock()
    item_mock_2.inner_text = AsyncMock(return_value="2")

    items_list = [item_mock_1, item_mock_2]

    # Mockeando _print_list_of_items
    captured_data = []

    monkeypatch.setattr(
        scraper, "_print_list_of_items", lambda items: captured_data.append(items)
    )

    # Testeando
    await scraper._print_elementhandles(items_list)

    # Haciendo comprobaciones
    assert captured_data[0] == ["1", "2"]


# Test para comprobar la selección del filtro
@pytest.mark.asyncio
async def test_select_filter(monkeypatch):
    # Creando mocks que se pasarán como argumentos
    item_mock_1 = AsyncMock()
    item_mock_2 = AsyncMock()
    item_mock_3 = AsyncMock()
    items = [item_mock_1, item_mock_2, item_mock_3]
    page_mock = MagicMock()
    filter = "ciudad"

    # Configurando funciones
    captured_data_print_elementhandles = []

    async def mock_print_elementhandles(items):
        captured_data_print_elementhandles.append(items)

    captured_data_ask_user_for_input = []

    async def mock_ask_user_for_input(items, filter):
        captured_data_ask_user_for_input.append((items, filter))
        return 5

    captured_data_execute_user_input = []

    async def mock_execute_user_input(items, page, filter_chosen):
        captured_data_execute_user_input.append((items, page, filter_chosen))
        return ("result", True)

    # Mockeando funciones
    monkeypatch.setattr(scraper, "_print_elementhandles", mock_print_elementhandles)
    monkeypatch.setattr(scraper, "_ask_user_for_input", mock_ask_user_for_input)
    monkeypatch.setattr(scraper, "_execute_user_input", mock_execute_user_input)

    # Testeando
    result = await scraper._select_filter(items, page_mock, filter)

    # Haciendo comprobaciones
    assert result == ("result", True)
    assert captured_data_print_elementhandles[0] == [
        item_mock_1,
        item_mock_2,
        item_mock_3,
    ]
    assert captured_data_ask_user_for_input[0] == (
        [item_mock_1, item_mock_2, item_mock_3],
        "ciudad",
    )
    assert captured_data_execute_user_input[0] == (
        [item_mock_1, item_mock_2, item_mock_3],
        page_mock,
        5,
    )


# Test para comprobar que cargan todas las películas
@pytest.mark.asyncio
async def test_load_all_movies():
    # Creando mocks
    page_mock = AsyncMock()
    button_mock = AsyncMock()

    # Simula que se encuentra el botón de "Ver más"
    page_mock.wait_for_selector = AsyncMock(return_value=button_mock)

    # Simula visibilidad del botón
    button_mock.is_visible = AsyncMock(side_effect=[True, False])

    # Testeando
    await scraper.load_all_movies(page_mock)

    # Haciendo comprobaciones
    assert page_mock.wait_for_selector.call_count == 2
    assert button_mock.click.call_count == 1


# Test para comprobar que se scrapean todos los showtimes
@pytest.mark.asyncio
async def test_scrape_showtimes_data(monkeypatch):
    # Creando mocks y variables necesarias
    movie_data_mock = {}
    page_mock = AsyncMock()
    cinema_elements = [1]

    # Configurando funciones
    page_mock.query_selector_all = AsyncMock(return_value=cinema_elements)

    # Interceptando funciones
    async def parse_showtimes_for_cinema_mock(*args, **kwargs):
        return "test-cinema-name", [{"test-key": "test-value"}]

    monkeypatch.setattr(
        scraper, "_parse_showtimes_for_cinema", parse_showtimes_for_cinema_mock
    )

    # Testeando
    await scraper.scrape_showtimes_data(page_mock, movie_data_mock)
    assert movie_data_mock["showtimes"] == {
        "test-cinema-name": [{"test-key": "test-value"}]
    }
    page_mock.query_selector_all.assert_called_with(".film-detail-showtimes--accordion")


# Test para comprobar que se parsean los showtimes de cada cine
@pytest.mark.asyncio
async def test_parse_showtimes_for_cinema(monkeypatch):
    # Creando mocks y variables necesarias
    cine_idx = 0
    page_mock = AsyncMock()
    cine_mock = AsyncMock()
    cinema_elements = [cine_mock]

    # Configurando funciones
    page_mock.query_selector_all = AsyncMock(return_value=cinema_elements)
    cine_mock.query_selector_all = AsyncMock(return_value=[1])

    # Interceptando función
    async def extract_cinema_name_mock(*args, **kwargs):
        return "cinema-test"

    async def build_showtime_entry_mock(*args, **kwargs):
        return {"test-key": "test-value"}

    monkeypatch.setattr(scraper, "_extract_cinema_name", extract_cinema_name_mock)
    monkeypatch.setattr(scraper, "_build_showtime_entry", build_showtime_entry_mock)

    # Testeando
    result_1, result_2 = await scraper._parse_showtimes_for_cinema(page_mock, cine_idx)

    # Haciendo comprobaciones
    assert result_1 == "cinema-test"
    assert result_2 == [{"test-key": "test-value"}]
    page_mock.query_selector_all.assert_called_with(".film-detail-showtimes--accordion")
    cine_mock.query_selector_all.assert_called_once()


# Test para comprobar que se construye el showtime_entry
@pytest.mark.asyncio
async def test_build_showtime_entry(monkeypatch):
    # Creando mocks y variables necesarias
    page_mock = AsyncMock()
    cine_idx = 0
    container_idx = 0
    cine_mock = AsyncMock()
    cinema_elements = [cine_mock]
    container_mock = AsyncMock()
    containers = [container_mock]
    formats_mock = AsyncMock()
    dimension_mock = AsyncMock()
    theather_mock = AsyncMock()
    language_mock = AsyncMock()
    session_items = [1]

    # Creando función
    def query_selector_side_effect(selector):
        if selector == ".sessions-details--formats-dimension":
            return dimension_mock
        elif selector == ".sessions-details--formats-theather":
            return theather_mock
        elif selector == ".sessions-details--formats-language":
            return language_mock

    # Configurando funciones
    page_mock.query_selector_all = AsyncMock(return_value=cinema_elements)
    cine_mock.query_selector_all = AsyncMock(return_value=containers)
    container_mock.query_selector = AsyncMock(return_value=formats_mock)
    formats_mock.query_selector = AsyncMock(side_effect=query_selector_side_effect)
    dimension_mock.inner_text = AsyncMock(return_value="dimension test")
    theather_mock.inner_text = AsyncMock(return_value="theather test")
    language_mock.inner_text = AsyncMock(return_value="language test")
    container_mock.query_selector_all = AsyncMock(return_value=session_items)

    # Interceptando función
    async def parse_showtimes_mock(*args, **kwargs):
        return ["showtime", "link"]

    monkeypatch.setattr(scraper, "_parse_showtimes", parse_showtimes_mock)

    # Testeando
    result = await scraper._build_showtime_entry(page_mock, cine_idx, container_idx)

    # Haciendo comprobaciones
    assert result == {
        "dimension": "dimension test",
        "format": "theather test",
        "language": "language test",
        "showtimes": [["showtime", "link"]],
    }
    container_mock.query_selector.assert_called_once()
    dimension_mock.inner_text.assert_awaited_once()
    theather_mock.inner_text.assert_awaited_once()
    language_mock.inner_text.assert_awaited_once()
    assert page_mock.query_selector_all.call_count > 1


# Test para comprobar que se parsea los showtimes
@pytest.mark.asyncio
async def test_parse_showtimes(monkeypatch):
    page_mock = AsyncMock()
    showtime_idx = 0
    showtime_button = AsyncMock()
    showtime_text = "Showtime Test"
    showtime_item = AsyncMock()
    session_items = [showtime_item]
    showtime_item.get_attribute = AsyncMock(return_value="showtime-selector")
    showtime_item.query_selector = AsyncMock(return_value=showtime_button)
    showtime_button.inner_text = AsyncMock(return_value=showtime_text)

    async def mock_click_extract_then_go_back(*args, **kwargs):
        return "Url Test"

    monkeypatch.setattr(
        scraper, "_click_extract_then_go_back", mock_click_extract_then_go_back
    )

    result = await scraper._parse_showtimes(session_items, showtime_idx, page_mock)

    assert result == ["Showtime Test", "Url Test"]
    assert len(result) == 2
    showtime_item.get_attribute.assert_called_once_with("class")
    showtime_item.query_selector.assert_called_once_with(".showtime-selector--link")
    showtime_button.inner_text.assert_awaited_once()


# Test para comprobar que se regresa una lista vacía si el selector está deshabilitado
@pytest.mark.asyncio
async def test_fail_parse_showtimes():
    # Creando mocks y variables necesarias
    page_mock = AsyncMock()
    showtime_idx = 0
    showtime_item = AsyncMock()
    session_items = [showtime_item]

    # Configurando funciones
    showtime_item.get_attribute = AsyncMock(return_value="showtime-selector_disable")

    # Testeando
    result = await scraper._parse_showtimes(session_items, showtime_idx, page_mock)

    # Haciendo comprobaciones
    assert result == []
    showtime_item.get_attribute.assert_called_once_with("class")
    showtime_item.query_selector.assert_not_called()


# Test para comprobar que se extrae el nombre del cine
@pytest.mark.asyncio
async def test_extract_cinema_name():
    # Creando mocks
    cine_mock = AsyncMock()
    cinema_name_mock = AsyncMock()

    # Configurando funciones
    cine_mock.query_selector = AsyncMock(return_value=cinema_name_mock)
    cinema_name_mock.inner_text = AsyncMock(return_value="  Nombre test  ")

    # Testeando
    result = await scraper._extract_cinema_name(cine_mock)

    # Haciendo comprobaciones
    assert result == "Nombre test"


# Test para comprobar que se ingresa a la página de venta, se guarda el enlace y se regresa
@pytest.mark.asyncio
async def test_click_extract_then_go_back():
    # Creando mocks
    page_mock = AsyncMock()
    page_mock.url = "test-original"
    clickable_element_mock = AsyncMock()
    expected_new_url = "test-url"
    wait_for_selector_new_page = "test-new-selector"
    wait_for_selector_old_page = "test-old-selector"
    confirm_purchase_mock = AsyncMock()

    clickable_element_mock.click = AsyncMock()
    page_mock.query_selector = AsyncMock(return_value=confirm_purchase_mock)
    page_mock.go_back = AsyncMock()
    page_mock.wait_for_function = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()
    page_mock.wait_for_url = AsyncMock(
        side_effect=lambda *args, **kwargs: setattr(page_mock, "url", expected_new_url)
    )

    # Testeando
    result = await scraper._click_extract_then_go_back(
        page_mock,
        clickable_element_mock,
        expected_new_url,
        wait_for_selector_new_page,
        wait_for_selector_old_page,
    )

    # Haciendo comprobaciones
    confirm_purchase_mock.click.assert_called_once()
    page_mock.wait_for_url.assert_called_with(expected_new_url)
    page_mock.wait_for_selector.assert_any_call(
        wait_for_selector_new_page, timeout=10000
    )
    page_mock.wait_for_selector.assert_any_call(
        wait_for_selector_old_page, timeout=10000
    )
    assert result == expected_new_url
