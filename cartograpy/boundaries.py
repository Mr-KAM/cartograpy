"""Runfola, Daniel, Community Contributors, and [v4.0: Lindsey Rogers, Joshua Habib, Sidonie Horn, Sean Murphy, Dorian Miller, Hadley Day, Lydia Troup, Dominic Fornatora, Natalie Spage, Kristina Pupkiewicz, Michael Roth, Carolina Rivera, Charlie Altman, Isabel Schruer, Tara McLaughlin, Russ Biddle, Renee Ritchey, Emily Topness, James Turner, Sam Updike, Helena Buckman, Neel Simpson, Jason Lin], [v2.0: Austin Anderson, Heather Baier, Matt Crittenden, Elizabeth Dowker, Sydney Fuhrig, Seth Goodman, Grace Grimsley, Rachel Layko, Graham Melville, Maddy Mulder, Rachel Oberman, Joshua Panganiban, Andrew Peck, Leigh Seitz, Sylvia Shea, Hannah Slevin, Rebecca Yougerman, Lauren Hobbs]. "geoBoundaries: A global database of political administrative boundaries." Plos one 15, no. 4 (2020): e0231866."""

from typing import List
import geojson
import requests
import cartograpy.countries_iso3 as countries_iso3
import cartograpy.iso3_codes as iso3_codes
from requests_cache import CachedSession

_session = CachedSession(expire_after=604800) #cache expires after 1 week

def clear_cache():
    _session.cache.clear()

def set_cache_expire_time(seconds: int):
    """Update cache expiring time. Does not clear cache."""
    global _session
    _session = CachedSession(expire_after=seconds)

def disable_cache():
    global _session
    _session = requests

def is_valid_adm(iso3, adm: str) -> bool :
    html = _session.get("https://www.geoboundaries.org/api/current/gbOpen/{}/".format(iso3), verify=True).text
    #print('adm in html =' + str(adm in html))
    return adm in html

def _validate_adm(adm: str | int) -> str :
    if type(adm).__name__ == 'int' or len(str(adm)) == 1:
        adm = 'ADM' + str(adm)
    if str.upper(adm) in ['ADM{}'.format(str(i)) for i in range(6)] or str.upper(adm) == 'ALL':
        return str.upper(adm)
    raise KeyError

def _get_smallest_adm(iso3):
    current_adm = 5
    adm_exists = False
    while current_adm >= 0:
        #print('testing adm'+str(current_adm))
        if is_valid_adm(iso3, 'ADM' + str(current_adm)):
            break
        current_adm -= 1
    print('Smallest ADM level found for {} : ADM{}'.format(iso3, current_adm))
    return 'ADM' + str(current_adm)

def _is_valid_iso3_code(territory: str) -> bool :
    return str.lower(territory) in iso3_codes.iso_codes

def _get_iso3_from_name_or_iso2(name: str) -> str:
    try :
        return str.upper(countries_iso3.countries_iso3[str.lower(name)])
    except KeyError as e:
        print("KeyError : Couldn't find country named {}".format(e))
        raise KeyError

def _generate_url(territory: str, adm : str | int) -> str :
    iso3 = str.upper(territory) if _is_valid_iso3_code(territory) else _get_iso3_from_name_or_iso2(territory)
    if adm != -1:
        adm = _validate_adm(adm)
    else:
        adm = _get_smallest_adm(iso3)
    if not is_valid_adm(iso3, adm):
        print("KeyError : ADM level '{}' doesn't exist for country '{}' ({})".format(adm, territory, iso3))
        raise KeyError
    return "https://www.geoboundaries.org/api/current/gbOpen/{}/{}/".format(iso3, adm)

def get_metadata(territory: str, adm: str | int) -> dict:
    """
    Returns a json of specifided territory's metadata.
    Use adm='ALL' to get metadata for every ADM levels.
    """
    return _session.get(_generate_url(territory, adm), verify=True).json() #TO DO get rid of verify arg

def _get_data(territory: str, adm: str, simplified: bool) -> dict:
    """Requests the geoboundaries API and returns a JSON str object of the specified territory and ADM """
    geom_complexity = 'simplifiedGeometryGeoJSON' if simplified else 'gjDownloadURL'
    try:
        json_uri = get_metadata(territory, adm)[geom_complexity]
    except:
        print("Error while requesting geoboudaries API\n URL : {}\n".format(_generate_url(territory, adm)))
        raise
    return _session.get(json_uri).text

def get_adm(territories: str | List[str], adm: str | int, simplified=True) -> dict:
    """
    Returns a json of specifided territories at specifided adm levels.

    Allowed values for <territories> argument :

        - ISO 3166-1 (alpha2) : AFG, QAT, YEM, etc.
        - ISO 3166-1 (alpha3) : AF, QA, YE, etc.
        - Country name (i.e ADM0 territories) in any of the following languages : Arabic, Armenian, Basque, Bulgarian, Chinese (simplified), Chinese (traditional), Czech,
             Danish, Dutch, English, Esperanto, Estonian, Finnish, French, German, Greek, Hungarian, Italian, Japanese, Korean, Lithuanian,
             Norwegian, Polish, Portuguese, Romanian, Russian, Slovak, Spanish, Swedish, Thai, Ukrainian
        For more information, check out https://stefangabos.github.io/world_countries/ (the data source for ISO codes and countries' names)

    Allowed format for <territories> argument :

        - a single string : "Senegal", "SEN", "เซเนกัล"
        - a list of strings : ["SEN", "Mali'], ["セネガル", "մալի"]

    Allowed values for <adm> argument :
        - 'ADM0' to 'ADM5' (if exists for specified country)
        - int 0 to 5
        - int -1 (returns the smallest available ADM level)
        For more information about ADM levels, check out https://www.geoboundaries.org/index.html
    """

    if type(territories) == str:
        return geojson.loads(_get_data(territories, adm, simplified))
    geojsons = [geojson.loads(_get_data(i, adm, simplified))['features'][0] for i in territories]
    feature_collection = geojson.FeatureCollection(geojsons)
    return feature_collection

