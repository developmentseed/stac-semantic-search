"""
FastAPI server for STAC Natural Query
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from stac_search.agents.collections_search import collection_search
from stac_search.agents.items_search import item_search, Context as ItemSearchContext

# Initialize FastAPI app
app = FastAPI(
    title="STAC Natural Query API",
    description="API for semantic search of STAC collections",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# Define request model
class QueryRequest(BaseModel):
    query: str


class STACItemsRequest(BaseModel):
    query: str
    return_search_params_only: bool = False


# Define search endpoint
@app.post("/search")
async def search(request: QueryRequest):
    """Search for STAC collections using natural language"""
    results = collection_search(request.query)
    return {"results": results}


@app.post("/items/search")
async def search_items(request: STACItemsRequest):
    """Search for STAC items using natural language"""
    ctx = ItemSearchContext(
        query=request.query, return_search_params_only=request.return_search_params_only
    )
    results = await item_search(ctx)
    return {"results": results}


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI server"""
    uvicorn.run(app, host=host, port=port)
