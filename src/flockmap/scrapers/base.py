"""
Abstract base interface for bird data scrapers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any
import asyncio


class ScrapingError(Exception):
    """Exception raised during scraping operations."""
    pass


@dataclass
class SightingData:
    """Standardized sighting data structure for scrapers."""
    species_name: str
    scientific_name: str
    latitude: float
    longitude: float
    count: int
    observation_date: datetime
    location_name: str
    
    # Optional fields
    observer: Optional[str] = None
    rarity: Optional[str] = None
    remarks: Optional[str] = None
    custom_attributes: Optional[Dict[str, Any]] = None


class BirdDataScraper(ABC):
    """
    Abstract base class for bird data scrapers.
    
    Provides a standardized interface for scraping bird sighting data
    from various external sources.
    """
    
    def __init__(self, base_url: str, rate_limit_seconds: float = 1.0):
        """
        Initialize the scraper.
        
        Args:
            base_url: The base URL for the data source
            rate_limit_seconds: Minimum seconds between requests to avoid rate limiting
        """
        self.base_url = base_url
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_time: Optional[float] = None
    
    async def _rate_limit_delay(self) -> None:
        """Apply rate limiting delay between requests."""
        if self._last_request_time is not None:
            import time
            time_since_last = time.time() - self._last_request_time
            if time_since_last < self.rate_limit_seconds:
                delay = self.rate_limit_seconds - time_since_last
                await asyncio.sleep(delay)
        
        import time
        self._last_request_time = time.time()
    
    @abstractmethod
    async def scrape_sightings(
        self,
        region: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        rarity_filters: Optional[List[str]] = None,
        max_results: Optional[int] = None
    ) -> List[SightingData]:
        """
        Scrape bird sighting data from the external source.
        
        Args:
            region: Geographic region code/identifier (source-specific)
            date_from: Start date for sighting observations
            date_to: End date for sighting observations  
            rarity_filters: List of rarity categories to include
            max_results: Maximum number of results to return
            
        Returns:
            List of standardized SightingData objects
            
        Raises:
            ScrapingError: When scraping fails or data is invalid
        """
        pass
    
    @abstractmethod
    async def get_available_regions(self) -> Dict[str, str]:
        """
        Get available geographic regions from the data source.
        
        Returns:
            Dictionary mapping region codes to human-readable names
            
        Raises:
            ScrapingError: When region data cannot be retrieved
        """
        pass
    
    @abstractmethod
    def get_supported_rarity_filters(self) -> List[str]:
        """
        Get supported rarity filter categories.
        
        Returns:
            List of supported rarity category strings
        """
        pass
    
    @abstractmethod
    def validate_sighting_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate raw sighting data from the source.
        
        Args:
            data: Raw data dictionary from the external source
            
        Returns:
            True if data is valid, False otherwise
        """
        pass
    
    def get_scraper_info(self) -> Dict[str, Any]:
        """
        Get information about this scraper.
        
        Returns:
            Dictionary with scraper metadata
        """
        return {
            "base_url": self.base_url,
            "rate_limit_seconds": self.rate_limit_seconds,
            "scraper_type": self.__class__.__name__,
            "supported_rarity_filters": self.get_supported_rarity_filters()
        }