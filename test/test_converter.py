"""Tests pour le module converter."""

import os
import json
import pytest
import tempfile
from cartograpy.converter import converter, extract_gpx_data


SAMPLE_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test">
  <wpt lat="48.8566" lon="2.3522">
    <name>Paris</name>
    <ele>35.0</ele>
  </wpt>
  <wpt lat="45.764" lon="4.8357">
    <name>Lyon</name>
    <ele>170.0</ele>
  </wpt>
  <trk>
    <name>Track 1</name>
    <trkseg>
      <trkpt lat="48.8566" lon="2.3522">
        <ele>35.0</ele>
      </trkpt>
      <trkpt lat="48.8600" lon="2.3400">
        <ele>40.0</ele>
      </trkpt>
    </trkseg>
  </trk>
</gpx>"""

SAMPLE_GEOJSON = json.dumps({
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [2.3522, 48.8566]},
            "properties": {"name": "Paris", "elevation": 35.0},
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[2.3522, 48.8566], [2.34, 48.86]],
            },
            "properties": {"name": "Route"},
        },
    ],
})


@pytest.fixture
def gpx_file(tmp_path):
    path = tmp_path / "test.gpx"
    path.write_text(SAMPLE_GPX, encoding="utf-8")
    return str(path)


@pytest.fixture
def geojson_file(tmp_path):
    path = tmp_path / "test.geojson"
    path.write_text(SAMPLE_GEOJSON, encoding="utf-8")
    return str(path)


class TestExtractGpxData:
    """Tests de la fonction extract_gpx_data."""

    def test_returns_dict(self, gpx_file):
        result = extract_gpx_data(gpx_file)
        assert isinstance(result, dict)

    def test_has_tracks_and_waypoints(self, gpx_file):
        result = extract_gpx_data(gpx_file)
        assert "tracks" in result
        assert "waypoints" in result

    def test_waypoints_extracted(self, gpx_file):
        result = extract_gpx_data(gpx_file)
        assert len(result["waypoints"]) == 2
        paris = result["waypoints"][0]
        assert paris["name"] == "Paris"
        assert paris["latitude"] == 48.8566
        assert paris["longitude"] == 2.3522
        assert paris["elevation"] == 35.0

    def test_tracks_extracted(self, gpx_file):
        result = extract_gpx_data(gpx_file)
        assert len(result["tracks"]) == 1
        track = result["tracks"][0]
        assert track["name"] == "Track 1"
        assert len(track["segments"]) == 1
        assert len(track["segments"][0]) == 2

    def test_invalid_file_returns_none(self, tmp_path):
        path = tmp_path / "invalid.gpx"
        path.write_text("not xml", encoding="utf-8")
        result = extract_gpx_data(str(path))
        assert result is None

    def test_nonexistent_file_returns_none(self):
        result = extract_gpx_data("/nonexistent/path/file.gpx")
        assert result is None


class TestConverterGpx:
    """Tests de la classe converter avec GPX."""

    def test_init_parses_gpx(self, gpx_file):
        conv = converter(gpx_file)
        assert len(conv.waypoints) == 2
        assert len(conv.tracks) == 1

    def test_waypoint_data(self, gpx_file):
        conv = converter(gpx_file)
        paris = conv.waypoints[0]
        assert paris["name"] == "Paris"
        assert paris["latitude"] == 48.8566

    def test_track_data(self, gpx_file):
        conv = converter(gpx_file)
        track = conv.tracks[0]
        assert track["name"] == "Track 1"

    def test_to_geojson(self, gpx_file):
        conv = converter(gpx_file)
        geojson_data = conv.to_geojson()
        assert geojson_data["type"] == "FeatureCollection"
        assert len(geojson_data["features"]) > 0


class TestConverterGeoJson:
    """Tests de la classe converter avec GeoJSON."""

    def test_init_parses_geojson(self, geojson_file):
        conv = converter(geojson_file)
        assert len(conv.waypoints) == 1
        assert len(conv.tracks) == 1

    def test_waypoint_from_geojson(self, geojson_file):
        conv = converter(geojson_file)
        paris = conv.waypoints[0]
        assert paris["name"] == "Paris"
        assert paris["latitude"] == 48.8566
        assert paris["longitude"] == 2.3522

    def test_to_geojson_roundtrip(self, geojson_file):
        conv = converter(geojson_file)
        result = conv.to_geojson()
        assert result["type"] == "FeatureCollection"


class TestConverterUnsupported:
    """Tests avec format non supporté."""

    def test_unsupported_format(self, tmp_path):
        path = tmp_path / "test.xyz"
        path.write_text("data", encoding="utf-8")
        conv = converter(str(path))
        assert conv.waypoints == []
        assert conv.tracks == []
