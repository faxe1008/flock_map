"""
Ornitho.de scraper implementation.

Scrapes bird sighting data from the German ornitho.de platform.
"""

import random
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

import httpx

from .base import BirdDataScraper, ScrapingError, SightingData


class OrnithoScraper(BirdDataScraper):
    """
    Scraper for ornitho.de - German bird observation platform.
    
    URL Parameter Analysis:
    - m_id=1351: Module ID for observations
    - content=observations_by_page: Content type  
    - sp_DateSynth: Date in DD.MM.YYYY format
    - sp_DOffset: Days offset from date (e.g., 15 = last 15 days)
    - sp_Cat[rarity]: Rarity filters (never, veryrare, rare, unusual, escaped, common, verycommon)
    - sp_cC: Regional filter (binary string representing cantons/regions)
    - mp_current_page: Pagination
    """
    
    # Realistic browser user agent strings for anti-blocking
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/120.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0"
    ]
    
    # Ornitho.de rarity categories
    RARITY_CATEGORIES = [
        "never", "veryrare", "rare", "unusual", 
        "escaped", "common", "verycommon"
    ]
    
    # German regional codes and their positions in the sp_cC binary string
    # Based on analysis of ornitho.de HTML interface
    REGIONAL_POSITIONS = {
        # District-level codes (Baden-Württemberg districts as examples) 
        "MOS": 25,   # Neckar-Odenwald-Kreis (Mosbach) - position 25
        "OG": 26,    # Ortenaukreis (Offenburg) - position 26
        "AA": 0,     # Ostalbkreis - position 0
        "BAD": 1,    # Baden-Baden (Stadtkreis) - position 1
        "BB": 2,     # Böblingen - position 2
        "KA": 18,    # Karlsruhe - position 18
        "KAstar": 19, # Karlsruhe (Stadtkreis) - position 19
        
        # Country/state-level codes (German states)
        "BW": 0,     # Baden-Württemberg - Position 0 (state level)
        "BY": 1,     # Bayern - Position 1
        "BE": 2,     # Berlin - Position 2  
        "BB": 3,     # Brandenburg - Position 3
        "HB": 4,     # Bremen - Position 4
        "HH": 5,     # Hamburg - Position 5
        "HE": 6,     # Hessen - Position 6
        "MV": 7,     # Mecklenburg-Vorpommern - Position 7
        "NI": 8,     # Niedersachsen - Position 8
        "NW": 9,     # Nordrhein-Westfalen - Position 9
        "RP": 10,    # Rheinland-Pfalz - Position 10
        "SL": 11,    # Saarland - Position 11
        "SN": 12,    # Sachsen - Position 12
        "ST": 13,    # Sachsen-Anhalt - Position 13
        "SH": 14,    # Schleswig-Holstein - Position 14
        "TH": 15,    # Thüringen - Position 15
        
        # Neighboring countries
        "AT": 21,    # Austria - Position 21
        "CH": 22,    # Switzerland - Position 22
        "F": 23,     # France - Position 23
        "BE_": 24,   # Belgium - Position 24 (using BE_ to avoid conflict with Berlin)
        "NL": 25,    # Netherlands - Position 25
        "LUX": 17,   # Luxembourg - Position 17
        "DK": 18,    # Denmark - Position 18
        "PL": 19,    # Poland - Position 19
        "CZ": 20,    # Czech Republic - Position 20
    }
    
    # Human-readable region names for user interface
    REGIONS = {
        # Baden-Württemberg districts (examples - can be expanded)
        "MOS": "Neckar-Odenwald-Kreis (Mosbach)",
        "OG": "Ortenaukreis (Offenburg)",
        "AA": "Ostalbkreis",
        "BAD": "Baden-Baden (Stadtkreis)",
        "BB": "Böblingen",
        "KA": "Karlsruhe (Landkreis)",
        "KAstar": "Karlsruhe (Stadtkreis)",
        
        # German states
        "BW": "Baden-Württemberg",
        "BY": "Bayern",
        "BE": "Berlin",
        "BB": "Brandenburg", 
        "HB": "Bremen",
        "HH": "Hamburg",
        "HE": "Hessen",
        "MV": "Mecklenburg-Vorpommern",
        "NI": "Niedersachsen",
        "NW": "Nordrhein-Westfalen",
        "RP": "Rheinland-Pfalz",
        "SL": "Saarland",
        "SN": "Sachsen",
        "ST": "Sachsen-Anhalt",
        "SH": "Schleswig-Holstein",
        "TH": "Thüringen",
        
        # Neighboring countries
        "AT": "Austria",
        "CH": "Switzerland", 
        "F": "France",
        "BE_": "Belgium",
        "NL": "Netherlands",
        "LUX": "Luxembourg",
        "DK": "Denmark",
        "PL": "Poland",
        "CZ": "Czech Republic",
    }
    
    def __init__(self, rate_limit_seconds: float = 2.0, random_delay: bool = True):
        """
        Initialize OrnithoScraper with conservative rate limiting and anti-blocking measures.
        
        Args:
            rate_limit_seconds: Base delay between requests
            random_delay: Add random jitter to delays for more natural patterns
        """
        super().__init__(
            base_url="https://www.ornitho.de",
            rate_limit_seconds=rate_limit_seconds
        )
        self.random_delay = random_delay
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/120.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0 Safari/537.36"
        ]
    
    def _get_random_user_agent(self) -> str:
        """Get a random browser user agent to avoid detection."""
        return random.choice(self.user_agents)
    
    async def _rate_limit_delay(self) -> None:
        """Apply rate limiting delay with optional random jitter."""
        if self._last_request_time is not None:
            import time
            import asyncio
            
            time_since_last = time.time() - self._last_request_time
            base_delay = self.rate_limit_seconds
            
            # Add random jitter (±20%) for more natural request patterns
            if self.random_delay:
                jitter = random.uniform(-0.2, 0.2) * base_delay
                delay_needed = base_delay + jitter
            else:
                delay_needed = base_delay
            
            if time_since_last < delay_needed:
                sleep_time = delay_needed - time_since_last
                await asyncio.sleep(sleep_time)
        
        import time
        self._last_request_time = time.time()
    
    def _build_regional_filter(self, region: Optional[str] = None) -> str:
        """
        Build the sp_cC regional filter binary string.
        
        Args:
            region: Regional code (OG, MOS, etc.) or None for all regions
            
        Returns:
            426-character binary string for the sp_cC parameter
        """
        # Start with all zeros (no regions selected)
        filter_bits = ['0'] * 426
        
        if region and region in self.REGIONAL_POSITIONS:
            # Set the bit for the specific region
            position = self.REGIONAL_POSITIONS[region]
            filter_bits[position] = '1'
        elif not region:
            # No region filter - return all zeros (includes all regions by default)
            pass
        else:
            # Unknown region - log warning but don't fail
            print(f"Warning: Unknown region code '{region}'. Available: {list(self.REGIONAL_POSITIONS.keys())}")
        
        return ''.join(filter_bits)
    
    
    def get_supported_rarity_filters(self) -> List[str]:
        """Get supported rarity filter categories."""
        return self.RARITY_CATEGORIES.copy()
    
    def get_supported_regional_codes(self) -> List[str]:
        """Get supported regional filter codes."""
        return list(self.REGIONAL_POSITIONS.keys())
    
    async def get_available_regions(self) -> Dict[str, str]:
        """Get available German regions."""
        return self.REGIONS.copy()
    
    def validate_sighting_data(self, data: Dict[str, Any]) -> bool:
        """
        Validate raw sighting data from ornitho.de.
        
        Required fields: lat, lon, species_array, date_raw
        """
        required_fields = ["lat", "lon", "species_array", "date_raw"]
        
        # Check required fields exist
        for field in required_fields:
            if field not in data:
                return False
        
        # Validate coordinates
        try:
            lat = float(data["lat"])
            lon = float(data["lon"])
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return False
        except (ValueError, TypeError):
            return False
        
        # Validate species data
        species = data["species_array"]
        if not isinstance(species, dict):
            return False
        
        required_species_fields = ["name", "latin_name"]
        for field in required_species_fields:
            if field not in species:
                return False
        
        # Validate date
        try:
            datetime.fromisoformat(data["date_raw"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return False
        
        return True
    
        """
        Validate raw sighting data from ornitho.de.
        
        Required fields: lat, lon, species_array, date_raw
        """
        required_fields = ["lat", "lon", "species_array", "date_raw"]
        
        # Check required fields exist
        for field in required_fields:
            if field not in data:
                return False
        
        # Validate coordinates
        try:
            lat = float(data["lat"])
            lon = float(data["lon"])
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                return False
        except (ValueError, TypeError):
            return False
        
        # Validate species data
        species = data["species_array"]
        if not isinstance(species, dict):
            return False
        
        required_species_fields = ["name", "latin_name"]
        for field in required_species_fields:
            if field not in species:
                return False
        
        # Validate date
        try:
            datetime.fromisoformat(data["date_raw"].replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return False
        
        return True
    
    def _build_url_params(
        self,
        region: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        rarity_filters: Optional[List[str]] = None,
        page: int = 1
    ) -> Dict[str, str]:
        """Build URL parameters for ornitho.de API."""
        
        # Base parameters
        params = {
            "m_id": "1351",
            "content": "observations_by_page",
            "backlink": "skip",
            "p_c": "duration",
            "p_cc": "-",
            "sp_tg": "1",
            "sp_DChoice": "offset",
            "sp_SChoice": "category",
            "sp_PChoice": "canton",
            "sp_FChoice": "list",
            "sp_FGraphFormat": "auto",
            "sp_FMapFormat": "none",
            "sp_FDisplay": "DATE_PLACE_SPECIES",
            "sp_FOrder": "ALPHA",
            "sp_FOrderListSpecies": "ALPHA",
            "sp_FListSpeciesChoice": "DATA",
            "sp_FOrderSynth": "ALPHA",
            "sp_FGraphChoice": "DATA",
            "sp_DFormat": "DESC",
            "sp_FAltScale": "250",
            "sp_FAltChoice": "DATA",
            "sp_FExportFormat": "XLS",
            "mp_current_page": str(page),
            "txid": "1"
        }
        
        # Date handling - use date_from if provided, else current date
        target_date = date_from if date_from else datetime.now()
        params["sp_DateSynth"] = target_date.strftime("%d.%m.%Y")
        
        # Calculate offset days (default to last 15 days)
        if date_to and date_from:
            offset_days = (target_date - date_to).days
            params["sp_DOffset"] = str(max(1, abs(offset_days)))
        else:
            params["sp_DOffset"] = "15"  # Default to last 15 days
        
        # Rarity filters
        if rarity_filters:
            for rarity in rarity_filters:
                if rarity in self.RARITY_CATEGORIES:
                    params[f"sp_Cat[{rarity}]"] = "1"
        else:
            # Include all rarity categories by default
            for rarity in self.RARITY_CATEGORIES:
                params[f"sp_Cat[{rarity}]"] = "1"
        
        # Regional filter using binary string
        params["sp_cC"] = self._build_regional_filter(region)
        
        return params
    
    def _clean_species_name(self, name: str) -> str:
        """
        Clean species name by removing pipe symbols and other formatting artifacts.
        
        Args:
            name: Raw species name from ornitho.de
            
        Returns:
            Cleaned species name with proper formatting
        """
        if not name:
            return ""
        
        # Remove pipe symbols used as syllable separators in German compound words
        cleaned_name = name.replace("|", "")
        
        # Remove any extra whitespace
        cleaned_name = cleaned_name.strip()
        
        return cleaned_name
    
    def _parse_sighting_data(self, raw_data: Dict[str, Any]) -> Optional[SightingData]:
        """Parse raw sighting data from ornitho.de into standardized format."""
        
        if not self.validate_sighting_data(raw_data):
            return None
        
        try:
            # Extract basic info
            species = raw_data["species_array"]
            species_name = self._clean_species_name(species["name"])
            scientific_name = species["latin_name"]
            latitude = float(raw_data["lat"])
            longitude = float(raw_data["lon"])
            
            # Parse observation date
            date_str = raw_data["date_raw"]
            # Handle different datetime formats from ornitho.de
            if date_str.endswith("+02:00") or date_str.endswith("+01:00"):
                observation_date = datetime.fromisoformat(date_str)
            else:
                # Fallback parsing
                observation_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            
            # Parse count - handle special formats like "≥12" or ">12"
            count_raw = raw_data.get("birds_count_raw", "1")
            if isinstance(count_raw, str):
                # Extract numeric value from strings like "≥12", ">12", "~5"
                count_match = re.search(r'(\d+)', count_raw)
                count = int(count_match.group(1)) if count_match else 1
            else:
                count = max(1, int(count_raw))
            
            # Location info
            location_name = ""
            if "listSubmenu" in raw_data and "title" in raw_data["listSubmenu"]:
                location_name = raw_data["listSubmenu"]["title"]
            
            # Extract rarity and other optional data
            rarity = species.get("rarity", "")
            
            # Combine remarks
            remarks = []
            if "remarks" in raw_data:
                for remark in raw_data["remarks"]:
                    if remark.get("content"):
                        remarks.append(remark["content"])
            
            # Custom attributes
            custom_attributes = {
                "ornitho_species_id": species.get("id"),
                "rarity_color": raw_data.get("rarity_color"),
                "protocol_name": raw_data.get("protocol_name", ""),
                "is_rare": rarity in ["rare", "veryrare", "unusual"],
                "day_number": raw_data.get("day_number"),
            }
            
            return SightingData(
                species_name=species_name,
                scientific_name=scientific_name,
                latitude=latitude,
                longitude=longitude,
                count=count,
                observation_date=observation_date,
                location_name=location_name,
                rarity=rarity,
                remarks=" | ".join(remarks) if remarks else None,
                custom_attributes=custom_attributes
            )
            
        except (KeyError, ValueError, TypeError) as e:
            # Log the error but don't raise - just skip this sighting
            print(f"Error parsing sighting data: {e}")
            return None
    
    async def scrape_sightings(
        self,
        region: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        rarity_filters: Optional[List[str]] = None,
        max_results: Optional[int] = None
    ) -> List[SightingData]:
        """
        Scrape bird sighting data from ornitho.de.
        
        Args:
            region: German region code (BW, BY, etc.)
            date_from: Start date for observations  
            date_to: End date for observations
            rarity_filters: List of rarity categories to include
            max_results: Maximum number of results to return
            
        Returns:
            List of SightingData objects
            
        Raises:
            ScrapingError: When scraping fails
        """
        
        sightings = []
        page = 1
        
        try:
            # Set up HTTP client with rotating user agent and realistic headers
            headers = {
                "User-Agent": self._get_random_user_agent(),
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
            
            async with httpx.AsyncClient(
                timeout=30.0,
                headers=headers,
                follow_redirects=True
            ) as client:
                
                while True:
                    # Apply rate limiting
                    await self._rate_limit_delay()
                    
                    # Build URL parameters
                    params = self._build_url_params(
                        region=region,
                        date_from=date_from,
                        date_to=date_to,
                        rarity_filters=rarity_filters,
                        page=page
                    )
                    
                    # Make request
                    url = f"{self.base_url}/index.php"
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    
                    # Parse JSON response
                    try:
                        data = response.json()
                    except Exception as e:
                        raise ScrapingError(f"Failed to parse JSON response: {e}")
                    
                    # Extract sightings data
                    if "data" not in data or not isinstance(data["data"], list):
                        break
                    
                    raw_sightings = data["data"]
                    
                    # No more data available
                    if not raw_sightings:
                        break
                    
                    # Parse each sighting
                    page_sightings = []
                    for raw_sighting in raw_sightings:
                        parsed = self._parse_sighting_data(raw_sighting)
                        if parsed:
                            page_sightings.append(parsed)
                    
                    sightings.extend(page_sightings)
                    
                    # Check if we've reached max results
                    if max_results and len(sightings) >= max_results:
                        sightings = sightings[:max_results]
                        break
                    
                    # Check if there are more pages
                    if data.get("data_is_finished", 1) == 1:
                        break
                    
                    page += 1
                    
                    # Safety limit to prevent infinite loops
                    if page > 50:
                        break
        
        except httpx.RequestError as e:
            raise ScrapingError(f"HTTP request failed: {e}")
        except Exception as e:
            raise ScrapingError(f"Scraping failed: {e}")
        
        return sightings