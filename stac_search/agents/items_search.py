from datetime import date
import logging
import os
from dataclasses import dataclass
from pprint import pformat
from typing import List, Dict, Any, Union

import requests
from pydantic_ai import Agent, RunContext
from pystac_client import Client
from pydantic import BaseModel, ConfigDict

from stac_search.agents.collections_search import (
    collection_search,
    CollectionWithExplanation,
)


GEODINI_API = os.getenv("GEODINI_API", "https://geodini.k8s.labs.ds.io")
SMALL_MODEL_NAME = os.getenv("SMALL_MODEL_NAME", "openai:gpt-4.1-mini")
STAC_CATALOG_URL = os.getenv(
    "STAC_CATALOG_URL", "https://planetarycomputer.microsoft.com/api/stac/v1"
)

logger = logging.getLogger(__name__)


@dataclass
class Context:
    query: str
    location: str | None = None
    top_k: int = 5
    return_search_params_only: bool = False


@dataclass
class ItemSearchParams:
    """Parameters to be used to query the STAC API"""

    location: str | None = None
    datetime: str | None = None
    filter: Dict[str, Any] | None = None


search_items_agent = Agent(
    SMALL_MODEL_NAME,
    result_type=ItemSearchParams,
    deps_type=Context,
    system_prompt="""
For the given query, extract the start date, end date, and location.

If the query contains a spatial extent, use the `set_spatial_extent` tool to get the location.
If the query contains a temporal range, use the `set_temporal_range` tool to get the datetime.
If the query needs cloud cover filtering, use the `construct_cql2_filter` tool to create a CQL2 filter.

""",
)


@search_items_agent.system_prompt
def search_items_agent_system_prompt():
    return f"The current date is {date.today()}"


@dataclass
class CollectionQuery:
    query: str
    is_specific: bool = False


collection_query_framing_agent = Agent(
    SMALL_MODEL_NAME,
    result_type=CollectionQuery,
    system_prompt="""
The user query is searching for relevant satellite imagery. 
You have to rephrase the user query to include information that is useful to filter STAC collections for
relevance through full text search on description.
Strip out the specific filters. Only include parts of the query that's relevant at the collection level:

for example:
cloudless imagery from sentinel over Paris -> sentinel imagery over Paris
There was a wildfire in Florida in 2023. I want images -> wildfire and burn scar imagery over Florida
I want to check how much forest reduced in Africa -> land cover land use data in Africa

If the user query is specific about a type of collection, return is_specific as True. Things that are specific to a collection
can be type of imagery like land cover, land use, forest cover change, burn scar, etc, type of platform like sentinel, landsat, etc.

For example:
"I want to check how much forest reduced in Africa" -> is_specific = True because it's looking for forest cover change data
"imagery of Paris" -> is_specific = False because it's looking for any imagery of Paris
"wildfire in Florida in 2023" -> is_specific = True because it's looking for wildfire imagery or burn scar data in Florida in 2023
"sentinel-2 imagery of Paris" -> is_specific = True because it's looking for sentinel-2 imagery of Paris
"show me relatively cloudless images of Colorado" -> is_specific = False because it's looking for general imagery of Colorado; cloud cover is not specific to a collection
""",
)


@dataclass
class CollectionSearchResult:
    collections: List[CollectionWithExplanation]


async def search_collections(query: str) -> CollectionSearchResult | None:
    logger.info("Searching for relevant collections ...")
    collection_query = await collection_query_framing_agent.run(query)
    logger.info(f"Framed collection query: {collection_query.data.query}")
    if collection_query.data.is_specific:
        collections = await collection_search(collection_query.data.query)
        return CollectionSearchResult(collections=collections)
    else:
        return None


@dataclass
class GeocodingResult:
    location: str


geocoding_agent = Agent(
    SMALL_MODEL_NAME,
    result_type=GeocodingResult,
    system_prompt="""
For the given query, if it contains a location, return location query to be used to search for the location.
Return enough information if available to uniquely identify the location.
If it doesn't contain a location, return an empty string.

For example, if the query is "cloudless imagery over France", the location query should be "France".
If the query is "show me images of Paris in Michigan", the location query should be "Paris, Michigan".
If the query is "do you have anything from Georgia the country", the location query should be "Georgia the country".
""",
)


@search_items_agent.tool
async def set_spatial_extent(ctx: RunContext[Context]) -> GeocodingResult:
    result = await geocoding_agent.run(ctx.deps.query)
    return result.data


@dataclass
class TemporalRangeResult:
    datetime: str | None


temporal_range_agent = Agent(
    SMALL_MODEL_NAME,
    result_type=TemporalRangeResult,
    system_prompt="""
For the given query, if it contains a temporal range, return the start date and end date. If it doesn't contain a temporal range, return None.
The temporal range should be of the form YYYY-MM-DD/YYYY-MM-DD.
For open-ended ranges, use "..", for example "2023-01-01/.." or "../2023-12-31".
""",
)


@temporal_range_agent.system_prompt
def temporal_range_agent_system_prompt():
    return f"The current date is {date.today()}"


@search_items_agent.tool
async def set_temporal_range(ctx: RunContext[Context]) -> TemporalRangeResult:
    result = await temporal_range_agent.run(ctx.deps.query)
    return result.data


