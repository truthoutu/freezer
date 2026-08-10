"""
Production-Hardened Web Server & REST API for 'The Harvester' Dashboard
Includes session isolation, schema validation, rate limiting, input whitelisting, SQLite persistence, and multi-tier AI fallback.
"""

import json
import logging
import os
import re
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
from db import get_harvest_history, init_db, save_harvest_run
from targets_registry import get_default_sources
from external_apis import fetch_serpapi_urls, verify_phone_number

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
ALLOWED_COUNTRIES = ["Germany", "Switzerland", "Australia", "United States", "Canada"]
RATE_LIMIT_STORE = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
MAX_REQUESTS_PER_WINDOW = 20

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

init_db()


def check_rate_limit(client_ip: str) -> bool:
    """Rate limit per client IP."""
    now = time.time()
    timestamps = RATE_LIMIT_STORE[client_ip]
    RATE_LIMIT_STORE[client_ip] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]
    if len(RATE_LIMIT_STORE[client_ip]) >= MAX_REQUESTS_PER_WINDOW:
        return False
    RATE_LIMIT_STORE[client_ip].append(now)
    return True


def sanitize_input(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    clean = re.sub(r"[<>]", "", text)
    return clean.strip()[:100]


def enforce_contact_schema(records: list[dict], default_country: str, default_occ: str, default_gen: str) -> list[dict]:
    """Validate and enforce consistent contact data schema."""
    valid_records = []
    for r in records:
        if not isinstance(r, dict):
            continue
        phone = str(r.get("Phone Number") or r.get("phone") or "").strip()
        if not phone or re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", phone):
            continue

        raw_name = str(r.get("Name") or r.get("name") or "").strip()
        if not raw_name or "not available" in raw_name.lower() or raw_name in ["N/A", "Unknown"]:
            name = "Verified Contact"
        else:
            name = raw_name

        raw_occ = str(r.get("Occupation") or r.get("occupation") or "").strip()
        if not raw_occ or "not available" in raw_occ.lower() or raw_occ in ["N/A", "Unknown"]:
            occ = default_occ
        else:
            occ = raw_occ

        raw_gen = str(r.get("Gender (Inferred)") or r.get("gender") or "").strip()
        if not raw_gen or "not available" in raw_gen.lower() or raw_gen in ["N/A", "Unknown"]:
            gender = default_gen
        else:
            gender = raw_gen

        raw_country = str(r.get("Country") or r.get("country") or "").strip()
        if not raw_country or "not available" in raw_country.lower() or raw_country in ["N/A", "Unknown"]:
            country_val = default_country
        else:
            country_val = raw_country

        # Validate line status with Numverify API
        v_res = verify_phone_number(phone)
        if not v_res.get("valid", True):
            logger.warning(f"Rejecting invalid phone number: {phone}")
            continue

        verified_phone = v_res.get("phone", phone)

        valid_records.append({
            "Name": name,
            "Occupation": occ,
            "Gender (Inferred)": gender,
            "Phone Number": verified_phone,
            "Country": country_val
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

    logger.info(f"[{session_id}] Harvest request: Country='{country}', Occupation='{occupation}', Gender='{gender}', Limit={limit}")

    extracted_records = []
    
    # SPEED-OPTIMIZED PIPELINE: Firecrawl → Cerebras → Results
    firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    
    # Get target URLs (custom URLs take priority)
    custom_urls = data.get("custom_urls", [])
    if custom_urls and isinstance(custom_urls, list) and len(custom_urls) > 0:
        # Use user-provided URLs
        target_urls = [url for url in custom_urls if url.startswith('http')]
        logger.info(f"[{session_id}] Using {len(target_urls)} custom URLs provided by user")
    else:
        # Query SerpAPI Google Search Dorking for live target URLs
        serp_urls = fetch_serpapi_urls(country, occupation, limit=5)
        registry_urls = get_default_sources(country, occupation)
        target_urls = list(dict.fromkeys(serp_urls + registry_urls))
        logger.info(f"[{session_id}] Assembled {len(target_urls)} live target URLs (SerpAPI: {len(serp_urls)}, Registry: {len(registry_urls)})")
    
    # STEP 1: Web Content Retrieval (Firecrawl -> Direct HTTP Fallback)
    crawled_content = []
    if firecrawl_key and Firecrawl and target_urls:
        logger.info(f"[{session_id}] 🚀 Firecrawl: Scraping target URLs...")
        try:
            firecrawl_client = Firecrawl(api_key=firecrawl_key)
            for url in target_urls[:2]:
                try:
                    result = firecrawl_client.scrape(
                        url=url,
                        formats=["markdown"],
                        only_main_content=True
                    )
                    if result and hasattr(result, 'markdown') and result.markdown:
                        crawled_content.append(result.markdown[:15000])
                        logger.info(f"[{session_id}] ✅ Firecrawl scraped: {url}")
                except Exception as e:
                    logger.warning(f"[{session_id}] Firecrawl notice for {url}: {e}")
                    break
        except Exception as e:
            logger.error(f"[{session_id}] Firecrawl client error: {e}")

    # Fallback to Direct HTTP fetch if Firecrawl returned 0 content
    if not crawled_content and target_urls:
        logger.info(f"[{session_id}] 🌐 Direct HTTP Fallback: Fetching live target web pages...")
        import requests
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        proxies_dict = None
        if PROXIES_FILE_PATH.exists():
            try:
                lines = [l.strip() for l in PROXIES_FILE_PATH.read_text().splitlines() if l.strip()]
                if lines:
                    parts = lines[0].split(":")
                    if len(parts) == 4:
                        p_str = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
                        proxies_dict = {"http": p_str, "https": p_str}
            except Exception:
                pass

        for url in target_urls[:3]:
            try:
                resp = requests.get(url, headers=headers, proxies=proxies_dict, timeout=8)
                if resp.status_code == 200 and len(resp.text) > 300:
                    crawled_content.append(resp.text[:20000])
                    logger.info(f"[{session_id}] ✅ Direct HTTP fetched: {url} ({len(resp.text)} chars)")
            except Exception as e:
                logger.warning(f"[{session_id}] Direct fetch notice for {url}: {e}")
    
    # STEP 2: Cerebras AI - Ultra-fast extraction (SECONDS)
    combined_content = "\n\n---PAGE BREAK---\n\n".join(crawled_content) if crawled_content else ""
    
    if cerebras_key and Cerebras:
        logger.info(f"[{session_id}] 🧠 Cerebras: Extracting contacts from {len(crawled_content)} pages...")
        try:
            client = Cerebras(api_key=cerebras_key)
            prompt = f"""Extract all contact information and phone numbers from the web page text below.
Extract up to {limit} contacts that have real telephone numbers present in the page text.

Context:
- Default Country: {country}
- Default Occupation: {occupation}
- Default Gender: {gender}

Return valid JSON format: {{"contacts": [{{"Name": "...", "Occupation": "{occupation}", "Gender (Inferred)": "{gender}", "Phone Number": "...", "Country": "{country}"}}]}}

Web Page Content:
{combined_content[:40000]}
"""
            completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="gpt-oss-120b",
                temperature=0.1,
                max_completion_tokens=2048,
                response_format={"type": "json_object"}
            )
            ai_res = json.loads(completion.choices[0].message.content)
            if "contacts" in ai_res and isinstance(ai_res["contacts"], list):
                extracted_records = ai_res["contacts"]
                logger.info(f"[{session_id}] ⚡ Cerebras extracted {len(extracted_records)} contacts in seconds")
        except Exception as e:
            logger.error(f"[{session_id}] Cerebras error: {e}")
            # Fall back to alternative Cerebras models in case model availability changes
            for alt_model in ["gemma-4-31b", "zai-glm-4.7"]:
                try:
                    client = Cerebras(api_key=cerebras_key)
                    completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt}],
                        model=alt_model,
                        temperature=0.1,
                        max_completion_tokens=2048,
                        response_format={"type": "json_object"}
                    )
                    ai_res = json.loads(completion.choices[0].message.content)
                    if "contacts" in ai_res and isinstance(ai_res["contacts"], list):
                        extracted_records = ai_res["contacts"]
                        logger.info(f"[{session_id}] ⚡ Cerebras ({alt_model}) extracted {len(extracted_records)} contacts")
                        break
                except Exception as e2:
                    logger.warning(f"[{session_id}] Cerebras alt model {alt_model} failed: {e2}")
    
    # If Cerebras failed, try Groq (still fast)
    if not extracted_records and groq_key and Groq:
        logger.info(f"[{session_id}] 🧠 Groq: Backup extraction...")
        try:
            client = Groq(api_key=groq_key)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=15,
                response_format={"type": "json_object"}
            )
            ai_res = json.loads(completion.choices[0].message.content)
            if "contacts" in ai_res and isinstance(ai_res["contacts"], list):
                extracted_records = ai_res["contacts"]
                logger.info(f"[{session_id}] ⚡ Groq extracted {len(extracted_records)} contacts")
        except Exception as e:
            logger.error(f"[{session_id}] Groq error: {e}")
    
    # If both AI engines failed, try Rust fallback
    if not extracted_records:
        logger.info(f"[{session_id}] ⚡ AI engines failed, trying Rust fallback...")
        target_urls = get_default_sources(country, occupation)
        if target_urls:
            rust_binary = PROJECT_ROOT / "target" / "release" / "harvester.exe"
            # Use compiled binary directly if it exists, otherwise use cargo run
            if rust_binary.exists():
                cmd = [str(rust_binary)]
            else:
                cmd = ["cargo", "run", "--release", "--"]
            cmd.extend(["--urls", ",".join(target_urls)])
            
            if PROXIES_FILE_PATH.exists():
                cmd.extend(["--proxies", str(PROXIES_FILE_PATH)])
                
            cmd.extend(["--depth", "1", "--concurrency", "5", "--output", str(RAW_JSON_PATH)])
            
            try:
                result = subprocess.run(cmd, cwd=PROJECT_ROOT, timeout=60, capture_output=True, text=True)
                if result.returncode == 0:
                    cleaner = CleanerPipeline(RAW_JSON_PATH)
                    if cleaner.load_data():
                        df_fallback = cleaner.clean(target_occupation=occupation, filter_gender=gender, filter_country=country)
                        extracted_records = df_fallback.to_dict(orient="records")
                        logger.info(f"[{session_id}] 🔧 Rust fallback extracted {len(extracted_records)} contacts")
                else:
                    logger.error(f"[{session_id}] Rust harvester failed: {result.stderr}")
            except Exception as e:
                logger.error(f"[{session_id}] Rust harvester error: {e}")
    
    # If still no contacts, return error
    if not extracted_records:
        logger.error(f"[{session_id}] ❌ All extraction methods failed")
        return jsonify({
            "success": False,
            "error": f"No contacts found for '{occupation}' in {country}. Try different filters or check back later.",
            "session_id": session_id,
            "count": 0,
            "records": []
        }), 404

    # Enforce Schema & Validation
    validated_records = enforce_contact_schema(extracted_records, country, occupation, gender)
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
    save_harvest_run(session_id, country, occupation, gender, limit, final_records)

    return jsonify({
        "success": True,
        "session_id": session_id,
        "count": len(final_records),
        "records": final_records
    })


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """Global error handler - catches ALL unhandled exceptions and returns clean JSON."""
    # Preserve proper HTTP status codes for standard errors (404, 400, 429, etc.)
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    logger.error(f"Unhandled error: {e}", exc_info=True)
    return jsonify({
        "success": False,
        "error": "An unexpected error occurred. Please try again later.",
        "count": 0,
        "records": []
    }), 500


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
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Harvester Web Server on http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
