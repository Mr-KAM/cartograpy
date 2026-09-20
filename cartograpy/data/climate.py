from __future__ import annotations

import datetime as _dt
import logging
from typing import Iterable, Optional

import pandas as pd
import geopandas as gpd
from requests_cache import CachedSession

from ._types import BBox

logger = logging.getLogger(__name__)

# Fill value used by NASA POWER for missing data.
_FILL_VALUE = -999.0


class Climate:
    """Global weather/climate data via the NASA POWER API — no API key needed.

    NASA POWER (https://power.larc.nasa.gov/) provides daily, hourly,
    monthly, or climatological weather series worldwide, derived from
    reanalysis (MERRA-2) and satellite products. Originally designed
    for agro-climatology, solar, and building applications.

    Two entry points:

    - :meth:`get_point` — time series at a single point (lon, lat) →
      ``geopandas.GeoDataFrame`` indexed by date (constant geometry).
    - :meth:`get_region` — grid of points over an extent →
      ``geopandas.GeoDataFrame`` in long format (one row per point ×
      parameter × time step).

    Parameters
    ----------
    cache_expire_seconds : lifetime of the local HTTP cache (7 days by
        default). ``-1`` = never expire, ``0`` = no cache.
    timeout : maximum delay per HTTP request (seconds).

    Example
    -------
    >>> clim = Climate()
    >>> gdf = clim.get_point(-3.99, 5.35, "2023-01-01", "2023-12-31")   # Abidjan
    >>> gdf[["T2M", "PRECTOTCORR"]].describe()
    >>> gdf.crs, gdf.geometry.iloc[0]
    >>> region = clim.get_region((-6, 4, -2, 8), 2020, 2022, temporal="monthly")
    """

    BASE_URL = "https://power.larc.nasa.gov/api/temporal"
    COMMUNITIES = ("ag", "sb", "re")
    TEMPORAL = ("hourly", "daily", "monthly", "climatology")

    #: Default parameters if the caller doesn't provide any (temperature,
    #: dew point, precipitation, wind, radiation, humidity).
    DEFAULT_PARAMETERS = (
        "T2M", "T2M_MIN", "T2M_MAX", "T2MDEW",
        "PRECTOTCORR", "WS2M", "ALLSKY_SFC_SW_DWN", "RH2M",
    )

    def __init__(self, cache_expire_seconds: int = 604800, timeout: int = 60):
        self.timeout = timeout
        self._session = CachedSession(
            cache_name=".nasapower_cache", expire_after=cache_expire_seconds,
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_point(
        self,
        longitude: float,
        latitude: float,
        start,
        end,
        parameters: Optional[Iterable[str]] = None,
        community: str = "ag",
        temporal: str = "daily",
    ) -> gpd.GeoDataFrame:
        """NASA POWER weather series at a single point.

        Parameters
        ----------
        longitude, latitude : coordinates of the point (WGS-84 / EPSG:4326).
        start, end : period bounds. ``datetime.date``,
            ``datetime.datetime``, ``"YYYY-MM-DD"`` or ``"YYYYMMDD"`` for
            ``temporal="daily"``/``"hourly"``; a year (``int`` or
            ``"YYYY"``) for ``"monthly"``/``"climatology"``.
        parameters : list of POWER codes (e.g. ``["T2M", "PRECTOTCORR"]``).
            ``None`` or ``[]`` → :attr:`DEFAULT_PARAMETERS`. See the full
            list: https://power.larc.nasa.gov/parameters/
        community : ``"ag"`` (agro, default), ``"sb"`` (building) or
            ``"re"`` (renewable).
        temporal : ``"daily"`` (default), ``"hourly"``, ``"monthly"`` or
            ``"climatology"``.

        Returns
        ------
        geopandas.GeoDataFrame (CRS EPSG:4326) indexed by date/time
        (``DatetimeIndex`` for daily/hourly, monthly dates for monthly),
        one column per parameter + a constant ``geometry`` column
        (the queried point). Missing values (-999) → ``NaN``.
        """
        temporal, community, params = self._validate(temporal, community, parameters)
        query = {
            "parameters": ",".join(params),
            "community": community.upper(),
            "longitude": longitude,
            "latitude": latitude,
            "start": self._fmt_date(start, temporal),
            "end": self._fmt_date(end, temporal),
            "format": "JSON",
        }
        payload = self._get(f"{self.BASE_URL}/{temporal}/point", query)
        series = payload["properties"]["parameter"]
        df = pd.DataFrame(series).replace(_FILL_VALUE, pd.NA).astype("Float64")
        df.index = self._parse_index(df.index, temporal)
        df.index.name = "date"
        if temporal == "monthly":  # drop the 'annual average' row (month 13)
            df = df[df.index.notna()]
        return gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy([longitude] * len(df), [latitude] * len(df)),
            crs="EPSG:4326",
            index=df.index,
        )

    def get_region(
        self,
        bbox: BBox,
        start,
        end,
        parameters: Optional[Iterable[str]] = None,
        community: str = "ag",
        temporal: str = "daily",
    ) -> gpd.GeoDataFrame:
        """Grid of NASA POWER points over an extent.

        Same parameters as :meth:`get_point`, but ``bbox`` replaces
        ``longitude``/``latitude``: ``[xmin, ymin, xmax, ymax]`` in
        EPSG:4326. The extent must stay moderate (the API limits the
        region size, ~10° per side depending on the temporal resolution).

        Returns
        ------
        geopandas.GeoDataFrame in long format: columns ``parameter``,
        ``date``, ``value``, ``geometry`` (POWER grid points, ~0.5°).
        Pivot with ``gdf.pivot_table(index="geometry",
        columns="parameter", values="value")`` to map it.
        """
        temporal, community, params = self._validate(temporal, community, parameters)
        xmin, ymin, xmax, ymax = bbox
        query = {
            "parameters": ",".join(params),
            "community": community.upper(),
            "longitude-min": xmin, "longitude-max": xmax,
            "latitude-min": ymin, "latitude-max": ymax,
            "start": self._fmt_date(start, temporal),
            "end": self._fmt_date(end, temporal),
            "format": "JSON",
        }
        payload = self._get(f"{self.BASE_URL}/{temporal}/regional", query)

        rows = []
        for feat in payload["features"]:
            lon, lat = feat["geometry"]["coordinates"][:2]
            for pname, series in feat["properties"]["parameter"].items():
                for key, value in series.items():
                    rows.append((pname, key, value, lon, lat))

        df = pd.DataFrame(rows, columns=["parameter", "date", "value", "_lon", "_lat"])
        df["value"] = df["value"].replace(_FILL_VALUE, pd.NA).astype("Float64")
        df["date"] = self._parse_index(pd.Index(df["date"]), temporal)
        if temporal == "monthly":
            df = df[df["date"].notna()]
        gdf = gpd.GeoDataFrame(
            df.drop(columns=["_lon", "_lat"]),
            geometry=gpd.points_from_xy(df["_lon"], df["_lat"]),
            crs="EPSG:4326",
        )
        return gdf

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _validate(self, temporal, community, parameters):
        temporal = temporal.lower()
        if temporal not in self.TEMPORAL:
            raise ValueError(
                f"temporal doit être l'un de {self.TEMPORAL}, reçu {temporal!r}."
            )
        community = community.lower()
        if community not in self.COMMUNITIES:
            raise ValueError(
                f"community doit être l'un de {self.COMMUNITIES}, reçu {community!r}."
            )
        params = list(parameters) if parameters else list(self.DEFAULT_PARAMETERS)
        if not params:
            raise ValueError("Au moins un paramètre POWER est requis.")
        return temporal, community, params

    @staticmethod
    def _fmt_date(value, temporal) -> str:
        """Normalizes a date to 'YYYYMMDD' (daily/hourly) or 'YYYY'
        (monthly/climatology)."""
        year_only = temporal in ("monthly", "climatology")
        if isinstance(value, int):
            return str(value) if year_only else f"{value:04d}0101"
        if isinstance(value, (_dt.date, _dt.datetime)):
            return value.strftime("%Y" if year_only else "%Y%m%d")
        s = str(value).strip().replace("-", "").replace("/", "")
        return s[:4] if year_only else s

    @staticmethod
    def _parse_index(index, temporal):
        s = pd.Series(pd.Index(index).astype(str))
        if temporal == "climatology":
            return pd.Index(s)  # 'JAN', 'FEB', ..., 'ANN'
        if temporal == "monthly":
            # NASA POWER: 'YYYYMM' (month '13' = annual average → NaT).
            month_ok = (s.str.len() == 6) & (~s.str.endswith("13"))
            s = s.where(month_ok)
            return pd.Index(pd.to_datetime(s, format="%Y%m", errors="coerce"))
        fmt = "%Y%m%d%H" if temporal == "hourly" else "%Y%m%d"
        return pd.Index(pd.to_datetime(s, format=fmt, errors="coerce"))

    def sources(self) -> pd.DataFrame:
        """Returns a table of the data sources used by this class.

        Returns
        ------
        pd.DataFrame with columns 'name', 'url', 'description'.
        """
        return pd.DataFrame([
            {
                "name": "NASA POWER",
                "url": "https://power.larc.nasa.gov/",
                "description": "Global weather/climate data (used by get_point() and get_region()).",
            },
        ])

    def _get(self, url, params) -> dict:
        resp = self._session.get(url, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(
                f"NASA POWER a renvoyé {resp.status_code} — {resp.text[:300]}"
            )
        return resp.json()
