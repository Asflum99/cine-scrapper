from scrapers.cineplanet_scraper import CineplanetScraper, console
from playwright.async_api import TimeoutError, Locator
from unittest.mock import MagicMock, AsyncMock, patch
from slugify import slugify
from pathlib import Path
import pytest, json, pandas, asyncio, os, scrapers.cineplanet_scraper


@pytest.fixture
def scraper():
    return CineplanetScraper()


# Tests para comprobar que se aceptan las cookies
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_accept_cookies(scraper):
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
async def test_fail_accept_cookies(scraper, capfd):
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
async def test_ask_user_for_input_locator(scraper, monkeypatch):
    # Creando mocks
    items_mock = MagicMock(spec=Locator)
    items_mock.count = AsyncMock(return_value=2)

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: " 1 ")

    result = await scraper._ask_user_for_input(items_mock, "test")

    assert result == 1


@pytest.mark.asyncio
@pytest.mark.refactor
async def test_ask_user_for_input_list(scraper, monkeypatch):
    # Creando mocks
    items_mock = ["Lima", "Arequipa"]

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "1  ")

    result = await scraper._ask_user_for_input(items_mock, "test")

    assert result == 1


@pytest.mark.asyncio
@pytest.mark.refactor
async def test_ask_user_for_input_fail_then_success(scraper, monkeypatch):
    inputs = iter(["5", "2"])

    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: next(inputs))

    # Creando mocks
    items_mock = MagicMock(spec=Locator)
    items_mock.count = AsyncMock(return_value=3)

    result = await scraper._ask_user_for_input(items_mock, "test")

    assert result == 2


# Test para comprobar la transformación de ElementHandle a str
@pytest.mark.asyncio
@pytest.mark.refactor
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


# Test para comprobar que se aplica el filtro
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_apply_filters(scraper):
    # Creando mocks
    page_mock = MagicMock()
    filters_mock = MagicMock()

    # Mockeando funciones
    page_mock.locator = MagicMock(return_value=filters_mock)
    filters_mock.count = AsyncMock(return_value=3)
    filters_mock.nth = MagicMock()

    def side_effect(filter_element, name, page):
        return (name, True)

    # Testeando
    with patch.object(
        scraper, "_apply_specific_filter", side_effect=side_effect
    ) as apply_filter_mock:
        result = await scraper.apply_filters(page_mock)

        assert result == ["Ciudad", "Cine", "Día"]
        page_mock.locator.assert_called_with(
            ".movies-filter--filter-category-accordion"
        )
        filters_mock.count.assert_awaited_once()
        assert apply_filter_mock.await_count == 3


# Test para comprobar que se construye el showtime_entry
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_build_showtime_entry(scraper):
    # Creando mocks
    page_mock = MagicMock()
    cine_mock = MagicMock()
    cinema_elements_mock = MagicMock()
    containers_mock = MagicMock()
    container_mock = MagicMock()
    formats_mock = MagicMock()
    dimension_raw_mock = MagicMock()
    theather_raw_mock = MagicMock()
    language_raw_mock = MagicMock()
    session_items_mock = MagicMock()

    def container_effect(selector):
        if selector == ".sessions-details--formats":
            return formats_mock
        elif selector == ".sessions-details--session-item":
            return session_items_mock

    def formats_effect(selector):
        if selector == ".sessions-details--formats-dimension":
            return dimension_raw_mock
        elif selector == ".sessions-details--formats-theather":
            return theather_raw_mock
        elif selector == ".sessions-details--formats-language":
            return language_raw_mock

    # Mockeando funciones
    page_mock.locator = MagicMock(return_value=cinema_elements_mock)
    cinema_elements_mock.nth = MagicMock(return_value=cine_mock)
    cine_mock.locator = MagicMock(return_value=containers_mock)
    containers_mock.nth = MagicMock(return_value=container_mock)
    container_mock.locator = MagicMock(side_effect=container_effect)
    formats_mock.locator = MagicMock(side_effect=formats_effect)
    dimension_raw_mock.inner_text = AsyncMock(return_value="  dimension-test ")
    theather_raw_mock.inner_text = AsyncMock(return_value=" theather-test   ")
    language_raw_mock.inner_text = AsyncMock(return_value="   language-test ")
    session_items_mock.count = AsyncMock(return_value=1)
    cine_mock.get_attribute = AsyncMock(
        return_value="accordion_expanded"
    )  # Este test tiene el acordión

    # Testeando
    with patch.object(
        scraper, "_parse_showtimes", AsyncMock(return_value=["test-text", "test-url"])
    ):
        result = await scraper._build_showtime_entry(page_mock, 1, 1)

        assert result == {
            "dimension": "dimension-test",
            "format": "theather-test",
            "language": "language-test",
            "showtimes": [["test-text", "test-url"]],
        }
        assert formats_mock.locator.call_count == 3
        session_items_mock.count.assert_awaited_once()
        dimension_raw_mock.inner_text.assert_awaited_once()
        theather_raw_mock.inner_text.assert_awaited_once()
        language_raw_mock.inner_text.assert_awaited_once()


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


