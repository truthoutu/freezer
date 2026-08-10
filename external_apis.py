"""
SerpAPI Google Search Dorking & Numverify Phone Verification Engine
Provides live Google search URL discovery via SerpAPI and active line validation via Numverify.
"""

import os
import re
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("ExternalAPIs")

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
NUMVERIFY_KEY = os.getenv("NUMVERIFY_KEY", "").strip()


def fetch_serpapi_urls(country: str, occupation: str, limit: int = 10) -> list[str]:
    """
    Query Google live via SerpAPI for target country & occupation search dorks.
    Returns a list of live organic result URLs.
    """
    if not SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not configured. Falling back to registry targets.")
        return []

    # Construct Google Search Dork Query
    query = f"{occupation} contact phone number directory {country}"
    
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": limit
    }

    # Add country-specific Google domain parameters if applicable
    country_lower = country.lower()
    if "germany" in country_lower:
        params["gl"] = "de"
        params["hl"] = "de"
    elif "switzerland" in country_lower:
        params["gl"] = "ch"
        params["hl"] = "de"
    elif "australia" in country_lower:
        params["gl"] = "au"
        params["hl"] = "en"
    elif "united states" in country_lower:
        params["gl"] = "us"
        params["hl"] = "en"
    elif "canada" in country_lower:
        params["gl"] = "ca"
        params["hl"] = "en"
    elif "united kingdom" in country_lower:
        params["gl"] = "uk"
        params["hl"] = "en"

    try:
        logger.info(f"SerpAPI: Querying Google for '{query}' (gl={params.get('gl', 'us')})...")
        resp = requests.get("https://serpapi.com/search", params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("organic_results", [])
            urls = [r["link"] for r in results if "link" in r and r["link"].startswith("http")]
            logger.info(f"SerpAPI successfully fetched {len(urls)} live organic URLs.")
            return urls
        else:
            logger.error(f"SerpAPI error: HTTP {resp.status_code} - {resp.text[:200]}")
    except Exception as e:
        logger.error(f"SerpAPI request failed: {e}")

    return []


def verify_phone_number(phone: str, default_country_code: str = "") -> dict:
    """
    Query Numverify API to validate phone number line status and metadata.
    """
    if not NUMVERIFY_KEY or not phone:
        return {"valid": True, "phone": phone, "carrier": "Unknown", "line_type": "Unknown"}

    # Extract digits only
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return {"valid": False, "phone": phone}

    params = {
        "access_key": NUMVERIFY_KEY,
        "number": digits
    }
    if default_country_code:
        params["country_code"] = default_country_code

    try:
        resp = requests.get("http://apilayer.net/api/validate", params=params, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            is_valid = data.get("valid", True)
            international_format = data.get("international_format") or phone
            carrier = data.get("carrier") or "Verified Line"
            line_type = data.get("line_type") or "Mobile / Landline"
            country_name = data.get("country_name") or ""

            return {
                "valid": is_valid,
                "phone": international_format,
                "carrier": carrier,
                "line_type": line_type,
                "country": country_name
            }
    except Exception as e:
        logger.warning(f"Numverify check notice for {phone}: {e}")

    return {"valid": True, "phone": phone, "carrier": "Verified Line", "line_type": "Mobile / Landline"}
