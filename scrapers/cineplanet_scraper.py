from playwright.async_api import async_playwright, Page, ElementHandle, TimeoutError
from scrapers.base_scraper import BaseScraper
from scrapers.utils.browser_utils import (
    setup_browser,
    load_page,
    extract_general_information,
    enter_movie_details_page,
)
from slugify import slugify
from typing import List, Tuple, TypeVar
from rich.text import Text
from rich.console import Console
from rich.traceback import install
import json, os, asyncio, pandas

console = Console()
install()
T = TypeVar("T")


class CineplanetScraper(BaseScraper):

    async def accept_cookies(self, page: Page):
        # Espera y hace clic en el botón "Aceptar Cookies" para cerrar el aviso, si existe
        try:
            button = await page.query_selector('button:has-text("Aceptar Cookies")')
            if button and await button.is_visible():
                await button.click()
        except Exception as e:
            print("No se encontró botón de cookies o hubo un problema: ", e)

    async def apply_filters(self, page: Page) -> List[str]:
        # Selecciona todos los filtros y solo aplica los de "Ciudad", "Cine" y "Día"
        filters = await page.query_selector_all(
            ".movies-filter--filter-category-accordion"
        )
        city_filter_added = False
        cinema_filter_added = False
        day_filter_added = False
        data: List = []
        for filter in filters:
            if not city_filter_added:
                # Aplica el filtro de "Ciudad"
                raw_data = await self._apply_specific_filter(filter, "Ciudad", page)
                city, city_filter_added = await raw_data
                if city_filter_added:
                    data.append(city)
                    continue
            if not cinema_filter_added:
                # Aplica el filtro de "Cine"
                raw_data = await self._apply_specific_filter(filter, "Cine", page)
                cinema, cinema_filter_added = await raw_data
                if cinema_filter_added:
                    data.append(cinema)
                    continue
            if not day_filter_added:
                # Aplica el filtro de "Día"
                raw_data = await self._apply_specific_filter(filter, "Día", page)
                day, day_filter_added = await raw_data
                if day_filter_added:
                    data.append(day)
                    break
        return data

    async def _apply_specific_filter(
        self,
        filter: ElementHandle,
        specific_filter: str,
        page: Page,
    ) -> Tuple[str, bool]:
        title_element = await filter.query_selector(
            ".movies-filter--filter-category-accordion-trigger h3"
        )
        if not title_element:
            return ("Missing filter title", False)
        if (await title_element.inner_text()).strip() == specific_filter:
            classes = await filter.get_attribute("class")
            # Verificar si el acordeón del filtro está expandido
            if "accordion_expanded" not in classes:
                await filter.click()

            items = await filter.query_selector_all(
                ".movies-filter--filter-category-list-item-label"
            )

            filters = {
                "Ciudad": "ciudad",
                "Cine": "cine",
                "Día": "día",
            }

            if specific_filter in filters:
                return self._select_filter(items, page, filters[specific_filter])

        # Si no hay ningún filtro que coincida, se retorna nada
        return ("Filters don't matches", False)

    async def _select_filter(
        self, items: List[ElementHandle], page: Page, filter: str
    ) -> Tuple[str, bool]:
        # Imprime la lista de items disponibles
        await self._print_elementhandles(items)
        # Pedirle al usuario que seleccione un item
        filter_chosen = await self._ask_user_for_input(items, filter)
        return await self._execute_user_input(items, page, filter_chosen)

    async def _ask_user_for_input(self, items: List[T], filter: str):
        while True:
            try:
                print()
                item_chosen = int(input(f"Seleccione el número de {filter}: ").strip())
                if item_chosen <= 0 or item_chosen > len(items):
                    raise ValueError
                return item_chosen
            except ValueError:
                print("El número que ingresó es inválido. Ingrese uno válido.")
                continue

    async def _execute_user_input(
        self, items: List[ElementHandle], page: Page, item_chosen: int
    ):
        print()
        console.rule("")
        await items[item_chosen - 1].click()
        item_text = (await items[item_chosen - 1].inner_text()).strip()
        await page.wait_for_function(
            f"""() => {{
                const chips = document.querySelectorAll('.movies-chips--chip');
                return Array.from(chips).some(chip => chip.innerText.includes("{item_text}"));
            }}"""
        )
        return (item_text, True)

    async def _print_elementhandles(self, items: List[ElementHandle]):
        strings = [(await item.inner_text()).strip() for item in items]
        self._print_list_of_items(strings)

    def _print_list_of_items(self, items: List[str]):
        print()
        max_length = max(len(item) for item in items)
        width_length = max_length + 8
        for i in range(0, len(items), 3):
            fila = Text()
            for j in range(3):
                idx = i + j
                if idx < len(items):
                    item = Text()
                    item.append(Text(f"{idx + 1}) ", style="cyan bold"))
                    item.append(Text(f"{items[idx]}", style="none"))
                    item.pad_right(width_length - len(item.plain))
                    fila.append(item)
            console.print(fila)

    async def load_all_movies(self, page: Page):
        # Si hay botón de "Ver más", se presiona. De lo contrario, se salta la función
        try:
            await page.wait_for_selector(".movies-list--view-more-button", timeout=2000)
            while True:
                try:
                    button = await page.query_selector(".movies-list--view-more-button")
                    if not button or not await button.is_visible():
                        break
                    await button.click()
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    print(f"Error al intentar hacer click en 'Ver más': {e}")
                    break
        except:
            return

    async def scrape_showtimes_data(self, page: Page, movie_data: dict):
        # Construir el diccionario de los cines y los horarios de proyección de la película
        showtimes_by_cinema: dict = {}
        cinema_elements = await page.query_selector_all(
            ".film-detail-showtimes--accordion"
        )
        for cine_idx in range(len(cinema_elements)):
            cinema_name, raw_data = await self._parse_showtimes_for_cinema(
                page, cine_idx
            )
            showtimes_by_cinema[cinema_name] = raw_data
        movie_data["showtimes"] = showtimes_by_cinema

    async def _parse_showtimes_for_cinema(
        self, page: Page, cine_idx: int
    ) -> Tuple[str, List[dict]]:
        cinema_elements = await page.query_selector_all(
            ".film-detail-showtimes--accordion"
        )
        cine = cinema_elements[cine_idx]
        cinema_name = await self._extract_cinema_name(cine)
        containers = await cine.query_selector_all(
            ".cinema-showcases--sessions-details"
        )
        raw_data: List = []
        for container_idx in range(len(containers)):
            showtime_block = await self._build_showtime_entry(
                page, cine_idx, container_idx
            )
            raw_data.append(showtime_block)
        return cinema_name, raw_data

    async def _extract_cinema_name(self, cine: ElementHandle) -> str:
        cinema_name = await cine.query_selector(".cinema-showcases--summary-name")
        return (await cinema_name.inner_text()).strip()

    async def _build_showtime_entry(
        self, page: Page, cine_idx: int, container_idx: int
    ) -> dict:
        # Formar el diccionario con las claves de formato, lenguaje y horarios de proyección
        cinema_elements = await page.query_selector_all(
            ".film-detail-showtimes--accordion"
        )
        cine = cinema_elements[cine_idx]
        containers = await cine.query_selector_all(
            ".cinema-showcases--sessions-details"
        )
        container = containers[container_idx]
        formats = await container.query_selector(".sessions-details--formats")
        # Extraer los formatos y lenguaje
        dimension_raw = await formats.query_selector(
            ".sessions-details--formats-dimension"
        )
        dimension = (await dimension_raw.inner_text()).strip()

        theather_raw = await formats.query_selector(
            ".sessions-details--formats-theather"
        )
        theather = (await theather_raw.inner_text()).strip()

        language_raw = await formats.query_selector(
            ".sessions-details--formats-language"
        )
        language = (await language_raw.inner_text()).strip()

        session_items = await container.query_selector_all(
            ".sessions-details--session-item"
        )
        showtimes: List[ElementHandle] = []
        for showtime_idx in range(len(session_items)):
            # Actualizar nodos después de page.go_back()
            cinema_elements = await page.query_selector_all(
                ".film-detail-showtimes--accordion"
            )
            cine = cinema_elements[cine_idx]
            if "accordion_expanded" not in (await cine.get_attribute("class") or ""):
                await cine.click()

            containers = await cine.query_selector_all(
                ".cinema-showcases--sessions-details"
            )
            container = containers[container_idx]
            session_items = await container.query_selector_all(
                ".sessions-details--session-item"
            )

            showtime_and_link = await self._parse_showtimes(
                session_items, showtime_idx, page
            )
            if showtime_and_link == []:
                continue

            showtimes.append(showtime_and_link)
        return {
            "dimension": dimension,
            "format": theather,
            "language": language,
            "showtimes": showtimes,
        }

    async def _parse_showtimes(
        self, session_items: List[ElementHandle], showtime_idx: int, page: Page
    ) -> List:
        # Extrae la hora y su enlace de compra
        showtime_data = []
        showtime = session_items[showtime_idx]
        class_attribute = await showtime.get_attribute("class") or ""
        if "showtime-selector_disable" in class_attribute:
            return []

        showtime = session_items[showtime_idx]
        showtime_button = await showtime.query_selector(".showtime-selector--link")
        showtime_text = (await showtime_button.inner_text()).strip()

        showtime_url = await self._click_extract_then_go_back(
            page,
            showtime_button,
            "**/compra/**/asientos",
            ".purchase-seating--seat-map",
            ".film-detail-showtimes--accordion",
        )

        showtime_data.append(showtime_text)
        showtime_data.append(showtime_url)
        return showtime_data

    async def _click_extract_then_go_back(
        self,
        page: Page,
        clickable_element: ElementHandle,
        expected_new_url: str,
        wait_for_selector_new_page: str,
        wait_for_selector_return_page: str,
    ) -> str:
        # Ingresa a la página de venta y guarda el URL
        try:
            previous_url = page.url
            await clickable_element.click()

            # Presionar el botón de confirmación de compra en caso aparezca
            confirm_purchase = await page.query_selector(
                ".call-to-action_rounded-solid.call-to-action_pink-solid.call-to-action_large"
            )
            if confirm_purchase:
                await confirm_purchase.click()

            await page.wait_for_url(expected_new_url, timeout=10000)
            await page.wait_for_selector(wait_for_selector_new_page, timeout=10000)
            current_url = page.url
        except TimeoutError:
            print(
                "[!] No se logró navegar correctamente o no se encontró el selector esperado."
            )
            current_url = "Error"
        finally:
            await page.go_back(wait_until="domcontentloaded")
            await page.wait_for_function(
                f"() => window.location.href === '{previous_url}'", timeout=10000
            )
            await page.wait_for_selector(wait_for_selector_return_page, timeout=10000)
        return current_url

    def save_json(self, output_folder, movie_data):
        file_path = os.path.join(output_folder, f"{slugify(movie_data['title'])}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(movie_data, f, ensure_ascii=False, indent=4)

    def save_excel(self, output_folder, movie_data):
        file_path = os.path.join(output_folder, f"{slugify(movie_data['title'])}.xlsx")
        rows = []

        for cinema, funciones in movie_data.get("showtimes", {}).items():
            for funcion in funciones:
                dimension = funcion.get("dimension", "")
                formato = funcion.get("format", "")
                idioma = funcion.get("language", "")

                for hora_url in funcion.get("showtimes", []):
                    hora, url = hora_url

                    rows.append(
                        {
                            "Título": movie_data.get("title", ""),
                            "Género": movie_data.get("genre", ""),
                            "Duración": movie_data.get("running_time", ""),
                            "Restricción de edad": movie_data.get(
                                "age_restriction", ""
                            ),
                            "Cine": cinema,
                            "Ciudad": movie_data.get("city", ""),
                            "Día": movie_data.get("day", ""),
                            "Dimensión": dimension,
                            "Formato": formato,
                            "Idioma": idioma,
                            "Hora": hora,
                            "URL": url,
                        }
                    )

        df = pandas.DataFrame(rows)
        df.to_excel(file_path, index=False)

    async def message_if_takes_time(self):
        try:
            await asyncio.sleep(5)
            console.print(
                "Espere un momento, es que hay [cyan]muchos horarios[/] por recopilar."
            )
            await asyncio.sleep(17)
            console.print(
                "Vaya, sí que hay [bold cyan]demasiados horarios[/] para esta película."
            )
        except asyncio.CancelledError:
            pass

    async def scrape(self, url: str):

        async with async_playwright() as p:
            # Abrir navegador y página web
            browser = await setup_browser(p)
            page = await load_page(browser, url, 'button:has-text("Aceptar Cookies")')

            # Aceptar cookies del sitio
            await self.accept_cookies(page)

            # Aplicar filtros
            city, cinema, day = await self.apply_filters(page)

            # Crear ruta de carpetas
            city_slugify = slugify(city)
            day_slugify = slugify(day, separator="_")
            cinema_slugify = slugify(cinema, separator="_")
            output_folder = (
                f"data/{city_slugify}/cineplanet/{cinema_slugify}/{day_slugify}"
            )
            os.makedirs(output_folder, exist_ok=True)

            # Preguntar al usuario en qué formato desea guardar la información
            formats = {"JSON": self.save_json, "Excel": self.save_excel}
            formats_keys = list(formats.keys())
            self._print_list_of_items(formats_keys)
            format_chosen = await self._ask_user_for_input(formats_keys, "formato")
            key_chosen = formats_keys[format_chosen - 1]
            format_to_save = formats[key_chosen]

            # Presionar el botón "Ver más películas" para cargar toda la cartelera
            await self.load_all_movies(page)

            # Almacenar cada div que contiene toda la informació de la película
            movies = await page.query_selector_all(".movies-list--large-item")

            # Iterar sobre cada película
            with console.status(
                "[bold green]Recopilando información de películas...[/]",
                spinner="bouncingBall",
                spinner_style="bold green",
            ):

                for i in range(len(movies)):
                    movie = movies[i]
                    # Diccionario para cada película
                    movie_data = {}

                    # Extraer información general de la películas
                    await extract_general_information(
                        movie,
                        movie_data,
                        ".movies-list--large-movie-description-title",
                        ".movies-list--large-movie-description-extra",
                        ".image-loader--image_loaded",
                        ", ",
                    )

                    filters = await page.query_selector_all(".movies-chips--chip")
                    for i, filter in enumerate(filters):
                        if i == 0:
                            movie_data["city"] = (await filter.inner_text()).strip()
                        elif i == 1:
                            movie_data["cinema"] = (await filter.inner_text()).strip()
                        else:
                            movie_data["day"] = (await filter.inner_text()).strip()

                    # Ingresar a la página específica de la película
                    console.print(
                        f"\n[cyan]▶️ Recopilando horarios de proyección de [bold]{movie_data['title']}[/bold][/cyan]"
                    )
                    await enter_movie_details_page(
                        movie,
                        page,
                        ".movie-info-details--second-button",
                        ".movie-details--info",
                    )

                    # Extraer datos para luego armar diccionario
                    wait_message = asyncio.create_task(self.message_if_takes_time())
                    await self.scrape_showtimes_data(page, movie_data)
                    wait_message.cancel()

                    # Guardar la información según el formato escogido
                    format_to_save(output_folder, movie_data)
                    console.print(
                        f"[green]✅ Horarios de [bold]{movie_data['title']}[/bold] guardados[/green]"
                    )

                    # Vover a la página anterior (cartelera)
                    await page.go_back()
                    await page.wait_for_selector(".movies-list--large-item")
                    await self.load_all_movies(page)
                    movies = await page.query_selector_all(".movies-list--large-item")

                console.print(
                    "\n[bold green]🎉 ¡Todos los horarios han sido guardados exitosamente![/bold green]"
                )
                await browser.close()


if __name__ == "__main__":
    asyncio.run(CineplanetScraper().scrape("https://www.cineplanet.com.pe/peliculas"))
