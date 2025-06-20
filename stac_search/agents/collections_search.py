"""
Search module for STAC Natural Query
"""

import os
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
import chromadb
from typing import List, Dict, Any
from pprint import pformat
import time
import logging

from pydantic_ai import Agent


logger = logging.getLogger(__name__)

# Constants
MODEL_NAME = "all-MiniLM-L6-v2"
DATA_PATH = os.environ.get("DATA_PATH", "data/chromadb")
OPENAI_MODEL = "gpt-4o-mini"

STAC_CATALOG_NAME = os.getenv("STAC_CATALOG_NAME", "planetarycomputer")
STAC_COLLECTIONS_URL = os.getenv(
    "STAC_COLLECTIONS_URL", "https://planetarycomputer.microsoft.com/api/stac/v1"
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)


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
    "openai:gpt-4o-mini",
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
    stac_catalog_name: str = STAC_CATALOG_NAME,
) -> List[CollectionWithExplanation]:
    """
    Search for collections and rerank results with explanations

    Args:
        query: The user's natural language query
        top_k: Maximum number of results to return
        model_name: Name of the sentence transformer model to use
        data_path: Path to the vector database
        stac_catalog_name: Name of the STAC catalog
        stac_collections_url: URL of the STAC collections API

    Returns:
        Ranked results with relevance explanations
    """
    start_time = time.time()

    # Initialize model and database connections
    model = SentenceTransformer(model_name)
    load_model_time = time.time()
    logger.info(f"Model loading time: {load_model_time - start_time:.4f} seconds")

    client = chromadb.PersistentClient(path=data_path)
    logger.info(client.list_collections())
    collection_name = f"{stac_catalog_name}_collections"
    collection = client.get_collection(name=collection_name)

    # Generate query embedding
    query_embedding = model.encode([query])

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
