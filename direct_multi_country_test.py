"""
Direct Multi-Country Pipeline Test
Runs SerpAPI Google Dorking + Direct Fetch + Cerebras AI + Numverify for Germany, Switzerland, USA, Canada
"""

import os
import json
import requests
from dotenv import load_dotenv
from external_apis import fetch_serpapi_urls, verify_phone_number
from cerebras.cloud.sdk import Cerebras

load_dotenv()

cerebras_key = os.getenv("CEREBRAS_API_KEY")
client = Cerebras(api_key=cerebras_key)

countries = [
    {"country": "Germany", "occupation": "Dentist"},
    {"country": "Switzerland", "occupation": "Doctor"},
    {"country": "United States", "occupation": "Architect"},
    {"country": "Canada", "occupation": "Realtor"},
]

print("=== DIRECT MULTI-COUNTRY TEST SUITE ===\n")

for c in countries:
    country = c["country"]
    occ = c["occupation"]
    print(f"Testing {country} ({occ})...")
    
    # 1. SerpAPI
    urls = fetch_serpapi_urls(country, occ, limit=3)
    print(f"   SerpAPI Found {len(urls)} URLs: {urls[:2]}")
    
    # 2. Fetch HTML
    page_text = ""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for u in urls[:2]:
        try:
            r = requests.get(u, headers=headers, timeout=6)
            if r.status_code == 200:
                page_text += "\n" + r.text[:15000]
                print(f"   Fetched {u} ({len(r.text)} chars)")
                break
        except Exception as e:
            print(f"   Notice fetching {u}: {e}")
            
    if not page_text:
        print("   Notice: No HTML text fetched, skipping AI extraction.")
        print("-" * 60)
        continue

    # 3. Cerebras AI
    prompt = f"""Extract 3 contact entries with phone numbers for {occ} in {country}.
Return JSON format: {{"contacts": [{{"Name": "...", "Occupation": "{occ}", "Gender (Inferred)": "Any", "Phone Number": "...", "Country": "{country}"}}]}}

Page Text:
{page_text[:20000]}
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
        print(f"   Extracted {len(contacts)} contacts from Cerebras AI:")
        for idx, item in enumerate(contacts[:3], 1):
            # 4. Numverify
            v = verify_phone_number(item.get("Phone Number", ""))
            phone_val = v.get("phone") or item.get("Phone Number")
            print(f"     [{idx}] Name: '{item.get('Name')}' | Phone: '{phone_val}' | Carrier: '{v.get('carrier')}'")
    except Exception as e:
        print(f"   Cerebras error: {e}")
        
    print("-" * 60)

print("\n=== MULTI-COUNTRY TEST COMPLETE ===")
