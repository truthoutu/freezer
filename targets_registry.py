"""
Target Directory Registry - Live Production Sources
Contains real, public directory search URLs for Germany, Switzerland, Australia, United States, and Canada.
"""

TARGET_SOURCES = {
    "Germany": {
        "Nurse": [
            "https://www.gelbenseiten.de/suche/pflegedienst/bundesweit",
            "https://www.dasoertliche.de/Themen/Krankenschwester"
        ],
        "Doctor": [
            "https://www.gelbenseiten.de/suche/aerzte/bundesweit",
            "https://www.dasoertliche.de/Themen/Arzt"
        ],
        "Realtor": [
            "https://www.gelbenseiten.de/suche/immobilienmakler/bundesweit"
        ],
        "Lawyer": [
            "https://www.gelbenseiten.de/suche/rechtsanwalt/bundesweit"
        ],
        "default": [
            "https://www.gelbenseiten.de/suche/pflegedienst/bundesweit"
        ]
    },
    "Switzerland": {
        "Nurse": [
            "https://tel.search.ch/?was=Infirmiere&wo=Schweiz"
        ],
        "Doctor": [
            "https://tel.search.ch/?was=Arzt&wo=Schweiz"
        ],
        "Lawyer": [
            "https://tel.search.ch/?was=Avocat&wo=Schweiz"
        ],
        "default": [
            "https://tel.search.ch/?was=Infirmiere&wo=Schweiz"
        ]
    },
    "Australia": {
        "Nurse": [
            "https://www.yellowpages.com.au/search/findings?text=nurse"
        ],
        "Doctor": [
            "https://www.yellowpages.com.au/search/findings?text=doctor"
        ],
        "Realtor": [
            "https://www.yellowpages.com.au/search/findings?text=real+estate+agent"
        ],
        "Lawyer": [
            "https://www.yellowpages.com.au/search/findings?text=solicitor"
        ],
        "default": [
            "https://www.yellowpages.com.au/search/findings?text=nurse"
        ]
    },
    "United States": {
        "Nurse": [
            "https://www.yellowpages.com/search?search_terms=nurse&geo_location_terms=NY"
        ],
        "Realtor": [
            "https://www.yellowpages.com/search?search_terms=real+estate+agent&geo_location_terms=NY"
        ],
        "Lawyer": [
            "https://www.yellowpages.com/search?search_terms=lawyer&geo_location_terms=NY"
        ],
        "default": [
            "https://www.yellowpages.com/search?search_terms=nurse&geo_location_terms=NY"
        ]
    }
}


def get_default_sources(country: str, occupation: str) -> list[str]:
    c_sources = TARGET_SOURCES.get(country, TARGET_SOURCES.get("United States", {}))
    sources = c_sources.get(occupation, c_sources.get("default", ["https://www.yellowpages.com/search?search_terms=nurse"]))
    return sources
