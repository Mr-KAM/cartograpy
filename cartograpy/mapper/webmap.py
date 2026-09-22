"""cartograpy.mapper.webmap — interactive web maps.

Defaults to Folium/Leaflet (fully supported). Two optional GPU-accelerated
backends are available for datasets too large for a Leaflet DOM map:
`engine="lonboard"` (deck.gl/GeoArrow) and `engine="kepler.gl"`. Not every
method is meaningful on every engine — a method unsupported by the current
engine raises a clear `NotImplementedError` rather than silently doing
nothing.
"""
import json
import logging
from importlib import import_module

import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)

ENGINES = ("folium", "lonboard", "kepler.gl")


def _require(module_name, package_name=None):
    """Imports an optional dependency with an explicit error message."""
    try:
        return import_module(module_name)
    except ImportError as e:
        install_name = package_name or module_name
        raise ImportError(
            f"Cette fonctionnalité nécessite le paquet optionnel '{install_name}'. "
            f"Installez-le avec: pip install {install_name}"
        ) from e


def _to_wgs84(gdf):
    return gdf.to_crs(epsg=4326) if gdf.crs and gdf.crs.to_epsg() != 4326 else gdf


def _resolve_branca_colormap(name):
    """Resolves a friendly color name (e.g. 'YlOrRd', 'viridis') to a
    branca.colormap.linear entry, trying a ColorBrewer 9-class suffix
    when the plain name doesn't exist (branca stores most ColorBrewer
    palettes as e.g. 'YlOrRd_09', not 'YlOrRd')."""
    import branca.colormap as bcm

    if hasattr(bcm.linear, name):
        return getattr(bcm.linear, name)
    candidate = f"{name}_09"
    if hasattr(bcm.linear, candidate):
        return getattr(bcm.linear, candidate)
    available = sorted(n for n in dir(bcm.linear) if not n.startswith("_"))
    raise ValueError(
        f"cmap '{name}' inconnu. Essayez un nom de branca.colormap.linear "
        f"(ex: {', '.join(available[:12])}, ...)"
    )


