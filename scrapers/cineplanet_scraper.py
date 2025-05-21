from playwright.sync_api import sync_playwright
from base_scraper import BaseScraper


class CineplanetScraper(BaseScraper):

    def scrape(self, url: str):
        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(url)

            # Esperar a que algún selector este visible o cargado
            try:
                button = page.wait_for_selector('button:has-text("Aceptar Cookies")')
                if button and button.inner_text().strip() == "Aceptar Cookies":
                    button.click()
            except Exception as e:
                print("No se encontró botón de cookies o hubo un problema:", e)

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

                # Extraer título (PRIMERA EXTRACCIÓN PRINCIPAL)
                title = movie.query_selector(
                    ".movies-list--large-movie-description-title"
                )
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

                # Ingresar a la página de la película (SEGUNDA EXTRACCIÓN PRINCIPAL)
                button = movie.query_selector(".movie-info-details--second-button")
                button.click()
                page.wait_for_selector(".movie-details--info")

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
                        formats = (
                            sibling.evaluate("el => el.textContent").strip().split(",")
                        )
                        format_list = []
                        for format in formats:
                            format_list.append(format.strip())
                        movie_data["available_formats"] = format_list

                # Extraer cines, formatos y horarios en los que está disponible
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
                    formats = cine.query_selector_all(
                        ".cinema-showcases--sessions-details"
                    )
                    movie_data[cinema_name] = {}
                    for format in formats:
                        format_type = format.query_selector(
                            ".sessions-details--formats"
                        )
                        dimension = (
                            format_type.query_selector(
                                ".sessions-details--formats-dimension"
                            )
                            .inner_text()
                            .strip()
                        )
                        theather = (
                            format_type.query_selector(
                                ".sessions-details--formats-theather"
                            )
                            .inner_text()
                            .strip()
                        )
                        language = (
                            format_type.query_selector(
                                ".sessions-details--formats-language"
                            )
                            .inner_text()
                            .strip()
                        )
                        movie_format = f"{dimension} {theather} {language}"
                        # Extraer horarios de proyección de la película
                        showtimes_list = []
                        showtimes = format.query_selector_all(".showtime-selector--link")
                        for showtime in showtimes:
                            showtimes_list.append(showtime.inner_text().strip())
                        movie_data[cinema_name][movie_format] = showtimes_list
                print(movie_data)

            browser.close()
        return results


if __name__ == "__main__":
    scraper = CineplanetScraper()
    movies = scraper.scrape("https://www.cineplanet.com.pe/peliculas")
    print(movies)
