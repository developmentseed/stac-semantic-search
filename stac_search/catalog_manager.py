"""
Catalog Manager for STAC Natural Query - handles dynamic catalog loading and management
"""

import hashlib
import logging
import os
from typing import Optional, Dict, Any
import chromadb
from pystac_client import Client
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Constants
MODEL_NAME = "all-MiniLM-L6-v2"
DATA_PATH = os.environ.get("DATA_PATH", "data/chromadb")


class CatalogManager:
    """Manages STAC catalog indexing and retrieval operations"""

    def __init__(self, data_path: str = DATA_PATH, model_name: str = MODEL_NAME):
        self.data_path = data_path
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.PersistentClient(path=data_path)

    def _get_catalog_name(self, catalog_url: str) -> str:
        """Generate a unique catalog name from URL"""
        # Create a hash of the URL for consistent naming
        url_hash = hashlib.md5(catalog_url.encode()).hexdigest()[:8]
        # Clean URL for readability
        clean_url = catalog_url.replace("https://", "").replace("http://", "")
        clean_url = clean_url.replace("/", "_").replace(".", "_")
        return f"{clean_url}_{url_hash}"

    def _get_collection_name(self, catalog_url: str) -> str:
        """Get ChromaDB collection name for a catalog"""
        catalog_name = self._get_catalog_name(catalog_url)
        return f"{catalog_name}_collections"

    def catalog_exists(self, catalog_url: str) -> bool:
        """Check if a catalog is already indexed in the vector database"""
        collection_name = self._get_collection_name(catalog_url)
        try:
            existing_collections = self.client.list_collections()
            print(f"Existing collections: {[col.name for col in existing_collections]}")
            print(f"Checking for collection: {collection_name}")
            return any(col.name == collection_name for col in existing_collections)
        except Exception as e:
            logger.error(f"Error checking catalog existence: {e}")
            return False

    def validate_catalog_url(self, catalog_url: str) -> bool:
        """Validate that the catalog URL is accessible and is a valid STAC catalog"""
        try:
            stac_client = Client.open(catalog_url)
            # Try to get at least one collection to verify it's a valid catalog
            collections = list(stac_client.collection_search().collections())
            return len(collections) > 0
        except Exception as e:
            logger.error(f"Invalid catalog URL {catalog_url}: {e}")
            return False

    def fetch_collections(self, stac_client: Client) -> list:
        """Fetch STAC collections using pystac-client"""
        try:
            collections = stac_client.collection_search().collections()
            return list(collections)
        except Exception as e:
            logger.error(f"Error fetching collections: {e}")
            return []

    def generate_embeddings(self, collections: list) -> list:
        """Generate embeddings for each collection (title + description)"""
        texts = []
        for collection in collections:
            title = getattr(collection, "title", "") or ""
            description = getattr(collection, "description", "") or ""
            texts.append(f"{title} {description}")

        embeddings = self.model.encode(texts)
        return embeddings

    def store_in_vector_db(self, collections: list, chroma_collection) -> None:
        """Store embeddings in ChromaDB"""
        if not collections:
            logger.warning("No collections to store")
            return

        metadatas = []
        for collection in collections:
            metadata = {
                "title": getattr(collection, "title", "") or "",
                "description": getattr(collection, "description", "") or "",
                "collection_id": getattr(collection, "id", ""),
            }
            metadatas.append(metadata)

        embeddings = self.generate_embeddings(collections)

        chroma_collection.add(
            ids=[str(i) for i in range(len(collections))],
            embeddings=embeddings,
            metadatas=metadatas,
        )

    async def load_catalog(self, catalog_url: str) -> Dict[str, Any]:
        """Load and index a catalog if it doesn't exist"""
        try:
            # Validate catalog URL first
            if not self.validate_catalog_url(catalog_url):
                return {
                    "success": False,
                    "error": f"Invalid or inaccessible catalog URL: {catalog_url}",
                }

            # Check if catalog already exists
            if self.catalog_exists(catalog_url):
                logger.info(f"Catalog {catalog_url} already indexed")
                return {
                    "success": True,
                    "message": f"Catalog already indexed",
                    "catalog_name": self._get_catalog_name(catalog_url),
                }

            # Load the catalog
            logger.info(f"Loading catalog from {catalog_url}")
            stac_client = Client.open(catalog_url)
            collections = self.fetch_collections(stac_client)

            if not collections:
                return {
                    "success": False,
                    "error": f"No collections found in catalog {catalog_url}",
                }

            # Create ChromaDB collection
            collection_name = self._get_collection_name(catalog_url)
            chroma_collection = self.client.create_collection(
                name=collection_name, get_or_create=True
            )

            # Store in vector database
            self.store_in_vector_db(collections, chroma_collection)

            logger.info(
                f"Successfully indexed {len(collections)} collections from {catalog_url}"
            )
            return {
                "success": True,
                "message": f"Successfully indexed {len(collections)} collections",
                "catalog_name": self._get_catalog_name(catalog_url),
                "collections_count": len(collections),
            }

        except Exception as e:
            logger.error(f"Error loading catalog {catalog_url}: {e}")
            return {"success": False, "error": f"Error loading catalog: {str(e)}"}

    def get_catalog_collection(
        self, catalog_url: Optional[str] = None
    ) -> chromadb.Collection:
        """Get the ChromaDB collection for a catalog"""
        if not catalog_url:
            catalog_url = os.environ.get("STAC_CATALOG_URL")

        collection_name = self._get_collection_name(catalog_url)

        try:
            return self.client.get_collection(name=collection_name)
        except Exception as e:
            logger.error(f"Error getting collection {collection_name}: {e}")
            raise
