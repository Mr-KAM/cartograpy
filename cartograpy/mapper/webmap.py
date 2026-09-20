import logging

logger = logging.getLogger(__name__)


class WebMap:
    """
    Interactive map based on Folium / Leaflet.

    Parameters:
    -----------
    location : tuple
        Initial center (latitude, longitude)
    zoom_start : int
        Initial zoom level
    tiles : str
        Basemap (e.g. 'OpenStreetMap', 'CartoDB positron', 'Stamen Terrain')
    width : str
        Map width ('100%' or pixels)
    height : str
        Map height ('600px' or percentage)

    Example:
    --------
    >>> wm = WebMap(location=(5.35, -4.0), zoom_start=7)
    >>> wm.add_layer(gdf, column="population", cmap="YlOrRd")
    >>> wm.show()
    """

    def __init__(
        self,
        location=(0, 0),
        zoom_start=6,
        tiles="OpenStreetMap",
        width="100%",
        height="600px",
    ):
        try:
            import folium
        except ImportError:
            raise ImportError(
                "folium est requis pour WebMap. "
                "Installez-le avec : pip install folium"
            )
        self._folium = folium
        self.map = folium.Map(
            location=location,
            zoom_start=zoom_start,
            tiles=tiles,
            width=width,
            height=height,
        )

    # -- vector layer --------------------------------------------------------

    def add_layer(self, gdf, column=None, cmap="YlOrRd",
                  style_function=None, tooltip_columns=None,
                  popup_columns=None, name=None, **kwargs):
        """
        Adds a GeoDataFrame as a GeoJson or Choropleth layer.

        Parameters:
        -----------
        gdf : gpd.GeoDataFrame
            Geographic data
        column : str, optional
            Column used for choropleth coloring
        cmap : str
            Color palette
        style_function : callable, optional
            Folium style function
        tooltip_columns : list, optional
            Columns shown on hover
        popup_columns : list, optional
            Columns shown on click
        name : str, optional
            Layer name (for the layer control)
        """
        import branca.colormap as bcm

        gdf_wgs84 = gdf.to_crs(epsg=4326) if gdf.crs and gdf.crs.to_epsg() != 4326 else gdf

        if column and column in gdf_wgs84.columns:
            vmin = gdf_wgs84[column].min()
            vmax = gdf_wgs84[column].max()
            colormap = bcm.linear.YlOrRd_09.scale(vmin, vmax)
            colormap.caption = column

            def _style(feature):
                val = feature["properties"].get(column, vmin)
                return {
                    "fillColor": colormap(val) if val is not None else "gray",
                    "color": "black",
                    "weight": 0.5,
                    "fillOpacity": 0.7,
                }

            layer = self._folium.GeoJson(
                gdf_wgs84.__geo_interface__,
                style_function=style_function or _style,
                name=name or column,
            )
            colormap.add_to(self.map)
        else:
            default_style = {
                "fillColor": "steelblue",
                "color": "black",
                "weight": 0.5,
                "fillOpacity": 0.6,
            }
            layer = self._folium.GeoJson(
                gdf_wgs84.__geo_interface__,
                style_function=style_function or (lambda f: default_style),
                name=name or "layer",
            )

        if tooltip_columns:
            layer.add_child(
                self._folium.GeoJsonTooltip(fields=tooltip_columns)
            )
        if popup_columns:
            layer.add_child(
                self._folium.GeoJsonPopup(fields=popup_columns)
            )

        layer.add_to(self.map)
        return self

    # -- markers ---------------------------------------------------------------

    def add_marker(self, location, popup=None, tooltip=None, icon=None):
        """
        Adds a marker.

        Parameters:
        -----------
        location : tuple
            (latitude, longitude)
        popup : str, optional
            Text shown on click
        tooltip : str, optional
            Text shown on hover
        icon : folium.Icon, optional
            Custom icon
        """
        self._folium.Marker(
            location=location, popup=popup, tooltip=tooltip, icon=icon,
        ).add_to(self.map)
        return self

    # -- appearance ------------------------------------------------------------

    def add_layer_control(self):
        """Adds a layer control (LayerControl)."""
        self._folium.LayerControl().add_to(self.map)
        return self

    def fit_bounds(self, gdf):
        """Fits the zoom to a GeoDataFrame's bounds."""
        gdf_wgs84 = gdf.to_crs(epsg=4326) if gdf.crs and gdf.crs.to_epsg() != 4326 else gdf
        bounds = gdf_wgs84.total_bounds  # minx, miny, maxx, maxy
        self.map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        return self

    # -- output ------------------------------------------------------------

    def show(self):
        """Returns the Folium map (auto-displayed in a notebook)."""
        return self.map

    def save(self, filename="map.html"):
        """Saves the map to HTML."""
        self.map.save(filename)
        return self

    def _repr_html_(self):
        return self.map._repr_html_()