# Test para comprobar que el scrapping está bien preparado
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_prepare_scrapping(scraper, monkeypatch):
    page_mock = MagicMock()
    movies_mock = MagicMock()
    browser_mock = MagicMock()
    page_mock.locator = MagicMock(return_value=movies_mock)
    p_mock = MagicMock()
    format_mock = MagicMock()

    def apply_filters_side_effect(page_mock):
        return ("Lima", "CP Alcazar", "Hoy Lunes")

    def create_folder_side_effect(city, cinema, day):
        return Path("test/test_folder")

    with patch.object(
        scraper, "setup_browser", AsyncMock(return_value=browser_mock)
    ) as setup_broweser_mock, patch.object(
        scraper, "load_page", AsyncMock(return_value=page_mock)
    ), patch.object(
        scraper, "accept_cookies"
    ) as accept_cookies_mock, patch.object(
        scraper, "apply_filters", side_effect=apply_filters_side_effect
    ) as apply_filters_mock, patch.object(
        scraper, "create_folder", side_effect=create_folder_side_effect
    ) as create_folder_mock, patch.object(
        scraper, "ask_format_to_save", AsyncMock(return_value=format_mock)
    ) as ask_format_mock, patch.object(
        scraper, "load_all_movies", AsyncMock()
    ) as load_all_movies_mock:
        (
            browser_result,
            page_result,
            movies_result,
            output_folder_result,
            format_to_save_result,
        ) = await scraper.prepare_scrapping(p_mock, "https://www.test.com")

        setup_broweser_mock.assert_awaited_once_with(p_mock)
        accept_cookies_mock.assert_awaited_once_with(page_mock)
        apply_filters_mock.assert_awaited_once_with(page_mock)
        create_folder_mock.assert_awaited_once_with("Lima", "CP Alcazar", "Hoy Lunes")
        ask_format_mock.assert_awaited_once()
        load_all_movies_mock.assert_awaited_once_with(page_mock)
        page_mock.locator.assert_called_once_with(".movies-list--large-item")
        assert browser_result is browser_mock
        assert page_result is page_mock
        assert movies_result is movies_mock
        assert output_folder_result == Path("test/test_folder")
        assert format_to_save_result is format_mock


# Test para comprobar que se envían mensajes a la terminal
@pytest.mark.asyncio
# @pytest.mark.refactor
async def test_message_if_takes_time(scraper):
    with patch("scrapers.cineplanet_scraper.console.print") as mock_print:
        task = asyncio.create_task(scraper.message_if_takes_time())
        await asyncio.sleep(6)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert mock_print.call_count == 1
        mock_print.assert_called_once_with(
            "Espere un momento, es que hay [cyan]muchos horarios[/] por recopilar."
        )


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
@pytest.mark.refactor
async def test_parse_showtimes_for_cinema(scraper):
    # Creando mocks
    page_mock = MagicMock()
    cinema_elements_mock = MagicMock()
    cine_mock = MagicMock()
    containers_mock = MagicMock()
    cinema_name_mock = MagicMock()

    def cine_side_effect(selector):
        if selector == ".cinema-showcases--summary-name":
            return cinema_name_mock
        elif selector == ".cinema-showcases--sessions-details":
            return containers_mock

    def build_side_effect(page, cine_idx, container_idx):
        return {
            "dimension": "dimension-test",
            "format": "theather-test",
            "language": "language-test",
            "showtimes": [["test-text", "test-url"]],
        }

    # Mockeando funciones
    page_mock.locator = MagicMock(return_value=cinema_elements_mock)
    cinema_elements_mock.nth = MagicMock(return_value=cine_mock)
    cine_mock.locator = MagicMock(side_effect=cine_side_effect)
    containers_mock.count = AsyncMock(return_value=1)
    cinema_name_mock.inner_text = AsyncMock(return_value="   cinema_name_test  ")

    with patch.object(
        scraper, "_build_showtime_entry", side_effect=build_side_effect
    ) as build_mock:
        cinema_name_result, raw_data_result = await scraper._parse_showtimes_for_cinema(
            page_mock, 1
        )

        assert cinema_name_result == "cinema_name_test"
        assert raw_data_result == [
            {
                "dimension": "dimension-test",
                "format": "theather-test",
                "language": "language-test",
                "showtimes": [["test-text", "test-url"]],
            }
        ]
        page_mock.locator.assert_called_once_with(".film-detail-showtimes--accordion")
        assert cine_mock.locator.call_count == 2
        build_mock.assert_awaited_with(page_mock, 1, 0)
        containers_mock.count.assert_awaited_once()
        cinema_elements_mock.nth.assert_called_once_with(1)


