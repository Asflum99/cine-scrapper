from playwright.sync_api import sync_playwright, expect, Page
from scrapers.base_scraper import BaseScraper
from scrapers.utils.browser_utils import (
    setup_browser_and_load_page,
    extract_general_information,
    enter_movie_details_page,
)
from slugify import slugify
import json, os


class UvkScrapers(BaseScraper):

    def extract_info_from_details_page(self, page: Page, movie_data: dict):
        movie_extra_info = page.query_selector_all(".language-tag")
        languages = []
        for extra in reversed(movie_extra_info):
            genre_added = False
            if genre_added:
                languages.append(extra.inner_text().strip())
            else:
                movie_data["genre"] = extra.inner_text().strip()
                genre_added = True
        movie_data["languages"] = languages

    def filter_cinemas(self, page: Page) -> list:
        cinemas = page.query_selector_all(".cinema-shows")  # TESTEAR

        exclude = ["UVK ILO", "UVK TUMBES"]

        cinemas_filtered = []

        for cinema in cinemas:
            cinema_title = cinema.query_selector(".cinema-title")
            if cinema_title:
                title_text = cinema_title.inner_text().strip()
                if title_text not in exclude:
                    cinemas_filtered.append(cinema)
        return cinemas_filtered

    def extract_showtimes(self, cinemas: list, page: Page, movie_data: dict):
        # TODO:
        pass

    def scrape(self, url: str):
        with sync_playwright() as p:
            # Abrir navegador y página web
            broswer, page = setup_browser_and_load_page(p, url)

            # Marcar la casilla de Lima y esperar a que se actualice
            page.check("#cb-City-0")
            expect(page.locator("#cityCounter")).to_have_text("1")

            # Almacenar cada div container que contiene toda la información
            movies = page.query_selector_all(".movie-list-item")

            output_folder = "data/uvk"
            os.makedirs(output_folder, exist_ok=True)
            for i in range(len(movies)):
                movie = movies[i]
                # Diccionario para cada película
                movie_data = {}

                # Extraer información general de las películas
                title = movie.query_selector("h5.title")
                movie_data["title"] = title.inner_text().strip()

                # Extraer género, duración y restricción de edad
                extract_general_information(
                    movie,
                    movie_data,
                    "h5.title",
                    ".movie-tags",
                    ".movie-thumb img",
                    "|",
                )

                # Entrar a la sección detalles de la película
                enter_movie_details_page(movie, page, ".movie-thumb a", ".text-left")

                # Extraer información específica de la película
                self.extract_info_from_details_page(page, movie_data)

                cinemas = self.filter_cinemas(page)


if __name__ == "__main__":
    UvkScrapers().scrape("https://uvk.pe/peliculas")
