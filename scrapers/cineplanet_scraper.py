from playwright.sync_api import sync_playwright, Page
from scrapers.base_scraper import BaseScraper
from scrapers.utils.browser_utils import (
    setup_browser_and_load_page,
    extract_general_information,
    enter_movie_details_page,
)
from slugify import slugify
from typing import List
import json, os


class CineplanetScraper(BaseScraper):

    def accept_cookies(self, page: Page):
        try:
            button = page.wait_for_selector('button:has-text("Aceptar Cookies")')
            if button and button.inner_text().strip() == "Aceptar Cookies":
                button.click()
        except Exception as e:
            print("No se encontró botón de cookies o hubo un problema:", e)

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

    def extract_data_for_dictionary(self, page: Page, movie_data: dict):
        cinemas = page.query_selector_all(".film-detail-showtimes--accordion")
        showtimes_by_cinema: dict = {}
        for cine in cinemas:
            # Extraer nombre del cine
            cinemas_containers = cine.query_selector_all(
                ".cinema-showcases--sessions-details"
            )
            cinema_name = (
                cine.query_selector(".cinema-showcases--summary-name")
                .inner_text()
                .strip()
            )
            raw_data: List = []
            for cinema_container in cinemas_containers:
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
                        showtime.query_selector(".showtime-selector--link")
                        .inner_text()
                        .strip()
                    )
                raw_data.append(
                    {
                        "dimension": dimension,
                        "format": theather,
                        "language": language,
                        "showtimes": showtimes,
                    }
                )
            showtimes_by_cinema[cinema_name] = raw_data
        movie_data["showtimes"] = showtimes_by_cinema

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

            # Seleccionar Lima como ciudad
            cities = page.query_selector_all(
                ".movies-filter--filter-category-list-item-label"
            )
            for city in cities:
                if city.inner_text().strip() == "Lima":
                    city.click()

            # Seleccionar el presente día
            days = page.query_selector_all(".")

            # Presionar el botón "Ver más películas" para cargar toda la cartelera
            self.load_all_movies(page)

            # Almacenar cada div que contiene toda la informació de la película
            movies = page.query_selector_all(".movies-list--large-item")

            output_folder = "data/cineplanet"
            os.makedirs(output_folder, exist_ok=True)
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

                # Ingresar a la página específica de la película
                enter_movie_details_page(
                    movie,
                    page,
                    ".movie-info-details--second-button",
                    ".movie-details--info",
                )

                # Extraer datos para luego armar diccionario
                self.extract_data_for_dictionary(page, movie_data)

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
