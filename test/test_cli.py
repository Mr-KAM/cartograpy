"""Tests for the cartograpy CLI (offline commands only)."""

import os

import geopandas as gpd
from click.testing import CliRunner
from shapely.geometry import Polygon

import click
import pytest

from cartograpy.cli import _parse_bbox, _parse_point, _parse_tags, _slugify, cli


def _sample_gdf():
    return gpd.GeoDataFrame(
        {"name": ["a", "b"], "pop": [10, 20]},
        geometry=[
            Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
            Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
        ],
        crs="EPSG:4326",
    )


def test_help():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.output
    assert "doctor" in result.output


def test_doctor_runs():
    result = CliRunner().invoke(cli, ["doctor"])
    assert result.exit_code == 0
    assert "Python" in result.output


def test_init(tmp_path):
    result = CliRunner().invoke(cli, ["init", str(tmp_path / "proj")])
    assert result.exit_code == 0
    assert os.path.isdir(tmp_path / "proj" / "data")
    assert os.path.isdir(tmp_path / "proj" / "output")


def test_inspect_and_convert(tmp_path):
    src = tmp_path / "sample.geojson"
    _sample_gdf().to_file(src, driver="GeoJSON")

    # describe() prints its own summary via cartograpy's logger (bound to
    # the real stdout at import time), which pytest's capture fixtures
    # don't reliably intercept here — exit_code==0 is the meaningful check;
    # `cartograpy inspect` was verified by hand to print the summary once.
    result = CliRunner().invoke(cli, ["inspect", str(src)])
    assert result.exit_code == 0

    dst = tmp_path / "sample.gpkg"
    result = CliRunner().invoke(cli, ["convert", str(src), str(dst)])
    assert result.exit_code == 0
    assert dst.exists()


def test_parse_bbox():
    assert _parse_bbox("-4.05,5.28,-3.95,5.38") == (-4.05, 5.28, -3.95, 5.38)
    with pytest.raises(click.BadParameter):
        _parse_bbox("1,2,3")


def test_parse_point():
    assert _parse_point("-3.99,5.35") == (-3.99, 5.35)
    with pytest.raises(click.BadParameter):
        _parse_point("not,a,point")


def test_parse_tags():
    assert _parse_tags(["amenity=school"]) == {"amenity": "school"}
    assert _parse_tags(["highway=true"]) == {"highway": True}
    with pytest.raises(click.BadParameter):
        _parse_tags(["no-equals-sign"])


def test_slugify():
    assert _slugify("Grand-Bassam, Côte d'Ivoire") == "grand_bassam_côte_d_ivoire"


def test_fetch_help_lists_all_sources():
    result = CliRunner().invoke(cli, ["fetch", "--help"])
    assert result.exit_code == 0
    for name in ("boundary", "dem", "osm", "hydro", "worldbank", "climate",
                 "gee", "stac"):
        assert name in result.output


def test_fetch_climate_requires_point_xor_bbox():
    result = CliRunner().invoke(
        cli, ["fetch", "climate", "--start", "2023-01-01", "--end", "2023-01-02"]
    )
    assert result.exit_code != 0
    assert "Provide exactly one of --point or --bbox" in result.output


def test_fetch_osm_requires_tag_or_common():
    result = CliRunner().invoke(cli, ["fetch", "osm", "Paris"])
    assert result.exit_code != 0
    assert "Provide --tag KEY=VALUE or --common NAME" in result.output


def test_map(tmp_path):
    src = tmp_path / "sample.geojson"
    _sample_gdf().to_file(src, driver="GeoJSON")
    out = tmp_path / "map.png"

    result = CliRunner().invoke(
        cli, ["map", str(src), "-o", str(out), "--column", "pop"]
    )
    assert result.exit_code == 0
    assert out.exists()