class PropertyRef(BaseModel):
    property: str


class Geometry(BaseModel):
    type: str
    coordinates: Any


class GeometryLiteral(BaseModel):
    geometry: Geometry


class PeriodLiteral(BaseModel):
    period: List[str]


FilterArg = Union[
    "FilterExpr", PropertyRef, GeometryLiteral, PeriodLiteral, int, float, str
]


class FilterExpr(BaseModel):
    op: str
    args: List[FilterArg]

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="ignore")


FilterExpr.update_forward_refs()


cql2_filter_agent = Agent(
    SMALL_MODEL_NAME,
    result_type=FilterExpr,
    system_prompt="""
For the given query, construct a CQL2 filter to be used to query the STAC API only if required.
Return None if the query doesn't require a CQL2 filter or if you can't determine the filter or if the property is not supported.

Here is some example CQL2 filters:
{
    "op": "lte", "args": [{"property": "property_name"}, 10]
}

Here 10 is the value and property_name is the name of the property to filter on.

Only the follow are allowed as property_name:
- eo:cloud_cover


Here is an example of a more complex CQL2 filter:

{
    "op": "and",
    "args": [
        {"op": "eq", "args": [{"property": "property_name"}, 60]},
        {"op": "gte", "args": [{"property": "property_name"}, 40]},
    ]
}

The `op` should be one of the following: `and`, `or`, `not`, `eq`, `neq`, `gt`, `gte`, `lt`, `lte`.
The `args` should be a list of CQL2 filters.


Here's a list of properties that you can filter on:
"eo:cloud_cover" - Cloud cover percentage on a scale of 0 to 100. Cloudless imagery means cloud cover less than 10.

Return None if the query doesn't require a CQL2 filter or if you can't determine the filter or if the property is not supported.

Some examples of CQL2 filters:
- "cloudless imagery" -> {"op": "lte", "args": [{"property": "eo:cloud_cover"}, 10]}
- "imagery from 2023 to 2024 over France with less than 10 percent cloud cover" -> {"op": "and", "args": [{"op": "lte", "args": [{"property": "eo:cloud_cover"}, 10]}]}
- "imagery over Brazil with cloud cover between 10 and 20" -> {"op": "and", "args": [{"op": "gte", "args": [{"property": "eo:cloud_cover"}, 10]}, {"op": "lte", "args": [{"property": "eo:cloud_cover"}, 20]}]}

Return the filter dictionary itself as a JSON object. No additional keys or values; just the filter dictionary.
""",
)


@search_items_agent.tool
async def construct_cql2_filter(ctx: RunContext[Context]) -> FilterExpr | None:
    return await cql2_filter_agent.run(ctx.deps.query)


def get_polygon_from_geodini(location: str):
    geodini_api = f"{GEODINI_API}/search_complex"
    response = requests.get(
        geodini_api,
        params={"query": location},
    )
    result = response.json().get("result", None)
    if result:
        return result.get("geometry", None)
    return None


@dataclass
class ItemSearchResult:
    items: List[Dict[str, Any]] | None = None
    search_params: Dict[str, Any] | None = None
    aoi: Dict[str, Any] | None = None
    explanation: str = ""


async def item_search(ctx: Context) -> ItemSearchResult:
    # formulate the query to be used for the search
    results = await search_items_agent.run(
        f"Find items for the query: {ctx.query}", deps=ctx
    )

    # determine the collections to search
    target_collections = await search_collections(ctx.query) or []
    logger.info(f"Target collections: {pformat(target_collections)}")
    default_target_collections = [
        "landsat-8-c2-l2",
        "sentinel-2-l2a",
    ]
    if target_collections:
        explanation = "Considering the following collections:"
        for result in target_collections.collections:
            explanation += f"\n- {result.collection_id}: {result.explanation}"
        collections_to_search = [
            collection.collection_id for collection in target_collections.collections
        ]
    else:
        explanation = f"Including the following common collections in the search: {', '.join(default_target_collections)}\n"
        collections_to_search = default_target_collections

    # Actually perform the search
    client = Client.open(STAC_CATALOG_URL)
    params = {
        "max_items": 20,
        "collections": collections_to_search,
        "datetime": results.data.datetime,
        "filter": results.data.filter,
    }

    logger.info(f"Searching with params: {params}")

    polygon = get_polygon_from_geodini(results.data.location)
    if polygon:
        logger.info(f"Found polygon for {results.data.location}")
        params["intersects"] = polygon
    else:
        return ItemSearchResult(
            items=None,
            search_params=params,
            aoi=None,
            explanation=f"No polygon found for {results.data.location}",
        )

    if ctx.return_search_params_only:
        logger.info("Returning STAC query parameters only")
        return ItemSearchResult(
            search_params=params, aoi=polygon, explanation=explanation
        )

    items = list(client.search(**params).items_as_dicts())
    return ItemSearchResult(
        items=items, aoi=polygon, explanation=explanation, search_params=params
    )


async def main():
    ctx = Context(query="NAIP imagery from Washington state")
    results = await item_search(ctx)
    logger.info(pformat(results))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
