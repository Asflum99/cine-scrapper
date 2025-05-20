from abc import ABC, abstractmethod

class BaseScraper(ABC):
    @abstractmethod
    def scrape(self):
        """
        Devuelve una lista de diccionarios con los datos de las películas
        """
        pass