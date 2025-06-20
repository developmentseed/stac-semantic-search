"""
STAC Natural Query - Vector search for STAC collections
"""

import logging
import os


log_level = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
