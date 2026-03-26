"""Tests pour le module iso_code."""

from cartograpy.iso_code import countries_iso3, iso_codes, iso2_iso3_dict


class TestCountriesIso3:
    """Tests du dictionnaire countries_iso3."""

    def test_is_dict(self):
        assert isinstance(countries_iso3, dict)

    def test_not_empty(self):
        assert len(countries_iso3) > 0

    def test_known_country_english(self):
        assert countries_iso3["france"] == "fra"
        assert countries_iso3["germany"] == "deu"
        assert countries_iso3["brazil"] == "bra"
        assert countries_iso3["japan"] == "jpn"
        assert countries_iso3["china"] == "chn"

    def test_known_country_french(self):
        assert countries_iso3["algérie"] == "dza"
        assert countries_iso3["allemagne"] == "deu"

    def test_known_country_iso2_key(self):
        assert countries_iso3["fr"] == "fra"
        assert countries_iso3["us"] == "usa"
        assert countries_iso3["de"] == "deu"
        assert countries_iso3["ci"] == "civ"

    def test_values_are_lowercase_3letter(self):
        for key, value in countries_iso3.items():
            assert isinstance(value, str)
            assert len(value) == 3, f"ISO3 code for '{key}' has length {len(value)}"
            assert value == value.lower(), f"ISO3 code '{value}' is not lowercase"

    def test_missing_country_returns_none(self):
        assert countries_iso3.get("nonexistent_country") is None


class TestIsoCodes:
    """Tests de la liste iso_codes."""

    def test_is_list(self):
        assert isinstance(iso_codes, list)

    def test_not_empty(self):
        assert len(iso_codes) > 0

    def test_contains_known_codes(self):
        assert "fra" in iso_codes
        assert "usa" in iso_codes
        assert "civ" in iso_codes
        assert "deu" in iso_codes

    def test_all_codes_are_3letter_lowercase(self):
        for code in iso_codes:
            assert isinstance(code, str)
            assert len(code) == 3
            assert code == code.lower()

    def test_no_duplicates(self):
        assert len(iso_codes) == len(set(iso_codes))


class TestIso2Iso3Dict:
    """Tests du dictionnaire iso2_iso3_dict."""

    def test_is_dict(self):
        assert isinstance(iso2_iso3_dict, dict)

    def test_not_empty(self):
        assert len(iso2_iso3_dict) > 0

    def test_keys_are_2letter(self):
        for key in iso2_iso3_dict:
            assert len(key) == 2, f"Key '{key}' is not 2 letters"

    def test_values_are_3letter(self):
        for key, value in iso2_iso3_dict.items():
            assert len(value) == 3, f"Value '{value}' for key '{key}' is not 3 letters"

    def test_known_mappings(self):
        assert iso2_iso3_dict["fr"] == "fra"
        assert iso2_iso3_dict["us"] == "usa"
        assert iso2_iso3_dict["de"] == "deu"
        assert iso2_iso3_dict["gb"] == "gbr"
        assert iso2_iso3_dict["jp"] == "jpn"

    def test_values_are_valid_iso3(self):
        for value in iso2_iso3_dict.values():
            assert value in iso_codes, f"ISO3 code '{value}' not found in iso_codes"
