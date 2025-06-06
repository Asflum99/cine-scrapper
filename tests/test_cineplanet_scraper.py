from scrapers.cineplanet_scraper import CineplanetScraper, console
from playwright.async_api import TimeoutError, Locator
from unittest.mock import MagicMock, AsyncMock, patch
from slugify import slugify
from pathlib import Path
import pytest, json, pandas, asyncio, os, scrapers.cineplanet_scraper

scraper = CineplanetScraper()


# Tests para comprobar que se aceptan las cookies
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_accept_cookies():
    # Creando mocks
    page_mock = MagicMock()
    button_mock = AsyncMock()

    # Definiendo la acción de query_selector
    page_mock.locator = MagicMock(return_value=button_mock)
    button_mock.is_visible = AsyncMock(return_value=True)
    button_mock.wait_for = AsyncMock()

    # Testeando función
    await scraper.accept_cookies(page_mock)

    # Haciendo comprobaciones
    page_mock.locator.assert_called_with("button:has-text('Aceptar Cookies')")
    button_mock.wait_for.assert_awaited_with(timeout=2000)
    button_mock.click.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.refactor
async def test_fail_accept_cookies(capfd):
    # Creando mocks
    page_mock = MagicMock()
    button_mock = AsyncMock()

    # Forzando el error de query_selector
    page_mock.locator = MagicMock(return_value=button_mock)
    button_mock.wait_for = AsyncMock(side_effect=TimeoutError("fail"))

    # Llamando a la función
    await scraper.accept_cookies(page_mock)

    # Verificando que se imprimió el mensaje de la excepción
    out, _ = capfd.readouterr()
    assert "No se encontró botón de cookies o hubo un problema" in out
    button_mock.click.assert_not_called()


# Tests para comprobar que se captura correctamente el input del usuario
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_ask_user_for_input_locator(monkeypatch):
    # Creando mocks
    items_mock = MagicMock(spec=Locator)
    items_mock.count = AsyncMock(return_value=2)

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: " 1 ")

    result = await scraper._ask_user_for_input(items_mock, "test")

    assert result == 1


@pytest.mark.asyncio
@pytest.mark.refactor
async def test_ask_user_for_input_list(monkeypatch):
    # Creando mocks
    items_mock = ["Lima", "Arequipa"]

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "1  ")

    result = await scraper._ask_user_for_input(items_mock, "test")

    assert result == 1


@pytest.mark.asyncio
@pytest.mark.refactor
async def test_ask_user_for_input_fail_then_success(monkeypatch):
    inputs = iter(["5", "2"])

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(inputs))

    # Creando mocks
    items_mock = MagicMock(spec=Locator)
    items_mock.count = AsyncMock(return_value=3)

    result = await scraper._ask_user_for_input(items_mock, "test")

    assert result == 2


# Test para comprobar la impresión de la lista de elementos
@patch("scrapers.cineplanet_scraper.console.print")
@pytest.mark.refactor
def test_print_list_with_3_items_should_print_one_row(mock_print):
    # Creando lista de items
    test_items = ["hola", "chau", "adiós"]

    # Testeando
    scraper._print_list_of_items(test_items)

    # Obtener textos que se imprimieron
    args, _ = mock_print.call_args
    fila = args[0]

    # Haciendo comprobaciones
    assert mock_print.call_count == 1
    texto = fila.plain
    assert "1)" in texto and "hola" in texto
    assert "2)" in texto and "chau" in texto
    assert "3)" in texto and "adiós" in texto


@patch("scrapers.cineplanet_scraper.console.print")
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
    scraper._print_list_of_items(test_items)

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


# Test para comprobar la transformación de ElementHandle a str
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_print_locators():
    # Creando mocks
    mock_items = MagicMock()
    mock_items.count = AsyncMock(return_value=2)

    mock_item_0 = AsyncMock()
    mock_item_0.inner_text = AsyncMock(return_value=" Hola ")

    mock_item_1 = AsyncMock()
    mock_item_1.inner_text = AsyncMock(return_value=" Chau   ")

    mock_items.nth = MagicMock(side_effect=[mock_item_0, mock_item_1])

    # Testeando
    with patch.object(scraper, "_print_list_of_items") as mock_print:
        await scraper._print_locators(mock_items)

        # Haciendo comprobaciones
        mock_print.assert_called_once_with(["Hola", "Chau"])
        mock_items.count.assert_awaited()
        mock_items.nth.assert_any_call(0)
        mock_items.nth.assert_any_call(1)
        assert mock_items.nth.call_count == 2
        mock_item_0.inner_text.assert_awaited_once()
        mock_item_1.inner_text.assert_awaited_once()


