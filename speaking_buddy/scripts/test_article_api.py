#!/usr/bin/env python3
"""
Test fetching article details from LOD.lu API
"""

import requests
import json
from urllib.parse import quote

def get_article_id(word):
    """Get the article ID for a word."""
    search_url = f"https://lod.lu/api/lb/search?_app_name=LOD&lang=lb&query={quote(word)}"
    try:
        response = requests.get(search_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('results') and len(data['results']) > 0:
                article_id = data['results'][0]['article_id']
                print(f"  Found article_id: {article_id}")
                return article_id
    except Exception as e:
        print(f"  Error getting article_id: {e}")
    return None

def fetch_article_details(article_id):
    """Fetch full article details including audio."""
    # Try different API endpoints
    endpoints = [
        f"https://lod.lu/api/lb/article/{article_id}?_app_name=LOD",
        f"https://lod.lu/api/lb/articles/{article_id}?_app_name=LOD",
        f"https://lod.lu/api/lb/entry/{article_id}?_app_name=LOD",
        f"https://lod.lu/api/lb/entries/{article_id}?_app_name=LOD",
    ]

    for url in endpoints:
        print(f"\n  Trying: {url}")
        try:
            response = requests.get(url, timeout=10)
            print(f"  Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"  Response (first 3000 chars):")
                response_str = json.dumps(data, indent=2, ensure_ascii=False)
                print(response_str[:3000])

                # Search for audio URLs
                def find_audio_urls(obj, path=""):
                    urls = []
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, str) and ('.ogg' in value or '.mp3' in value or 'audio' in value.lower()):
                                urls.append((f"{path}.{key}", value))
                            urls.extend(find_audio_urls(value, f"{path}.{key}"))
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            urls.extend(find_audio_urls(item, f"{path}[{i}]"))
                    return urls

                audio_urls = find_audio_urls(data)
                if audio_urls:
                    print(f"\n  FOUND AUDIO URLs:")
                    for path, url in audio_urls:
                        print(f"    {path}: {url}")
                    return audio_urls[0][1]

        except Exception as e:
            print(f"  Error: {e}")

    return None

def main():
    test_words = ["haus", "merci", "eent"]

    print("Testing LOD.lu Article API")
    print("="*80)

    for word in test_words:
        print(f"\n{'='*80}")
        print(f"Word: {word}")
        print('='*80)

        article_id = get_article_id(word)
        if article_id:
            audio_url = fetch_article_details(article_id)
            if audio_url:
                print(f"\n\nSUCCESS: {word} -> {audio_url}")
            else:
                print(f"\n\nFailed to find audio URL for {word}")
        else:
            print(f"\nFailed to find article_id for {word}")

if __name__ == "__main__":
    main()
