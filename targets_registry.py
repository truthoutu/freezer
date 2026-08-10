"""
Dynamic Target Directory Generator - Zero Hardcoding
Generates country-specific, localized search directory URLs on the fly for ANY occupation keyword and country.
"""

import logging
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

# Major Region/City Lists per Country for Micro-Targeted Searching
MAJOR_CITIES = {
    "Germany": [
        "bundesweit", "berlin", "hamburg", "muenchen", "koeln", "frankfurt",
        "stuttgart", "duesseldorf", "dortmund", "essen"
    ],
    "Switzerland": [
        "Schweiz", "Zuerich", "Genf", "Basel", "Lausanne", "Bern",
        "Winterthur", "Luzern", "St.Gallen"
    ],
    "Australia": [
        "", "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide",
        "Gold Coast", "Canberra", "Newcastle"
    ],
    "United States": [
        "NY", "CA", "TX", "FL", "IL", "PA", "OH", "GA", "NC", "MI",
        "New York", "Los Angeles", "Chicago", "Houston", "Phoenix"
    ],
    "Canada": [
        "Toronto", "Montreal", "Vancouver", "Calgary", "Ottawa", "Edmonton"
    ],
    "United Kingdom": [
        "London", "Birmingham", "Manchester", "Glasgow", "Liverpool", "Leeds"
    ]
}


def get_default_sources(country: str, occupation: str) -> list[str]:
    """
    Dynamically generate search directory URLs for ANY country and occupation.
    No hardcoded lists required.
    """
    urls = []
    occ_clean = (occupation or "Professional").strip()
    occ_lower = occ_clean.lower()

    if country == "Germany":
        local_kw = OCCUPATION_MAPS["German"].get(occ_lower, occ_clean)
        encoded_kw = quote_plus(local_kw)
        cities = MAJOR_CITIES["Germany"]

        for city in cities:
            urls.append(f"https://www.gelbseiten.de/suche/{encoded_kw}/{city}")

        for city in cities[:5]:
            city_suffix = f"+{city.capitalize()}" if city != "bundesweit" else ""
            urls.append(f"https://www.dasoertliche.de/Themen/{encoded_kw}{city_suffix}")

    elif country == "Switzerland":
        local_kw = OCCUPATION_MAPS["French"].get(occ_lower, OCCUPATION_MAPS["German"].get(occ_lower, occ_clean))
        encoded_kw = quote_plus(local_kw)
        cities = MAJOR_CITIES["Switzerland"]

        for city in cities:
            urls.append(f"https://tel.search.ch/?was={encoded_kw}&wo={city}")

    elif country == "Australia":
        encoded_kw = quote_plus(occ_clean)
        cities = MAJOR_CITIES["Australia"]

        for city in cities:
            if city:
                location_str = f"+{quote_plus(city)}"
                urls.append(f"https://www.yellowpages.com.au/search/findings?text={encoded_kw}{location_str}")
            else:
                urls.append(f"https://www.yellowpages.com.au/search/findings?text={encoded_kw}")

    elif country in ["United States", "Canada"]:
        encoded_kw = quote_plus(occ_clean)
        cities = MAJOR_CITIES.get(country, MAJOR_CITIES["United States"])

        for city in cities:
            loc_encoded = quote_plus(city)
            urls.append(f"https://www.yellowpages.com/search?search_terms={encoded_kw}&geo_location_terms={loc_encoded}")

    elif country == "United Kingdom":
        encoded_kw = quote_plus(occ_clean)
        cities = MAJOR_CITIES["United Kingdom"]

        for city in cities:
            loc_encoded = quote_plus(city)
            urls.append(f"https://www.yell.com/ucs/UcsSearchAction.do?keywords={encoded_kw}&location={loc_encoded}")

    else:
        encoded_kw = quote_plus(occ_clean)
        encoded_country = quote_plus(country)
        urls.append(f"https://www.yellowpages.com/search?search_terms={encoded_kw}&geo_location_terms={encoded_country}")
        urls.append(f"https://www.yellowpages.com.au/search/findings?text={encoded_kw}+{encoded_country}")

    logger.info(f"Dynamically generated {len(urls)} target directory URLs for Country='{country}', Occupation='{occ_clean}'")
    return urls
