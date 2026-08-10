"""
Multi-Country Live Harvest Pipeline Verification Script
Tests extraction for Germany, Switzerland, United States, and Canada with extended timeout.
"""

import requests
import json

BASE_URL = "http://localhost:5000"

test_cases = [
    {"country": "Germany", "occupation": "Dentist", "gender": "Female", "limit": 5},
    {"country": "Switzerland", "occupation": "Doctor", "gender": "Female", "limit": 5},
    {"country": "United States", "occupation": "Architect", "gender": "Any", "limit": 5},
    {"country": "Canada", "occupation": "Realtor", "gender": "Any", "limit": 5},
]

print("=== STARTING MULTI-COUNTRY LIVE HARVEST TEST ===\n")

for tc in test_cases:
    print(f"Testing Country: '{tc['country']}', Occupation: '{tc['occupation']}', Gender: '{tc['gender']}'...")
    try:
        res = requests.post(
            f"{BASE_URL}/api/harvest",
            json=tc,
            headers={"Content-Type": "application/json"},
            timeout=45
        )
        print(f"   Status Code: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   Records Count: {data.get('count')}")
            if data.get('records'):
                for idx, r in enumerate(data['records'][:3], 1):
                    print(f"     [{idx}] Name: '{r.get('Name')}' | Phone: '{r.get('Phone Number')}' | Occ: '{r.get('Occupation')}' | Country: '{r.get('Country')}'")
            else:
                print("     [Notice] No records returned for this query.")
        else:
            print(f"   Error: {res.text}")
    except Exception as e:
        print(f"   Request Exception: {e}")
    print("-" * 70)

print("\n=== MULTI-COUNTRY TEST COMPLETE ===")
