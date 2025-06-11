from abc import ABC, abstractmethod
from playwright.async_api import Playwright, Browser, Page, Locator, TimeoutError as PlaywrightTimeoutError
from rich.text import Text
from rich.console import Console
from typing import List, Tuple
import asyncio

console = Console()


class BaseScraper(ABC):
    @abstractmethod
    def scrape(self):
        """
        Devuelve una lista de diccionarios con los datos de las películas
        """
        pass

    def print_list_of_items(self, items: list[str]):
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

    async def setup_browser(self, p: Playwright) -> Browser:
        return await p.chromium.launch(headless=False)

    async def load_page(self, browser: Browser, url: str, selector_check: str) -> Page:
        page = await browser.new_page()
        await page.goto(url)
        page_selector = page.locator(selector_check)

        for _ in range(3):
            try:
                await page_selector.wait_for(timeout=3000)
                break
            except:
                print("Contenido no cargó, refrescando página...")
                await page.reload()
                await asyncio.sleep(2)
        return page

    async def extract_general_information(
        self,
        movie: Locator,
        movie_data: dict,
        title_selector: str,
        movie_extra_info_selector: str,
        image_selector: str,
        splitter: str,
    ):
        title = movie.locator(title_selector)
        movie_data["title"] = (await title.inner_text()).strip()

        # Extraer género, duración y restricción de edad
        keys = ["genre", "running_time", "age_restriction"]
        movie_extra_info = movie.locator(movie_extra_info_selector)
        extras: List[Locator] = (
            (await movie_extra_info.inner_text()).strip().split(splitter)
        )

        for key, extra in zip(keys, extras):
            movie_data[key] = extra

        # Extraer url de imagen
        image = movie.locator(image_selector)
        movie_data["image_url"] = await image.get_attribute("src")

    async def enter_movie_details_page(
        self,
        movie: Locator,
        page: Page,
        button_selector: str,
        movie_details_selector: str,
    ):
        button = movie.locator(button_selector)
        await button.click()
        await page.locator(movie_details_selector).wait_for(timeout=3000)

    async def ask_user_for_input(self, items, filter: str) -> int:
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

    async def print_locators(self, items: Locator):
        count = await items.count()
        strings = []
        for i in range(count):
            strings.append((await items.nth(i).inner_text()).strip())
        self.print_list_of_items(strings)

    async def select_filter(
        self, items: Locator, page: Page, filter: str
    ) -> Tuple[str, bool]:
        async def execute_user_input(
            items: Locator, page: Page, item_chosen: int
        ) -> Tuple[str, bool]:
            print()
            console.rule("")
            items_idx = item_chosen - 1
            selected_item = items.nth(items_idx)
            item_text = (await selected_item.inner_text()).strip()
            await selected_item.click()
            await page.wait_for_function(
                f"""() => {{
                    const chips = document.querySelectorAll('.movies-chips--chip');
                    return Array.from(chips).some(chip => chip.innerText.includes("{item_text}"));
                }}"""
            )
            return (item_text, True)

        # Imprime la lista de items disponibles
        await self.print_locators(items)
        # Pedirle al usuario que seleccione un item
        filter_chosen = await self.ask_user_for_input(items, filter)
        return await execute_user_input(items, page, filter_chosen)

    async def apply_specific_filter(
        self,
        page: Page,
        filter_name: str,
        title_selector: str,
        accordion_selector: str,
        item_selector: str,
    ) -> Tuple[str, bool]:
        title_element = page.locator(title_selector)
        if not title_element:
            return ("Missing filter title", False)
        accordion_locator = page.locator(accordion_selector)
        title_element_count = await title_element.count()
        for i in range(title_element_count):
            if (await title_element.nth(i).inner_text()).strip() == filter_name:
                classes = await accordion_locator.nth(i).get_attribute("class")
                # Verificar si el acordeón del filtro está expandido
                if "accordion_expanded" not in classes:
                    await accordion_locator.nth(i).click()

                accordion = accordion_locator.nth(i)
                items = accordion.locator(item_selector)

                return await self.select_filter(items, page, filter_name)

        # Si no hay ningún filtro que coincida, se retorna nada
        return ("Filters don't matches", False)

    async def apply_filters(
        self,
        page: Page,
        filters_to_apply: List[str],
        title_selector: str,
        accordion: str,
        item_selector: str,
    ) -> List[str]:
        # Selecciona todos los filtros y aplicar los escogidos
        applied = {filter_name: False for filter_name in filters_to_apply}
        data = []
        for filter_name in filters_to_apply:
            if not applied[filter_name]:
                # Aplica el filtro
                result, was_applied = await self.apply_specific_filter(
                    page, filter_name, title_selector, accordion, item_selector
                )
                if was_applied:
                    data.append(result)
                    applied[filter_name] = True
                    continue
        return data