# Test para comprobar la selección del filtro
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_select_filter():
    # Creando mocks
    items_mock = MagicMock()
    page_mock = MagicMock()
    filter_mock = "ciudad"
    selected_item_mock = AsyncMock()

    items_mock.nth = MagicMock(return_value=selected_item_mock)
    selected_item_mock.inner_text = AsyncMock(return_value="  test ")
    selected_item_mock.click = AsyncMock()
    page_mock.wait_for_function = AsyncMock()

    with patch.object(scraper, "_print_locators") as mock_print, patch.object(
        scraper, "_ask_user_for_input", AsyncMock(return_value=1)
    ) as mock_ask:
        result = await scraper._select_filter(items_mock, page_mock, filter_mock)

        # Verifica llamadas
        mock_print.assert_called_once_with(items_mock)
        mock_ask.assert_called_once_with(items_mock, filter_mock)
        selected_item_mock.inner_text.assert_awaited_once()
        selected_item_mock.click.assert_awaited_once()
        page_mock.wait_for_function.assert_awaited_once()

        # Verifica resultado
        assert result == ("test", True)


# Test para comprobar filtro
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_apply_specific_filter_success():
    # Creando mocks
    filter_mock = MagicMock()
    specific_filter_mock = "Cine"
    page_mock = MagicMock()
    title_element_mock = AsyncMock()
    items_mock = MagicMock()

    def locator_side_effect(selector):
        if selector == ".movies-filter--filter-category-accordion-trigger h3":
            return title_element_mock
        elif selector == ".movies-filter--filter-category-list-item-label":
            return items_mock

    # Mockeando funciones
    filter_mock.locator = MagicMock(side_effect=locator_side_effect)
    title_element_mock.inner_text = AsyncMock(return_value="   Cine  ")
    filter_mock.get_attribute = AsyncMock(return_value="test-class")
    filter_mock.click = AsyncMock()

    with patch.object(
        scraper, "_select_filter", MagicMock(return_value=("test", True))
    ) as mock_filter:
        result = await scraper._apply_specific_filter(
            filter_mock, specific_filter_mock, page_mock
        )

        assert result == ("test", True)
        assert filter_mock.locator.call_count > 1
        title_element_mock.inner_text.assert_awaited_once()
        filter_mock.get_attribute.assert_called_once_with("class")
        filter_mock.click.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.refactor
async def test_apply_specific_filter_first_failure():
    filter_mock = MagicMock()
    filter_mock.locator = MagicMock(return_value=None)

    result = await scraper._apply_specific_filter(filter_mock, "test", None)

    assert result == ("Missing filter title", False)
    filter_mock.locator.assert_called_once_with(
        ".movies-filter--filter-category-accordion-trigger h3"
    )


@pytest.mark.asyncio
@pytest.mark.refactor
async def test_apply_specific_filter_second_failure():
    # Creando mocks
    filter_mock = MagicMock()
    title_element_mock = MagicMock()
    filter_mock.locator = MagicMock(return_value=title_element_mock)
    title_element_mock.inner_text = AsyncMock(return_value="no-test")

    # Testeando
    result = await scraper._apply_specific_filter(filter_mock, "test", None)

    assert result == ("Filters don't matches", False)
    filter_mock.locator.assert_called_once_with(
        ".movies-filter--filter-category-accordion-trigger h3"
    )
    title_element_mock.inner_text.assert_called_once()


# Test para comrpobar que se crea la carpeta
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_create_folder():
    city_mock = "Lima"
    day_mock = "Hoy"
    cinema_mock = "cp alcazar"

    expected_path = Path("data/lima/cineplanet/cp_alcazar/hoy")

    result = await scraper.create_folder(city_mock, cinema_mock, day_mock)

    assert result == expected_path


# Test para comprobar que cargan todas las películas
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_load_all_movies():
    # Creando mocks
    page_mock = MagicMock()
    button_mock = AsyncMock()

    # Simula que se encuentra el botón de "Ver más"
    page_mock.locator = MagicMock(return_value=button_mock)

    # Simula visibilidad del botón
    button_mock.is_visible = AsyncMock(side_effect=[True, False])
    button_mock.click = AsyncMock()
    page_mock.wait_for_timeout = AsyncMock()

    # Testeando
    try:
        await asyncio.wait_for(scraper.load_all_movies(page_mock), timeout=2)
    except asyncio.TimeoutError:
        pytest.fail("El test se colgó (posible bucle infinito)")

    # Haciendo comprobaciones
    page_mock.locator.assert_called_once_with(".movies-list--view-more-button")
    button_mock.click.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.refactor
