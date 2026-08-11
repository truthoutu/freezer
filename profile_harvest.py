"""
Profile script to pinpoint exact slow function in api_harvest
"""

import time
import os
from dotenv import load_dotenv

load_dotenv()

print("=== PROFILING HARVEST PIPELINE ===")

# 1. Test URL Discovery (SerpAPI / DuckDuckGo)
t0 = time.time()
from external_apis import fetch_serpapi_urls, fetch_duckduckgo_urls, fetch_tavily_content
from targets_registry import get_default_sources

print("1. Testing SerpAPI...")
urls = fetch_serpapi_urls("Germany", "Dentist", limit=3)
print(f"   SerpAPI returned {len(urls)} URLs in {round(time.time() - t0, 2)}s")

if not urls:
    t1 = time.time()
    print("   Testing DuckDuckGo fallback...")
    urls = fetch_duckduckgo_urls("Germany", "Dentist", [], limit=3)
    print(f"   DuckDuckGo returned {len(urls)} URLs in {round(time.time() - t1, 2)}s")

# 2. Test Tavily
t2 = time.time()
print("2. Testing Tavily AI Search...")
tavily_pages = fetch_tavily_content("Germany", "Dentist", limit=3)
print(f"   Tavily returned {len(tavily_pages)} pages in {round(time.time() - t2, 2)}s")

# 3. Test Firecrawl
t3 = time.time()
print("3. Testing Firecrawl...")
from server import _fetch_content_firecrawl
fc_pages = _fetch_content_firecrawl("test", urls[:2], os.getenv("FIRECRAWL_API_KEY", ""))
print(f"   Firecrawl returned {len(fc_pages)} pages in {round(time.time() - t3, 2)}s")

print("=== PROFILING COMPLETE ===")
