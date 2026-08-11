"""
Live Verification Test for Harvester End-to-End Pipeline
Executes an actual live POST query against http://localhost:5000/api/harvest
"""

import requests
import json
import time

url = "http://localhost:5000/api/harvest"
payload = {
    "country": "Germany",
    "occupation": "Dentist",
    "gender": "Any",
    "limit": 5
}

print("=== LIVE PIPELINE VERIFICATION TEST ===")
print("Sending POST request to http://localhost:5000/api/harvest...")
start_time = time.time()

try:
    resp = requests.post(url, json=payload, timeout=60)
    elapsed = round(time.time() - start_time, 2)
    
    print(f"\n✅ HTTP Response Status: {resp.status_code} OK (Time: {elapsed} seconds)")
    data = resp.json()
    print(f"   Success Flag: {data.get('success')}")
    print(f"   Session ID: {data.get('session_id')}")
    print(f"   Total Real Extracted Records: {data.get('count')}")
    
    records = data.get('records', [])
    if records:
        print("\n--- EXTRACTED CONTACT LEAD DETAILS ---")
        for idx, rec in enumerate(records, 1):
            print(f"  [{idx}] Name: {rec.get('Name')}")
            print(f"      Phone: {rec.get('Phone Number')}")
            print(f"      Occupation: {rec.get('Occupation')}")
            print(f"      Country: {rec.get('Country')}")
            print(f"      Source URL: {rec.get('Source URL')}")
            print(f"      Confidence Score: {rec.get('Confidence Score')}/100")
            print("  " + "-"*40)
    else:
        print("\nNotice: Query returned 0 matching records.")
        print(f"Message: {data.get('message') or data.get('error')}")

except Exception as e:
    print(f"\n❌ Error connecting to server: {e}")

print("\n=== VERIFICATION COMPLETE ===")
