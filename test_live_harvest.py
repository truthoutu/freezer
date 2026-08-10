import os
import json
import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

PROXIES = {
    'http': 'socks5://rwyqonni:13rzh27ci73w@31.59.20.176:6754',
    'https': 'socks5://rwyqonni:13rzh27ci73w@31.59.20.176:6754'
}

url = "https://www.yellowpages.com/search?search_terms=nurse&geo_location_terms=New+York+NY"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

print(f"[*] Fetching live URL via SOCKS5 proxy: {url}")
resp = requests.get(url, proxies=PROXIES, headers=headers, timeout=15)
html_snippet = resp.text[:15000]

print(f"[+] Fetched {len(resp.text)} bytes. Passing HTML snippet to Groq Llama-3.3 AI...")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

prompt = f"""Extract real business/person names, occupations, and phone numbers from this webpage snippet.
Return strictly JSON in format:
{{"contacts": [{{"Name": "...", "Occupation": "...", "Phone Number": "...", "Gender (Inferred)": "Female", "Country": "United States"}}]}}

Webpage Content:
{html_snippet}
"""

res = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.1,
    response_format={"type": "json_object"}
)

print("\n[+] Groq AI Live Extracted Output:")
print(res.choices[0].message.content)
