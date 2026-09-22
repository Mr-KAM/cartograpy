"""Command-line interface for cartograpy (``cartograpy`` entry point)."""

import os
import re
import sys
import importlib.metadata as _im

import click

from cartograpy import __version__


def _split_output(output):
    """Splits 'path/name.ext' into ('path/name', 'ext')."""
    root, ext = os.path.splitext(output)
    return root, ext.lstrip(".").lower()


def _save(data, output):
    from cartograpy.data import save

    root, ext = _split_output(output)
    return save(data, ext, filename=root)


def _slugify(text):
    return re.sub(r"\W+", "_", text.lower()).strip("_")


def _parse_bbox(value):
    parts = value.split(",")
    if len(parts) != 4:
        raise click.BadParameter("expected 'xmin,ymin,xmax,ymax'")
    try:
        return tuple(float(p) for p in parts)
    except ValueError:
        raise click.BadParameter("expected 'xmin,ymin,xmax,ymax' (numbers)")


def _parse_point(value):
    parts = value.split(",")
    if len(parts) != 2:
        raise click.BadParameter("expected 'lon,lat'")
    try:
        return tuple(float(p) for p in parts)
    except ValueError:
        raise click.BadParameter("expected 'lon,lat' (numbers)")


def _parse_tags(tag_options):
    tags = {}
    for item in tag_options:
        if "=" not in item:
            raise click.BadParameter(f"--tag must be KEY=VALUE, got '{item}'")
        key, value = item.split("=", 1)
        tags[key] = True if value.lower() in ("true", "*") else value
    return tags


@click.group()
@click.version_option(__version__, prog_name="cartograpy")
def cli():
    """cartograpy: cartography and geospatial data toolkit."""


@cli.command()
@click.argument("path", required=False, default=None)
def init(path):
    """Initializes a new project (data/ and output/ folders)."""
    from cartograpy.project import Project

    project = Project(path)
    result = project.init()
    click.echo(f"OK: project initialized -> {result}")


@cli.group()
def fetch():
    """Downloads data from an online source."""


@fetch.command("boundary")
@click.argument("territory")
@click.option("--adm", default="0", show_default=True,
              help="Administrative level (0-5, or -1 for the finest level).")
@click.option("--simplified/--no-simplified", default=True,
              help="Use simplified geometry (faster, smaller file).")
@click.option("-o", "--output", default=None,
              help="Output file (default: <territory>_adm<adm>.gpkg).")
def fetch_boundary(territory, adm, simplified, output):
    """Downloads administrative boundaries for TERRITORY (GeoBoundaries)."""
    from cartograpy.data import Bound

    try:
        adm_level = int(adm)
    except ValueError:
        adm_level = adm

    gdf = Bound().get_admin(territory, adm_level, simplified=simplified)
    output = output or f"{territory.lower()}_adm{adm}.gpkg"
    path = _save(gdf, output)
    click.echo(f"OK: {len(gdf)} feature(s) -> {path}")


@fetch.command("dem")
@click.argument("territory")
@click.option("-o", "--output", default=None,
              help="Output GeoTIFF (default: <territory>_dem.tif).")
def fetch_dem(territory, output):
    """Downloads an SRTM DEM covering TERRITORY's bounding box."""
    from cartograpy.data import Bound, DEM

    bbox = Bound().get_bbox(territory)
    output = output or f"{territory.lower()}_dem.tif"
    path = DEM().download(bbox, output)
    click.echo(f"OK: DEM -> {path}")


@fetch.command("osm")
@click.argument("place")
@click.option("--tag", "tags", multiple=True,
              help="OSM tag filter KEY=VALUE (repeatable, e.g. --tag amenity=school).")
@click.option("--common", default=None,
              help="Shortcut tag combo from OSM.get_common_tag() (e.g. 'schools').")
@click.option("--data-type", default="all",
              type=click.Choice(["points", "polygons", "lines", "all"]))
@click.option("-o", "--output", default=None,
              help="Output file (default: osm_<place>.gpkg).")
def fetch_osm(place, tags, common, data_type, output):
    """Downloads OSM features matching tags for PLACE (a place name)."""
    from cartograpy.data import OSM

    osm = OSM()
    if common:
        tag_dict = osm.get_common_tag()[common]
    elif tags:
        tag_dict = _parse_tags(tags)
    else:
        raise click.UsageError("Provide --tag KEY=VALUE or --common NAME.")

    gdf = osm.get_data(place, tag_dict, data_type=data_type)
    output = output or f"osm_{_slugify(place)}.gpkg"
    path = _save(gdf, output)
    click.echo(f"OK: {len(gdf)} feature(s) -> {path}")


