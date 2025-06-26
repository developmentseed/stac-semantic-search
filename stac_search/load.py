"""
Load CLI for STAC Natural Query - creates and populates the vector database
"""

import asyncio
import logging
import os

from stac_search.catalog_manager import CatalogManager

logger = logging.getLogger(__name__)


def load_data(catalog_url: str):
    """Load STAC collections into the vector database using CatalogManager"""
    try:
        # Initialize catalog manager
        catalog_manager = CatalogManager()

        # Load catalog using async method
        result = asyncio.run(catalog_manager.load_catalog(catalog_url))

        if result["success"]:
            logger.info(f"Successfully loaded catalog: {result['message']}")
            if "collections_count" in result:
                logger.info(f"Indexed {result['collections_count']} collections")
        else:
            logger.error(f"Failed to load catalog: {result['error']}")
            raise Exception(result["error"])

    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise


if __name__ == "__main__":
    # load_data(catalog_url="https://stac.eoapi.dev/", catalog_name="eoapi.dev")
    # load_data(
    #     catalog_url="https://planetarycomputer.microsoft.com/api/stac/v1",
    #     catalog_name="planetarycomputer",
    # )
    STAC_CATALOG_URL = os.environ.get(
        "STAC_CATALOG_URL", "https://planetarycomputer.microsoft.com/api/stac/v1"
    )
    load_data(catalog_url=STAC_CATALOG_URL)
