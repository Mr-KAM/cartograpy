from __future__ import annotations

from ._optional import _require_wbdata
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class WorldBank:
    def __init__(self):
        self.api_key = ""
        self._wbdata = _require_wbdata()
    
    def get_sources(self):
        # Returns a list of data sources available on the World Bank's site.
        return self._wbdata.get_sources()
    
    def get_indicators(self,source=1,query=None):
        return self._wbdata.get_indicators(source=source)
    
    def get_countries(self,query):
        return self._wbdata.get_countries(query=query)
    
    def get_data(self, indicators, country='all', **kwargs):
        return self._wbdata.get_dataframe(indicators, country, **kwargs)

    def sources(self) -> pd.DataFrame:
        """Returns a table of the data sources used by this class."""
        return pd.DataFrame([
            {
                "name": "World Bank Open Data",
                "url": "https://data.worldbank.org/",
                "description": "Global development indicators (get_data, get_indicators, get_countries).",
            },
        ])
