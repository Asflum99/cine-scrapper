from playwright.sync_api import sync_playwright
from scrapers.base_scraper import BaseScraper


class CineplanetScraper(BaseScraper):

    def scrape(self, url: str):
        url = "https://www.cineplanet.com.pe/peliculas"
        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)  # Preguntar
            page = browser.new_page()
            page.goto(url)

            # Esperar a que algún selector este visible o cargado
            page.wait_for_selector(".movies-list")

            while True:
                try:
                    button = page.query_selector(
                        ".movies-list--view-more-button-wrapper"
                    )
                    if not button or not button.is_visible():
                        break
                    button.click()
                    page.wait_for_timeout(1000)
                except Exception as e:
                    print(f"Error al intentar hacer clic en 'Ver más': {e}")
                    break

            # Extraer div container con información de la película
            movies = page.query_selector_all(".movies-list--large-item-content-wrapper")

            for movie in movies:
                # Diccionario para cada película
                movie_data = {}

                # Extraer título
                title = movie.query_selector(
                    ".movies-list--large-movie-description-title"
                )
                movie_data["title"] = title.inner_text().strip()

                # Extraer género, duración y restricción de edad
                # TODO: Considerar si colocar DNI o no
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

            browser.close()
        return results


if __name__ == "__main__":
    scraper = CineplanetScraper()
    movies = scraper.scrape()
    print(movies)
