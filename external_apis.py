"""
SerpAPI Google Search Dorking & Numverify Phone Verification Engine
Provides live Google search URL discovery via SerpAPI and active line validation via Numverify.
"""

import os
from bs4 import BeautifulSoup
import re
import logging
import requests
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger("ExternalAPIs")

SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
NUMVERIFY_KEY = os.getenv("NUMVERIFY_KEY", "").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()


def fetch_tavily_content(country: str, occupation: str, limit: int = 5) -> list[str]:
    """
    Query Tavily AI Search API for deep web scraping of real contact directories.
    Returns raw scraped markdown/content strings.
    """
    if not TAVILY_API_KEY:
        logger.info("Tavily: TAVILY_API_KEY not configured. Skipping Tavily deep web search.")
        return []

    query = f'"{occupation}" phone directory contact list "{country}"'
    logger.info(f"Tavily: Performing deep AI web search for '{query}'...")
    
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "search_depth": "advanced",
        "include_answer": True,
        "include_raw_content": True,
        "max_results": limit
    }

    try:
        resp = requests.post("https://api.tavily.com/search", json=payload, timeout=20)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            contents = []
            for r in results:
                raw_c = r.get("raw_content") or r.get("content") or ""
                if len(raw_c) > 200:
                    contents.append(raw_c[:25000])
            logger.info(f"Tavily successfully scraped {len(contents)} deep web content pages.")
            return contents
        else:
            logger.warning(f"Tavily error: HTTP {resp.status_code} - {resp.text[:150]}")
    except Exception as e:
        logger.error(f"Tavily search request failed: {e}")

    return []


def validate_api_keys():
    """
    Performs a simple validation on API keys on startup.
    Logs a clear warning if a key seems invalid or is missing.
    """
    logger.info("Validating external API keys...")
    if not SERPAPI_KEY:
        logger.warning("SerpAPI: SERPAPI_KEY is not set. Live URL discovery will be disabled.")
    elif len(SERPAPI_KEY) < 20:
        logger.warning("SerpAPI: SERPAPI_KEY appears to be too short. Please verify it.")

    if not NUMVERIFY_KEY:
        logger.warning("Numverify: NUMVERIFY_KEY is not set. Phone validation will be skipped.")
    elif len(NUMVERIFY_KEY) < 20:
        logger.warning("Numverify: NUMVERIFY_KEY appears to be too short. Please verify it.")

    # Check keys for AI/Scraping providers, which are critical
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not firecrawl_key:
        logger.error("CRITICAL: FIRECRAWL_API_KEY is missing. The primary scraping pipeline will fail.")

    cerebras_key = os.getenv("CEREBRAS_API_KEY", "").strip()
    if not cerebras_key:
        logger.warning("Cerebras: CEREBRAS_API_KEY is missing. AI extraction will fall back to other providers.")

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        logger.warning("Groq: GROQ_API_KEY is missing. AI extraction fallback will be limited.")


def fetch_serpapi_urls(country: str, occupation: str, limit: int = 10) -> list[str]:
    """
    Query Google live via SerpAPI for target country & occupation search dorks.
    Returns a list of live organic result URLs.
    """
    if not SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not configured. Falling back to registry targets.")
        return []

    # High-Yield Directories & Specialized Hub Dorks
    query_templates = [
        f'"{occupation}" contact phone number directory "{country}" -filetype:pdf -site:instagram.com -site:wikipedia.org',
        f'site:yellowpages.* OR site:gelbseiten.de OR site:dasoertliche.de OR site:tel.search.ch "{occupation}" "{country}"',
        f'site:doctena.de OR site:jameda.de OR site:healthgrades.com OR site:zocdoc.com "{occupation}" "{country}"',
        f'site:avvo.com OR site:martindale.com OR site:zillow.com OR site:redfin.com "{occupation}" "{country}"',
        f'site:clutch.co OR site:bark.com OR site:crunchbase.com "{occupation}" "{country}"',
        f'inurl:"member-directory" "{occupation}" "{country}" -filetype:pdf'
    ]
    

    urls = set()
    query = query_templates[0] # Use the first query for the main request

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": limit,
        "async": True # Use async for faster parallel searches
    }
    search_ids = []

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

    # Dispatch multiple parallel searches for diverse results
    logger.info(f"SerpAPI: Dispatching {len(query_templates)} parallel searches for '{occupation}' in {country}...")
    for i, q_template in enumerate(query_templates):
        if i >= limit: break
        try:
            search_params = params.copy()
            search_params["q"] = q_template
            resp = requests.get("https://serpapi.com/search.json", params=search_params, timeout=5)
            if resp.status_code == 200:
                search_ids.append(resp.json()["search_metadata"]["id"])
        except Exception as e:
            logger.warning(f"SerpAPI dispatch notice: {e}")

    # Collect results from parallel searches
    for search_id in search_ids:
        try:
            result_url = f"https://serpapi.com/searches/{search_id}?api_key={SERPAPI_KEY}"
            # Wait for async result
            for _ in range(3): # Poll a few times
                resp = requests.get(result_url, timeout=10)
                if resp.status_code == 200 and "organic_results" in resp.json():
                    data = resp.json()
                    found_urls = [r["link"] for r in data.get("organic_results", []) if "link" in r and r["link"].startswith("http")]
                    urls.update(found_urls)
                    break
        except Exception as e:
            logger.warning(f"SerpAPI result collection notice: {e}")

    logger.info(f"SerpAPI successfully fetched {len(urls)} unique live organic URLs from {len(search_ids)} queries.")
    return list(urls)[:limit]


def fetch_duckduckgo_urls(country: str, occupation: str, cities: list, limit: int = 5) -> list[str]:
    """
    Query DuckDuckGo's HTML version for target URLs. Free alternative to SerpAPI.
    """
    urls = set()
    # Use more diverse search queries for better results
    search_queries = [
        f'"{occupation}" contact phone directory {country}',
        f'"{occupation}" member list "{country}"',
        f'"{occupation}" directory "{country}"'
    ]
    for city in cities[:2]: # Add a couple of city-specific searches
        search_queries.append(f'"{occupation}" contact "{city}"')

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    for query in search_queries:
        if len(urls) >= limit:
            break
        try:
            logger.info(f"DuckDuckGo: Querying for '{query}'...")
            resp = requests.post("https://html.duckduckgo.com/html/", data={"q": query}, headers=headers, timeout=8)
            if resp.status_code == 200:
                # Basic regex to find result URLs in DDG's simple HTML
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = soup.find_all('a', class_='result__a')
                for link in links:
                    clean_url = requests.utils.unquote(link['href'].split("uddg=")[-1])
                    if clean_url.startswith("http"):
                        urls.add(clean_url)
            else:
                logger.warning(f"DuckDuckGo search failed with status {resp.status_code}")
        except Exception as e:
            logger.error(f"DuckDuckGo request failed: {e}")

    logger.info(f"DuckDuckGo successfully fetched {len(urls)} live organic URLs.")
    return list(urls)[:limit]

def verify_phone_number(phone: str, default_country_code: str = "") -> dict:
    """
    Query Numverify API to validate phone number line status and metadata.
    """
    if not NUMVERIFY_KEY or not phone: # If no key or phone, we can't validate.
        return None

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
        resp = requests.get("https://apilayer.net/api/validate", params=params, timeout=8) # Use HTTPS for security
        if resp.status_code == 200:
            data = resp.json()
            is_valid = data.get("valid", False) # Default to False if 'valid' key is missing
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

    # If API call fails, we cannot guarantee validity.
    return None
