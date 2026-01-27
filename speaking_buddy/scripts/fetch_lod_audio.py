#!/usr/bin/env python3
"""
Script to fetch audio URLs from lod.lu (Luxembourgish Online Dictionary)
for a list of Luxembourgish words.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import json
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

def fetch_audio_url(word, session=None):
    """
    Fetch the audio URL for a given Luxembourgish word from lod.lu.

    Args:
        word: The Luxembourgish word to look up
        session: Optional requests session for connection reuse

    Returns:
        The OGG audio file URL, or None if not found
    """
    if session is None:
        session = requests.Session()

    # lod.lu might have an API - let's try the API approach first
    api_url = f"https://lod.lu/api/v1/search/{quote(word)}"

    try:
        print(f"  Trying API URL: {api_url}")
        response = session.get(api_url, timeout=10)

        if response.status_code == 200:
            try:
                data = response.json()
                print(f"  API Success! Got JSON data")

                # Try to find audio URL in the JSON response
                # The structure might vary, so we'll search recursively
                def find_ogg_in_json(obj, path=""):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, str) and '.ogg' in value:
                                print(f"  Found OGG in JSON at {path}.{key}: {value}")
                                if not value.startswith('http'):
                                    return 'https://lod.lu' + value if value.startswith('/') else f'https://lod.lu/{value}'
                                return value
                            result = find_ogg_in_json(value, f"{path}.{key}")
                            if result:
                                return result
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            result = find_ogg_in_json(item, f"{path}[{i}]")
                            if result:
                                return result
                    return None

                audio_url = find_ogg_in_json(data)
                if audio_url:
                    return audio_url

            except json.JSONDecodeError:
                print(f"  API response is not JSON")
        else:
            print(f"  API failed with status code: {response.status_code}")

    except requests.RequestException as e:
        print(f"  API error: {e}")

    # Try different URL formats for the web interface
    url_formats = [
        f"https://lod.lu/query/{quote(word)}",
        f"https://lod.lu/q/{quote(word)}",
        f"https://lod.lu/{quote(word)}",
        f"https://lod.lu/#{quote(word)}",
    ]

    for url in url_formats:
        try:
            print(f"  Trying URL: {url}")
            response = session.get(url, timeout=10, allow_redirects=True)

            if response.status_code == 200:
                print(f"  Success! Status code: {response.status_code}")

                # Parse the HTML
                soup = BeautifulSoup(response.content, 'html.parser')

                # Look for OGG audio files in various ways
                # Method 1: Look for <audio> tags
                audio_tags = soup.find_all('audio')
                for audio in audio_tags:
                    source = audio.find('source', {'type': 'audio/ogg'})
                    if source and source.get('src'):
                        audio_url = source['src']
                        if not audio_url.startswith('http'):
                            audio_url = 'https://lod.lu' + audio_url
                        print(f"  Found audio URL (method 1): {audio_url}")
                        return audio_url

                # Method 2: Look for any .ogg links in the HTML
                ogg_pattern = re.compile(r'(https?://[^\s"\']+\.ogg)')
                matches = ogg_pattern.findall(str(soup))
                if matches:
                    audio_url = matches[0]
                    print(f"  Found audio URL (method 2): {audio_url}")
                    return audio_url

                # Method 3: Look in the raw HTML for ogg references
                ogg_pattern2 = re.compile(r'([/a-zA-Z0-9_\-./]+\.ogg)')
                matches2 = ogg_pattern2.findall(response.text)
                if matches2:
                    audio_url = matches2[0]
                    if not audio_url.startswith('http'):
                        audio_url = 'https://lod.lu' + audio_url
                    print(f"  Found audio URL (method 3): {audio_url}")
                    return audio_url

                print(f"  No audio URL found in successful response")
            else:
                print(f"  Failed with status code: {response.status_code}")

        except requests.RequestException as e:
            print(f"  Error fetching {url}: {e}")
            continue

    return None

def main():
    """Main function to fetch all audio URLs."""
    print("Fetching audio URLs from lod.lu for 49 Luxembourgish words...")
    print("=" * 80)

    # Create a session for connection reuse
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })

    # First, test with a few sample words
    test_words = ["merci", "haus", "eent"]
    print(f"\nTesting with sample words: {test_words}")
    print("-" * 80)

    test_results = {}
    for word in test_words:
        print(f"\nFetching audio for: {word}")
        audio_url = fetch_audio_url(word, session)
        test_results[word] = audio_url
        if audio_url:
            print(f"SUCCESS: {word} -> {audio_url}")
        else:
            print(f"FAILED: Could not find audio URL for {word}")
        time.sleep(1)  # Be polite to the server

    print("\n" + "=" * 80)
    print("Test results:")
    print(json.dumps(test_results, indent=2, ensure_ascii=False))

    # Ask user if they want to continue with all words
    print("\n" + "=" * 80)
    proceed = input("Test complete. Proceed with all 49 words? (y/n): ").lower().strip()

    if proceed != 'y':
        print("Exiting. Test results saved above.")
        return

    # Fetch all words
    print("\nFetching all 49 words...")
    print("-" * 80)

    all_words = get_all_words()
    audio_urls = {}

    for i, word in enumerate(all_words, 1):
        print(f"\n[{i}/{len(all_words)}] Fetching audio for: {word}")
        audio_url = fetch_audio_url(word, session)
        audio_urls[word] = audio_url

        if audio_url:
            print(f"  SUCCESS: {audio_url}")
        else:
            print(f"  FAILED: Could not find audio URL")

        # Be polite to the server
        time.sleep(1)

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

if __name__ == "__main__":
    main()