async def test_load_all_movies_no_button():
    page_mock = MagicMock()
    button_mock = MagicMock()

    page_mock.locator = MagicMock(return_value=button_mock)
    button_mock.wait_for = AsyncMock(side_effect=Exception("No button"))

    await scraper.load_all_movies(page_mock)

    # Asegura que no se intentó hacer clic
    button_mock.click.assert_not_called()


# Test para comprobar la elección del usuario al escoger el formato
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_ask_format_to_save():

    with patch.object(
        scraper, "save_json", autospec=True
    ) as mock_save_json, patch.object(
        scraper, "save_excel", autospec=True
    ) as mock_save_excel, patch.object(
        scraper, "_print_list_of_items"
    ) as mock_print, patch.object(
        scraper, "_ask_user_for_input", AsyncMock(return_value=1)
    ):
        result = await scraper.ask_format_to_save()

        assert result == mock_save_json


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


# Test para comprobar que se guarda la información en json
@pytest.mark.refactor
def test_save_json(tmp_path):
    # 1. Setup
    movie_data = {"title": "Mi Película"}
    output_folder = tmp_path / "lima/cinema/cinema1/day"
    output_folder.mkdir(parents=True)
    expected_file = output_folder / f"{slugify(movie_data['title'])}.json"

    # 2. Ejecución
    scraper.save_json(output_folder, movie_data)

    # 3. Verificación
    assert expected_file.exists()
    with expected_file.open(encoding="utf-8") as f:
        content = json.load(f)
    assert content == movie_data


# Test para comprobar que se guarda la información en excel
@pytest.mark.refactor
def test_save_excel(tmp_path):
    # Crear carpetas y archivo
    movie_data = {
        "title": "Mi Película",
        "genre": "Drama",
        "running_time": "120 min",
        "age_restriction": "13+",
        "city": "Lima",
        "day": "Hoy",
        "showtimes": {
            "Cinepolis": [
                {
                    "dimension": "2D",
                    "format": "Digital",
                    "language": "Español",
                    "showtimes": [("19:00", "https://example.com/funcion1")],
                }
            ]
        },
    }
    output_folder = tmp_path / "lima/cinema/cinema1/day/"
    output_folder.mkdir(parents=True)
    expected_file = output_folder / f"{slugify(movie_data['title'])}.xlsx"

    # Testeando
    scraper.save_excel(output_folder, movie_data)
    df = pandas.read_excel(expected_file)

    # Haciendo comprobaciones
    assert expected_file.exists()
    assert len(df) == 1
    assert df.loc[0, "Título"] == movie_data["title"]


# Test para comprobar que se envían mensajes a la terminal
@pytest.mark.asyncio
async def test_message_if_takes_time():
    with patch("scrapers.cineplanet_scraper.console.print") as mock_print:
        task = asyncio.create_task(scraper.message_if_takes_time())
        await asyncio.sleep(6)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert mock_print.call_count == 1
        mock_print.assert_called_with(
            "Espere un momento, es que hay [cyan]muchos horarios[/] por recopilar."
        )


