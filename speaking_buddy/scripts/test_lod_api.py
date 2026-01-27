#!/usr/bin/env python3
"""
Test the LOD.lu API directly to fetch audio URLs
"""

import requests
import json
from urllib.parse import quote

def test_search_api(word):
    """Test the search API for a word."""
    print(f"\n{'='*80}")
    print(f"Testing word: {word}")
    print('='*80)

    # Try the search API
    search_url = f"https://lod.lu/api/lb/search?_app_name=LOD&lang=lb&query={quote(word)}"
    print(f"\nSearch API: {search_url}")

    try:
        response = requests.get(search_url, timeout=10)
        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse structure:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])

            # Search for audio URLs in the response
            def find_audio_urls(obj, path=""):
                urls = []
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, str) and ('.ogg' in value or '.mp3' in value or 'audio' in key.lower()):
                            urls.append((f"{path}.{key}", value))
                        urls.extend(find_audio_urls(value, f"{path}.{key}"))
                elif isinstance(obj, list):
                    for i, item in enumerate(obj):
                        urls.extend(find_audio_urls(item, f"{path}[{i}]"))
                return urls

            audio_urls = find_audio_urls(data)
            if audio_urls:
                print(f"\nFound audio URLs:")
                for path, url in audio_urls:
                    print(f"  {path}: {url}")
                return audio_urls[0][1]  # Return first audio URL
            else:
                print("\nNo audio URLs found in response")

    except Exception as e:
        print(f"Error: {e}")

    # Try the suggest API
    suggest_url = f"https://lod.lu/api/lb/suggest?_app_name=LOD&lang=lb&query={quote(word)}"
    print(f"\n{'---'*20}")
    print(f"Suggest API: {suggest_url}")

    try:
        response = requests.get(suggest_url, timeout=10)
        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse structure:")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])

    except Exception as e:
        print(f"Error: {e}")

    return None

def main():
    test_words = ["haus", "merci", "eent"]

    print("Testing LOD.lu API endpoints")
    print("="*80)

    for word in test_words:
        audio_url = test_search_api(word)
        if audio_url:
            print(f"\n\nSUCCESS: Found audio URL for '{word}': {audio_url}")

if __name__ == "__main__":
    main()