@fetch.command("hydro")
@click.argument("region")
@click.option("-o", "--output", default=None,
              help="Output file (default: hydro_<region>.gpkg).")
def fetch_hydro(region, output):
    """Downloads HydroRIVERS data for REGION (af, as, au, eu, na, sa)."""
    from cartograpy.data import Hydro

    gdf = Hydro().download(region)
    output = output or f"hydro_{region.lower()}.gpkg"
    path = _save(gdf, output)
    click.echo(f"OK: {len(gdf)} feature(s) -> {path}")


@fetch.command("worldbank")
@click.option("-i", "--indicator", "indicators", multiple=True, required=True,
              help="World Bank indicator code (repeatable), e.g. SP.POP.TOTL.")
@click.option("-c", "--country", "countries", multiple=True, default=("all",),
              show_default=True, help="ISO3 country code (repeatable).")
@click.option("-o", "--output", default="worldbank.csv", show_default=True)
def fetch_worldbank(indicators, countries, output):
    """Downloads World Bank indicator series."""
    from cartograpy.data import WorldBank

    country_arg = list(countries) if countries != ("all",) else "all"
    df = WorldBank().get_data({code: code for code in indicators}, country=country_arg)
    df = df.reset_index()
    path = _save(df, output)
    click.echo(f"OK: {len(df)} row(s) -> {path}")


@fetch.command("climate")
@click.option("--point", default=None, help="Single point 'lon,lat' (point mode).")
@click.option("--bbox", default=None, help="Bounding box 'xmin,ymin,xmax,ymax' (regional mode).")
@click.option("--start", required=True, help="Start date (or year for monthly/climatology).")
@click.option("--end", required=True, help="End date (or year for monthly/climatology).")
@click.option("--parameter", "parameters", multiple=True,
              help="NASA POWER parameter code (repeatable, default: Climate.DEFAULT_PARAMETERS).")
@click.option("--community", default="ag", show_default=True,
              type=click.Choice(["ag", "sb", "re"]))
@click.option("--temporal", default="daily", show_default=True,
              type=click.Choice(["daily", "hourly", "monthly", "climatology"]))
@click.option("-o", "--output", default="climate.gpkg", show_default=True)
def fetch_climate(point, bbox, start, end, parameters, community, temporal, output):
    """Downloads NASA POWER weather/climate series for a point or a region."""
    from cartograpy.data import Climate

    if bool(point) == bool(bbox):
        raise click.UsageError("Provide exactly one of --point or --bbox.")

    clim = Climate()
    params = list(parameters) or None
    if point:
        lon, lat = _parse_point(point)
        gdf = clim.get_point(lon, lat, start, end, parameters=params,
                              community=community, temporal=temporal)
    else:
        gdf = clim.get_region(_parse_bbox(bbox), start, end, parameters=params,
                               community=community, temporal=temporal)

    path = _save(gdf.reset_index(), output)
    click.echo(f"OK: {len(gdf)} row(s) -> {path}")


@fetch.command("gee")
@click.argument("collection", type=click.Choice(["sentinel2", "landsat9"]))
@click.option("--bbox", required=True, help="Bounding box 'xmin,ymin,xmax,ymax'.")
@click.option("--start", required=True, help="Start date YYYY-MM-DD.")
@click.option("--end", required=True, help="End date YYYY-MM-DD.")
@click.option("--cloud", default=0.2, show_default=True, help="Max cloud cover fraction (0-1).")
@click.option("--scale", default=None, type=int,
              help="Resolution in meters (default: 10 for sentinel2, 30 for landsat9).")
@click.option("-o", "--output", default=None,
              help="Output GeoTIFF (default: <collection>.tif).")
def fetch_gee(collection, bbox, start, end, cloud, scale, output):
    """Downloads a cloud-free Sentinel-2/Landsat-9 median mosaic (Google Earth Engine)."""
    from cartograpy.data import Gee

    gee = Gee()
    bbox_t = _parse_bbox(bbox)
    getter = gee.get_sentinel2 if collection == "sentinel2" else gee.get_landsat9
    image = getter(bbox_t, start, end, cloud=cloud)
    scale = scale or (10 if collection == "sentinel2" else 30)
    output = output or f"{collection}.tif"
    path = gee.download(image, bbox=bbox_t, filename=os.path.basename(output),
                         scale=scale, output_dir=os.path.dirname(output) or ".")
    click.echo(f"OK: {collection} -> {path}")


