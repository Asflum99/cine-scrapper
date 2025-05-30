from scrapers.cineplanet_scraper import CineplanetScraper, console
from playwright.sync_api import sync_playwright
from unittest.mock import MagicMock, AsyncMock
import pytest, os

scraper = CineplanetScraper()


# Página base para tests y sirve para comprobar URL
@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.cineplanet.com.pe/peliculas")
        yield page
        browser.close()


# Test para comprobar que la página carga
def test_site_homepage_loads():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto("https://www.cineplanet.com.pe/")

        # La página respondió satisfactoriamente
        assert (
            response is not None
        ), "La respuesta fue None, puede que el sitio esté caído"
        assert response.status == 200
        assert page.url.startswith("https://www.cineplanet.com.pe/")

        browser.close()


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
    # Configurando input()
    monkeypatch.setattr("builtins.input", lambda _: "1")

    # Creando lista
    items_mock = ["Elemento 1", "Elemento 2"]

    # Testeando
    result = await scraper._ask_user_for_input(items_mock, "Filtro test")
    assert result == 1


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
def test_scraper_load_all_movies(page):
    scraper.load_all_movies(page)


# Test para comprobar que se extrae toda la información general
def test_scraper_extract_general_information(page):
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, "test_data", "movie_sample.html")

    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    page.set_content(html_content)

    movie = page.query_selector(".movies-list--large-item")
    movie_data = {}
    scraper.extract_general_information(movie, movie_data)
    assert movie_data["title"] == "Película de prueba"
    assert movie_data["genre"] == "Drama"
    assert movie_data["running_time"] == "1h 50m"
    assert movie_data["age_restriction"] == "+14."
    assert movie_data["image_url"] == "https://estaesunaimagen.com.pe"


# Test para comprobar que se extrae toda la información específica
def test_scraper_extract_specific_information(page):
    movie_data = {}
    scraper.extract_info_from_details_page(page, movie_data)
