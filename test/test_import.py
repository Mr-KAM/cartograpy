"""Tests de base pour le package cartograpy."""

import pytest


class TestImports:
    """Vérifie que le package et ses sous-modules s'importent correctement."""

    def test_import_package(self):
        import cartograpy

    def test_import_all_exports(self):
        from cartograpy import __all__
        import cartograpy

        for name in __all__:
            assert hasattr(cartograpy, name), f"{name} absent de cartograpy"

    def test_import_map(self):
        from cartograpy import Map

    def test_import_map2d(self):
        from cartograpy import Map2D

    def test_import_webmap(self):
        from cartograpy import WebMap

    def test_import_situation_map(self):
        from cartograpy import SituationMap

    def test_map2d_inherits_map(self):
        from cartograpy import Map, Map2D
        assert issubclass(Map2D, Map)

    def test_import_data(self):
        from cartograpy import load, save, list_geofiles
        from cartograpy import GeoBoundaries, Bound, WorldBank, OSM, Hydro, DEM

    def test_import_processing(self):
        from cartograpy import centroids, join, fusion, add_column, split_multipolygon

    def test_import_styling(self):
        from cartograpy import (
            get_fonts,
            get_available_palettes,
            color_palettes,
            custom_palettes,
            load_cmap,
            to_cmap,
            show_palette,
            show_palette_details,
            palettes_by_popularity,
            palettes_with_color,
            preview_multiple_palettes,
            set_style,
            list_all_styles,
        )

    def test_import_geocoder(self):
        from cartograpy import (
            GeocodingProvider,
            NominatimProvider,
            OpenCageProvider,
            GeocodingResult,
        )

    def test_import_converter(self):
        from cartograpy import converter, extract_gpx_data

    def test_import_country_iso3(self):
        from cartograpy import COUNTRY_ISO3
        assert isinstance(COUNTRY_ISO3, dict)
        assert len(COUNTRY_ISO3) > 0
        # Vérifie quelques entrées connues
        assert COUNTRY_ISO3.get("france") == "fra"
        assert COUNTRY_ISO3.get("germany") == "deu"

    def test_init_project(self):
        from cartograpy import init_project
        assert callable(init_project)


class TestStyling:
    """Vérifie les fonctions de styling."""

    def test_get_available_palettes_returns_dict(self):
        from cartograpy import get_available_palettes
        result = get_available_palettes()
        assert isinstance(result, dict)
        assert "custom" in result

    def test_color_palettes_returns_dict(self):
        from cartograpy import color_palettes
        assert isinstance(color_palettes, dict)

    def test_get_fonts_returns_list(self):
        from cartograpy import get_fonts
        result = get_fonts()
        assert isinstance(result, list)
