"""
Load CLI for STAC Natural Query - creates and populates the vector database
"""

import logging
import os

import chromadb
from pystac_client import Client
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Constants
MODEL_NAME = "all-MiniLM-L6-v2"
DATA_PATH = os.environ.get("DATA_PATH", "data/chromadb")


def load_data(catalog_url, catalog_name):
    """Load STAC collections into the vector database"""
    logger.info("Initializing vector database...")

    # Initialize the model
    model = SentenceTransformer(MODEL_NAME)

    # Initialize ChromaDB client with persistence settings
    client = chromadb.PersistentClient(path=DATA_PATH)
    chroma_collection = client.create_collection(
        name=f"{catalog_name}_collections", get_or_create=True
    )

    # Initialize STAC client
    stac_client = Client.open(catalog_url)

    logger.info("Fetching STAC collections...")
    collections = fetch_collections(stac_client)
    logger.info(f"Found {len(collections)} collections")

    logger.info("Generating embeddings and storing in vector database...")
    store_in_vector_db(collections, model, chroma_collection)

    logger.info("Data loading complete!")


def fetch_collections(stac_client):
    """Fetch STAC collections using pystac-client"""
    collections = stac_client.collection_search().collections()
    return list(collections)


def generate_embeddings(collections, model):
    """Generate embeddings for each collection (title + description)"""
    texts = [
        f"{collection.title} {collection.description}" for collection in collections
    ]
    embeddings = model.encode(texts)
    return embeddings


def store_in_vector_db(collections, model, chroma_collection):
    """Store embeddings in ChromaDB"""
    metadatas = [
        {
            "title": collection.title or "",
            "description": collection.description or "",
            "collection_id": collection.id,
        }
        for collection in collections
    ]

    embeddings = generate_embeddings(collections, model)

    chroma_collection.add(
        ids=[str(i) for i in range(len(collections))],
        embeddings=embeddings,
        metadatas=metadatas,
    )


if __name__ == "__main__":
    # load_data(catalog_url="https://stac.eoapi.dev/", catalog_name="eoapi.dev")
    # load_data(
    #     catalog_url="https://planetarycomputer.microsoft.com/api/stac/v1",
    #     catalog_name="planetarycomputer",
    # )
    import os

    STAC_CATALOG_URL = os.environ.get(
        "STAC_CATALOG_URL", "https://planetarycomputer.microsoft.com/api/stac/v1"
    )
    STAC_CATALOG_NAME = os.environ.get("STAC_CATALOG_NAME", "planetarycomputer")
    load_data(catalog_url=STAC_CATALOG_URL, catalog_name=STAC_CATALOG_NAME)
