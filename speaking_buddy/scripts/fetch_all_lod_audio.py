#!/usr/bin/env python3
"""
Final script to fetch audio URLs from lod.lu for all 49 Luxembourgish words.
Uses the LOD API to get article details and extract audio URLs.
"""

import requests
import json
import time
from urllib.parse import quote

# All 49 Luxembourgish words organized by category
WORDS = {
    "greetings": ["äddi", "merci", "wëllkomm", "pardon", "jo", "nee", "wéi", "gär", "bis"],
    "numbers": ["eent", "zwee", "dräi", "véier", "fënnef", "sechs", "siwen", "aacht", "néng", "zéng"],
    "family": ["papp", "mamm", "kand", "jong", "meedchen", "frau", "mann", "brudder", "schwëster", "grousselteren"],
    "objects": ["haus", "dier", "fënster", "buch", "stull", "dësch", "auto", "telefon", "waasser", "kaffi"],
    "time_nature": ["dag", "nuecht", "mëtteg", "owes", "sonn", "mound", "stierm", "reen", "schnéi", "loft"]
}

def get_all_words():
    """Flatten all words into a single list."""
    all_words = []
    for category_words in WORDS.values():
        all_words.extend(category_words)
    return all_words

def fetch_audio_url(word):
    """
    Fetch the audio URL for a given Luxembourgish word from lod.lu API.

    Args:
        word: The Luxembourgish word to look up

    Returns:
        The OGG audio file URL, or None if not found
    """
    # Step 1: Search for the word to get its article_id
    search_url = f"https://lod.lu/api/lb/search?_app_name=LOD&lang=lb&query={quote(word)}"

    try:
        response = requests.get(search_url, timeout=10)
        if response.status_code != 200:
            print(f"  Search failed with status {response.status_code}")
            return None

        data = response.json()
        if not data.get('results') or len(data['results']) == 0:
            print(f"  No results found")
            return None

        article_id = data['results'][0]['article_id']
        print(f"  Article ID: {article_id}")

    except Exception as e:
        print(f"  Search error: {e}")
        return None

    # Step 2: Fetch the full article entry to get audio URL
    entry_url = f"https://lod.lu/api/lb/entry/{article_id}?_app_name=LOD"

    try:
        response = requests.get(entry_url, timeout=10)
        if response.status_code != 200:
            print(f"  Entry fetch failed with status {response.status_code}")
            return None

        data = response.json()

        # Extract the main audio file (word pronunciation)
        if 'entry' in data and 'audioFiles' in data['entry']:
            audio_files = data['entry']['audioFiles']
            if 'ogg' in audio_files:
                audio_url = audio_files['ogg']
                print(f"  Audio URL: {audio_url}")
                return audio_url

        print(f"  No audio file found in entry")
        return None

    except Exception as e:
        print(f"  Entry fetch error: {e}")
        return None

def main():
    """Main function to fetch all audio URLs."""
    print("Fetching audio URLs from lod.lu for 49 Luxembourgish words...")
    print("Using LOD.lu REST API")
    print("=" * 80)

    all_words = get_all_words()
    audio_urls = {}

    for i, word in enumerate(all_words, 1):
        print(f"\n[{i}/{len(all_words)}] {word}")
        audio_url = fetch_audio_url(word)
        audio_urls[word] = audio_url

        if not audio_url:
            print(f"  FAILED: Could not find audio URL")

        # Be polite to the server
        time.sleep(0.5)

    # Print results
    print("\n" + "=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)

    # Separate successful and failed fetches
    successful = {k: v for k, v in audio_urls.items() if v is not None}
    failed = [k for k, v in audio_urls.items() if v is None]

    print(f"\nSuccessful: {len(successful)}/{len(all_words)}")
    print(f"Failed: {len(failed)}/{len(all_words)}")

    if failed:
        print(f"\nFailed words: {', '.join(failed)}")

    # Print as Python dictionary
    print("\n" + "=" * 80)
    print("PYTHON DICTIONARY:")
    print("=" * 80)
    print("audio_urls = {")
    for word, url in audio_urls.items():
        url_str = f'"{url}"' if url else 'None'
        print(f'    "{word}": {url_str},')
    print("}")

    # Save to JSON file
    output_file = "/Users/skoppar/workspace/kaushalavardhanam/speaking_buddy/data/lod_audio_urls.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(audio_urls, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_file}")

    # Also save by category
    output_by_category = {}
    for category, words in WORDS.items():
        output_by_category[category] = {word: audio_urls.get(word) for word in words}

    category_file = "/Users/skoppar/workspace/kaushalavardhanam/speaking_buddy/data/lod_audio_urls_by_category.json"
    with open(category_file, 'w', encoding='utf-8') as f:
        json.dump(output_by_category, f, indent=2, ensure_ascii=False)

    print(f"Results by category saved to: {category_file}")

if __name__ == "__main__":
    main()