# Test para comprobar que se parsea los showtimes
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_parse_showtimes(scraper):
    # Creando mocks
    page_mock = MagicMock()
    session_items_mock = MagicMock()
    showtime_mock = MagicMock()
    showtime_button_mock = MagicMock()

    # Mockeando funciones
    session_items_mock.nth = MagicMock(return_value=showtime_mock)
    showtime_mock.get_attribute = AsyncMock(return_value="selector")
    showtime_mock.locator = MagicMock(return_value=showtime_button_mock)
    showtime_button_mock.inner_text = AsyncMock(return_value="  test-text ")

    # Testeando
    with patch.object(
        scraper, "_click_extract_then_go_back", AsyncMock(return_value="test-url")
    ) as click_mock:
        result = await scraper._parse_showtimes(session_items_mock, 1, page_mock)

        assert result == ["test-text", "test-url"]
        showtime_mock.get_attribute.assert_awaited_once_with("class")
        showtime_mock.locator.assert_called_once_with(".showtime-selector--link")
        click_mock.assert_awaited_once_with(
            page_mock,
            showtime_button_mock,
            "**/compra/**/asientos",
            ".purchase-seating--seat-map",
            ".film-detail-showtimes--accordion",
        )


# Test para comprobar que se regresa una lista vacía si el selector está deshabilitado
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_fail_parse_showtimes(scraper):
    # Creando mocks
    page_mock = MagicMock()
    session_items_mock = MagicMock()
    showtime_mock = MagicMock()

    # Mockeando funciones
    session_items_mock.nth = MagicMock(return_value=showtime_mock)
    showtime_mock.get_attribute = AsyncMock(return_value="showtime-selector_disable")

    # Testeando
    result = await scraper._parse_showtimes(session_items_mock, 1, page_mock)

    # Haciendo comprobaciones
    assert result == []
    showtime_mock.get_attribute.assert_called_once_with("class")
    showtime_mock.locator.assert_not_called()


# Test para comprobar que se ingresa a la página de venta, se guarda el enlace y se regresa
# TODO: FALTA CUANDO SALTA EL TIMEOUTERROR
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_click_extract_then_go_back(scraper):
    # Creando mocks
    page_mock = MagicMock()
    new_page_mock = MagicMock()
    return_page_mock = MagicMock()
    tickets_section_mock = MagicMock()
    clickable_element_mock = MagicMock()

    def side_effect(selector):
        if (
            selector
            == ".call-to-action_rounded-solid.call-to-action_pink-solid.call-to-action_large"
        ):
            return tickets_section_mock
        elif selector == "test2":
            return new_page_mock
        elif selector == "test3":
            return return_page_mock

    # Mockeando funciones
    clickable_element_mock.click = AsyncMock()
    page_mock.locator = MagicMock(side_effect=side_effect)
    tickets_section_mock.click = AsyncMock()
    tickets_section_mock.is_visible = AsyncMock()
    page_mock.wait_for_url = AsyncMock()
    new_page_mock.wait_for = AsyncMock()
    page_mock.go_back = AsyncMock()
    page_mock.url = "test4"
    return_page_mock.wait_for = AsyncMock()

    # Testeando
    result = await scraper._click_extract_then_go_back(
        page_mock, clickable_element_mock, "test1", "test2", "test3"
    )

    assert result == "test4"
    assert page_mock.locator.call_count == 3
    clickable_element_mock.click.assert_awaited_once()
    tickets_section_mock.click.assert_awaited_once()
    page_mock.wait_for_url.assert_awaited_once_with("test1")
    page_mock.go_back.assert_awaited_once()


# Test para comprobar que cargan todas las películas
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_load_all_movies(scraper):
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
async def test_load_all_movies_no_button(scraper):
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
async def test_ask_format_to_save(scraper):

    with patch.object(
        scraper, "save_json", MagicMock()
    ) as mock_save_json, patch.object(
        scraper, "save_excel", MagicMock()
    ) as mock_save_excel, patch.object(
        scraper, "print_list_of_items"
    ) as mock_print, patch.object(
        scraper, "_ask_user_for_input", AsyncMock(return_value=1)
    ):
        result = await scraper.ask_format_to_save()
        assert result == mock_save_json


# Test para comprobar filtro
@pytest.mark.asyncio
@pytest.mark.refactor
async def test_apply_specific_filter_success(scraper):
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
async def test_apply_specific_filter_first_failure(scraper):
    filter_mock = MagicMock()
    filter_mock.locator = MagicMock(return_value=None)

    result = await scraper._apply_specific_filter(filter_mock, "test", None)

    assert result == ("Missing filter title", False)
    filter_mock.locator.assert_called_once_with(
        ".movies-filter--filter-category-accordion-trigger h3"
    )


@pytest.mark.asyncio
@pytest.mark.refactor
async def test_apply_specific_filter_second_failure(scraper):
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
async def test_create_folder(scraper):
    city_mock = "Lima"
    day_mock = "Hoy"
    cinema_mock = "cp alcazar"

    expected_path = Path("data/lima/cineplanet/cp_alcazar/hoy")

    result = await scraper.create_folder(city_mock, cinema_mock, day_mock)

    assert result == expected_path


# Test para comprobar que se guarda la información en json
@pytest.mark.refactor
def test_save_json(scraper, tmp_path):
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
def test_save_excel(tmp_path, scraper):
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
