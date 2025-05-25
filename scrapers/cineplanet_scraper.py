from playwright.sync_api import sync_playwright, Page, ElementHandle
from scrapers.base_scraper import BaseScraper
from scrapers.utils.browser_utils import (
    setup_browser_and_load_page,
    extract_general_information,
    enter_movie_details_page,
)
from slugify import slugify
from typing import List, Tuple
import json, os


class CineplanetScraper(BaseScraper):

    def accept_cookies(self, page: Page):
        try:
            button = page.wait_for_selector('button:has-text("Aceptar Cookies")')
            if button and button.inner_text().strip() == "Aceptar Cookies":
                button.click()
        except Exception as e:
            print("No se encontró botón de cookies o hubo un problema:", e)

    def apply_filters(self, page: Page) -> List[str]:
        filters = page.query_selector_all(".movies-filter--filter-category-accordion")
        city_filter_added = False
        day_filter_added = False
        data: List = []
        for filter in filters:
            if not city_filter_added:
                # Aplicar filtros de ciudad
                raw_data = self._apply_specific_filter(
                    filter,
                    "Ciudad",
                    page,
                )
                city, city_filter_added = raw_data
                if city_filter_added:
                    data.append(city)
                    continue
            if not day_filter_added:
                # Aplicar filtros de día
                raw_data = self._apply_specific_filter(filter, "Día", page)
                day, day_filter_added = raw_data
                if day_filter_added:
                    data.append(day)
                    break
        return data

    def _apply_specific_filter(
        self,
        filter: ElementHandle,
        specific_filter: str,
        page: Page,
    ) -> Tuple[str, bool]:
        title_element = filter.query_selector(
            ".movies-filter--filter-category-accordion-trigger h3"
        )
        if not title_element:
            return ("Missing filter title", False)
        if title_element.inner_text().strip() == specific_filter:
            # Activar acordeón
            classes = filter.get_attribute("class")
            if "accordion_expanded" not in classes:
                filter.click()

            cities = filter.query_selector_all(
                ".movies-filter--filter-category-list-item-label"
            )

            # Escoger filtro
            if specific_filter == "Ciudad":
                city, city_selected = self._select_city(cities, page)
                return (city, city_selected)
            elif specific_filter == "Día":
                day, day_selected = self._select_day(cities, page)
                return (day, day_selected)
        return ("Filters don't matches", False)

    def _select_city(self, cities: List[ElementHandle], page: Page) -> Tuple[str, bool]:
        city_chosen = slugify(input("Escoja una ciudad: ")).strip().lower()
        for city in cities:
            city_text = city.inner_text().strip()
            if slugify(city_text) == city_chosen:
                city.click()
                page.wait_for_function(
                    f"""() => {{
                        const chips = document.querySelectorAll('.movies-chips--chip');
                        return Array.from(chips).some(chip => chip.innerText.includes("{city_text}"));
                    }}"""
                )
                return (city_text, True)
        return ("No match found", False)

    def _select_day(self, days: List[ElementHandle], page: Page) -> Tuple[str, bool]:
        day_chosen = slugify(input("Escoja un día: ").strip().lower())
        for day in days:
            day_text = slugify(day.inner_text().strip())
            if day_chosen in day_text:
                day.click()
                day_text = day.inner_text().strip()
                page.wait_for_function(
                    f"""() => {{
                        const chips = document.querySelectorAll('.movies-chips--chip');
                        return Array.from(chips).some(chip => chip.innerText.includes("{day_text}"));
                    }}"""
                )
                return (day_text, True)
        return ("No match found", False)

    def load_all_movies(self, page: Page):
        page.wait_for_selector(".movies-list--view-more-button")

        while True:
            try:
                button = page.query_selector(".movies-list--view-more-button")
                if not button or not button.is_visible():
                    break
                button.click()
                page.wait_for_timeout(1000)
            except Exception as e:
                print(f"Error al intentar hacer click en 'Ver más': {e}")
                break

    def scrape_showtimes_data(self, page: Page, movie_data: dict):
        cinemas = page.query_selector_all(".film-detail-showtimes--accordion")
        showtimes_by_cinema: dict = {}
        for cine in cinemas:
            cinema_name, raw_data = self._parse_showtimes_for_cinema(cine)
            showtimes_by_cinema[cinema_name] = raw_data
        movie_data["showtimes"] = showtimes_by_cinema

    def _parse_showtimes_for_cinema(
        self, cine: ElementHandle
    ) -> Tuple[str, List[dict]]:
        cinemas_containers = cine.query_selector_all(
            ".cinema-showcases--sessions-details"
        )
        cinema_name = self._extract_cinema_name(cine)
        raw_data: List = []
        for cinema_container in cinemas_containers:
            showtime_block = self._build_showtime_entry(cinema_container)
            raw_data.append(showtime_block)
        return cinema_name, raw_data

    def _extract_cinema_name(self, cine: ElementHandle) -> str:
        return (
            cine.query_selector(".cinema-showcases--summary-name").inner_text().strip()
        )

    def _build_showtime_entry(self, cinema_container: ElementHandle) -> dict:
        formats = cinema_container.query_selector(".sessions-details--formats")
        dimension = (
            formats.query_selector(".sessions-details--formats-dimension")
            .inner_text()
            .strip()
        )
        theather = (
            formats.query_selector(".sessions-details--formats-theather")
            .inner_text()
            .strip()
        )
        language = (
            formats.query_selector(".sessions-details--formats-language")
            .inner_text()
            .strip()
        )
        showtimes = []
        showtimes_list = cinema_container.query_selector_all(
            ".sessions-details--session-item"
        )
        for showtime in showtimes_list:
            showtimes.append(
                showtime.query_selector(".showtime-selector--link").inner_text().strip()
            )
        return {
            "dimension": dimension,
            "format": theather,
            "language": language,
            "showtimes": showtimes,
        }

    def save_json(self, output_folder, movie_data):
        file_path = os.path.join(output_folder, f"{slugify(movie_data['title'])}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(movie_data, f, ensure_ascii=False, indent=4)

    def scrape(self, url: str):

        with sync_playwright() as p:
            # Abrir navegador y página web
            browser, page = setup_browser_and_load_page(p, url)

            # Aceptar cookies del sitio
            self.accept_cookies(page)

            # Aplicar filtros
            city, day = self.apply_filters(page)

            # Presionar el botón "Ver más películas" para cargar toda la cartelera
            self.load_all_movies(page)

            # Almacenar cada div que contiene toda la informació de la película
            movies = page.query_selector_all(".movies-list--large-item")

            # Crear ruta de carpetas
            city_slugify = slugify(city)
            day_slugify = slugify(day, separator="_")
            output_folder = f"data/{city_slugify}/cineplanet/{day_slugify}"
            os.makedirs(output_folder, exist_ok=True)

            # Iterar sobre cada película
            for i in range(len(movies)):
                movie = movies[i]
                # Diccionario para cada película
                movie_data = {}

                # Extraer información general de la películas
                extract_general_information(
                    movie,
                    movie_data,
                    ".movies-list--large-movie-description-title",
                    ".movies-list--large-movie-description-extra",
                    ".image-loader--image_loaded",
                    ", ",
                )

                filters = page.query_selector_all(".movies-chips--chip")
                for i, filter in enumerate(filters):
                    if i == 0:
                        movie_data["city"] = filter.inner_text().strip()
                    else:
                        movie_data["day"] = filter.inner_text().strip()

                # Ingresar a la página específica de la película
                enter_movie_details_page(
                    movie,
                    page,
                    ".movie-info-details--second-button",
                    ".movie-details--info",
                )

                # Extraer datos para luego armar diccionario
                self.scrape_showtimes_data(page, movie_data)

                # Guardar toda la información en un archivo JSON
                self.save_json(output_folder, movie_data)

                # Vover a la página anterior (cartelera)
                page.go_back()
                page.wait_for_selector(".movies-list--large-item")
                self.load_all_movies(page)
                movies = page.query_selector_all(".movies-list--large-item")

            browser.close()


if __name__ == "__main__":
    CineplanetScraper().scrape("https://www.cineplanet.com.pe/peliculas")
