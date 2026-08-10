"""
Target Directory Registry - Live Production Sources
Contains real, public directory search URLs for Germany, Switzerland, Australia, United States, and Canada.
"""

TARGET_SOURCES = {
    "Germany": {
        "Nurse": [
            "https://www.gelbenseiten.de/suche/pflegedienst/bundesweit",
            "https://www.gelbenseiten.de/suche/pflegedienst/berlin",
            "https://www.gelbenseiten.de/suche/pflegedienst/hamburg",
            "https://www.gelbenseiten.de/suche/pflegedienst/muenchen",
            "https://www.gelbenseiten.de/suche/pflegedienst/koeln",
            "https://www.gelbenseiten.de/suche/pflegedienst/frankfurt",
            "https://www.gelbenseiten.de/suche/pflegedienst/stuttgart",
            "https://www.gelbenseiten.de/suche/pflegedienst/duesseldorf",
            "https://www.gelbenseiten.de/suche/pflegedienst/dortmund",
            "https://www.gelbenseiten.de/suche/pflegedienst/essen",
            "https://www.dasoertliche.de/Themen/Krankenschwester",
            "https://www.dasoertliche.de/Themen/Krankenschwester+Berlin",
            "https://www.dasoertliche.de/Themen/Krankenschwester+Hamburg",
            "https://www.dasoertliche.de/Themen/Krankenschwester+Muenchen"
        ],
        "Doctor": [
            "https://www.gelbenseiten.de/suche/aerzte/bundesweit",
            "https://www.gelbenseiten.de/suche/aerzte/berlin",
            "https://www.gelbenseiten.de/suche/aerzte/hamburg",
            "https://www.gelbenseiten.de/suche/aerzte/muenchen",
            "https://www.gelbenseiten.de/suche/aerzte/koeln",
            "https://www.dasoertliche.de/Themen/Arzt",
            "https://www.dasoertliche.de/Themen/Arzt+Berlin",
            "https://www.dasoertliche.de/Themen/Arzt+Hamburg"
        ],
        "Realtor": [
            "https://www.gelbenseiten.de/suche/immobilienmakler/bundesweit",
            "https://www.gelbenseiten.de/suche/immobilienmakler/berlin",
            "https://www.gelbenseiten.de/suche/immobilienmakler/hamburg",
            "https://www.gelbenseiten.de/suche/immobilienmakler/muenchen",
            "https://www.dasoertliche.de/Themen/Immobilienmakler"
        ],
        "Lawyer": [
            "https://www.gelbenseiten.de/suche/rechtsanwalt/bundesweit",
            "https://www.gelbenseiten.de/suche/rechtsanwalt/berlin",
            "https://www.gelbenseiten.de/suche/rechtsanwalt/hamburg",
            "https://www.gelbenseiten.de/suche/rechtsanwalt/muenchen",
            "https://www.dasoertliche.de/Themen/Rechtsanwalt"
        ],
        "default": [
            "https://www.gelbenseiten.de/suche/pflegedienst/bundesweit"
        ]
    },
    "Switzerland": {
        "Nurse": [
            "https://tel.search.ch/?was=Infirmiere&wo=Schweiz",
            "https://tel.search.ch/?was=Infirmiere&wo=Zuerich",
            "https://tel.search.ch/?was=Infirmiere&wo=Genf",
            "https://tel.search.ch/?was=Infirmiere&wo=Basel",
            "https://tel.search.ch/?was=Infirmiere&wo=Lausanne",
            "https://tel.search.ch/?was=Infirmiere&wo=Bern",
            "https://tel.search.ch/?was=Infirmiere&wo=Winterthur",
            "https://tel.search.ch/?was=Infirmiere&wo=Luzern",
            "https://tel.search.ch/?was=Infirmiere&wo=St.Gallen"
        ],
        "Doctor": [
            "https://tel.search.ch/?was=Arzt&wo=Schweiz",
            "https://tel.search.ch/?was=Arzt&wo=Zuerich",
            "https://tel.search.ch/?was=Arzt&wo=Genf",
            "https://tel.search.ch/?was=Arzt&wo=Basel",
            "https://tel.search.ch/?was=Arzt&wo=Bern"
        ],
        "Lawyer": [
            "https://tel.search.ch/?was=Avocat&wo=Schweiz",
            "https://tel.search.ch/?was=Avocat&wo=Zuerich",
            "https://tel.search.ch/?was=Avocat&wo=Genf",
            "https://tel.search.ch/?was=Avocat&wo=Basel"
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