# Test para comprobar que el scrapping está bien preparado
@pytest.mark.asyncio
async def test_prepare_scrapping(monkeypatch):
    # Creando mocks y variables necesarias
    page_mock = AsyncMock()
    url = "https://wwww.test.com"

    # Mockeando funciones
    scraper.save_json = MagicMock()
    scraper.save_excel = MagicMock()

    async def setup_browser_mock(*args, **kwargs):
        return "browser-test"

    async def load_page_mock(*args, **kwargs):
        return page_mock

    accept_cookies_captured = []

    async def accept_cookies_mock(*args, **kwargs):
        accept_cookies_captured.append("cookies aceptadas")

    async def apply_filters_mock(*args, **kwargs):
        return "Lima", "CP Alcazar", "Hoy Martes"

    print_list_of_items_captured = []

    def print_list_of_items_mock(*args, **kwargs):
        print_list_of_items_captured.append("listas impresas")

    async def ask_user_for_input_mock(*args, **kwargs):
        return 1

    load_all_movies_captured = []

    async def load_all_movies_mock(*args, **kwargs):
        load_all_movies_captured.append("todas las películas cargadas")

    output_folder_created = []

    def makedirs_mock(path, exist_ok=True):
        output_folder_created.append((path, exist_ok))

    # Aplicando intercepciones
    monkeypatch.setattr(
        scrapers.cineplanet_scraper, "setup_browser", setup_browser_mock
    )
    monkeypatch.setattr(scrapers.cineplanet_scraper, "load_page", load_page_mock)
    monkeypatch.setattr(scraper, "accept_cookies", accept_cookies_mock)
    monkeypatch.setattr(scraper, "apply_filters", apply_filters_mock)
    monkeypatch.setattr(scraper, "_print_list_of_items", print_list_of_items_mock)
    monkeypatch.setattr(scraper, "_ask_user_for_input", ask_user_for_input_mock)
    monkeypatch.setattr(scraper, "load_all_movies", load_all_movies_mock)
    monkeypatch.setattr(os, "makedirs", makedirs_mock)

    # Configurando funciones
    page_mock.query_selector_all = AsyncMock(return_value="películas")

    # Testeando
    (
        browser_result,
        page_result,
        movies_result,
        output_folder_result,
        format_to_save_result,
    ) = await scraper.prepare_scrapping(url)

    # Haciendo comprobaciones
    assert browser_result == "browser-test"
    assert page_result == page_mock
    assert movies_result == "películas"
    assert output_folder_result == output_folder_created[0][0]
    assert output_folder_created[0][1] == True
    assert format_to_save_result is scraper.save_json
    assert "listas impresas" in print_list_of_items_captured
    assert "todas las películas cargadas" in load_all_movies_captured


# Test para comprobar que las películas se procesan
@pytest.mark.asyncio
async def test_process_movies(monkeypatch):
    original_create_task = asyncio.create_task
    created_task = None

    class FakeTask:
        def __init__(self, coro):
            self.cancel = MagicMock()
            self._task = original_create_task(coro)

        def __await__(self):
            return self._task.__await__()

    def create_task_mock(coro, *args, **kwargs):
        nonlocal created_task
        created_task = FakeTask(coro)
        return created_task

    # Creando mocks y variables necesarias
    page_mock = AsyncMock()
    filter_mock = AsyncMock()
    filters = [filter_mock]
    movies = [1]
    output_folder = "test"
    captured_movie_data = {}
    captured_output = []

    # Configurando funciones
    page_mock.query_selector_all = AsyncMock(return_value=filters)
    page_mock.go_back = AsyncMock()
    page_mock.wait_for_selector = AsyncMock()
    filter_mock.inner_text = AsyncMock(return_value="lima")

    # Mockeando funciones
    scraper.load_all_movies = AsyncMock()
    scraper.scrape_showtimes_data = AsyncMock()
    scrapers.cineplanet_scraper.enter_movie_details_page = AsyncMock()

    async def extract_general_information_mock(movie, movie_data, *args, **kwargs):
        movie_data["title"] = "Superman"

    def format_to_save_mock(*args, **kwargs):
        captured_movie_data.update(args[1])

    monkeypatch.setattr(
        scrapers.cineplanet_scraper,
        "extract_general_information",
        extract_general_information_mock,
    )
    monkeypatch.setattr(asyncio, "create_task", create_task_mock)
    monkeypatch.setattr(console, "print", lambda text: captured_output.append(text))

    # Testeando
    await scraper.process_movies(page_mock, movies, output_folder, format_to_save_mock)

    # Aserciones opcionales
    assert captured_movie_data["title"] == "Superman"
    assert captured_movie_data["city"] == "lima"
    assert created_task is not None, "No se creó la tarea FakeTask"
    created_task.cancel.assert_called_once()
    assert page_mock.query_selector_all.await_count >= 1
    assert (
        f"\n[cyan]▶️ Recopilando horarios de proyección de [bold]{captured_movie_data['title']}[/bold][/cyan]"
        in captured_output
    )


# Test para comprobar que scrapea orquesta bien todo
@pytest.mark.asyncio
async def test_scrape():
    # Creando mocks y variables necesarias
    browser_mock = AsyncMock()
    scraper.prepare_scrapping = AsyncMock(
        return_value=(browser_mock, None, None, None, None)
    )
    scraper.process_movies = AsyncMock()
    url = "https://www.test.com"

    # Configurando mocks y funciones
    browser_mock.close = AsyncMock()

    # Testeando
    with patch("scrapers.cineplanet_scraper.console.print") as mock_print:
        await scraper.scrape(url)

    # Haciendo comprobaciones
    mock_print.assert_any_call(
        "\n[bold green]🎉 ¡Todos los horarios han sido guardados exitosamente![/bold green]"
    )
    scraper.process_movies.assert_awaited_once()
    browser_mock.close.assert_awaited_once()
