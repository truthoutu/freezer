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

query = "Nurse phone number Berlin Germany"
url = "https://html.duckduckgo.com/html/"
params = {"q": query}
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

print(f"[*] Executing Live Web Search via SOCKS5 proxy: '{query}'...")
resp = requests.post(url, data=params, proxies=PROXIES, headers=headers, timeout=15)
html_text = resp.text[:12000]

print(f"[+] Web Search returned {len(resp.text)} bytes. Passing live web search results to Groq Llama-3.3 AI...")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

prompt = f"""Extract real person/business names, occupations, phone numbers, and inferred gender from these live web search results.
Target Criteria: Germany, Nurse, Female.

Return strictly JSON in format:
{{"contacts": [{{"Name": "...", "Occupation": "Nurse", "Gender (Inferred)": "Female", "Phone Number": "...", "Country": "Germany"}}]}}

Live Web Search Content:
{html_text}
"""

res = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.1,
    response_format={"type": "json_object"}
)

print("\n[+] Real Live Extracted Contacts:")
print(res.choices[0].message.content)
