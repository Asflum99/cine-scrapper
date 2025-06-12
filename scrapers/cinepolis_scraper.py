from playwright.async_api import async_playwright, Playwright, Page, Browser, Locator
from scrapers.base_scraper import BaseScraper
from rich.console import Console
from rich.traceback import install
from slugify import slugify
from pathlib import Path
from typing import Tuple, Callable
import asyncio

console = Console()
install


class CinepolisScraper(BaseScraper):

    async def scrape_showtimes_data(self, movie: Locator, movie_data: dict):
        cinema_selector = movie.locator(".horarioExp")
        cinema_selector_count = await cinema_selector.count()
        final_data = []
        data = {}
        for i in range(cinema_selector_count):
            movie_extra_info = cinema_selector.nth(i).locator(".col3")
            children = movie_extra_info.locator(":scope > *")
            formats = await children.count()
            if formats > 0:
                data["language"] = (await children.nth(formats - 1).inner_text()).strip()
            if formats > 1:
                data["format"] = (await children.nth(formats - 2).inner_text()).strip()
            times_row = cinema_selector.nth(i).locator(".col9")
            running_times = times_row.locator(".btnhorario")
            running_times_count = await running_times.count()
            showtimes_total = []
            for j in range(running_times_count):
                showtimes_individual = []
                time = await running_times.nth(j).locator("a").inner_text()
                link = await running_times.nth(j).locator("a").get_attribute("href")
                showtimes_individual.append(time)
                showtimes_individual.append(link)
                showtimes_total.append(showtimes_individual)
            data["showtimes"] = showtimes_total
        final_data.append(data)
        movie_data["showtimes"] = final_data

    async def extract_general_information_cinepolis(
        self, page: Page, movie: Locator, movie_data: dict, title_selector: str
    ):
        # Guardar título de la película
        title = movie.locator(title_selector)
        movie_data["title"] = (await title.inner_text()).strip()

        # Guardar duración y restricción de edad
        age_restriction = await movie.locator(".clasificacion").get_attribute(
            "data-description"
        )
        running_time = await movie.locator(".duracion").inner_text()
        movie_data["age_restriction"] = age_restriction
        movie_data["running_time"] = running_time

    async def extract_filters(
        self, page: Page, id_filter: str, filter_type: str
    ) -> list[str]:
        select_locator = page.locator(id_filter)
        await select_locator.wait_for(timeout=4000)
        option_locators = select_locator.locator("option")
        count = await option_locators.count()

        filters = []
        for i in range(count):
            option = option_locators.nth(i)
            text = await option.inner_text()

            if "Selecciona un" not in text:
                filters.append(
                    text.removesuffix(", Perú") if filter_type == "ciudad" else text
                )

        return filters

    async def extract_chosen_filter(
        self, filter_chosen: int, page: Page, id_filter: str, filters: list
    ) -> str:
        select_locator = page.locator(id_filter)
        option_locators = select_locator.locator("option")
        count = await option_locators.count()

        for i in range(count):
            option = option_locators.nth(i)
            text = (await option.inner_text()).strip()

            if filters[filter_chosen - 1] in text:
                return text

    async def select_filter_cinepolis(
        self, filter_type: str, page: Page, id_filter: str
    ) -> str:
        filters = await self.extract_filters(page, id_filter, filter_type)
        self.print_list_of_items(filters)
        filter_chosen = await self.ask_user_for_input(filters, filter_type)
        filter_name = await self.extract_chosen_filter(
            filter_chosen, page, id_filter, filters
        )
        await page.select_option(id_filter, label=filter_name)
        return filter_name

    async def apply_filters_cinepolis(self, page: Page) -> list[str]:
        # Seleccionar ciudad, cine y día
        filters = {
            "ciudad": "#cmbCiudades",
            "cine": "#cmbComplejos",
            "día": "#cmbFechas",
        }
        filters_keys = list(filters.keys())
        filters_applied = []
        for filter in filters_keys:
            filter_name = await self.select_filter_cinepolis(
                filter, page, filters[filter]
            )
            filters_applied.append(filter_name)
        return filters_applied

    async def prepare_scrapping(
        self, p: Playwright, url: str
    ) -> Tuple[Browser, Page, Path, Callable, Locator, str, str, str]:
        # Abrir navegador y página web
        browser = await self.setup_browser(p)
        page = await self.load_page(browser, url, ".contentBusqueda")

        # Aplicar filtros
        city, cinema, day = await self.apply_filters_cinepolis(page)

        # Crear ruta de carpetas
        output_folder = await self.create_folder(
            city.removesuffix(", Perú"), cinema, day, "cinepolis"
        )

        # Preguntar al usuario el formato de archivo en el que desea guardar
        format_to_save = await self.ask_format_to_save()

        movies = page.locator(".divFecha article")

        return browser, page, output_folder, format_to_save, movies, city, cinema, day

    async def process_movies(
        self,
        page: Page,
        movies: Locator,
        output_folder: Path,
        format_to_save: Callable,
        city: str,
        cinema: str,
        day: str,
    ):
        movies_count = await movies.count()
        for i in range(movies_count):
            movie = movies.nth(i)
            movie_data = {}
            movie_data["city"] = city
            movie_data["cinema"] = cinema
            movie_data["day"] = day

            await self.extract_general_information_cinepolis(
                page, movie, movie_data, ".datalayer-movie"
            )

            console.print(
                f"\n[cyan]▶️ Recopilando horarios de proyección de [bold]{movie_data['title']}[/bold][/cyan]"
            )

            wait_message = asyncio.create_task(self.message_if_takes_time())
            await self.scrape_showtimes_data(movie, movie_data)
            wait_message.cancel()

            format_to_save(output_folder, movie_data)
            console.print(
                f"[green]✅ Horarios de [bold]{movie_data['title']}[/bold] guardados[/green]"
            )

    async def scrape(self, url: str):
        async with async_playwright() as p:
            browser, page, output_folder, format_to_save, movies, city, cinema, day = (
                await self.prepare_scrapping(p, url)
            )

            with console.status(
                "[bold green]Recopilando información de películas...[/]",
                spinner="bouncingBall",
                spinner_style="bold green",
            ):
                await self.process_movies(
                    page, movies, output_folder, format_to_save, city, cinema, day
                )

            console.print(
                "\n[bold green]🎉 ¡Todos los horarios han sido guardados exitosamente![/bold green]"
            )
            await browser.close()


if __name__ == "__main__":
    asyncio.run(CinepolisScraper().scrape("https://cinepolis.com.pe/"))
