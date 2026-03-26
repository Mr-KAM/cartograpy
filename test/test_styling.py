"""Tests pour le module styling."""

import pytest
from cartograpy.styling import (
    get_fonts,
    color_palettes,
    custom_palettes,
    get_available_palettes,
    show_palette_details,
    palettes_by_popularity,
    palettes_with_color,
    to_cmap,
    load_cmap,
    set_style,
    list_all_styles,
)


class TestGetFonts:
    """Tests de la fonction get_fonts."""

    def test_returns_list(self):
        result = get_fonts()
        assert isinstance(result, list)

    def test_not_empty(self):
        result = get_fonts()
        assert len(result) > 0

    def test_sorted_by_default(self):
        result = get_fonts()
        assert result == sorted(result)

    def test_no_duplicates(self):
        result = get_fonts()
        assert len(result) == len(set(result))

    def test_filter_pattern(self):
        all_fonts = get_fonts()
        if len(all_fonts) > 0:
            # Use first 3 chars of first font as pattern
            pattern = all_fonts[0][:3]
            filtered = get_fonts(pattern=pattern)
            assert len(filtered) <= len(all_fonts)
            for font in filtered:
                assert pattern.lower() in font.lower()

    def test_unsorted(self):
        result = get_fonts(sort=False)
        assert isinstance(result, list)
        assert len(result) > 0


class TestColorPalettes:
    """Tests du dictionnaire color_palettes."""

    def test_is_dict(self):
        assert isinstance(color_palettes, dict)

    def test_not_empty(self):
        assert len(color_palettes) > 0

    def test_palette_structure(self):
        for key, palette in color_palettes.items():
            assert "nom" in palette, f"Palette '{key}' missing 'nom'"
            assert "likes" in palette, f"Palette '{key}' missing 'likes'"
            assert "couleurs" in palette, f"Palette '{key}' missing 'couleurs'"
            assert isinstance(palette["couleurs"], list)
            assert len(palette["couleurs"]) > 0

    def test_colors_are_hex(self):
        for key, palette in color_palettes.items():
            for color in palette["couleurs"]:
                assert color.startswith("#"), f"Color '{color}' in palette '{key}' is not hex"

    def test_known_palettes_exist(self):
        assert "p1" in color_palettes
        assert "p2" in color_palettes


class TestCustomPalettes:
    """Tests de la fonction custom_palettes."""

    def test_returns_dict(self):
        result = custom_palettes()
        assert isinstance(result, dict)

    def test_same_keys_as_color_palettes(self):
        result = custom_palettes()
        assert set(result.keys()) == set(color_palettes.keys())


class TestGetAvailablePalettes:
    """Tests de la fonction get_available_palettes."""

    def test_returns_dict(self):
        result = get_available_palettes()
        assert isinstance(result, dict)

    def test_contains_custom_key(self):
        result = get_available_palettes()
        assert "custom" in result

    def test_exclude_custom(self):
        result = get_available_palettes(include_custom=False)
        assert result["custom"] == []

    def test_include_seaborn(self):
        result = get_available_palettes(include_seaborn=True)
        assert "seaborn_qualitative" in result
        assert len(result["seaborn_qualitative"]) > 0

    def test_include_matplotlib(self):
        result = get_available_palettes(include_matplotlib=True)
        assert "matplotlib_sequential" in result
        assert len(result["matplotlib_sequential"]) > 0


class TestPalettesByPopularity:
    """Tests de la fonction palettes_by_popularity."""

    def test_returns_list(self):
        result = palettes_by_popularity()
        assert isinstance(result, list)

    def test_sorted_descending(self):
        result = palettes_by_popularity()
        likes_values = [item[2] for item in result]
        assert likes_values == sorted(likes_values, reverse=True)

    def test_min_likes_filter(self):
        all_palettes = palettes_by_popularity(min_likes=0)
        filtered = palettes_by_popularity(min_likes=50000)
        assert len(filtered) <= len(all_palettes)
        for _, _, likes in filtered:
            assert likes >= 50000


class TestPalettesWithColor:
    """Tests de la fonction palettes_with_color."""

    def test_returns_list(self):
        result = palettes_with_color("#FFFFFF")
        assert isinstance(result, list)

    def test_finds_known_color(self):
        # Use a color from p1
        result = palettes_with_color("#B19CD9")
        assert len(result) > 0

    def test_no_match(self):
        result = palettes_with_color("#AAAAAA")
        assert isinstance(result, list)


class TestToCmap:
    """Tests de la fonction to_cmap."""

    def test_returns_cmap(self):
        colors = ["#FF0000", "#00FF00", "#0000FF"]
        result = to_cmap(colors)
        assert result is not None

    def test_continuous_type(self):
        colors = ["#FF0000", "#0000FF"]
        result = to_cmap(colors, cmap_type="continuous")
        assert result is not None


class TestSetStyleAndListStyles:
    """Tests de set_style et list_all_styles."""

    def test_list_all_styles_returns_dict(self):
        result = list_all_styles()
        assert isinstance(result, dict)
        assert "matplotlib" in result

    def test_list_all_styles_has_matplotlib_styles(self):
        result = list_all_styles()
        assert len(result["matplotlib"]) > 0

    def test_set_style_known(self):
        styles = list_all_styles()
        mpl_styles = styles.get("matplotlib", [])
        if mpl_styles:
            # Should not raise
            set_style(mpl_styles[0])
