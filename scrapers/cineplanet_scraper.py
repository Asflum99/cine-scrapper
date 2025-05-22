from playwright.sync_api import sync_playwright
from .base_scraper import BaseScraper
from slugify import slugify
import json, os


class CineplanetScraper(BaseScraper):

    def setup_browser_and_load_page(self, p, url):
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url)
        return browser, page

    def accept_cookies(self, page):
        try:
            button = page.wait_for_selector('button:has-text("Aceptar Cookies")')
            if button and button.inner_text().strip() == "Aceptar Cookies":
                button.click()
        except Exception as e:
            print("No se encontró botón de cookies o hubo un problema:", e)

    def load_all_movies(self, page):
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

    def extract_general_information(self, movie, movie_data):
        title = movie.query_selector(".movies-list--large-movie-description-title")
        movie_data["title"] = title.inner_text().strip()

        # Extraer género, duración y restricción de edad
        keys = ["genre", "running_time", "age_restriction"]
        movie_info_extra = movie.query_selector(
            ".movies-list--large-movie-description-extra"
        )
        extras = movie_info_extra.inner_text().strip().split(",")

        for key, extra in zip(keys, extras):
            movie_data[key] = extra.strip()

        # Extraer url de imagen
        image = movie.query_selector(".image-loader--image_loaded")
        movie_data["image_url"] = image.get_attribute("src")

    def extract_specific_information(self, movie, page, movie_data):
        button = movie.query_selector(".movie-info-details--second-button")
        button.click()
        page.wait_for_selector(".movie-details--info")
        self.extract_info_from_details_page(page, movie_data)

    def extract_info_from_details_page(self, page, movie_data):
        # Extraer idiomas disponibles
        languages = page.query_selector_all(".movie-details--info-chip")
        languages_list = []
        for lang in languages:
            languages_list.append(lang.inner_text().strip())
        movie_data["languages"] = languages_list

        # Extraer formatos disponibles
        labels = page.query_selector_all(".movie-details--info-label")
        for label in labels:
            if label.inner_text().strip() == "Disponible":
                sibling = label.evaluate_handle("el => el.nextElementSibling")
                formats = sibling.evaluate("el => el.textContent").strip().split(",")
                format_list = []
                for format in formats:
                    format_list.append(format.strip())
                movie_data["available_formats"] = format_list
    
    def extract_showtimes(self, page, movie_data):
        select = page.query_selector("select.dropdown--select")
        select.select_option("Lima")

        page.wait_for_function(
            """
            () => {
                const label = document.querySelector(".dropdown--label-container");
                return label && label.innerText.trim() === "Lima";
            }
        """
        )
        cinemas = page.query_selector_all(".film-detail-showtimes--accordion")
        for cine in cinemas:
            # Extraer nombre del cine
            cinema_name = (
                cine.query_selector(".cinema-showcases--summary-name")
                .inner_text()
                .strip()
            )

            # Extraer formatos de proyección de la película
            details = cine.query_selector_all(".cinema-showcases--sessions-details")
            movie_data[cinema_name] = {}
            for formats in details:
                format_type = formats.query_selector(".sessions-details--formats")
                dimension = (
                    format_type.query_selector(".sessions-details--formats-dimension")
                    .inner_text()
                    .strip()
                )
                theather = (
                    format_type.query_selector(".sessions-details--formats-theather")
                    .inner_text()
                    .strip()
                )
                language = (
                    format_type.query_selector(".sessions-details--formats-language")
                    .inner_text()
                    .strip()
                )
                movie_details = f"{dimension} {theather} {language}"
                # Extraer horarios de proyección de la película
                showtimes_list = []
                showtimes = formats.query_selector_all(".showtime-selector--link")
                for showtime in showtimes:
                    showtimes_list.append(showtime.inner_text().strip())
                movie_data[cinema_name][movie_details] = showtimes_list

    def save_json(self, output_folder, movie_data):
        file_path = os.path.join(output_folder, f"{slugify(movie_data['title'])}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(movie_data, f, ensure_ascii=False, indent=4)

    def scrape(self, url: str):

        with sync_playwright() as p:
            # Abrir navegador y página web
            browser, page = self.setup_browser_and_load_page(p, url)

            # Aceptar cookies del sitio
            self.accept_cookies(page)

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
                self.extract_general_information(movie, movie_data)

                # Ingresar a la página específica de la película y extraer información específica
                self.extract_specific_information(movie, page, movie_data)

                # Extraer los horarios de proyección
                self.extract_showtimes(page, movie_data)

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
