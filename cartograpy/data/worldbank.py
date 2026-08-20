from __future__ import annotations

from ._optional import _require_wbdata
import logging

logger = logging.getLogger(__name__)


class WorldBank:
    def __init__(self):
        self.api_key = ""
        self._wbdata = _require_wbdata()
    
    def get_sources(self):
        # Renvoie une liste de sources de données disponibles sur le site de la Banque mondiale.
        return self._wbdata.get_sources()
    
    def get_indicators(self,source=1,query=None):
        return self._wbdata.get_indicators(source=source)
    
    def get_countries(self,query):
        return self._wbdata.get_countries(query=query)
    
    def get_data(self, indicators, country='all', **kwargs):
        return self._wbdata.get_dataframe(indicators, country, **kwargs)
