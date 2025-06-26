"""
Search module for STAC Natural Query
"""

import logging
import os
import time
from dataclasses import dataclass
from pprint import pformat
from typing import List, Dict, Any

from pydantic_ai import Agent
from stac_search.catalog_manager import CatalogManager


logger = logging.getLogger(__name__)

# Constants
MODEL_NAME = "all-MiniLM-L6-v2"
DATA_PATH = os.environ.get("DATA_PATH", "data/chromadb")

STAC_COLLECTIONS_URL = os.getenv(
    "STAC_COLLECTIONS_URL", "https://planetarycomputer.microsoft.com/api/stac/v1"
)
SMALL_MODEL_NAME = os.getenv("SMALL_MODEL_NAME", "openai:gpt-4.1-mini")


@dataclass
class CollectionWithExplanation:
    """Model for a single reranked result"""

    collection_id: str
    explanation: str


@dataclass
class RerankContext:
    query: str
    collections: List[Dict[str, Any]]


@dataclass
class RankedCollections:
    results: List[CollectionWithExplanation]


rerank_agent = Agent(
    SMALL_MODEL_NAME,
    result_type=RankedCollections,
    deps_type=RerankContext,
    system_prompt="""
You are an expert assistant helping to rank geospatial collections based on their relevance to a user query.
For each collection, provide:
1. A concise explanation of why the collection is relevant to the query or not - only a short sentence.
2. Order the results with the most relevant first
3. Drop the irrelevant collections from the response
""",
)


async def collection_search(
    query: str,
    top_k: int = 5,
    model_name: str = MODEL_NAME,
    data_path: str = DATA_PATH,
    catalog_url: str = None,
) -> List[CollectionWithExplanation]:
    """
    Search for collections and rerank results with explanations

    Args:
        query: The user's natural language query
        top_k: Maximum number of results to return
        model_name: Name of the sentence transformer model to use
        data_path: Path to the vector database
        catalog_url: URL of the STAC catalog

    Returns:
        Ranked results with relevance explanations
    """
    start_time = time.time()

    # Initialize catalog manager
    catalog_manager = CatalogManager(data_path=data_path, model_name=model_name)

    # If catalog_url is provided, ensure it's loaded
    if catalog_url:
        load_result = await catalog_manager.load_catalog(catalog_url)
        if not load_result["success"]:
            logger.error(f"Failed to load catalog: {load_result['error']}")
            raise ValueError(f"Failed to load catalog: {load_result['error']}")

    # Get the appropriate collection
    collection = catalog_manager.get_catalog_collection(catalog_url)

    load_model_time = time.time()
    logger.info(f"Model loading time: {load_model_time - start_time:.4f} seconds")

    # Generate query embedding
    query_embedding = catalog_manager.model.encode([query])

    # Search vector database
    results = collection.query(
        query_embeddings=query_embedding.tolist(),
        n_results=top_k * 2,  # Get more results initially for better reranking
    )

    # Prepare the collections information
    collections_text = "\n\n".join(
        [
            f"Collection ID: {c['collection_id']}\nTitle: {c.get('title', '')}\nDescription: {c.get('description', '')}"
            for c in results["metadatas"][0]
        ]
    )

    user_prompt = f"""
User query: "{query}"

Collections to evaluate:
{collections_text}
"""

    agent_result = await rerank_agent.run(user_prompt)

    return agent_result.data.results


async def main():
    collections = await collection_search("Sentinel-2 imagery over France")
    logger.info(pformat(collections))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
