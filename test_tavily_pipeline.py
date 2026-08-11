"""
Tavily AI Search + Cerebras Extraction Verification Script
Tests deep AI web search via Tavily and extracts real contact leads.
"""

import os
import json
import requests
from dotenv import load_dotenv
from external_apis import fetch_tavily_content, verify_phone_number
from cerebras.cloud.sdk import Cerebras

load_dotenv()

tavily_key = os.getenv("TAVILY_API_KEY")
cerebras_key = os.getenv("CEREBRAS_API_KEY")

print("=== TESTING TAVILY AI SEARCH PIPELINE ===\n")
print(f"Tavily Key Configured: {bool(tavily_key)}")

# Test Tavily Deep Search for Germany Dentists
country = "Germany"
occupation = "Dentist"

print(f"\n1. Fetching Tavily deep web search content for {occupation} in {country}...")
crawled_pages = fetch_tavily_content(country, occupation, limit=5)
print(f"   Scraped {len(crawled_pages)} deep web pages from Tavily.")

if crawled_pages:
    combined_text = "\n\n---PAGE BREAK---\n\n".join(crawled_pages)
    print(f"   Total Scraped Content Length: {len(combined_text)} characters.")
    
    # Send to Cerebras AI
    print("\n2. Sending raw Tavily content to Cerebras AI (gemma-4-31b)...")
    client = Cerebras(api_key=cerebras_key)
    prompt = f"""Extract up to 5 real contact entries with telephone numbers for {occupation} in {country} from the text below.
Return JSON format: {{"contacts": [{{"Name": "...", "Occupation": "{occupation}", "Gender (Inferred)": "Any", "Phone Number": "...", "Country": "{country}"}}]}}

Web Page Content:
{combined_text[:30000]}
"""
    try:
        comp = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gemma-4-31b",
            temperature=0.1,
            max_completion_tokens=1024,
            response_format={"type": "json_object"}
        )
        res = json.loads(comp.choices[0].message.content)
        contacts = res.get("contacts", [])
        print(f"   Cerebras extracted {len(contacts)} contacts from Tavily search:")
        for idx, c in enumerate(contacts, 1):
            phone = c.get("Phone Number", "")
            v = verify_phone_number(phone)
            valid_phone = v.get("phone") or phone
            print(f"     [{idx}] Name: '{c.get('Name')}' | Phone: '{valid_phone}' | Carrier: '{v.get('carrier')}'")
    except Exception as e:
        print(f"   Cerebras AI error: {e}")

print("\n=== TAVILY PIPELINE TEST COMPLETE ===")
