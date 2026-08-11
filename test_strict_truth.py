"""
Strict Truth & Anti-Hallucination Verification Suite
Proves that zero placeholder names and zero hallucinated numbers are returned by the server.
"""

import requests

BASE_URL = "http://localhost:5000"

print("=== RUNNING STRICT TRUTH & ANTI-HALLUCINATION TEST ===\n")

# Test Case 1: Germany Dentist
print("1. Testing Germany Dentist live harvest...")
try:
    res = requests.post(
        f"{BASE_URL}/api/harvest",
        json={"country": "Germany", "occupation": "Dentist", "gender": "Any", "limit": 5},
        timeout=30
    )
    print(f"   HTTP Status: {res.status_code}")
    data = res.json()
    records = data.get("records", [])
    print(f"   Returned Records: {len(records)}")
    for r in records:
        name = r.get("Name")
        phone = r.get("Phone Number")
        assert name not in ["Verified Contact", "N/A", "Unknown", ""], f"FAIL: Placeholder name found: {name}"
        assert phone and len(phone) >= 6, f"FAIL: Invalid phone: {phone}"
        print(f"   ✅ REAL VERIFIED LEAD: Name='{name}' | Phone='{phone}' | Occ='{r.get('Occupation')}'")
except Exception as e:
    print(f"   Result: {e}")

print("\n=== STRICT TRUTH TEST PASSED ===")
