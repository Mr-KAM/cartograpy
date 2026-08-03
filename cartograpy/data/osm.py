from __future__ import annotations

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
        Récupère des données OpenStreetMap pour un lieu donné (str, bbox ou GeoDataFrame)
        et des tags OSM personnalisés.
        
        Args:
            place (str, tuple, list, GeoDataFrame): Nom de la zone, bbox (minx, miny, maxx, maxy), ou GeoDataFrame polygonal.
            tags (dict): Dictionnaire des tags OSM à filtrer, ex: {"amenity": "school"}.
            data_type (str): 'points' pour POIs, 'polygons' pour surfaces, 'lines' pour lignes, 'all' pour tous types.
            
        Returns:
            geopandas.GeoDataFrame : Les objets OSM correspondant à la requête.
        """
        
        def filter_by_geometry_type(gdf, data_type):
            """Filtre le GeoDataFrame selon le type de géométrie souhaité."""
            if data_type == "points":
                return gdf[gdf.geometry.type.isin(['Point', 'MultiPoint'])]
            elif data_type == "polygons":
                return gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            elif data_type == "lines":
                return gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
            elif data_type == "all":
                return gdf  # Retourne tous les types de géométries
            else:
                raise ValueError("data_type doit être 'points', 'polygons', 'lines' ou 'all'.")
        
        def handle_osm_request(request_func, *args, **kwargs):
            """Gère les requêtes OSM avec gestion d'erreurs."""
            try:
                gdf = request_func(*args, **kwargs)
                if gdf.empty:
                    logger.info(f"Aucune donnée trouvée avec les tags {tags}")
                    return gpd.GeoDataFrame()
                return filter_by_geometry_type(gdf, data_type)
            except Exception as e:
                logger.info(f"Erreur lors de la récupération des données : {e}")
                return gpd.GeoDataFrame()
        
        # Cas 1 : Nom de lieu (str)
        if isinstance(place, str):
            return handle_osm_request(self._ox.features_from_place, place, tags)
        
        # Cas 2 : Bounding box (tuple/list de 4 valeurs)
        elif isinstance(place, (tuple, list)) and len(place) == 4:
            minx, miny, maxx, maxy = place
            # bbox = (maxy, minx, miny, maxx)
            # OSMnx attend : north, south, east, west
            return handle_osm_request(self._ox.features_from_bbox, place, tags)
        
        # Cas 3 : GeoDataFrame (on prend l'enveloppe extérieure)
        elif isinstance(place, gpd.GeoDataFrame):
            try:
                # Utilise unary_union pour garder la forme exacte (sans convex_hull)
                polygon = place.union_all()
                return handle_osm_request(self._ox.features_from_polygon, polygon, tags)
            except Exception as e:
                logger.info(f"Erreur lors du traitement du GeoDataFrame : {e}")
                return gpd.GeoDataFrame()
        
        else:
            raise ValueError(
                "L'argument 'place' doit être un nom de lieu (str), "
                "une bbox (tuple/list de 4 valeurs) ou un GeoDataFrame."
            )
    
    def list_tags(self,category=None, show_examples=False):
        """
        Retourne une liste de tags OSM courants, ou ceux d'une catégorie donnée.
        
        Args:
            category (str): Catégorie de tags OSM ('building', 'highway', 'amenity', 'water', 
                        'landuse', 'natural', 'leisure', 'shop', 'tourism', 'transport', 'barrier')
                        Si None, retourne toutes les catégories.
            show_examples (bool): Si True, inclut des exemples d'utilisation pour chaque catégorie.
            
        Returns:
            dict ou list: Dictionnaire de catégories avec leurs tags, ou liste des tags de la catégorie demandée.
        """
        
        # Tags organisés par catégorie avec valeurs courantes
        tags = {
            "building": {
                "description": "Bâtiments et structures",
                "tags": {
                    "building": ["yes", "house", "apartment", "commercial", "industrial", "school", "hospital", "church"],
                    "building:levels": "Nombre d'étages (valeur numérique)",
                    "building:use": ["residential", "commercial", "industrial", "retail", "office"],
                    "building:material": ["brick", "concrete", "wood", "stone", "glass"]
                },
                "example": {"building": "house", "building:levels": "2"}
            },
            
            "highway": {
                "description": "Routes, chemins et voies de circulation",
                "tags": {
                    "highway": ["motorway", "trunk", "primary", "secondary", "tertiary", "residential", "footway", "cycleway"],
                    "lanes": "Nombre de voies (valeur numérique)",
                    "surface": ["asphalt", "concrete", "paved", "unpaved", "gravel", "dirt"],
                    "maxspeed": "Vitesse maximale (ex: 50, 90, 130)",
                    "oneway": ["yes", "no", "-1"]
                },
                "example": {"highway": "primary", "lanes": "2", "maxspeed": "50"}
            },
            
            "amenity": {
                "description": "Services publics et commodités",
                "tags": {
                    "amenity": ["school", "hospital", "bank", "cafe", "restaurant", "police", "post_office", 
                            "pharmacy", "fuel", "parking", "library", "fire_station", "place_of_worship"]
                },
                "example": {"amenity": "restaurant", "cuisine": "french"}
            },
            
            "water": {
                "description": "Cours d'eau et éléments hydrauliques",
                "tags": {
                    "waterway": ["river", "stream", "canal", "drain", "ditch"],
                    "natural": ["water", "bay", "coastline"],
                    "water": ["lake", "pond", "reservoir", "river"],
                    "dam": ["yes", "weir"]
                },
                "example": {"waterway": "river", "name": "Seine"}
            },
            
            "landuse": {
                "description": "Utilisation du sol et zonage",
                "tags": {
                    "landuse": ["residential", "commercial", "industrial", "forest", "farmland", 
                            "meadow", "cemetery", "military", "recreation_ground"],
                    "natural": ["forest", "grassland", "scrub", "heath"]
                },
                "example": {"landuse": "residential", "residential": "urban"}
            },
            
            "natural": {
                "description": "Éléments naturels",
                "tags": {
                    "natural": ["tree", "peak", "water", "wood", "beach", "cliff", "hill", "valley", "cave"],
                    "tree": ["deciduous", "coniferous", "palm"],
                    "leaf_type": ["broadleaved", "needleleaved"],
                    "ele": "Altitude en mètres (valeur numérique)"
                },
                "example": {"natural": "peak", "name": "Mont Blanc", "ele": "4809"}
            },
            
            "leisure": {
                "description": "Loisirs et activités récréatives",
                "tags": {
                    "leisure": ["park", "pitch", "stadium", "swimming_pool", "playground", "golf_course", 
                            "sports_centre", "garden", "marina", "beach_resort"]
                },
                "example": {"leisure": "park", "name": "Central Park"}
            },
            
            "shop": {
                "description": "Commerces et magasins",
                "tags": {
                    "shop": ["supermarket", "bakery", "butcher", "clothes", "shoes", "books", "pharmacy", 
                            "electronics", "furniture", "car", "bicycle", "hairdresser"]
                },
                "example": {"shop": "bakery", "name": "La Boulangerie"}
            },
            
            "tourism": {
                "description": "Sites touristiques et hébergements",
                "tags": {
                    "tourism": ["hotel", "museum", "attraction", "viewpoint", "information", "camp_site", 
                            "guest_house", "hostel", "monument", "artwork"],
                    "historic": ["castle", "monument", "memorial", "archaeological_site"]
                },
                "example": {"tourism": "museum", "name": "Louvre"}
            },
            
            "transport": {
                "description": "Transport public et infrastructure",
                "tags": {
                    "railway": ["rail", "subway", "tram", "light_rail", "station", "platform"],
                    "public_transport": ["platform", "station", "stop_position"],
                    "aeroway": ["runway", "taxiway", "terminal", "gate"],
                    "route": ["bus", "tram", "subway", "train"]
                },
                "example": {"railway": "station", "name": "Gare du Nord"}
            },
            
            "barrier": {
                "description": "Barrières et obstacles",
                "tags": {
                    "barrier": ["fence", "wall", "hedge", "gate", "bollard", "kerb"],
                    "access": ["yes", "no", "private", "permissive"]
                },
                "example": {"barrier": "fence", "material": "wood"}
            }
        }
        
        def format_category_info(cat_name, cat_data):
            """Formate les informations d'une catégorie."""
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
        Recherche des tags OSM contenant un mot-clé.
        
        Args:
            keyword (str): Mot-clé à rechercher dans les tags
            
        Returns:
            dict: Dictionnaire avec les catégories et tags correspondants
        """
        all_tags: dict = self.list_tags(show_examples=True)  # type: ignore[assignment]
        results = {}
        
        keyword = keyword.lower()
        
        for category, data in all_tags.items():
            matching_tags = {}
            
            # Recherche dans les tags
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


    def get_common_tag(self):
        """
        Retourne des combinaisons de tags couramment utilisées ensemble.
        
        Returns:
            dict: Dictionnaire avec des exemples de requêtes courantes
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
