import datetime
from dataclasses import dataclass
from typing import List, Dict, Any
from pystac_client import Client
import requests
from pydantic_ai import Agent, RunContext
from pprint import pprint
import os

from stac_search.agents.collections_search import (
    collection_search,
    CollectionWithExplanation,
)

GEODINI_API = os.getenv("GEODINI_API")


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
    "openai:gpt-4o-mini",
    result_type=ItemSearchParams,
    deps_type=Context,
    system_prompt=f"""
For the given query, extract the start date, end date, and location.

If the query contains a spatial extent, use the `set_spatial_extent` tool to get the location.
If the query contains a temporal range, use the `set_temporal_range` tool to get the datetime.
If the query needs cloud cover filtering, use the `construct_cql2_filter` tool to create a CQL2 filter.

For context, the current date is {datetime.datetime.now().strftime("%Y-%m-%d")}.
""",
)


@dataclass
class CollectionQuery:
    query: str
    is_specific: bool = False


collection_query_framing_agent = Agent(
    "openai:gpt-4o-mini",
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
    # print("Searching for relevant collections ...")
    collection_query = await collection_query_framing_agent.run(query)
    print("Framed collection query: ", collection_query.data.query)
    if collection_query.data.is_specific:
        collections = await collection_search(collection_query.data.query)
        return CollectionSearchResult(collections=collections)
    else:
        return None


@dataclass
class GeocodingResult:
    location: str


geocoding_agent = Agent(
    "openai:gpt-4o-mini",
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
    "openai:gpt-4o-mini",
    result_type=TemporalRangeResult,
    system_prompt="""
For the given query, if it contains a temporal range, return the start date and end date. If it doesn't contain a temporal range, return None.
The temporal range should be of the form YYYY-MM-DD/YYYY-MM-DD.
For open-ended ranges, use "..", for example "2023-01-01/.." or "../2023-12-31".
The current date is {datetime.datetime.now().strftime("%Y-%m-%d")}.
""",
)


@search_items_agent.tool
async def set_temporal_range(ctx: RunContext[Context]) -> TemporalRangeResult:
    result = await temporal_range_agent.run(ctx.deps.query)
    return result.data


@dataclass
class Cql2Filter:
    """Parameters to be used to query the STAC API"""

    op: str
    args: List[Any]


cql2_filter_agent = Agent(
    "openai:gpt-4o-mini",
    result_type=Cql2Filter,
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
""",
)


@search_items_agent.tool
async def construct_cql2_filter(ctx: RunContext[Context]) -> Cql2Filter:
    return await cql2_filter_agent.run(ctx.deps.query)


def get_polygon_from_geodini(location: str):
    geodini_api = f"{GEODINI_API}/search"
    response = requests.get(
        geodini_api,
        params={
            "query": location,
            "limit": 10,
            "include_geometry": True,
            "smart_parse": True,
            "rank": True,
        },
    )
    result = response.json().get("most_probable", None)
    if result:
        polygon = result.get("geometry")
        return polygon
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
    print(results.data)

    # determine the collections to search
    target_collections = await search_collections(ctx.query) or []
    print("Target collections: ", target_collections)
    default_target_collections = [
        "landsat-8-c2-l2",
        "sentinel-2-l2a",
        "landsat-8-c2-l2",
        "landsat-8-c2-l2",
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
    CATALOG_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
    client = Client.open(CATALOG_URL)
    params = {
        "max_items": 20,
        # looks like collections is required by Planetary Computer STAC API
        # but can be omitted for elasticsearch based STAC APIs like the element84 one
        "collections": collections_to_search,
        # "collections": ["*"],
        # "datetime": "2018",
        "datetime": results.data.datetime,
        "filter": results.data.filter,
    }

    print(f"Searching with params: {params}")

    polygon = get_polygon_from_geodini(results.data.location)
    if polygon:
        print(f"Found polygon for {results.data.location}")
        params["intersects"] = polygon

    # print(f"Searching with params: {params}")

    if ctx.return_search_params_only:
        print("Returning STAC query parameters only")
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
    pprint(results)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
