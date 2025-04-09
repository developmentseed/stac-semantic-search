"""
Streamlit app for STAC Natural Query
"""

import streamlit as st
import asyncio
import folium
from streamlit_folium import folium_static
import pandas as pd
import requests
from pprint import pprint
import os

# Get API URL from environment variable with a fallback
API_URL = os.environ.get("API_URL", "https://stac-semantic-search.labs.sunu.in/")
# Ensure API_URL ends with a trailing slash
if not API_URL.endswith("/"):
    API_URL += "/"

# Set page config
st.set_page_config(
    page_title="STAC Natural Query",
    page_icon="🌍",
    layout="wide",
)


# App title and description
st.title("🌍 STAC Natural Query")
st.markdown(
    """
    Search for satellite imagery using natural language. 
    This app converts your query into STAC API parameters and displays the results on a map.
    """
)

# Create input field for the query
query = st.text_input(
    "Enter your query",
    placeholder="Find imagery over Paris from 2017",
    help="Describe what kind of satellite imagery you're looking for",
)

# Add a search button
search_button = st.button("Search")


# Function to run the search asynchronously
async def run_search(query):
    response = requests.post(
        f"{API_URL}/items/search", json={"query": query, "limit": 10}
    )
    return response.json()["results"]


# Handle query submission
if query and search_button:
    with st.spinner("Searching for STAC items..."):
        try:
            # Run the async search
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results = loop.run_until_complete(run_search(query))
            items = results["items"]
            aoi = results["aoi"]
            explanation = results["explanation"]

            # pprint(items)
            st.info(f"**Info**: {explanation}")

            # Check if items were found
            if not items:
                st.warning("No items found matching your query.")
            else:
                st.success(f"Found {len(items)} items matching your query!")

            # Always show map if we have AOI, regardless of whether items were found
            # Center map on AOI if available, otherwise on the first item
            item_center = None

            # Try to use AOI center first
            if aoi:
                try:
                    # The AOI is likely a GeoJSON geometry
                    aoi_type = aoi.get("type")
                    aoi_coords = aoi.get("coordinates", [])

                    if aoi_type == "Polygon" and len(aoi_coords) > 0:
                        # Average the coordinates of the first ring
                        lngs = [coord[0] for coord in aoi_coords[0]]
                        lats = [coord[1] for coord in aoi_coords[0]]
                        item_center = [sum(lats) / len(lats), sum(lngs) / len(lngs)]
                    elif aoi_type == "MultiPolygon" and len(aoi_coords) > 0:
                        # Average the coordinates of the first polygon's first ring
                        lngs = [coord[0] for coord in aoi_coords[0][0]]
                        lats = [coord[1] for coord in aoi_coords[0][0]]
                        item_center = [sum(lats) / len(lats), sum(lngs) / len(lngs)]
                except Exception as e:
                    # If there's any error calculating AOI center, fall back to item center
                    # Silently fail and fall back to item center
                    pass

            # Fall back to item center if AOI center not found and we have items
            if not item_center and items:
                for item in items:
                    if (
                        "geometry" in item
                        and item["geometry"]
                        and "coordinates" in item["geometry"]
                    ):
                        # Get the center of the first polygon/multipolygon
                        coords = item["geometry"]["coordinates"]
                        if item["geometry"]["type"] == "Polygon":
                            # Average the coordinates of the first ring
                            lngs = [coord[0] for coord in coords[0]]
                            lats = [coord[1] for coord in coords[0]]
                            item_center = [
                                sum(lats) / len(lats),
                                sum(lngs) / len(lngs),
                            ]
                            break
                        elif item["geometry"]["type"] == "MultiPolygon":
                            # Average the coordinates of the first polygon's first ring
                            lngs = [coord[0] for coord in coords[0][0]]
                            lats = [coord[1] for coord in coords[0][0]]
                            item_center = [
                                sum(lats) / len(lats),
                                sum(lngs) / len(lngs),
                            ]
                            break

            # Default to world map if no valid geometry
            if not item_center:
                item_center = [0, 0]

            # Create the map if we have an AOI or items
            if aoi or items:
                # Create the map
                m = folium.Map(location=item_center, zoom_start=6)

                # Add AOI to the map if available
                if aoi:
                    folium.GeoJson(
                        aoi,
                        name="Area of Interest",
                        tooltip="Area of Interest",
                        style_function=lambda x: {
                            "fillColor": "#ff7800",
                            "color": "#ff0000",
                            "weight": 3,
                            "fill_opacity": 0.5,
                            "dashArray": "5, 5",
                        },
                    ).add_to(m)

                # Create a DataFrame for item details
                item_details = []

                # Add each item to the map if we have items
                if items:
                    for i, item in enumerate(items):
                        if "geometry" in item and item["geometry"]:
                            # Add the footprint to the map
                            if item["geometry"]["type"] in ["Polygon", "MultiPolygon"]:
                                folium.GeoJson(
                                    item["geometry"],
                                    name=item.get("id", f"Item {i}"),
                                    tooltip=item.get("id", f"Item {i}"),
                                    style_function=lambda x: {
                                        "fillColor": "#0000ff",
                                        "color": "#0000ff",
                                        "weight": 2,
                                        "fillOpacity": 0.1,
                                    },
                                ).add_to(m)

                        # Add to item details
                        item_details.append(
                            {
                                "ID": item.get("id", f"Item {i}"),
                                "Collection": item.get("collection"),
                                "Date": item.get("properties", {}).get(
                                    "datetime", "Unknown"
                                ),
                                "Cloud Cover": item.get("properties", {}).get(
                                    "eo:cloud_cover", "Unknown"
                                ),
                            }
                        )

                # Display the map
                st.subheader("Spatial Coverage")
                folium_static(m)

                # Display item details if we have items
                if items:
                    st.subheader("Item Details")
                    df = pd.DataFrame(item_details)
                    st.dataframe(df, use_container_width=True)

            # Always display raw response in expander
            with st.expander("Raw Response"):
                st.json(results)

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

# Add information about the app
with st.sidebar:
    st.header("About")
    st.markdown(
        """
        Search for satellite imagery using natural language.
        
        **Examples queries:**
        - imagery of Paris from 2017
        - Cloud-free satellite data of Georgia the country from 2022
        - relatively cloud-free images in 2024 that have RGB visual bands over Longmont, Colorado that can be downloaded via HTTP
        - images in 2024 over Odisha with cloud cover between 50 to 60%
        - NAIP imagery over the state of Washington
        - Burn scar imagery of from 2024 over the state of California
        """
    )
