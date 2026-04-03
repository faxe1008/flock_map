"""
Scheduled scraping service for FlockMap.

Uses APScheduler to automatically scrape bird sighting data from external sources
and import them into the database on a regular schedule.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from tortoise import Tortoise

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flockmap.config import DATABASE_URL
from flockmap.models.species import Species
from flockmap.models.sighting import Sighting
from flockmap.scrapers.ornitho import OrnithoScraper
from flockmap.scrapers.base import SightingData, ScrapingError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("scraper_scheduler.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class ScheduledScrapingService:
    """
    Manages scheduled scraping of bird sighting data from external sources.

    Features:
    - Configurable regional scraping targets
    - Random delays and anti-blocking measures
    - Database integration with deduplication
    - Comprehensive logging and error handling
    - Extensible for multiple data sources
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.db_initialized = False

        # Default scraping configuration - easily expandable
        self.scraping_config = {
            "ornitho_de": {
                "enabled": True,
                "scraper_class": OrnithoScraper,
                "regions": [
                    {
                        "code": "OG",
                        "name": "Ortenaukreis (Offenburg)",
                        "max_results": 100,
                        "days_back": 2,
                    },
                    {
                        "code": "MOS",
                        "name": "Neckar-Odenwald-Kreis (Mosbach)",
                        "max_results": 100,
                        "days_back": 2,
                    },
                ],
                "rarity_filters": ["common", "verycommon", "unusual", "rare", "veryrare"],
                "rate_limit": 3.0,  # Conservative rate limiting
                "random_delay": True,
            }
        }

    async def initialize_database(self):
        """Initialize database connection."""
        if not self.db_initialized:
            await Tortoise.init(
                db_url=DATABASE_URL,
                modules={"models": ["flockmap.models.species", "flockmap.models.sighting"]},
            )
            self.db_initialized = True
            logger.info("Database connection initialized")

    async def get_or_create_species(self, sighting_data: SightingData) -> Species:
        """
        Get existing species from database or create a new one.

        Args:
            sighting_data: Scraped sighting data containing species info

        Returns:
            Species model instance
        """

        # Try to find existing species by scientific name (most reliable)
        species = await Species.filter(scientific_name=sighting_data.scientific_name).first()

        if species:
            return species

        # If not found, try by common name
        species = await Species.filter(common_name=sighting_data.species_name).first()

        if species:
            # Update scientific name if it was missing
            if not species.scientific_name:
                species.scientific_name = sighting_data.scientific_name
                await species.save()
            return species

        # Create new species
        rarity_rank = self._determine_rarity_rank(sighting_data.rarity or "")

        species = await Species.create(
            common_name=sighting_data.species_name,
            scientific_name=sighting_data.scientific_name,
            family="",  # Not available from ornitho.de directly
            rarity_rank=rarity_rank,
            is_rare=sighting_data.rarity in ["never", "veryrare", "rare", "unusual"],
        )

        logger.info(f"Created new species: {species.common_name} ({species.scientific_name})")
        return species

    def _determine_rarity_rank(self, rarity: str) -> int:
        """Convert ornitho.de rarity to numeric rank."""
        rarity_map = {
            "never": 1,
            "veryrare": 1,
            "rare": 2,
            "unusual": 3,
            "common": 4,
            "verycommon": 5,
        }
        return rarity_map.get(rarity.lower(), 3)  # Default to uncommon

    def _generate_dedupe_key(self, sighting_data: SightingData, source: str) -> str:
        """
        Generate a unique deduplication key for a sighting.

        Uses SHA-256 hash of key sighting attributes to ensure uniqueness
        and prevent duplicate entries.
        """
        import hashlib

        # Create a string from key identifying attributes
        key_parts = [
            source,
            sighting_data.scientific_name,
            f"{sighting_data.latitude:.6f}",  # 6 decimal places for ~0.1m precision
            f"{sighting_data.longitude:.6f}",
            sighting_data.observation_date.isoformat(),
            str(sighting_data.count),
            sighting_data.location_name or "",
            sighting_data.observer or "",
        ]

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode("utf-8")).hexdigest()

    async def import_sighting(self, sighting_data: SightingData, source: str) -> Optional[Sighting]:
        """
        Import a single sighting into the database with deduplication.

        Args:
            sighting_data: Scraped sighting data
            source: Data source identifier

        Returns:
            Created Sighting instance or None if skipped (duplicate)
        """

        try:
            # Get or create the species
            species = await self.get_or_create_species(sighting_data)

            # Prepare custom attributes
            custom_attributes = sighting_data.custom_attributes or {}
            custom_attributes.update(
                {
                    "source": source,
                    "original_rarity": sighting_data.rarity,
                    "location_name": sighting_data.location_name,
                    "remarks": sighting_data.remarks,
                    "imported_at": datetime.now().isoformat(),
                }
            )

            # Generate dedupe_key for deduplication
            dedupe_key = self._generate_dedupe_key(sighting_data, source)

            # Create sighting (deduplication handled by unique dedupe_key)
            sighting = await Sighting.create(
                species=species,
                location_lat=sighting_data.latitude,
                location_lon=sighting_data.longitude,
                count=sighting_data.count,
                observed_at=sighting_data.observation_date,
                custom_attrs=custom_attributes,
                dedupe_key=dedupe_key,
            )

            # Update PostGIS geography column for spatial queries
            from tortoise import connections

            conn = connections.get("default")
            await conn.execute_query(
                "UPDATE sighting SET geog = ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography WHERE id = $3",
                [sighting_data.longitude, sighting_data.latitude, sighting.id],
            )

            logger.debug(
                f"Imported: {sighting.count}x {species.common_name} at {sighting_data.location_name}"
            )
            return sighting

        except Exception as e:
            # Handle potential duplicate entries and other errors
            error_msg = str(e).lower()
            if "duplicate" in error_msg or "unique constraint" in error_msg:
                logger.debug(
                    f"Skipped duplicate: {sighting_data.species_name} at {sighting_data.location_name}"
                )
                return None
            else:
                logger.error(f"Error importing sighting: {e}")
                return None

    async def scrape_region(
        self,
        scraper: Any,
        region_config: Dict[str, Any],
        source: str,
        rarity_filters: Optional[List[str]] = None,
    ) -> int:
        """
        Scrape a single region and import results.

        Args:
            scraper: Initialized scraper instance
            region_config: Region configuration dictionary
            source: Data source name
            rarity_filters: Optional rarity filter list

        Returns:
            Number of sightings successfully imported
        """

        region_code = region_config["code"]
        region_name = region_config["name"]
        max_results = region_config.get("max_results", 50)
        days_back = region_config.get("days_back", 2)

        logger.info(
            f"Scraping {region_name} ({region_code}) - last {days_back} days, max {max_results}"
        )

        try:
            # Add random delay before starting region (5-15 seconds)
            initial_delay = random.uniform(5, 15)
            logger.info(f"Waiting {initial_delay:.1f}s before scraping {region_code}")
            await asyncio.sleep(initial_delay)

            # Scrape the region
            sightings_data = await scraper.scrape_sightings(
                region=region_code,
                date_from=datetime.now() - timedelta(days=days_back),
                rarity_filters=rarity_filters,
                max_results=max_results,
            )

            if not sightings_data:
                logger.warning(f"No sightings found for {region_name} ({region_code})")
                return 0

            logger.info(f"Found {len(sightings_data)} sightings for {region_name}, importing...")

            # Import sightings with small delays between each
            imported_count = 0
            for i, sighting_data in enumerate(sightings_data, 1):
                sighting = await self.import_sighting(sighting_data, source)
                if sighting:
                    imported_count += 1

                # Small delay between imports (0.1-0.3 seconds)
                if i < len(sightings_data):  # Don't delay after last item
                    delay = random.uniform(0.1, 0.3)
                    await asyncio.sleep(delay)

            logger.info(
                f"Imported {imported_count}/{len(sightings_data)} sightings from {region_name}"
            )
            return imported_count

        except ScrapingError as e:
            logger.error(f"Scraping failed for {region_name} ({region_code}): {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error scraping {region_name} ({region_code}): {e}")
            return 0

    async def run_scheduled_scrape(self):
        """Execute a complete scheduled scraping run."""

        run_start = datetime.now()
        logger.info(f"🚀 Starting scheduled scraping run at {run_start}")

        try:
            # Initialize database if needed
            await self.initialize_database()

            total_imported = 0

            # Process each configured data source
            for source_name, source_config in self.scraping_config.items():
                if not source_config.get("enabled", False):
                    logger.info(f"Skipping disabled source: {source_name}")
                    continue

                logger.info(f"📊 Processing source: {source_name}")

                # Initialize scraper with anti-blocking measures
                scraper_class = source_config["scraper_class"]
                scraper = scraper_class(
                    rate_limit_seconds=source_config.get("rate_limit", 3.0),
                    random_delay=source_config.get("random_delay", True),
                )

                rarity_filters = source_config.get("rarity_filters")

                # Process each region
                for region_config in source_config.get("regions", []):
                    imported = await self.scrape_region(
                        scraper=scraper,
                        region_config=region_config,
                        source=source_name,
                        rarity_filters=rarity_filters,
                    )
                    total_imported += imported

                    # Random delay between regions (10-30 seconds)
                    region_delay = random.uniform(10, 30)
                    logger.info(f"Waiting {region_delay:.1f}s before next region...")
                    await asyncio.sleep(region_delay)

            # Summary
            run_duration = datetime.now() - run_start
            logger.info(f"✅ Scraping run completed in {run_duration}")
            logger.info(f"📈 Total sightings imported: {total_imported}")

            # Log database statistics
            species_count = await Species.all().count()
            sightings_count = await Sighting.all().count()
            logger.info(f"📊 Database: {species_count} species, {sightings_count} total sightings")

        except Exception as e:
            logger.error(f"❌ Scheduled scraping run failed: {e}")

    def add_region(self, source: str, region_code: str, region_name: str, **kwargs):
        """
        Add a new region to scraping configuration.

        Args:
            source: Data source name (e.g., "ornitho_de")
            region_code: Regional code (e.g., "BW", "BY")
            region_name: Human-readable name
            **kwargs: Additional region config (max_results, days_back, etc.)
        """
        if source not in self.scraping_config:
            logger.error(f"Unknown data source: {source}")
            return

        region_config = {
            "code": region_code,
            "name": region_name,
            "max_results": kwargs.get("max_results", 50),
            "days_back": kwargs.get("days_back", 2),
        }

        self.scraping_config[source]["regions"].append(region_config)
        logger.info(f"Added region {region_name} ({region_code}) to {source}")

    def start_scheduler(self):
        """Start the scheduled scraping service."""

        self.scheduler.add_job(
            self.run_scheduled_scrape,
            CronTrigger(hour=18, minute=0),  # 6:00 PM
            id="evening_scrape",
            name="Evening Bird Data Scraping",
            misfire_grace_time=300,
        )

        logger.info("📅 Scheduled scraping job configured:")
        logger.info("  - Daily evening scrape: 18:00")

        # Start the scheduler
        self.scheduler.start()
        logger.info("🎯 Scheduler started successfully")

    def stop_scheduler(self):
        """Stop the scheduled scraping service."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("🛑 Scheduler stopped")

    async def run_test_scrape(self):
        """Run a test scraping session immediately."""
        logger.info("🧪 Running test scraping session...")
        await self.run_scheduled_scrape()

    async def cleanup(self):
        """Clean up resources."""
        if self.db_initialized:
            await Tortoise.close_connections()
            logger.info("Database connections closed")


async def main():
    """Main function for running the scheduled scraping service."""

    service = ScheduledScrapingService()

    try:
        # For development/testing - run immediate scrape
        if len(sys.argv) > 1 and sys.argv[1] == "--test":
            await service.run_test_scrape()
            return

        # Start the scheduler for production use
        service.start_scheduler()

        logger.info("🌟 FlockMap Scheduled Scraping Service is running")
        logger.info("Press Ctrl+C to stop")

        # Keep the service running
        try:
            while True:
                await asyncio.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Received stop signal")

    finally:
        service.stop_scheduler()
        await service.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
