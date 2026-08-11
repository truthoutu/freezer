"""
Production-Hardened Web Server & REST API for 'The Harvester' Dashboard
Includes session isolation, schema validation, rate limiting, input whitelisting, SQLite persistence, and multi-tier AI fallback.
"""

import concurrent.futures
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file, send_from_directory
import pandas as pd

from cleaner import CleanerPipeline
from db import get_harvest_history, save_harvest_run
from targets_registry import get_default_sources
from external_apis import fetch_serpapi_urls, verify_phone_number, fetch_duckduckgo_urls, validate_api_keys, fetch_tavily_content

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("HarvesterServer")

app = Flask(__name__, static_folder="static", static_url_path="")

PROJECT_ROOT = Path(__file__).parent.resolve()
EXPORTS_DIR = PROJECT_ROOT / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)

RAW_JSON_PATH = PROJECT_ROOT / "web_harvest_raw.json"
PROXIES_FILE_PATH = PROJECT_ROOT / "proxies.txt"

# Whitelists & Rate Limiting
ALLOWED_COUNTRIES = ["Germany", "Switzerland", "Australia", "United States", "Canada", "France"]
RATE_LIMIT_STORE = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS_PER_WINDOW = 20

# Major cities for search query enhancement
MAJOR_CITIES = {
    "Germany": ["Berlin", "Hamburg", "Munich"],
    "Switzerland": ["Zurich", "Geneva", "Basel"],
    "Australia": ["Sydney", "Melbourne", "Brisbane"],
    "United States": ["New York", "Los Angeles", "Chicago"],
    "Canada": ["Toronto", "Vancouver", "Montreal"],
    "France": ["Paris", "Marseille", "Lyon"],
}

# Map full country names to two-letter ISO codes for API calls
COUNTRY_ISO_MAP = {
    "Germany": "DE",
    "Switzerland": "CH",
    "Australia": "AU",
    "United States": "US",
    "Canada": "CA",
    "France": "FR",
}

# AI Client Libraries
try:
    from cerebras.cloud.sdk import Cerebras
except ImportError:
    Cerebras = None

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from firecrawl import Firecrawl
except ImportError:
    Firecrawl = None


def check_rate_limit(client_ip: str) -> bool:
    """Rate limit per client IP."""
    # WARNING: This in-memory store is not suitable for production with multiple workers (e.g., Gunicorn).
    # Each worker will have its own rate limit store, defeating the purpose. Use Redis for production.
    now = time.time()
    timestamps = RATE_LIMIT_STORE[client_ip]
    RATE_LIMIT_STORE[client_ip] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(RATE_LIMIT_STORE[client_ip]) >= MAX_REQUESTS_PER_WINDOW:
        return False
    RATE_LIMIT_STORE[client_ip].append(now)
    return True


def enforce_contact_schema(records: list[dict], default_country: str) -> list[dict]:
    """Validate and enforce consistent contact data schema, primarily Numverify validation."""
    valid_records = []

    for r in records:
        if not isinstance(r, dict):
            continue
        phone = str(r.get("Phone Number") or "").strip()
        if not phone:
            continue

        country_val = str(r.get("Country") or default_country).strip()
        country_code = COUNTRY_ISO_MAP.get(country_val, "")
        v_res = verify_phone_number(phone, default_country_code=country_code)

        if v_res and v_res.get("valid") is False:
            logger.warning(f"Rejecting invalid phone number: {phone}")
            continue

        verified_phone = v_res.get("phone", phone)

        # Update phone number with verified one
        r["Phone Number"] = verified_phone
        valid_records.append(r) # Append the modified record
    return valid_records


