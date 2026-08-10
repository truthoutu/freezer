"""
Live Dynamic Target Generator & Pipeline Test Suite
Tests URL generation and API extraction across various countries and occupations.
"""

import requests
import json

BASE_URL = "http://localhost:5000"

test_cases = [
    {"country": "Germany", "occupation": "Dentist", "gender": "Any", "limit": 5},
    {"country": "Australia", "occupation": "Plumber", "gender": "Male", "limit": 5},
    {"country": "United States", "occupation": "Architect", "gender": "Any", "limit": 5},
    {"country": "Switzerland", "occupation": "Doctor", "gender": "Female", "limit": 5},
]

print("=== STARTING DYNAMIC PIPELINE TEST SUITE ===\n")

for tc in test_cases:
    print(f"Testing Target: Country='{tc['country']}', Occupation='{tc['occupation']}', Gender='{tc['gender']}', Limit={tc['limit']}")
    try:
        res = requests.post(
            f"{BASE_URL}/api/harvest",
            json=tc,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"   HTTP Status: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"   Success: {data.get('success')}")
            print(f"   Session ID: {data.get('session_id')}")
            print(f"   Records Extracted: {data.get('count')}")
            if data.get('records'):
                first = data['records'][0]
                print(f"   Sample Lead: Name='{first.get('Name')}', Phone='{first.get('Phone Number')}', Occ='{first.get('Occupation')}'")
        else:
            print(f"   Error Response: {res.text}")
    except Exception as e:
        print(f"   Request Exception: {e}")
    print("-" * 65)

print("\n=== TEST SUITE COMPLETE ===")
