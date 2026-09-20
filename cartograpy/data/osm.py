from __future__ import annotations

import pandas as pd
import geopandas as gpd
from ._optional import _require_osmnx
import logging

logger = logging.getLogger(__name__)


class OSM :
    def __init__(self):
        self.api_key = ""
        self._ox = _require_osmnx()

    def get_data(self,place, tags, data_type="all"):
        """
        Retrieves OpenStreetMap data for a given place (str, bbox, or GeoDataFrame)
        and custom OSM tags.

        Args:
            place (str, tuple, list, GeoDataFrame): Area name, bbox (minx, miny, maxx, maxy), or polygonal GeoDataFrame.
            tags (dict): Dictionary of OSM tags to filter on, e.g.: {"amenity": "school"}.
            data_type (str): 'points' for POIs, 'polygons' for areas, 'lines' for lines, 'all' for every type.

        Returns:
            geopandas.GeoDataFrame: The OSM objects matching the query.
        """

        def filter_by_geometry_type(gdf, data_type):
            """Filters the GeoDataFrame by the requested geometry type."""
            if data_type == "points":
                return gdf[gdf.geometry.type.isin(['Point', 'MultiPoint'])]
            elif data_type == "polygons":
                return gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            elif data_type == "lines":
                return gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            elif data_type == "all":
                return gdf  # Returns every geometry type
            else:
                raise ValueError("data_type doit être 'points', 'polygons', 'lines' ou 'all'.")

        def handle_osm_request(request_func, *args, **kwargs):
            """Handles OSM requests with error handling."""
            try:
                gdf = request_func(*args, **kwargs)
                if gdf.empty:
                    return gpd.GeoDataFrame()
                return filter_by_geometry_type(gdf, data_type)
            except Exception as e:
                logger.error(f"Erreur lors de la récupération des données : {e}")
                return gpd.GeoDataFrame()

        # Case 1: Place name (str)
        if isinstance(place, str):
            return handle_osm_request(self._ox.features_from_place, place, tags)

        # Case 2: Bounding box (tuple/list of 4 values)
        elif isinstance(place, (tuple, list)) and len(place) == 4:
            minx, miny, maxx, maxy = place
            # bbox = (maxy, minx, miny, maxx)
            # OSMnx expects: north, south, east, west
            return handle_osm_request(self._ox.features_from_bbox, place, tags)

        # Case 3: GeoDataFrame (use the outer envelope)
        elif isinstance(place, gpd.GeoDataFrame):
            try:
                # Use unary_union to keep the exact shape (no convex_hull)
                polygon = place.union_all()
                return handle_osm_request(self._ox.features_from_polygon, polygon, tags)
            except Exception as e:
                logger.error(f"Erreur lors du traitement du GeoDataFrame : {e}")
                return gpd.GeoDataFrame()

        else:
            raise ValueError(
                "L'argument 'place' doit être un nom de lieu (str), "
                "une bbox (tuple/list de 4 valeurs) ou un GeoDataFrame."
            )

    def list_tags(self,category=None, show_examples=False):
        """
        Returns a list of common OSM tags, or those of a given category.

        Args:
            category (str): OSM tag category ('building', 'highway', 'amenity', 'water',
                        'landuse', 'natural', 'leisure', 'shop', 'tourism', 'transport', 'barrier')
                        If None, returns every category.
            show_examples (bool): If True, includes usage examples for each category.

        Returns:
            dict or list: Dictionary of categories with their tags, or list of tags for the requested category.
        """

        # Tags organized by category with common values
        tags = {
            "building": {
                "description": "Buildings and structures",
                "tags": {
                    "building": ["yes", "house", "apartment", "commercial", "industrial", "school", "hospital", "church"],
                    "building:levels": "Number of floors (numeric value)",
                    "building:use": ["residential", "commercial", "industrial", "retail", "office"],
                    "building:material": ["brick", "concrete", "wood", "stone", "glass"]
                },
                "example": {"building": "house", "building:levels": "2"}
            },

            "highway": {
                "description": "Roads, paths, and traffic ways",
                "tags": {
                    "highway": ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "footway", "cycleway"],
                    "lanes": "Number of lanes (numeric value)",
                    "surface": ["asphalt", "concrete", "paved", "unpaved", "gravel", "dirt"],
                    "maxspeed": "Maximum speed (e.g.: 50, 90, 130)",
                    "oneway": ["yes", "no", "-1"]
                },
                "example": {"highway": "primary", "lanes": "2", "maxspeed": "50"}
            },

            "amenity": {
                "description": "Public services and amenities",
                "tags": {
                    "amenity": ["school", "hospital", "bank", "cafe", "restaurant", "police", "post_office",
                            "pharmacy", "fuel", "parking", "library", "fire_station", "place_of_worship"]
                },
                "example": {"amenity": "restaurant", "cuisine": "french"}
            },

            "water": {
                "description": "Waterways and water features",
                "tags": {
                    "waterway": ["river", "stream", "canal", "drain", "ditch"],
                    "natural": ["water", "bay", "coastline"],
                    "water": ["lake", "pond", "reservoir", "river"],
                    "dam": ["yes", "weir"]
                },
                "example": {"waterway": "river", "name": "Seine"}
            },

            "landuse": {
                "description": "Land use and zoning",
                "tags": {
                    "landuse": ["residential", "commercial", "industrial", "forest", "farmland",
                            "meadow", "cemetery", "military", "recreation_ground"],
                    "natural": ["forest", "grassland", "scrub", "heath"]
                },
                "example": {"landuse": "residential", "residential": "urban"}
            },

            "natural": {
                "description": "Natural features",
                "tags": {
                    "natural": ["tree", "peak", "water", "wood", "beach", "cliff", "hill", "valley", "cave"],
                    "tree": ["deciduous", "coniferous", "palm"],
                    "leaf_type": ["broadleaved", "needleleaved"],
                    "ele": "Elevation in meters (numeric value)"
                },
                "example": {"natural": "peak", "name": "Mont Blanc", "ele": "4809"}
            },

            "leisure": {
                "description": "Leisure and recreational activities",
                "tags": {
                    "leisure": ["park", "pitch", "stadium", "swimming_pool", "playground", "golf_course",
                            "sports_centre", "garden", "marina", "beach_resort"]
                },
                "example": {"leisure": "park", "name": "Central Park"}
            },

            "shop": {
                "description": "Shops and stores",
                "tags": {
                    "shop": ["supermarket", "bakery", "butcher", "clothes", "shoes", "books", "pharmacy",
                            "electronics", "furniture", "car", "bicycle", "hairdresser"]
                },
                "example": {"shop": "bakery", "name": "La Boulangerie"}
            },

            "tourism": {
                "description": "Tourist sites and lodging",
                "tags": {
                    "tourism": ["hotel", "museum", "attraction", "viewpoint", "information", "camp_site",
                            "guest_house", "hostel", "monument", "artwork"],
                    "historic": ["castle", "monument", "memorial", "archaeological_site"]
                },
                "example": {"tourism": "museum", "name": "Louvre"}
            },

            "transport": {
                "description": "Public transport and infrastructure",
                "tags": {
                    "railway": ["rail", "subway", "tram", "light_rail", "station", "platform"],
                    "public_transport": ["platform", "station", "stop_position"],
                    "aeroway": ["runway", "taxiway", "terminal", "gate"],
                    "route": ["bus", "tram", "subway", "train"]
                },
                "example": {"railway": "station", "name": "Gare du Nord"}
            },

            "barrier": {
                "description": "Barriers and obstacles",
                "tags": {
                    "barrier": ["fence", "wall", "hedge", "gate", "bollard", "kerb"],
                    "access": ["yes", "no", "private", "permissive"]
                },
                "example": {"barrier": "fence", "material": "wood"}
            }
        }

        def format_category_info(cat_name, cat_data):
            """Formats the information for a category."""
            if show_examples:
                return {
                    "description": cat_data["description"],
                    "tags": cat_data["tags"],
                    "example": cat_data.get("example", {})
                }
            else:
                return list(cat_data["tags"].keys())

        if category is None:
            if show_examples:
                return {cat: format_category_info(cat, data) for cat, data in tags.items()}
            else:
                return {cat: list(data["tags"].keys()) for cat, data in tags.items()}
        else:
            category = category.lower()
            if category in tags:
                return format_category_info(category, tags[category])
            else:
                available_categories = list(tags.keys())
                raise ValueError(f"Catégorie '{category}' non trouvée. Catégories disponibles : {available_categories}")


    def search_tags(self, keyword: str) -> dict:
        """
        Searches OSM tags containing a keyword.

        Args:
            keyword (str): Keyword to search for among the tags

        Returns:
            dict: Dictionary with matching categories and tags
        """
        all_tags: dict = self.list_tags(show_examples=True)  # type: ignore[assignment]
        results = {}

        keyword = keyword.lower()

        for category, data in all_tags.items():
            matching_tags = {}

            # Search within the tags
            for tag_key, tag_values in data["tags"].items():
                if keyword in tag_key.lower():
                    matching_tags[tag_key] = tag_values
                elif isinstance(tag_values, list):
                    matching_values = [v for v in tag_values if keyword in v.lower()]
                    if matching_values:
                        matching_tags[tag_key] = matching_values
                elif isinstance(tag_values, str) and keyword in tag_values.lower():
                    matching_tags[tag_key] = tag_values

            if matching_tags:
                results[category] = {
                    "description": data["description"],
                    "matching_tags": matching_tags,
                    "example": data.get("example", {})
                }

        return results


    def sources(self) -> pd.DataFrame:
        """
        Returns a table of the data sources used by this class.

        Returns:
            pd.DataFrame: Columns 'name', 'url', 'description'.
        """
        return pd.DataFrame([
            {
                "name": "OpenStreetMap",
                "url": "https://www.openstreetmap.org/",
                "description": "Crowdsourced geographic data (buildings, roads, POIs...) via osmnx.",
            },
        ])

    def get_common_tag(self):
        """
        Returns commonly used combinations of tags.

        Returns:
            dict: Dictionary with common query examples
        """
        return {
            "restaurants": {"amenity": "restaurant"},
            "schools": {"amenity": "school"},
            "hospitals": {"amenity": "hospital"},
            "parks": {"leisure": "park"},
            "supermarkets": {"shop": "supermarket"},
            "hotels": {"tourism": "hotel"},
            "gas_stations": {"amenity": "fuel"},
            "pharmacies": {"amenity": "pharmacy"},
            "banks": {"amenity": "bank"},
            "cafes": {"amenity": "cafe"},
            "museums": {"tourism": "museum"},
            "primary_roads": {"highway": ["primary", "trunk", "motorway"]},
            "residential_buildings": {"building": "residential"},
            "commercial_buildings": {"building": "commercial"},
            "rivers": {"waterway": "river"},
            "forests": {"landuse": "forest"},
            "beaches": {"natural": "beach"},
            "train_stations": {"railway": "station"},
            "bus_stops": {"highway": "bus_stop"},
            "parking": {"amenity": "parking"}
        }
