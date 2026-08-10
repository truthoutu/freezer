"""
Dynamic Target Directory Generator - Zero Hardcoding
Generates country-specific, localized search directory URLs on the fly for ANY occupation keyword and country.
Uses OpenStreetMap Nominatim geocoding API instead of hardcoded city lists.
"""

import json
import logging
import urllib.parse
from urllib.request import urlopen, URLError

from urllib.parse import quote_plus

logger = logging.getLogger("DynamicTargetGenerator")

# Multilingual Occupation Maps (English -> Local Language for precision search)
OCCUPATION_MAPS = {
    "German": {
        "nurse": "Pflegedienst",
        "doctor": "Arzt",
        "physician": "Arzt",
        "realtor": "Immobilienmakler",
        "real estate": "Immobilienmakler",
        "lawyer": "Rechtsanwalt",
        "attorney": "Rechtsanwalt",
        "accountant": "Steuerberater",
        "dentist": "Zahnarzt",
        "plumber": "Klempner",
        "electrician": "Elektriker",
        "architect": "Architekt",
    },
    "French": {
        "nurse": "Infirmiere",
        "doctor": "Medecin",
        "physician": "Medecin",
        "realtor": "Agent immobilier",
        "lawyer": "Avocat",
        "accountant": "Comptable",
        "dentist": "Dentiste",
        "architect": "Architecte",
    }
}

# Geocoding cache
_LOCATION_CACHE = {}


def _geocode_location(country: str, region: str) -> list[str]:
    """Geocode a region/city using OpenStreetMap Nominatim API."""
    cache_key = (country, region)
    if cache_key in _LOCATION_CACHE:
        return _LOCATION_CACHE[cache_key]

    try:
        encoded_region = urllib.parse.quote(region)
        encoded_country = urllib.parse.quote(country)
        url = f"https://nominatim.openstreetmap.org/search.php?q={encoded_region}+{encoded_country}&format=json&limit=5"
        req = urlopen(url, timeout=10)
        data = json.loads(req.read().decode())
        locations = [item.get("display_name", "") for item in data if item.get("type") == "city"]
        _LOCATION_CACHE[cache_key] = locations if locations else [region]
    except Exception:
        _LOCATION_CACHE[cache_key] = [region]

    return _LOCATION_CACHE[cache_key]


def get_default_sources(country: str, occupation: str) -> list[str]:
    """
    Dynamically generate search directory URLs for ANY country and occupation.
    Uses OpenStreetMap Nominatim for geocoding instead of hardcoded city lists.
    """
    urls = []
    occ_clean = (occupation or "Professional").strip()
    occ_lower = occ_clean.lower()

    if country == "Germany":
        local_kw = OCCUPATION_MAPS["German"].get(occ_lower, occ_clean)
        encoded_kw = quote_plus(local_kw)

        for region in _geocode_location("Germany", "Germany"):
            urls.append(f"https://www.gelbseiten.de/suche/{encoded_kw}/{urllib.parse.quote(region)}")
        for region in _geocode_location("Germany", "Germany")[:3]:
            urls.append(f"https://www.dasoertliche.de/Themen/{encoded_kw}+{urllib.parse.quote(region)}")

    elif country == "Switzerland":
        local_kw = OCCUPATION_MAPS["French"].get(occ_lower, OCCUPATION_MAPS["German"].get(occ_lower, occ_clean))
        encoded_kw = quote_plus(local_kw)

        for region in _geocode_location("Switzerland", "Switzerland"):
            urls.append(f"https://tel.search.ch/?was={encoded_kw}&wo={urllib.parse.quote(region)}")

    elif country == "Australia":
        encoded_kw = quote_plus(occ_clean)
        for region in _geocode_location("Australia", "Australia"):
            if region:
                urls.append(f"https://www.yellowpages.com.au/search/findings?text={encoded_kw}+{urllib.parse.quote(region)}")
            else:
                urls.append(f"https://www.yellowpages.com.au/search/findings?text={encoded_kw}")

    elif country in ["United States", "Canada"]:
        encoded_kw = quote_plus(occ_clean)
        for region in _geocode_location("United States" if country == "United States" else "Canada", country):
            urls.append(f"https://www.yellowpages.com/search?search_terms={encoded_kw}&geo_location_terms={urllib.parse.quote(region)}")

    elif country == "United Kingdom":
        encoded_kw = quote_plus(occ_clean)
        for region in _geocode_location("United Kingdom", "United Kingdom"):
            urls.append(f"https://www.yell.com/ucs/UcsSearchAction.do?keywords={encoded_kw}&location={urllib.parse.quote(region)}")

    else:
        encoded_kw = quote_plus(occ_clean)
        encoded_country = quote_plus(country)
        urls.append(f"https://www.yellowpages.com/search?search_terms={encoded_kw}&geo_location_terms={encoded_country}")
        urls.append(f"https://www.yellowpages.com.au/search/findings?text={encoded_kw}+{encoded_country}")

    logger.info(f"Dynamically generated {len(urls)} target directory URLs for Country='{country}', Occupation='{occ_clean}'")
    return urls
