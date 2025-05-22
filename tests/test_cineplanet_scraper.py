from scrapers.cineplanet_scraper import CineplanetScraper
from playwright.sync_api import sync_playwright
import pytest, os

scraper = CineplanetScraper()


# Página base para tests y sirve para comprobar URL
@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.cineplanet.com.pe/peliculas")
        yield page
        browser.close()


# Test para comprobar que la página carga
def test_site_homepage_loads():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        response = page.goto("https://www.cineplanet.com.pe/")

        # La página respondió satisfactoriamente
        assert (
            response is not None
        ), "La respuesta fue None, puede que el sitio esté caído"
        assert response.status == 200
        assert page.url.startswith("https://www.cineplanet.com.pe/")

        browser.close()


# Test para comprobar que se aceptan las cookies
def test_scraper_accept_cookies(page):
    scraper.accept_cookies(page)


# Test para comprobar que cargan todas las películas
def test_scraper_load_all_movies(page):
    scraper.load_all_movies(page)


# Test para comprobar que se extrae toda la información general
def test_scraper_extract_general_information(page):
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, "test_data", "movie_sample.html")

    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    page.set_content(html_content)

    movie = page.query_selector(".movies-list--large-item")
    movie_data = {}
    scraper.extract_general_information(movie, movie_data)
    assert movie_data["title"] == "Película de prueba"
    assert movie_data["genre"] == "Drama"
    assert movie_data["running_time"] == "1h 50m"
    assert movie_data["age_restriction"] == "+14."
    assert movie_data["image_url"] == "https://estaesunaimagen.com.pe"


# Test para comprobar que se extrae toda la información específica
def test_scraper_extract_specific_information(page):
    movie_data = {}
    scraper.extract_info_from_details_page(page, movie_data)
