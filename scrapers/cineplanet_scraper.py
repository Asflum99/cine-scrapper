from playwright.async_api import async_playwright, Page, TimeoutError, Locator, Browser, Playwright
from scrapers.base_scraper import BaseScraper
from scrapers.utils.browser_utils import (
    setup_browser,
    load_page,
    extract_general_information,
    enter_movie_details_page,
)
from slugify import slugify
from typing import List, Tuple, Callable
from rich.text import Text
from rich.console import Console
from rich.traceback import install
import json, os, asyncio, pandas

console = Console()
install()


class CineplanetScraper(BaseScraper):

    async def accept_cookies(self, page: Page):
        button = page.locator("button:has-text('Aceptar Cookies')")
        # Espera y hace clic en el botón "Aceptar Cookies" para cerrar el aviso, si existe
        try:
            await button.wait_for(timeout=2000)
            if await button.is_visible():
                await button.click()
        except TimeoutError:
            print("No se encontró botón de cookies o hubo un problema")

    async def apply_filters(self, page: Page) -> List[str]:
        # Selecciona todos los filtros y solo aplica los de "Ciudad", "Cine" y "Día"
        filters = page.locator(".movies-filter--filter-category-accordion")
        count = await filters.count()
        city_filter_added = False
        cinema_filter_added = False
        day_filter_added = False
        data: List = []
        for i in range(count):
            if not city_filter_added:
                # Aplica el filtro de "Ciudad"
                raw_data = await self._apply_specific_filter(
                    filters.nth(i), "Ciudad", page
                )
                city, city_filter_added = await raw_data
                if city_filter_added:
                    data.append(city)
                    continue
            if not cinema_filter_added:
                # Aplica el filtro de "Cine"
                raw_data = await self._apply_specific_filter(
                    filters.nth(i), "Cine", page
                )
                cinema, cinema_filter_added = await raw_data
                if cinema_filter_added:
                    data.append(cinema)
                    continue
            if not day_filter_added:
                # Aplica el filtro de "Día"
                raw_data = await self._apply_specific_filter(
                    filters.nth(i), "Día", page
                )
                day, day_filter_added = await raw_data
                if day_filter_added:
                    data.append(day)
                    break
        return data

    async def _apply_specific_filter(
        self,
        filter: Locator,
        specific_filter: str,
        page: Page,
    ) -> Tuple[str, bool]:
        title_element = filter.locator(
            ".movies-filter--filter-category-accordion-trigger h3"
        )
        if not title_element:
            return ("Missing filter title", False)
        if (await title_element.inner_text()).strip() == specific_filter:
            classes = await filter.get_attribute("class")
            # Verificar si el acordeón del filtro está expandido
            if "accordion_expanded" not in classes:
                await filter.click()

            items = filter.locator(".movies-filter--filter-category-list-item-label")

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
        self, items: Locator, page: Page, filter: str
    ) -> Tuple[str, bool]:
        # Imprime la lista de items disponibles
        await self._print_locators(items)
        # Pedirle al usuario que seleccione un item
        filter_chosen = await self._ask_user_for_input(items, filter)
        return await self._execute_user_input(items, page, filter_chosen)

    async def _ask_user_for_input(self, items, filter: str):
        while True:
            try:
                print()

                if isinstance(items, Locator):
                    total = await items.count()
                else:
                    total = len(items)

                item_chosen = int(input(f"Seleccione el número de {filter}: ").strip())
                if item_chosen <= 0 or item_chosen > total:
                    raise ValueError
                return item_chosen
            except ValueError:
                print("El número que ingresó es inválido. Ingrese uno válido.")
                continue

    async def _execute_user_input(self, items: Locator, page: Page, item_chosen: int):
        print()
        console.rule("")
        items_idx = item_chosen - 1
        selected_item = items.nth(items_idx)
        item_text = (await selected_item.inner_text()).strip()
        await items.nth(items_idx).click()
        await page.wait_for_function(
            f"""() => {{
                const chips = document.querySelectorAll('.movies-chips--chip');
                return Array.from(chips).some(chip => chip.innerText.includes("{item_text}"));
            }}"""
        )
        return (item_text, True)

    async def _print_locators(self, items: Locator):
        count = await items.count()
        strings = []
        for i in range(count):
            strings.append((await items.nth(i).inner_text()).strip())
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
        button = page.locator(".movies-list--view-more-button")
        # Intenta detectar el botón por 2 segundos
        try:
            await button.wait_for(timeout=2000)
        except:
            return  # Si no aparece, termina

        while True:
            try:
                if not await button.is_visible():
                    break
                await button.click()
                await page.wait_for_timeout(1000)
            except TimeoutError:
                print(f"Error al intentar hacer click en 'Ver más'")
                break

    async def scrape_showtimes_data(self, page: Page, movie_data: dict):
        # Construir el diccionario de los cines y los horarios de proyección de la película
        showtimes_by_cinema: dict = {}
        cinema_elements = page.locator(".film-detail-showtimes--accordion")
        cinema_elements_count = await cinema_elements.count()
        for cine_idx in range(cinema_elements_count):
            cinema_name, raw_data = await self._parse_showtimes_for_cinema(
                page, cine_idx
            )
            showtimes_by_cinema[cinema_name] = raw_data
        movie_data["showtimes"] = showtimes_by_cinema

    async def _parse_showtimes_for_cinema(
        self, page: Page, cine_idx: int
    ) -> Tuple[str, List[dict]]:
        cinema_elements = page.locator(".film-detail-showtimes--accordion")
        cine = cinema_elements.nth(cine_idx)
        cinema_name = await self._extract_cinema_name(cine)
        containers = cine.locator(".cinema-showcases--sessions-details")
        containers_count = await containers.count()
        raw_data: List = []
        for container_idx in range(containers_count):
            showtime_block = await self._build_showtime_entry(
                page, cine_idx, container_idx
            )
            raw_data.append(showtime_block)
        return cinema_name, raw_data

    async def _extract_cinema_name(self, cine: Locator) -> str:
        cinema_name = cine.locator(".cinema-showcases--summary-name")
        return (await cinema_name.inner_text()).strip()

    async def _build_showtime_entry(
        self, page: Page, cine_idx: int, container_idx: int
    ) -> dict:
        # Formar el diccionario con las claves de formato, lenguaje y horarios de proyección
        cinema_elements = page.locator(".film-detail-showtimes--accordion")
        cine = cinema_elements.nth(cine_idx)
        containers = cine.locator(".cinema-showcases--sessions-details")
        container = containers.nth(container_idx)
        formats = container.locator(".sessions-details--formats")

        # Extraer los formatos y lenguaje
        dimension_raw = formats.locator(".sessions-details--formats-dimension")
        dimension = (await dimension_raw.inner_text()).strip()

        theather_raw = formats.locator(".sessions-details--formats-theather")
        theather = (await theather_raw.inner_text()).strip()

        language_raw = formats.locator(".sessions-details--formats-language")
        language = (await language_raw.inner_text()).strip()

        session_items = container.locator(".sessions-details--session-item")
        session_items_count = await session_items.count()
        showtimes: List[str] = []
        for showtime_idx in range(session_items_count):
            # Actualizar nodos después de page.go_back()
            cinema_elements = page.locator(".film-detail-showtimes--accordion")
            cine = cinema_elements.nth(cine_idx)
            if "accordion_expanded" not in (await cine.get_attribute("class") or ""):
                await cine.click()

            containers = cine.locator(".cinema-showcases--sessions-details")
            container = containers.nth(container_idx)
            session_items = container.locator(".sessions-details--session-item")

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
        self, session_items: Locator, showtime_idx: int, page: Page
    ) -> List[str]:
        # Extrae la hora y su enlace de compra
        showtime_data = []
        showtime = session_items.nth(showtime_idx)
        class_attribute = await showtime.get_attribute("class") or ""
        if "showtime-selector_disable" in class_attribute:
            return []

        showtime_button = showtime.locator(".showtime-selector--link")
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
        clickable_element: Locator,
        expected_new_url: str,
        wait_for_selector_new_page: str,
        wait_for_selector_return_page: str,
    ) -> str:
        # Ingresa a la página de venta y guarda el URL
        try:
            previous_url = page.url
            await clickable_element.click()

            # Presionar el botón de confirmación de compra en caso aparezca
            buy_tickets_section = page.locator(
                ".call-to-action_rounded-solid.call-to-action_pink-solid.call-to-action_large"
            )
            if await buy_tickets_section.is_visible():
                await buy_tickets_section.click()

            await page.wait_for_url(expected_new_url)
            await page.locator(wait_for_selector_new_page).wait_for(timeout=5000)
            current_url = page.url
        except TimeoutError:
            print("[!] No se logró navegar correctamente")
            current_url = "Error"
        finally:
            await page.go_back(wait_until="domcontentloaded")
            await page.locator(wait_for_selector_return_page).wait_for(timeout=5000)

        return current_url

    def save_json(self, output_folder: str, movie_data: dict):
        file_path = os.path.join(output_folder, f"{slugify(movie_data['title'])}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(movie_data, f, ensure_ascii=False, indent=4)

    def save_excel(self, output_folder: str, movie_data: dict):
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

    async def prepare_scrapping(self, p: Playwright, url: str) -> Tuple[Browser, Page, Locator, str, Callable]:
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

        # Todos los divs de las películas
        movies = page.locator(".movies-list--large-item")

        return browser, page, movies, output_folder, format_to_save

    async def process_movies(
        self,
        page: Page,
        movies: Locator,
        output_folder: str,
        format_to_save,
    ):
        movies_count = await movies.count()
        for i in range(movies_count):
            movie = movies.nth(i)
            movie_data = {}

            await extract_general_information(
                movie,
                movie_data,
                ".movies-list--large-movie-description-title",
                ".movies-list--large-movie-description-extra",
                ".image-loader--image_loaded",
                ", ",
            )

            filters = page.locator(".movies-chips--chip")
            filters_count = await filters.count()

            for i in range(filters_count):
                text = (await filters.nth(i).inner_text()).strip()
                if i == 0:
                    movie_data["city"] = text
                elif i == 1:
                    movie_data["cinema"] = text
                else:
                    movie_data["day"] = text

            console.print(
                f"\n[cyan]▶️ Recopilando horarios de proyección de [bold]{movie_data['title']}[/bold][/cyan]"
            )

            await enter_movie_details_page(
                movie,
                page,
                ".movie-info-details--second-button",
                ".movie-details--info",
            )

            wait_message = asyncio.create_task(self.message_if_takes_time())
            await self.scrape_showtimes_data(page, movie_data)
            wait_message.cancel()

            format_to_save(output_folder, movie_data)
            console.print(
                f"[green]✅ Horarios de [bold]{movie_data['title']}[/bold] guardados[/green]"
            )

            await page.go_back()
            await page.wait_for_selector(".movies-list--large-item")
            await self.load_all_movies(page)
            movies = page.locator(".movies-list--large-item")

    async def scrape(self, url: str):
        async with async_playwright() as p:
            browser, page, movies, output_folder, format_to_save = (
                await self.prepare_scrapping(p, url)
            )

            with console.status(
                "[bold green]Recopilando información de películas...[/]",
                spinner="bouncingBall",
                spinner_style="bold green",
            ):
                await self.process_movies(page, movies, output_folder, format_to_save)

            console.print(
                "\n[bold green]🎉 ¡Todos los horarios han sido guardados exitosamente![/bold green]"
            )
            await browser.close()


if __name__ == "__main__":
    asyncio.run(CineplanetScraper().scrape("https://www.cineplanet.com.pe/peliculas"))