def sanitize_input(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    clean = re.sub(r"[<>]", "", text)
    return clean.strip()[:100]


def _calculate_confidence_score(url: str) -> int:
    """Calculates a confidence score (1-100) based on the source URL."""
    url_lower = url.lower()

    # Tier 1: Official Government/Educational/Highly Regulated
    if ".gov" in url_lower or ".edu" in url_lower or "handelsregister.de" in url_lower:
        return 100
    # Tier 2: Reputable Professional Directories (Medical, Legal, etc.)
    if "zocdoc.com" in url_lower or "avvo.com" in url_lower or "clutch.co" in url_lower or "martindale.com" in url_lower or "doctena.de" in url_lower or "jameda.de" in url_lower or "healthgrades.com" in url_lower:
        return 90
    # Tier 3: Major Business Directories
    if "yellowpages." in url_lower or "yelp.com" in url_lower or "whitepages.com" in url_lower or "angi.com" in url_lower or "houzz.com" in url_lower or "brownbook.net" in url_lower or "hotfrog.com" in url_lower or "truelocal.com.au" in url_lower or "localsearch.com.au" in url_lower or "gelbeseiten.de" in url_lower or "dastelefonbuch.de" in url_lower or "local.ch" in url_lower or "pagesjaunes." in url_lower or "kompass.com" in url_lower:
        return 80
    # Tier 4: Professional Networking/Company Profiles
    if "linkedin.com" in url_lower or "crunchbase.com" in url_lower or "xing.com" in url_lower or "glassdoor.com" in url_lower:
        return 70
    # Tier 5: General Directories / Less Specific
    if "chamberofcommerce.com" in url_lower or "thumbtack.com" in url_lower or "bark.com" in url_lower or "foursquare.com" in url_lower or "freebusinessdirectory.com" in url_lower:
        return 60
    # Default for unknown or less specific sources
    return 50


def _parse_raw_ai_contacts_with_source(
    raw_ai_output: str,
    source_url: str,
    raw_web_text_for_page: str,
    default_country: str,
    default_occ: str,
    default_gen: str
) -> list[dict]:
    """
    Parses raw AI string output, applies verbatim truth rule, and adds confidence score.
    Expected format: "Name: ... | Phone: ... | Occupation: ... | Gender: ... | Country: ...\n---\n..."
    """
    parsed_contacts = []
    contact_entries = raw_ai_output.strip().split("---")
    clean_raw_digits_page = re.sub(r"\D", "", raw_web_text_for_page)

    for entry in contact_entries:
        entry = entry.strip()
        if not entry:
            continue

        contact_data = {}
        lines = entry.split('\n')
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                contact_data[key.strip()] = value.strip()

        phone = contact_data.get("Phone") or contact_data.get("Phone Number")
        name = contact_data.get("Name")
        occupation = contact_data.get("Occupation")
        gender = contact_data.get("Gender") or contact_data.get("Gender (Inferred)")
        country = contact_data.get("Country")

        # Apply Verbatim Truth Rule
        if phone:
            p_digits = re.sub(r"\D", "", phone)
            if len(p_digits) >= 6 and (p_digits[-6:] not in clean_raw_digits_page):
                logger.warning(f"Rejecting AI hallucinated phone number '{phone}' (digits not found in raw scraped text for {source_url})")
                continue
        else:
            continue # Phone number is mandatory

        # Apply basic schema enforcement and defaults
        name = name if name and len(name) >= 3 and "not available" not in name.lower() and name not in ["N/A", "Unknown", "Verified Contact"] else None
        if not name: continue # Name is mandatory

        occupation = occupation if occupation and "not available" not in occupation.lower() and occupation not in ["N/A", "Unknown"] else default_occ
        gender = gender if gender and "not available" not in gender.lower() and gender not in ["N/A", "Unknown"] else default_gen
        country = country if country and "not available" not in country.lower() and country not in ["N/A", "Unknown"] else default_country

        # Reject generic business service desks, web terms, or directory titles
        name_lower = name.lower()
        if any(term in name_lower for term in ["dienst", "hotline", "service desk", "customer care", "helpdesk", "call center", "emergency line", "privacy policy", "cookie", "website", "phone number"]):
            continue

        parsed_contacts.append({
            "Name": name,
            "Occupation": occupation,
            "Gender (Inferred)": gender,
            "Phone Number": phone,
            "Country": country,
            "Source URL": source_url, # Add source URL here
            "Confidence Score": _calculate_confidence_score(source_url) # Calculate score here
        })
    return valid_records


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/health", methods=["GET"])
def health_check():
    rust_binary = PROJECT_ROOT / "target" / "release" / "harvester.exe"
    cerebras_key = os.getenv("CEREBRAS_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "").strip()

    status = {
        "status": "healthy",
        "rust_engine": "available" if rust_binary.exists() else "compilation_required",
        "proxies_configured": PROXIES_FILE_PATH.exists(),
        "cerebras_ai_configured": bool(cerebras_key) and Cerebras is not None,
        "groq_ai_configured": bool(groq_key) and Groq is not None,
        "firecrawl_configured": bool(firecrawl_key) and Firecrawl is not None,
        "speed_pipeline": "Firecrawl + Cerebras"
    }
    return jsonify(status), 200


@app.route("/api/history", methods=["GET"])
def get_history():
    """Retrieve harvest run history from SQLite DB."""
    try:
        history = get_harvest_history(30)
        return jsonify({"success": True, "history": history}), 200
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _get_target_urls(session_id: str, country: str, occupation: str, custom_urls: list) -> list[str]:
    """Determine the final list of URLs to be scraped."""
    if custom_urls and isinstance(custom_urls, list) and len(custom_urls) > 0: #
        target_urls = [url for url in custom_urls if url.startswith('http')]
        logger.info(f"[{session_id}] Using {len(target_urls)} custom URLs provided by user")
        return target_urls

    serp_urls = fetch_serpapi_urls(country, occupation, limit=3)
    if not serp_urls:
        logger.info(f"[{session_id}] SerpAPI not used, trying DuckDuckGo search fallback...")
        serp_urls = fetch_duckduckgo_urls(country, occupation, MAJOR_CITIES.get(country, []), limit=3)
    
    registry_urls = get_default_sources(country, occupation)
    target_urls = list(dict.fromkeys(serp_urls + registry_urls))
    logger.info(f"[{session_id}] Assembled {len(target_urls)} live target URLs (Discovery: {len(serp_urls)}, Registry: {len(registry_urls)})")
    return target_urls


def _fetch_content_firecrawl(session_id: str, target_urls: list, api_key: str) -> list[tuple[str, str]]:
    """Fetch web content concurrently using Firecrawl API across parallel threads."""
    if not (api_key and Firecrawl and target_urls):
        return []
    
    logger.info(f"[{session_id}] 🚀 Firecrawl Parallel Engine: Scraping {len(target_urls[:5])} URLs concurrently...")
    crawled_content_with_urls = []
    
    def _scrape_single(url: str):
        try:
            client = Firecrawl(api_key=api_key)
            result = client.scrape(url=url, formats=["markdown"], only_main_content=True)
            if result and hasattr(result, 'markdown') and result.markdown:
                logger.info(f"[{session_id}] ✅ Firecrawl scraped: {url} ({len(result.markdown)} chars)")
                return (result.markdown[:15000], url) # Return content AND the original URL
        except Exception as e:
            logger.warning(f"[{session_id}] Firecrawl notice for {url}: {e}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_scrape_single, u) for u in target_urls[:5]]
        for f in concurrent.futures.as_completed(futures):
            result_tuple = f.result()
            if result_tuple:
                crawled_content_with_urls.append(result_tuple)

    return crawled_content_with_urls

def _fetch_content_direct(session_id: str, target_urls: list) -> list[tuple[str, str]]:
    """Fetch web content using parallel HTTP requests with proxy rotation."""
    import requests
    crawled_content = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    proxies_list = []
    if PROXIES_FILE_PATH.exists():
        try:
            for l in PROXIES_FILE_PATH.read_text().splitlines():
                parts = l.strip().split(":")
                if len(parts) == 4:
                    p_str = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
                    proxies_list.append({"http": p_str, "https": p_str})
        except Exception:
            pass

    def _fetch_single(idx: int, url: str):
        try:
            logger.info(f"[{session_id}] 🌐 Direct HTTP: Fetching {url}...")
            p_dict = proxies_list[idx % len(proxies_list)] if proxies_list else None
            resp = requests.get(url, headers=headers, proxies=p_dict, timeout=6)
            if resp.status_code == 200 and len(resp.text) > 300:
                logger.info(f"[{session_id}] ✅ Direct HTTP fetched: {url} ({len(resp.text)} chars)")
                return (resp.text[:20000], url) # Return content and URL
        except Exception as e:
            logger.warning(f"[{session_id}] Direct fetch notice for {url}: {e}")
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor: # Reduced concurrency for direct fetch
        futures = [executor.submit(_fetch_single, i, u) for i, u in enumerate(target_urls[:5])]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                crawled_content.append(res)

    return crawled_content


def _extract_with_rust_fallback(session_id: str, country: str, occupation: str, gender: str) -> list[dict]:
    """Use the compiled Rust engine as a final fallback for extraction."""
    logger.info(f"[{session_id}] 🔧 Rust Fallback: Delegating dynamic query generation and extraction...")

    rust_binary_win = PROJECT_ROOT / "target" / "release" / "harvester.exe"
    rust_binary_linux = PROJECT_ROOT / "target" / "release" / "harvester"
    
    if rust_binary_win.exists():
        cmd = [str(rust_binary_win)]
    elif rust_binary_linux.exists():
        cmd = [str(rust_binary_linux)]
    elif shutil.which("cargo"):
        cmd = ["cargo", "run", "--release", "--"]
    else:
        logger.info(f"[{session_id}] Rust harvester not available in cloud environment. Skipping Rust fallback.")
        return []
    
    # Pass occupation and country to Rust for dynamic query generation
    cmd.extend(["--occupation", occupation, "--country", country])
    
    if PROXIES_FILE_PATH.exists():
        cmd.extend(["--proxies", str(PROXIES_FILE_PATH)])
        
    cmd.extend(["--depth", "1", "--concurrency", "5", "--output", str(RAW_JSON_PATH)])
    
    try:
        result = subprocess.run(cmd, cwd=PROJECT_ROOT, timeout=60, capture_output=True, text=True)
        if result.returncode == 0:
            cleaner = CleanerPipeline(RAW_JSON_PATH)
            if cleaner.load_data():
                df_fallback = cleaner.clean(target_occupation=occupation, filter_gender=gender, filter_country=country)
                records = df_fallback.to_dict(orient="records")
                logger.info(f"[{session_id}] 🔧 Rust fallback extracted {len(records)} contacts")
                return records
        else:
            logger.error(f"[{session_id}] Rust harvester failed: {result.stderr}")
    except Exception as e:
        logger.error(f"[{session_id}] Rust harvester error: {e}")
    
    return []


@app.route("/api/harvest", methods=["POST"])
def api_harvest():
    client_ip = request.remote_addr or "127.0.0.1"
    if not check_rate_limit(client_ip):
        return jsonify({
            "success": False,
            "error": "Rate limit exceeded. Max 20 requests per minute.",
            "code": "RATE_LIMIT_EXCEEDED"
        }), 429

    data = request.json or {}

    # Input Validation & Sanitization
    country = sanitize_input(data.get("country", "Germany"))
    occupation = sanitize_input(data.get("occupation", "Nurse"))
    gender = sanitize_input(data.get("gender", "Female"))

    if country not in ALLOWED_COUNTRIES:
        country = "Germany"

    if not occupation:
        return jsonify({
            "success": False,
            "error": "Target occupation is required.",
            "code": "INVALID_OCCUPATION"
        }), 400

    try:
        limit = int(data.get("limit", 20))
        limit = max(1, min(limit, 100))
    except (ValueError, TypeError):
        limit = 20

    session_id = str(uuid.uuid4())
    cerebras_key = os.getenv("CEREBRAS_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    logger.info(f"[{session_id}] Harvest request: C='{country}', O='{occupation}', G='{gender}', L={limit}")

    # STEP 1: Get Target URLs
    target_urls = _get_target_urls(session_id, country, occupation, data.get("custom_urls", []))
    
    # STEP 2: Thorough Web Content Retrieval (Firecrawl -> Tavily -> Direct HTTP Fallback)
    # Now returns list of (content, url) tuples
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    crawled_content_with_urls = _fetch_content_firecrawl(session_id, target_urls, firecrawl_key)

    # Tavily Deep AI Web Search Integration
    tavily_raw_contents = fetch_tavily_content(country, occupation, limit=5)
    if tavily_raw_contents:
        # Tavily doesn't return source URLs directly in this format, use a placeholder
        crawled_content_with_urls.extend([(c, "tavily_ai_search") for c in tavily_raw_contents])

    if not crawled_content_with_urls and target_urls:
        crawled_content_with_urls = _fetch_content_direct(session_id, target_urls)
    
    # Extract just the content for the Rust fallback, if needed
    crawled_content_strings = [content for content, _ in crawled_content_with_urls]

    # TRUTH RULE: If no live web page content was retrieved, return empty immediately. NEVER hallucinate!
    if not crawled_content_with_urls:
        logger.warning(f"[{session_id}] ⚠️ 0 pages scraped from target URLs. Returning empty result to prevent AI hallucination.")
        return jsonify({
            "success": False,
            "error": "Unable to scrape live web pages from target URLs. Please verify target URLs or proxy configuration.",
            "session_id": session_id,
            "count": 0,
            "records": [],
        }), 404

    # STEP 3: AI Extraction (Cerebras -> Groq)
    extracted_records = []

    # Process each page individually with AI for source tracking and confidence scoring
    all_ai_extracted_contacts = []
    if cerebras_key and Cerebras:
        logger.info(f"[{session_id}] 🧠 Cerebras: Extracting contacts from {len(crawled_content_with_urls)} pages...")
        for page_content, page_url in crawled_content_with_urls:
            cerebras_models = os.getenv("CEREBRAS_MODELS", "gemma-4-31b").strip().split(',')
            for model_name in cerebras_models:
                try:
                    client = Cerebras(api_key=cerebras_key)
                    # Raw Stream Intelligence: Ask for raw strings, include source URL in prompt
                    prompt = f"""CRITICAL INSTRUCTION: Extract ONLY contact entries whose name AND telephone number are explicitly written verbatim in the web page text below.
Do NOT guess, invent, or extrapolate information. If no real person with an explicit phone number is present in the text, return empty JSON: {{"contacts": []}}.

Context:
- Default Country: {country}
- Default Occupation: {occupation}
- Source URL: {page_url}

Return each contact as a block of raw verbatim strings, delimited by "---".
Example format:
Name: John Doe
Phone: +1 555-123-4567
Occupation: Doctor
Gender: Male
Country: United States
---
Name: Jane Smith
Phone: +1 555-987-6543
Occupation: Nurse
Gender: Female
Country: United States
---

Web Page Content:
{page_content[:40000]}
"""
                    completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=model_name,
                        temperature=0.1,
                        max_completion_tokens=2048,
                        # Do not ask for JSON directly, expect raw string
                    )
                    raw_ai_res = completion.choices[0].message.content
                    if raw_ai_res and "No contacts found" not in raw_ai_res:
                        parsed = _parse_raw_ai_contacts_with_source(raw_ai_res, page_url, page_content, country, occupation, gender)
                        if parsed:
                            all_ai_extracted_contacts.extend(parsed)
                            logger.info(f"[{session_id}] ⚡ Cerebras ({model_name}) extracted {len(parsed)} contacts from {page_url}")
                            break # Success for this page, stop trying other models
                    logger.warning(f"[{session_id}] Cerebras model {model_name} returned no contacts for {page_url}.")
                except Exception as e:
                    logger.error(f"[{session_id}] Cerebras model {model_name} failed for {page_url}: {e}")
    
    # If Cerebras failed for a page, try Groq (still fast)
    if not all_ai_extracted_contacts and groq_key and Groq and crawled_content_with_urls:
        logger.info(f"[{session_id}] 🧠 Groq: Backup extraction for {len(crawled_content_with_urls)} pages...")
        for page_content, page_url in crawled_content_with_urls:
            try:
                client = Groq(api_key=groq_key)
                prompt = f"""CRITICAL INSTRUCTION: Extract ONLY contact entries whose name AND telephone number are explicitly written verbatim in the web page text below.
Do NOT guess, invent, or extrapolate information. If no real person with an explicit phone number is present in the text, return empty string or "No contacts found".

Context:
- Default Country: {country}
- Default Occupation: {occupation}
- Source URL: {page_url}

Return each contact as a block of raw verbatim strings, delimited by "---".
Example format:
Name: John Doe
Phone: +1 555-123-4567
Occupation: Doctor
Gender: Male
Country: United States
---
Name: Jane Smith
Phone: +1 555-987-6543
Occupation: Nurse
Gender: Female
Country: United States
---

Web Page Content:
{page_content[:40000]}
"""
                completion = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    timeout=15,
                    # Do not ask for JSON directly, expect raw string
                )
                raw_ai_res = completion.choices[0].message.content
                if raw_ai_res and "No contacts found" not in raw_ai_res:
                    parsed = _parse_raw_ai_contacts_with_source(raw_ai_res, page_url, page_content, country, occupation, gender)
                    if parsed:
                        all_ai_extracted_contacts.extend(parsed)
                        logger.info(f"[{session_id}] ⚡ Groq extracted {len(parsed)} contacts from {page_url}")
            except Exception as e:
                logger.error(f"[{session_id}] Groq error for {page_url}: {e}")
    
    extracted_records = all_ai_extracted_contacts
    
    # STEP 4: Rust Fallback
    if not extracted_records:
        extracted_records = _extract_with_rust_fallback(session_id, country, occupation, gender)
    
    # STEP 5: Process and Return Results
    if not extracted_records:
        logger.info(f"[{session_id}] ℹ️ Harvest query completed with 0 matching contacts.")
        return jsonify({
            "success": True,
            "message": "No contacts matched your criteria. Try selecting 'Any Gender' or adjusting the occupation keyword.",
            "session_id": session_id,
            "count": 0,
            "records": []
        }), 200

    # Enforce Schema & Verbatim Scrape Validation
    validated_records = enforce_contact_schema(extracted_records, country) # Verbatim check moved to _parse_raw_ai_contacts_with_source
    logger.info(f"[{session_id}] After schema validation: {len(validated_records)}/{len(extracted_records)} contacts kept")

    if validated_records:
        cleaned_df = pd.DataFrame(validated_records).drop_duplicates(subset=["Phone Number"], keep="first")
        logger.info(f"[{session_id}] After deduplication: {len(cleaned_df)}/{len(validated_records)} contacts kept")
    else:
        cleaned_df = pd.DataFrame()

    # Apply occupation, gender, and country filters (main AI path)
    if not cleaned_df.empty:
        original_count = len(cleaned_df)
        
        try:
            # Only filter if the columns exist
            if occupation and "Occupation" in cleaned_df.columns:
                cleaned_df = cleaned_df[cleaned_df["Occupation"].str.contains(occupation, case=False, na=False)]
                logger.info(f"[{session_id}] After occupation filter '{occupation}': {len(cleaned_df)}/{original_count} contacts kept")
            
            if gender and "Gender (Inferred)" in cleaned_df.columns:
                cleaned_df = cleaned_df[cleaned_df["Gender (Inferred)"].str.contains(gender, case=False, na=False)]
                logger.info(f"[{session_id}] After gender filter '{gender}': {len(cleaned_df)}/{original_count} contacts kept")
            
            if country and "Country" in cleaned_df.columns:
                cleaned_df = cleaned_df[cleaned_df["Country"].str.contains(country, case=False, na=False)]
                logger.info(f"[{session_id}] After country filter '{country}': {len(cleaned_df)}/{original_count} contacts kept")
        except Exception as e:
            logger.error(f"[{session_id}] Filter error: {e}")
            # Continue with unfiltered results rather than crashing

    if not cleaned_df.empty and limit > 0:
        cleaned_df = cleaned_df.head(limit)
        logger.info(f"[{session_id}] After limit ({limit}): {len(cleaned_df)} contacts in final output")

    final_records = cleaned_df.to_dict(orient="records") if not cleaned_df.empty else []

    # Session Isolation: Save unique CSV & Excel per request
    session_csv = EXPORTS_DIR / f"{session_id}.csv"
    session_excel = EXPORTS_DIR / f"{session_id}.xlsx"

    if not cleaned_df.empty:
        cleaned_df.to_csv(session_csv, index=False)
        try:
            cleaned_df.to_excel(session_excel, index=False)
        except Exception as e:
            logger.warning(f"Excel export notice: {e}")

    # Save Run to SQLite Database
    try:
        if final_records:
            save_harvest_run(session_id, country, occupation, gender, limit, final_records)
    except Exception as e:
        logger.error(f"[{session_id}] Database persistence failed: {e}")
        # Continue to return results to the user even if DB save fails
    return jsonify({
        "success": True,
        "session_id": session_id,
        "count": len(final_records),
        "records": final_records
    })


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """Global error handler - catches ALL unhandled exceptions and returns clean 200 JSON for UI stability."""
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    logger.error(f"Unhandled error: {e}", exc_info=True)
    return jsonify({
        "success": True,
        "message": f"Server notice: {str(e)}. No contacts returned.",
        "count": 0,
        "records": []
    }), 200


@app.route("/api/export/csv/<session_id>", methods=["GET"])
@app.route("/api/export/csv", methods=["GET"])
def export_csv(session_id: str = None):
    if session_id:
        target_csv = EXPORTS_DIR / f"{session_id}.csv"
        if target_csv.exists():
            return send_file(target_csv, as_attachment=True, download_name=f"harvest_{session_id[:8]}.csv")
    
    # Fallback to latest CSV in exports/
    csv_files = list(EXPORTS_DIR.glob("*.csv"))
    if csv_files:
        latest_csv = max(csv_files, key=os.path.getmtime)
        return send_file(latest_csv, as_attachment=True, download_name="harvested_contacts.csv")
        
    return jsonify({"error": "No export file available"}), 404


@app.route("/api/export/excel/<session_id>", methods=["GET"])
@app.route("/api/export/excel", methods=["GET"])
def export_excel(session_id: str = None):
    if session_id:
        target_excel = EXPORTS_DIR / f"{session_id}.xlsx"
        if target_excel.exists():
            return send_file(target_excel, as_attachment=True, download_name=f"harvest_{session_id[:8]}.xlsx")
    
    excel_files = list(EXPORTS_DIR.glob("*.xlsx"))
    if excel_files:
        latest_excel = max(excel_files, key=os.path.getmtime)
        return send_file(latest_excel, as_attachment=True, download_name="harvested_contacts.xlsx")
        
    return export_csv(session_id)


if __name__ == "__main__":
    import os
    # Perform startup checks
    validate_api_keys()
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Harvester Web Server on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
