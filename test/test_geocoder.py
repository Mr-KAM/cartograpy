"""Tests pour le module geocoder."""

import pytest
from unittest.mock import patch, MagicMock
from cartograpy.geocoder import (
    GeocodingResult,
    GeocodingProvider,
    NominatimProvider,
)


class TestGeocodingResult:
    """Tests de la dataclass GeocodingResult."""

    def test_creation_minimal(self):
        result = GeocodingResult(query="Paris")
        assert result.query == "Paris"
        assert result.latitude is None
        assert result.longitude is None

    def test_creation_full(self):
        result = GeocodingResult(
            query="Paris",
            latitude=48.8566,
            longitude=2.3522,
            display_name="Paris, France",
            confidence=0.9,
        )
        assert result.latitude == 48.8566
        assert result.longitude == 2.3522
        assert result.display_name == "Paris, France"

    def test_coordinates_property_valid(self):
        result = GeocodingResult(query="Paris", latitude=48.8566, longitude=2.3522)
        assert result.coordinates == (48.8566, 2.3522)

    def test_coordinates_property_none(self):
        result = GeocodingResult(query="Paris")
        assert result.coordinates is None

    def test_coordinates_property_partial(self):
        result = GeocodingResult(query="Paris", latitude=48.8566)
        assert result.coordinates is None

    def test_is_valid_true(self):
        result = GeocodingResult(query="Paris", latitude=48.8566, longitude=2.3522)
        assert result.is_valid is True

    def test_is_valid_false_error(self):
        result = GeocodingResult(query="Paris", error="Not found")
        assert result.is_valid is False

    def test_is_valid_false_no_coords(self):
        result = GeocodingResult(query="Paris")
        assert result.is_valid is False

    def test_bbox_field(self):
        result = GeocodingResult(
            query="Paris",
            latitude=48.8566,
            longitude=2.3522,
            bbox=[48.8, 2.2, 48.9, 2.4],
        )
        assert result.bbox == [48.8, 2.2, 48.9, 2.4]

    def test_error_field(self):
        result = GeocodingResult(query="xyz", error="Not found")
        assert result.error == "Not found"


class TestGeocodingProvider:
    """Tests que GeocodingProvider est bien une ABC."""

    def test_is_abstract(self):
        with pytest.raises(TypeError):
            GeocodingProvider()

    def test_has_geocode_method(self):
        assert hasattr(GeocodingProvider, "geocode")

    def test_has_reverse_geocode_method(self):
        assert hasattr(GeocodingProvider, "reverse_geocode")


class TestNominatimProvider:
    """Tests du NominatimProvider (avec mocks pour les appels réseau)."""

    def test_instantiation(self):
        provider = NominatimProvider()
        assert provider.base_url == "https://nominatim.openstreetmap.org"
        assert provider.timeout == 10

    def test_custom_user_agent(self):
        provider = NominatimProvider(user_agent="TestAgent/1.0")
        assert provider.user_agent == "TestAgent/1.0"

    def test_custom_timeout(self):
        provider = NominatimProvider(timeout=30)
        assert provider.timeout == 30

    def test_geocode_success_mocked(self):
        provider = NominatimProvider()
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "lat": "48.8566",
                "lon": "2.3522",
                "display_name": "Paris, Île-de-France, France",
                "address": {"city": "Paris", "country": "France"},
                "importance": 0.9,
                "place_id": "12345",
                "boundingbox": ["48.8", "48.9", "2.2", "2.4"],
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.session, "get", return_value=mock_response):
            result = provider.geocode("Paris")
            assert result.is_valid
            assert result.latitude == 48.8566
            assert result.longitude == 2.3522
            assert "Paris" in result.display_name

    def test_geocode_no_results_mocked(self):
        provider = NominatimProvider()
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.session, "get", return_value=mock_response):
            result = provider.geocode("xyznonexistent")
            assert not result.is_valid
            assert result.error is not None

    def test_geocode_network_error_mocked(self):
        provider = NominatimProvider()

        with patch.object(
            provider.session, "get", side_effect=Exception("Connection error")
        ):
            result = provider.geocode("Paris")
            assert not result.is_valid
            assert "Erreur" in result.error

    def test_reverse_geocode_success_mocked(self):
        provider = NominatimProvider()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "lat": "48.8566",
            "lon": "2.3522",
            "display_name": "Paris, France",
            "address": {"city": "Paris"},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(provider.session, "get", return_value=mock_response):
            result = provider.reverse_geocode(48.8566, 2.3522)
            assert result.is_valid
            assert "Paris" in result.display_name

    def test_is_subclass_of_provider(self):
        assert issubclass(NominatimProvider, GeocodingProvider)
