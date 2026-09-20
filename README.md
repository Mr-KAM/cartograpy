<img src="https://raw.githubusercontent.com/Mr-KAM/cartograpy/master/assets/img/logo.png" alt="cartograpy logo" width="220">

# cartograpy

[![PyPI](https://img.shields.io/pypi/v/cartograpy.svg)](https://pypi.org/project/cartograpy/)
[![Python](https://img.shields.io/pypi/pyversions/cartograpy.svg)](https://pypi.org/project/cartograpy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/Mr-KAM/cartograpy/blob/master/LICENSE)
[![Docs](https://img.shields.io/badge/docs-mr--kam.github.io-blue.svg)](https://mr-kam.github.io/cartograpy/)

**Mapping in Python, the way it was always meant to be.**

Cartograpy is a Python package for loading, processing, and mapping
geographic data in a few lines of code: from a country's administrative
boundaries to the final static map, ready to export, anywhere in the world.

![Example map produced with cartograpy](https://raw.githubusercontent.com/Mr-KAM/cartograpy/master/assets/img/create_python_maps.py.png)

## Features

- **Data**: download administrative boundaries (`GeoBoundaries`),
  OpenStreetMap data, hydrography, geocoding, elevation (SRTM), World Bank
  indicators, weather/climate series (NASA POWER), or Google Earth Engine
  imagery in one line; results returned as `GeoDataFrame`/`DataFrame`.
- **Processing**: import/export all common formats (Shapefile, GeoJSON, KML,
  GPX, GPKG, CSV, Parquet…), reproject, clip, merge, compute centroids,
  joins, and dynamic attributes (`VectorTools`, `RasterTools`).
- **Mapping**: choropleth, point, polygon, raster, bivariate, or hexbin maps
  with the `Map` class: north arrow, scale bar, situation inset map,
  legends, graticule, PNG/SVG export.
- **Styling**: Google Fonts, 16 built-in palettes + seaborn/matplotlib,
  graphic styles (`scienceplots`, `mplcyberpunk`).
- **Project**: `Project` structures folders and outputs, tracks the CRS,
  and validates dataset integrity.

## Installation

```bash
pip install cartograpy
```

> [!NOTE]
> Python 3.11+. Use a virtual environment to avoid dependency conflicts
> (`venv`, `conda`, `uv`…). On Windows, if the GDAL/GEOS/PROJ installation
> fails, install `geopandas rasterio cartopy fiona` via `conda-forge` before
> `pip install cartograpy`.

## How it works

![Flow: sources → data → processing → mapper → final map](https://mermaid.ink/svg/Zmxvd2NoYXJ0IExSCiAgICBTWyJTb3VyY2VzPGJyLz5sb2NhbCBmaWxlcyDCtyBHZW9Cb3VuZGFyaWVzIMK3IE9TTTxici8-SHlkcm8gwrcgU1JUTSDCtyBXb3JsZCBCYW5rIMK3IEdFRSJdIC0tPiBEWyJjYXJ0b2dyYXB5LmRhdGEiXQogICAgRCAtLT58Ikdlb0RhdGFGcmFtZSAvIERhdGFGcmFtZSJ8IFBbImNhcnRvZ3JhcHkucHJvY2Vzc2luZyJdCiAgICBQIC0tPiBNWyJjYXJ0b2dyYXB5Lm1hcHBlciJdCiAgICBTVFsiY2FydG9ncmFweS5zdHlsaW5nIl0gLS4tPiBNCiAgICBNIC0tPiBPWyJGaW5hbCBtYXA8YnIvPlBORyDCtyBTVkcgwrcgSFRNTCJd)

<details><summary>Mermaid diagram source</summary>

```mermaid
flowchart LR
    S["Sources<br/>local files · GeoBoundaries · OSM<br/>Hydro · SRTM · World Bank · GEE"] --> D["cartograpy.data"]
    D -->|"GeoDataFrame / DataFrame"| P["cartograpy.processing"]
    P --> M["cartograpy.mapper"]
    ST["cartograpy.styling"] -.-> M
    M --> O["Final map<br/>PNG · SVG · HTML"]
```

</details>

## Quick start

```python
from cartograpy.data import Bound
from cartograpy.mapper import Map

bound = Bound()
civ = bound.get_admin("CIV", adm=0)          # national boundaries, via GeoBoundaries

m = Map(title="Côte d'Ivoire")
m.add_polygons(civ, facecolor="lightyellow", edge_color="black", alpha=1)
m.add_north_arrow()
m.add_scale_bar()
m.show()

m.save("cote-divoire.png", dpi=300)          # print-ready export
```

## The modules

![The modules: data, processing, mapper, styling, project](https://mermaid.ink/svg/Z3JhcGggVEQKICAgIEFbImNhcnRvZ3JhcHkiXSAtLT4gRFsiZGF0YTxici8-PGk-bG9hZC9zYXZlLCBvbmxpbmUgc291cmNlczwvaT4iXQogICAgQSAtLT4gUFsicHJvY2Vzc2luZzxici8-PGk-dmVjdG9yIGFuZCByYXN0ZXIgcHJvY2Vzc2luZzwvaT4iXQogICAgQSAtLT4gTVsibWFwcGVyPGJyLz48aT5zdGF0aWMgYW5kIHdlYiBtYXAgcmVuZGVyaW5nPC9pPiJdCiAgICBBIC0tPiBTWyJzdHlsaW5nPGJyLz48aT5mb250cywgcGFsZXR0ZXMsIGdyYXBoaWMgc3R5bGVzPC9pPiJdCiAgICBBIC0tPiBQUlsicHJvamVjdDxici8-PGk-Y2FydG9ncmFwaGljIHByb2plY3Qgb3JnYW5pemF0aW9uPC9pPiJd)

<details><summary>Mermaid diagram source</summary>

```mermaid
graph TD
    A["cartograpy"] --> D["data<br/><i>load/save, online sources</i>"]
    A --> P["processing<br/><i>vector and raster processing</i>"]
    A --> M["mapper<br/><i>static and web map rendering</i>"]
    A --> S["styling<br/><i>fonts, palettes, graphic styles</i>"]
    A --> PR["project<br/><i>cartographic project organization</i>"]
```

</details>

Everything is importable from the root (`from cartograpy import Map, Bound,
Project`) or from each submodule.

## Going further

Full documentation (API reference, step-by-step guides, gallery) is
available at **[mr-kam.github.io/cartograpy](https://mr-kam.github.io/cartograpy/)**.

For an interactive tour of all the features, see the notebook
[`notebooks/README.ipynb`](https://github.com/Mr-KAM/cartograpy/blob/master/notebooks/README.ipynb).

## License

MIT: see [`LICENSE`](https://github.com/Mr-KAM/cartograpy/blob/master/LICENSE).