class WebMap:
    """
    Interactive map, backed by Folium/Leaflet by default, with optional
    GPU-accelerated backends for large datasets.

    Parameters:
    -----------
    engine : str
        "folium" (default, full feature set), "lonboard" (deck.gl/GeoArrow,
        GPU-rendered, best for large point/polygon datasets), or
        "kepler.gl" (deck.gl-based studio with its own built-in UI).
    location : tuple
        Initial center (latitude, longitude).
    zoom_start : int
        Initial zoom level.
    tiles : str
        Basemap (e.g. 'OpenStreetMap', 'CartoDB positron'). Folium only.
    width, height : str
        Map size ('100%' or pixels / '600px').

    Example:
    --------
    >>> wm = WebMap(location=(5.35, -4.0), zoom_start=7)
    >>> wm.add_layer(gdf, column="population", cmap="YlOrRd")
    >>> wm.add_legend({"Low": "green", "High": "red"})
    >>> wm.show()

    >>> # Millions of features: render on the GPU via deck.gl instead.
    >>> wm = WebMap(engine="lonboard")
    >>> wm.add_layer(huge_gdf)
    >>> wm.save("big_map.html")
    """

    def __init__(
        self,
        engine="folium",
        location=(0, 0),
        zoom_start=6,
        tiles="OpenStreetMap",
        width="100%",
        height="600px",
    ):
        if engine not in ENGINES:
            raise ValueError(f"engine doit être parmi {ENGINES}, reçu: {engine!r}")
        self.engine = engine
        self._init_kwargs = dict(location=location, zoom_start=zoom_start, tiles=tiles)
        self._width, self._height = width, height

        if engine == "folium":
            folium = _require("folium")
            self._folium = folium
            self.map = folium.Map(
                location=location, zoom_start=zoom_start, tiles=tiles,
                width=width, height=height,
            )
        elif engine == "lonboard":
            self._lonboard = _require("lonboard")
            self.map = self._lonboard.Map(layers=[])
        elif engine == "kepler.gl":
            keplergl = _require("keplergl")
            self._keplergl = keplergl
            self.map = keplergl.KeplerGl(height=self._height_px())

    def _height_px(self):
        h = str(self._height)
        return int(h.replace("px", "")) if h.replace("px", "").isdigit() else 600

    def _require_engine(self, feature, *supported):
        if self.engine not in supported:
            hint = ""
            if self.engine == "kepler.gl" and feature in ("time_slider",):
                hint = (
                    " kepler.gl détecte nativement les colonnes temporelles "
                    "via add_layer(); passez-y directement vos données."
                )
            elif self.engine != "folium" and feature == "add_cluster":
                hint = (
                    " un moteur GPU affiche directement tous les points, "
                    "le clustering n'est pas nécessaire."
                )
            raise NotImplementedError(
                f"{feature} n'est pas disponible avec engine={self.engine!r} "
                f"(supporté par: {', '.join(supported)}).{hint}"
            )

    # ------------------------------------------------------------------ #
    # Vector data                                                        #
    # ------------------------------------------------------------------ #

    def add_layer(self, gdf, column=None, cmap="YlOrRd",
                  style_function=None, tooltip_columns=None,
                  popup_columns=None, name=None, **kwargs):
        """
        Adds a GeoDataFrame as a vector layer.

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            Geographic data.
        column : str, optional
            Column used for choropleth coloring (folium only).
        cmap : str
            Color palette name (branca.colormap.linear, e.g. "YlOrRd", "viridis").
        style_function : callable, optional
            Folium style function.
        tooltip_columns, popup_columns : list, optional
            Columns shown on hover / click (folium only).
        name : str, optional
            Layer name.
        **kwargs :
            Folium: forwarded to nothing extra. lonboard: forwarded to
            `lonboard.viz()`. kepler.gl: forwarded to `add_data()`.
        """
        gdf_wgs84 = _to_wgs84(gdf)

        if self.engine == "folium":
            return self._add_layer_folium(
                gdf_wgs84, column, cmap, style_function,
                tooltip_columns, popup_columns, name,
            )
        if self.engine == "lonboard":
            return self._add_layer_lonboard(gdf_wgs84, column, cmap, name, **kwargs)
        if self.engine == "kepler.gl":
            self.map.add_data(data=gdf_wgs84, name=name or "layer")
            return self

    def _add_layer_folium(self, gdf_wgs84, column, cmap, style_function,
                           tooltip_columns, popup_columns, name):
        if column and column in gdf_wgs84.columns:
            vmin, vmax = gdf_wgs84[column].min(), gdf_wgs84[column].max()
            colormap = _resolve_branca_colormap(cmap).scale(vmin, vmax)
            colormap.caption = column

            def _style(feature):
                val = feature["properties"].get(column, vmin)
                return {
                    "fillColor": colormap(val) if val is not None else "gray",
                    "color": "black", "weight": 0.5, "fillOpacity": 0.7,
                }

            layer = self._folium.GeoJson(
                gdf_wgs84.__geo_interface__,
                style_function=style_function or _style,
                name=name or column,
            )
            colormap.add_to(self.map)
        else:
            default_style = {
                "fillColor": "steelblue", "color": "black",
                "weight": 0.5, "fillOpacity": 0.6,
            }
            layer = self._folium.GeoJson(
                gdf_wgs84.__geo_interface__,
                style_function=style_function or (lambda f: default_style),
                name=name or "layer",
            )

        if tooltip_columns:
            layer.add_child(self._folium.GeoJsonTooltip(fields=tooltip_columns))
        if popup_columns:
            layer.add_child(self._folium.GeoJsonPopup(fields=popup_columns))
        layer.add_to(self.map)
        return self

    def _add_layer_lonboard(self, gdf_wgs84, column, cmap, name, **kwargs):
        # lonboard.viz() auto-picks a layer type (scatterplot/path/polygon)
        # from the geometry type and returns a full Map; only its layers
        # are reused so repeated add_layer() calls accumulate.
        built = self._lonboard.viz(gdf_wgs84, **kwargs)
        new_layers = list(built.layers) if hasattr(built, "layers") else [built]
        self.map.add_layer(new_layers)
        return self

    def add_geojson(self, data, name=None, style=None,
                     tooltip_columns=None, popup_columns=None, **kwargs):
        """
        Adds raw GeoJSON: a dict, a path to a .geojson file, or a GeoDataFrame.
        """
        if self.engine == "folium":
            layer = self._folium.GeoJson(data, style_function=style, name=name, **kwargs)
            if tooltip_columns:
                layer.add_child(self._folium.GeoJsonTooltip(fields=tooltip_columns))
            if popup_columns:
                layer.add_child(self._folium.GeoJsonPopup(fields=popup_columns))
            layer.add_to(self.map)
            return self

        if hasattr(data, "geometry"):
            gdf = data
        else:
            raw = data if isinstance(data, dict) else json.load(open(data))
            gdf = gpd.GeoDataFrame.from_features(raw["features"], crs="EPSG:4326")
        return self.add_layer(gdf, name=name)

    def add_marker(self, location, popup=None, tooltip=None, icon=None):
        """
        Adds a single marker (folium only).

        Parameters:
        -----------
        location : tuple
            (latitude, longitude)
        popup, tooltip : str, optional
        icon : folium.Icon, optional
        """
        self._require_engine("add_marker", "folium")
        self._folium.Marker(
            location=location, popup=popup, tooltip=tooltip, icon=icon,
        ).add_to(self.map)
        return self

    def add_cluster(self, gdf, popup_columns=None, tooltip_columns=None, name=None):
        """Adds points as a clustered marker layer (folium only)."""
        self._require_engine("add_cluster", "folium")
        plugins = _require("folium.plugins")
        gdf_wgs84 = _to_wgs84(gdf)
        cluster = plugins.MarkerCluster(name=name)
        for _, row in gdf_wgs84.iterrows():
            pt = row.geometry if row.geometry.geom_type == "Point" else row.geometry.centroid
            popup = "<br>".join(f"{c}: {row[c]}" for c in popup_columns) if popup_columns else None
            tooltip = ", ".join(str(row[c]) for c in tooltip_columns) if tooltip_columns else None
            self._folium.Marker(location=(pt.y, pt.x), popup=popup, tooltip=tooltip).add_to(cluster)
        cluster.add_to(self.map)
        return self

    def add_heatmap(self, data, weight_column=None, radius=15, blur=15,
                     name=None, **kwargs):
        """
        Adds a heatmap layer (folium only).

        Parameters:
        -----------
        data : GeoDataFrame of points, or a list of [lat, lon] / [lat, lon, weight].
        weight_column : str, optional
            Column used to weight each point (GeoDataFrame input only).
        """
        self._require_engine("add_heatmap", "folium")
        plugins = _require("folium.plugins")
        points = self._to_lat_lon_weight(data, weight_column)
        plugins.HeatMap(points, radius=radius, blur=blur, name=name, **kwargs).add_to(self.map)
        return self

    @staticmethod
    def _to_lat_lon_weight(data, weight_column=None):
        if hasattr(data, "geometry"):
            gdf = _to_wgs84(data)
            coords = gdf.geometry.apply(
                lambda g: (g.y, g.x) if g.geom_type == "Point" else (g.centroid.y, g.centroid.x)
            )
            if weight_column and weight_column in gdf.columns:
                return [[c[0], c[1], w] for c, w in zip(coords, gdf[weight_column])]
            return [[c[0], c[1]] for c in coords]
        return list(data)

    # ------------------------------------------------------------------ #
    # Raster / imagery                                                   #
    # ------------------------------------------------------------------ #

    def add_basemap(self, tiles, name=None, attr=None, **kwargs):
        """
        Adds an extra base layer.

        folium: any tile name/URL accepted by `folium.TileLayer`
        (e.g. 'CartoDB positron', or a raw XYZ URL).
        lonboard: a name matching `lonboard.basemap.CartoStyle`
        (e.g. 'positron', 'dark matter', 'voyager').
        """
        if self.engine == "folium":
            self._folium.TileLayer(tiles=tiles, name=name or tiles, attr=attr, **kwargs).add_to(self.map)
            return self
        if self.engine == "lonboard":
            basemap_module = _require("lonboard.basemap")
            carto_style = basemap_module.CartoStyle
            key = str(tiles).lower().replace(" ", "").replace("_", "").replace("-", "")
            match = next((s for s in carto_style if s.name.lower() == key), None)
            if match is None:
                available = ", ".join(s.name for s in carto_style)
                raise ValueError(
                    f"Style '{tiles}' inconnu pour engine='lonboard'. "
                    f"Essayez un nom parmi: {available}"
                )
            self.map.basemap = basemap_module.MaplibreBasemap(style=match)
            return self
        self._require_engine("add_basemap", "folium")

    def add_xyz(self, url_template, name=None, attr=""):
        """Adds a raw XYZ tile layer ('.../{z}/{x}/{y}.png'). Folium only."""
        self._require_engine("add_xyz", "folium")
        self._folium.TileLayer(tiles=url_template, name=name or "XYZ", attr=attr).add_to(self.map)
        return self

    def add_wms(self, url, layers, name=None, fmt="image/png",
                transparent=True, version="1.1.1", attr="", **kwargs):
        """Adds a WMS layer. Folium only."""
        self._require_engine("add_wms", "folium")
        self._folium.raster_layers.WmsTileLayer(
            url=url, layers=layers, fmt=fmt, transparent=transparent,
            version=version, attr=attr, name=name, **kwargs,
        ).add_to(self.map)
        return self

    def _read_raster_for_overlay(self, source, bands=None, cmap=None,
                                  vmin=None, vmax=None, max_size=1024):
        """
        Reads (and decimates) a raster for web display via rio-tiler —
        COG-aware, works on local paths and remote URLs alike, without
        ever downloading the full asset. Returns (PNG bytes,
        [[south, west], [north, east]] in WGS84).
        """
        Reader = _require("rio_tiler.io", "rio-tiler").Reader
        from ..processing.raster import RasterTools

        tmp_path = None
        if isinstance(source, RasterTools):
            path = source.path
            if path is None:
                path = tmp_path = source._write_tmp()
        else:
            path = source

        try:
            with Reader(path) as src:
                indexes = [b + 1 for b in bands] if bands else None
                img = src.preview(max_size=max_size, indexes=indexes)
                west, south, east, north = src.get_geographic_bounds(src.dataset.crs)

            stats = img.statistics()
            band_keys = list(stats)[: img.count]
            in_range = [
                (
                    vmin if vmin is not None else stats[k].min,
                    vmax if vmax is not None else stats[k].max,
                )
                for k in band_keys
            ]
            img.rescale(in_range=in_range)

            colormap = None
            if cmap:
                colormap = _require("rio_tiler.colormap", "rio-tiler").cmap.get(cmap)
            png_bytes = img.render(colormap=colormap)
        finally:
            if tmp_path:
                import os
                os.remove(tmp_path)

        return png_bytes, [[south, west], [north, east]]

    def add_raster(self, source, bands=None, cmap=None, vmin=None, vmax=None,
                    opacity=1.0, name=None, max_size=1024):
        """
        Adds a local raster as an image overlay (folium only), read via
        rio-tiler.

        Parameters:
        -----------
        source : str or RasterTools
            Path to a raster file, or an existing RasterTools instance.
        bands : list of int, optional
            0-based band indices to render (1 band -> grayscale/colormap, 3 -> RGB).
        cmap : str, optional
            Named colormap applied to a single band (e.g. "terrain", "viridis";
            see `rio_tiler.colormap.cmap.list()`).
        vmin, vmax : float, optional
            Value range used to stretch the data before display; auto-computed
            from the (decimated) data otherwise.
        max_size : int
            Longest side (px) the raster is decimated to before display.
        """
        self._require_engine("add_raster", "folium")
        import os
        import tempfile

        png_bytes, bounds = self._read_raster_for_overlay(
            source, bands=bands, cmap=cmap, vmin=vmin, vmax=vmax, max_size=max_size,
        )
        # folium.utilities.image_to_url only accepts a local file path, a
        # URL, or a numpy ndarray for `image=` (no file-like/bytes support),
        # so the rendered PNG is written to a short-lived temp file — its
        # content is base64-embedded into the overlay immediately below,
        # so the file can be removed right after construction.
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        try:
            tmp.write(png_bytes)
            tmp.close()
            overlay = self._folium.raster_layers.ImageOverlay(
                image=tmp.name, bounds=bounds, opacity=opacity, name=name or "raster",
            )
        finally:
            os.remove(tmp.name)
        overlay.add_to(self.map)
        return self

    def add_cog(self, url, bands=None, cmap=None, vmin=None, vmax=None,
                opacity=1.0, name=None, max_size=1024):
        """
        Adds a (local or remote) Cloud-Optimized GeoTIFF as a decimated
        preview overlay (folium only), read directly via rio-tiler —
        COG-aware, applies `cmap`/rescaling, and never downloads the full
        asset.

        Example:
            wm.add_cog("https://.../landcover.tif", cmap="terrain")
        """
        return self.add_raster(url, bands=bands, cmap=cmap, vmin=vmin, vmax=vmax,
                                opacity=opacity, name=name, max_size=max_size)

    # ------------------------------------------------------------------ #
    # Legend / colorbar / controls                                       #
    # ------------------------------------------------------------------ #

    def add_legend(self, items, title=None, position="bottomright"):
        """
        Adds a static color-swatch legend (folium only).

        Parameters:
        -----------
        items : dict {label: color} or list of (label, color) tuples.
        title : str, optional
        position : str
            "bottomright", "bottomleft", "topright", or "topleft".
        """
        self._require_engine("add_legend", "folium")
        from branca.element import MacroElement, Template

        if isinstance(items, dict):
            items = list(items.items())
        position_css = {
            "bottomright": "bottom: 20px; right: 20px;",
            "bottomleft": "bottom: 20px; left: 20px;",
            "topright": "top: 20px; right: 20px;",
            "topleft": "top: 20px; left: 20px;",
        }.get(position, "bottom: 20px; right: 20px;")
        rows = "".join(
            f'<div><span style="background:{color};width:12px;height:12px;'
            f'display:inline-block;margin-right:6px;border:1px solid #555;"></span>{label}</div>'
            for label, color in items
        )
        title_html = f"<div style='font-weight:bold;margin-bottom:4px;'>{title}</div>" if title else ""
        html = (
            "{% macro html(this, kwargs) %}"
            f'<div style="position: fixed; {position_css} z-index:9999; background:white;'
            'padding:8px 10px; border:1px solid #999; border-radius:4px;'
            f'font-size:12px; box-shadow:0 1px 4px rgba(0,0,0,0.3);">{title_html}{rows}</div>'
            "{% endmacro %}"
        )
        macro = MacroElement()
        macro._template = Template(html)
        self.map.get_root().add_child(macro)
        return self

    def add_colorbar(self, vmin, vmax, cmap="YlOrRd", caption=None):
        """Adds a continuous colorbar legend (folium only)."""
        self._require_engine("add_colorbar", "folium")
        colormap = _resolve_branca_colormap(cmap).scale(vmin, vmax)
        if caption:
            colormap.caption = caption
        colormap.add_to(self.map)
        return self

    def add_layer_control(self):
        """Adds a layer control (folium only)."""
        self._require_engine("add_layer_control", "folium")
        self._folium.LayerControl().add_to(self.map)
        return self

    def add_measure_control(self, **kwargs):
        """Adds a distance/area measurement tool (folium only)."""
        self._require_engine("add_measure_control", "folium")
        plugins = _require("folium.plugins")
        plugins.MeasureControl(**kwargs).add_to(self.map)
        return self

    def add_draw_control(self, **kwargs):
        """Adds free-hand drawing/editing tools (folium only)."""
        self._require_engine("add_draw_control", "folium")
        plugins = _require("folium.plugins")
        plugins.Draw(**kwargs).add_to(self.map)
        return self

    def add_fullscreen(self, **kwargs):
        """Adds a fullscreen toggle button (folium only)."""
        self._require_engine("add_fullscreen", "folium")
        plugins = _require("folium.plugins")
        plugins.Fullscreen(**kwargs).add_to(self.map)
        return self

    # ------------------------------------------------------------------ #
    # Views                                                              #
    # ------------------------------------------------------------------ #

    def fit_bounds(self, gdf):
        """Fits the zoom to a GeoDataFrame's bounds."""
        gdf_wgs84 = _to_wgs84(gdf)
        bounds = gdf_wgs84.total_bounds  # minx, miny, maxx, maxy
        if self.engine == "folium":
            self.map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
            return self
        self._require_engine("fit_bounds", "folium")

    def split(self, left, right, left_name=None, right_name=None,
              column=None, cmap="YlOrRd", layout="horizontal"):
        """
        Replaces this map with a side-by-side comparison of two layers
        (folium only): `folium.plugins.DualMap`.

        Parameters:
        -----------
        left, right : GeoDataFrame
            Layers shown on each side.
        left_name, right_name : str, optional
        column : str, optional
            Column used for choropleth coloring on both sides.
        layout : str
            "horizontal" or "vertical".
        """
        self._require_engine("split", "folium")
        plugins = _require("folium.plugins")
        dual = plugins.DualMap(
            location=self._init_kwargs["location"],
            zoom_start=self._init_kwargs["zoom_start"],
            layout=layout,
            tiles=self._init_kwargs["tiles"],
        )
        for gdf, side_name, m in ((left, left_name, dual.m1), (right, right_name, dual.m2)):
            gdf_wgs84 = _to_wgs84(gdf)
            saved_map = self.map
            self.map = m
            self._add_layer_folium(gdf_wgs84, column, cmap, None, None, None, side_name)
            self.map = saved_map
        self.map = dual
        return self

    def time_slider(self, gdf, time_column="date", style_columns=None,
                     period="P1D", duration=None, transition_time=200,
                     auto_play=True, loop=True):
        """
        Adds a time-animated layer (folium only): one row per
        (feature, timestamp).

        Parameters:
        -----------
        gdf : GeoDataFrame
            One row per feature per date; `time_column` holds a
            datetime-like value.
        time_column : str
        style_columns : list of str, optional
            Columns copied into each feature's 'style' (e.g. color, radius).
        period, duration : str
            ISO 8601 durations (see `folium.plugins.TimestampedGeoJson`).
        """
        self._require_engine("time_slider", "folium")
        plugins = _require("folium.plugins")
        gdf_wgs84 = _to_wgs84(gdf)
        features = []
        for _, row in gdf_wgs84.iterrows():
            iso = pd.Timestamp(row[time_column]).isoformat()
            props = {"times": [iso]}
            if style_columns:
                props["style"] = {c: row[c] for c in style_columns}
            features.append({
                "type": "Feature",
                "geometry": row.geometry.__geo_interface__,
                "properties": props,
            })
        fc = {"type": "FeatureCollection", "features": features}
        plugins.TimestampedGeoJson(
            fc, period=period, duration=duration,
            transition_time=transition_time, auto_play=auto_play, loop=loop,
        ).add_to(self.map)
        return self

    # ------------------------------------------------------------------ #
    # Output                                                             #
    # ------------------------------------------------------------------ #

    def show(self):
        """Returns the underlying map/widget object (auto-displayed in a notebook)."""
        return self.map

    def save(self, filename="map.html"):
        """Saves the map to a standalone HTML file."""
        if self.engine == "folium":
            self.map.save(filename)
        elif self.engine == "lonboard":
            self.map.to_html(filename)
        elif self.engine == "kepler.gl":
            self.map.save_to_html(file_name=filename)
        return self

    def _repr_html_(self):
        return self.map._repr_html_()
