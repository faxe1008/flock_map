"""
Scrapers module for external data source integration.
"""

from .base import BirdDataScraper, ScrapingError, SightingData
from .ornitho import OrnithoScraper

__all__ = [
    "BirdDataScraper",
    "ScrapingError", 
    "SightingData",
    "OrnithoScraper",
]