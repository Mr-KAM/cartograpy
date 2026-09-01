from __future__ import annotations

import datetime as _dt
import logging
from typing import Iterable, Optional

import pandas as pd
import geopandas as gpd
from requests_cache import CachedSession

from ._types import BBox

logger = logging.getLogger(__name__)

# Valeur de remplissage NASA POWER pour les données manquantes.
_FILL_VALUE = -999.0


class Climate:
    """Données météo/climat globales via l'API NASA POWER — sans clé API.

    NASA POWER (https://power.larc.nasa.gov/) fournit des séries
    météorologiques journalières, horaires, mensuelles ou climatologiques,
    partout dans le monde, issues de ré-analyses (MERRA-2) et de produits
    satellite. Pensé au départ pour l'agro-climatologie, le solaire et le
    bâtiment.

    Deux points d'entrée :

    - :meth:`get_point` — série temporelle en un point (lon, lat) →
      ``geopandas.GeoDataFrame`` indexé par date (géométrie constante).
    - :meth:`get_region` — grille de points sur une emprise →
      ``geopandas.GeoDataFrame`` au format long (une ligne par point ×
      paramètre × pas de temps).

    Paramètres
    ----------
    cache_expire_seconds : durée de vie du cache HTTP local (7 jours par
        défaut). ``-1`` = ne jamais expirer, ``0`` = pas de cache.
    timeout : délai maximal par requête HTTP (secondes).

    Exemple
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

    #: Paramètres par défaut si l'appelant n'en fournit pas (température,
    #: rosée, précipitations, vent, rayonnement, humidité).
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
    # API publique
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
        """Série météo NASA POWER en un point.

        Paramètres
        ----------
        longitude, latitude : coordonnées du point (WGS-84 / EPSG:4326).
        start, end : bornes de la période. ``datetime.date``,
            ``datetime.datetime``, ``"YYYY-MM-DD"`` ou ``"YYYYMMDD"`` pour
            ``temporal="daily"``/``"hourly"`` ; une année (``int`` ou
            ``"YYYY"``) pour ``"monthly"``/``"climatology"``.
        parameters : liste de codes POWER (ex. ``["T2M", "PRECTOTCORR"]``).
            ``None`` ou ``[]`` → :attr:`DEFAULT_PARAMETERS`. Voir la liste
            complète : https://power.larc.nasa.gov/parameters/
        community : ``"ag"`` (agro, défaut), ``"sb"`` (bâtiment) ou
            ``"re"`` (renouvelable).
        temporal : ``"daily"`` (défaut), ``"hourly"``, ``"monthly"`` ou
            ``"climatology"``.

        Retour
        ------
        geopandas.GeoDataFrame (CRS EPSG:4326) indexé par date/heure
        (``DatetimeIndex`` pour daily/hourly, dates mensuelles pour monthly),
        une colonne par paramètre + une colonne ``geometry`` constante
        (le point interrogé). Les valeurs manquantes (-999) → ``NaN``.
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
        if temporal == "monthly":  # écarte la ligne 'moyenne annuelle' (mois 13)
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
        """Grille de points NASA POWER sur une emprise.

        Mêmes paramètres que :meth:`get_point`, mais ``bbox`` remplace
        ``longitude``/``latitude`` : ``[xmin, ymin, xmax, ymax]`` en
        EPSG:4326. L'emprise doit rester modérée (l'API limite la taille de
        la région, ~10° de côté selon la résolution temporelle).

        Retour
        ------
        geopandas.GeoDataFrame au format long : colonnes ``parameter``,
        ``date``, ``value``, ``geometry`` (points de la grille POWER,
        ~0.5°). Pivoter avec ``gdf.pivot_table(index="geometry",
        columns="parameter", values="value")`` pour cartographier.
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
    # Interne
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
        """Normalise une date en 'YYYYMMDD' (daily/hourly) ou 'YYYY'
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
            # NASA POWER: 'YYYYMM' (le mois '13' = moyenne annuelle → NaT).
            month_ok = (s.str.len() == 6) & (~s.str.endswith("13"))
            s = s.where(month_ok)
            return pd.Index(pd.to_datetime(s, format="%Y%m", errors="coerce"))
        fmt = "%Y%m%d%H" if temporal == "hourly" else "%Y%m%d"
        return pd.Index(pd.to_datetime(s, format=fmt, errors="coerce"))

    def _get(self, url, params) -> dict:
        logger.info(f"NASA POWER: {url}")
        resp = self._session.get(url, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise RuntimeError(
                f"NASA POWER a renvoyé {resp.status_code} — {resp.text[:300]}"
            )
        return resp.json()