@fetch.command("stac")
@click.argument("collection")
@click.option("--bbox", required=True, help="Bounding box 'xmin,ymin,xmax,ymax'.")
@click.option("--start", required=True, help="Start date YYYY-MM-DD.")
@click.option("--end", required=True, help="End date YYYY-MM-DD.")
@click.option("--catalog", default="planetary-computer", show_default=True,
              help="STAC.CATALOGS key or a direct STAC API URL.")
@click.option("--cloud-cover", "cloud_cover", type=float, default=None,
              help="Maximum cloud cover percentage (0-100).")
@click.option("--band", "bands", multiple=True, required=True,
              help="Band to load: asset key or eo common_name (repeatable).")
@click.option("-o", "--output", default=None,
              help="Output GeoTIFF (default: <collection>.tif).")
def fetch_stac(collection, bbox, start, end, catalog, cloud_cover, bands, output):
    """Searches a STAC catalog and downloads the least-cloudy match's bands."""
    from cartograpy.data import STAC

    stac = STAC(catalog)
    results = stac.search(collection, _parse_bbox(bbox), start, end, cloud_cover=cloud_cover)
    if not len(results):
        raise click.ClickException("No STAC item found for this query.")

    rt = results.best().load(list(bands))
    output = output or f"{collection}.tif"
    path = rt.export_geotiff(output)
    click.echo(f"OK: {collection} -> {path}")


@cli.command()
@click.argument("path")
def inspect(path):
    """Prints metadata (layers, CRS, bounds...) for a geospatial file."""
    from cartograpy.data import describe

    describe(path)  # already prints a formatted summary as a side effect


@cli.command()
@click.argument("src")
@click.argument("dst")
def convert(src, dst):
    """Converts SRC to DST, format inferred from DST's extension."""
    from cartograpy.data import load

    data = load(src)
    path = _save(data, dst)
    click.echo(f"OK: {src} -> {path}")


@cli.command("map")
@click.argument("src")
@click.option("-o", "--output", default="map.png", show_default=True)
@click.option("--column", default=None, help="Column for a choropleth map.")
@click.option("--title", default="")
def map_(src, output, column, title):
    """Renders a quick static map from a vector or raster file."""
    from cartograpy.mapper import Map

    m = Map(title=title)
    m.add_layer(src, style={"column": column} if column else {})
    m.save(output)
    click.echo(f"OK: map -> {output}")


@cli.command()
def doctor():
    """Checks the GIS environment (GDAL/PROJ/GEOS, core and optional deps)."""

    def ok(label):
        click.secho(f"[OK] {label}", fg="green")

    def warn(label):
        click.secho(f"[!] {label}", fg="yellow")

    def fail(label):
        click.secho(f"[FAIL] {label}", fg="red")

    click.echo(f"Cartograpy {__version__}\n")
    ok(f"Python {sys.version.split()[0]}")

    try:
        import rasterio
        ok(f"GDAL {rasterio.__gdal_version__}")
    except Exception:
        fail("GDAL")

    try:
        import pyproj
        ok(f"PROJ {pyproj.proj_version_str}")
    except Exception:
        fail("PROJ")

    try:
        import shapely
        ok(f"GEOS {shapely.geos_version_string}")
    except Exception:
        fail("GEOS")

    for pkg in ("rasterio", "geopandas", "cartopy", "fiona"):
        try:
            ok(f"{pkg} {_im.version(pkg)}")
        except _im.PackageNotFoundError:
            fail(f"{pkg} not installed")

    for pkg in ("folium", "lonboard", "keplergl", "rio-tiler"):
        try:
            ok(f"{pkg} {_im.version(pkg)}")
        except _im.PackageNotFoundError:
            warn(f"{pkg} not installed (pip install cartograpy[webmap])")

    try:
        from ee.oauth import get_credentials_path

        if os.path.exists(get_credentials_path()):
            ok("earthengine-api authenticated")
        else:
            warn("earthengine-api authentication missing (ee.Authenticate())")
    except ImportError:
        warn("earthengine-api not installed (pip install earthengine-api)")


if __name__ == "__main__":
    cli()
