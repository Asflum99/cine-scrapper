from playwright.async_api import async_playwright, Page, ElementHandle, TimeoutError
from scrapers.base_scraper import BaseScraper
from scrapers.utils.browser_utils import (
    setup_browser_and_load_page,
    extract_general_information,
    enter_movie_details_page,
)
from slugify import slugify
from typing import List, Tuple
from rich.progress import track
import json, os, asyncio, pandas


class CineplanetScraper(BaseScraper):

    async def accept_cookies(self, page: Page):
        # Espera y hace clic en el botón "Aceptar Cookies" para cerrar el aviso, si existe
        try:
            button = await page.query_selector('button:has-text("Aceptar Cookies")')
            if button and await button.is_visible():
                await button.click()
        except Exception as e:
            print("No se encontró botón de cookies o hubo un problema:", e)

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
                "Ciudad": self._select_city,
                "Cine": self._select_cinema,
                "Día": self._select_day,
            }

            if specific_filter in filters:
                return filters[specific_filter](items, page)

        # Si no hay ningún filtro que coincida, se retorna nada
        return ("Filters don't matches", False)

    async def _select_city(
        self, cities: List[ElementHandle], page: Page
    ) -> Tuple[str, bool]:
        # Imprime la lista de ciudades disponibles
        await self._print_elementhandles(cities)
        # Pedirle al usuario que seleccione una ciudad
        return await self._ask_user_for_input(cities, page, "cine")

    async def _select_cinema(
        self, cinemas: List[ElementHandle], page: Page
    ) -> Tuple[str, bool]:
        # Imprime la lista de cines disponibles
        await self._print_elementhandles(cinemas)
        # Se le pide al usuario seleccionar un cine
        return await self._ask_user_for_input(cinemas, page, "cine")

    async def _select_day(
        self, days: List[ElementHandle], page: Page
    ) -> Tuple[str, bool]:
        # Imprime la lista de días disponibles
        await self._print_elementhandles(days)
        # Se le pide al usuario seleccionar un día
        return await self._ask_user_for_input(days, page, "día")

    async def _ask_user_for_input(
        self, items: List[ElementHandle], page: Page, filter: str
    ):
        item_chosen = int(input(f"Seleccione el número de {filter}: ").strip())
        for item in items:
            if (await item.inner_text()).strip() == (
                await items[item_chosen - 1].inner_text()
            ).strip():
                await item.click()
                item_text = (await item.inner_text()).strip()
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
        max_length = max(len(item) for item in items)
        width_length = max_length + 4
        for i in range(0, len(items), 3):
            fila = ""
            for j in range(3):
                idx = i + j
                if idx < len(items):
                    item = f"{idx + 1}) {items[idx]}"
                    fila += item.ljust(width_length)
            print(fila)

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
            print("Espera un momento, es que hay muchas funciones por recopilar.")
            await asyncio.sleep(17)
            print("Vaya, sí que hay demasiadas funciones para esta película.")
        except asyncio.CancelledError:
            pass

    async def scrape(self, url: str):

        async with async_playwright() as p:
            # Abrir navegador y página web
            browser, page = await setup_browser_and_load_page(p, url, 'button:has-text("Aceptar Cookies")')

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
            format_choice = int(
                input(
                    "Escoja el número de formato en el que desea guardar la información: "
                ).strip()
            )
            key_chosen = formats_keys[format_choice - 1]
            function_to_execute = formats[key_chosen]

            # Presionar el botón "Ver más películas" para cargar toda la cartelera
            await self.load_all_movies(page)

            # Almacenar cada div que contiene toda la informació de la película
            movies = await page.query_selector_all(".movies-list--large-item")

            # Iterar sobre cada película
            for i in track(range(len(movies)), description="Recopilando información de películas"):
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
                print(f"Recopilando horarios de proyección de {movie_data['title']}...")
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
                function_to_execute(output_folder, movie_data)
                print(f"Horarios de {movie_data["title"]} guardados")

                # Vover a la página anterior (cartelera)
                await page.go_back()
                await page.wait_for_selector(".movies-list--large-item")
                await self.load_all_movies(page)
                movies = await page.query_selector_all(".movies-list--large-item")

            print(
                f"Todos los horarios de las películas disponibles en {movie_data["cinema"]} para {movie_data["day"]} han sido guardados exitosamente."
            )
            await browser.close()


if __name__ == "__main__":
    asyncio.run(CineplanetScraper().scrape("https://www.cineplanet.com.pe/peliculas"))
