#!/usr/bin/env python3
"""
Script to inspect the HTML response from lod.lu
"""

import requests
from bs4 import BeautifulSoup

# Test with a simple word
word = "haus"
url = f"https://lod.lu/{word}"

print(f"Fetching: {url}")
response = requests.get(url, timeout=10)

print(f"Status code: {response.status_code}")
print(f"\n{'='*80}")
print("RAW HTML:")
print('='*80)
print(response.text[:5000])  # First 5000 chars

print(f"\n{'='*80}")
print("SCRIPTS IN HTML:")
print('='*80)

soup = BeautifulSoup(response.content, 'html.parser')
scripts = soup.find_all('script')
for i, script in enumerate(scripts):
    if script.get('src'):
        print(f"Script {i}: src={script.get('src')}")
    else:
        content = script.string or ""
        if len(content) > 100:
            print(f"Script {i}: Inline script ({len(content)} chars)")
            if 'ogg' in content.lower() or 'audio' in content.lower():
                print("  Contains 'ogg' or 'audio'!")
                print(f"  Snippet: {content[:500]}")
        else:
            print(f"Script {i}: Inline script: {content[:100]}")

# Save the full HTML
output_file = "/Users/skoppar/workspace/kaushalavardhanam/speaking_buddy/data/lod_sample_response.html"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(response.text)

print(f"\n{'='*80}")
print(f"Full HTML saved to: {output_file}")
