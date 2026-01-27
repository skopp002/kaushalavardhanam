#!/usr/bin/env python3
"""
Script to fetch audio URLs from lod.lu using Selenium for JavaScript rendering.
Selenium is needed because lod.lu is a JavaScript-heavy single-page application.
"""

import time
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

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

def setup_driver():
    """Setup Chrome driver with headless options."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36')

    try:
        # Use webdriver-manager to automatically download and setup chromedriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {e}")
        print("\nPlease ensure Chrome browser is installed")
        print("If the issue persists, try: brew install --cask google-chrome")
        return None

def fetch_audio_url(word, driver):
    """
    Fetch the audio URL for a given Luxembourgish word from lod.lu.

    Args:
        word: The Luxembourgish word to look up
        driver: Selenium WebDriver instance

    Returns:
        The OGG audio file URL, or None if not found
    """
    url = f"https://lod.lu/{word}"

    try:
        print(f"  Loading URL: {url}")
        driver.get(url)

        # Wait for the page to load (adjust timeout as needed)
        time.sleep(3)  # Give JavaScript time to render

        # Method 1: Look for audio elements
        try:
            audio_elements = driver.find_elements(By.TAG_NAME, 'audio')
            for audio in audio_elements:
                # Get the source from the audio element
                src = audio.get_attribute('src')
                if src and '.ogg' in src:
                    if not src.startswith('http'):
                        src = 'https://lod.lu' + src
                    print(f"  Found audio URL (audio tag): {src}")
                    return src

                # Check source children
                sources = audio.find_elements(By.TAG_NAME, 'source')
                for source in sources:
                    src = source.get_attribute('src')
                    if src and '.ogg' in src:
                        if not src.startswith('http'):
                            src = 'https://lod.lu' + src
                        print(f"  Found audio URL (source tag): {src}")
                        return src
        except NoSuchElementException:
            pass

        # Method 2: Look for links to .ogg files
        try:
            links = driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                href = link.get_attribute('href')
                if href and '.ogg' in href:
                    if not href.startswith('http'):
                        href = 'https://lod.lu' + href
                    print(f"  Found audio URL (link): {href}")
                    return href
        except NoSuchElementException:
            pass

        # Method 3: Search the page source for .ogg URLs
        page_source = driver.page_source
        ogg_pattern = re.compile(r'(https?://[^\s"\'<>]+\.ogg)')
        matches = ogg_pattern.findall(page_source)
        if matches:
            audio_url = matches[0]
            print(f"  Found audio URL (regex): {audio_url}")
            return audio_url

        # Method 4: Look for relative .ogg paths
        ogg_pattern2 = re.compile(r'"(/uploads/[^"]+\.ogg)"')
        matches2 = ogg_pattern2.findall(page_source)
        if matches2:
            audio_url = 'https://lod.lu' + matches2[0]
            print(f"  Found audio URL (relative path): {audio_url}")
            return audio_url

        print(f"  No audio URL found")
        return None

    except TimeoutException:
        print(f"  Timeout loading page")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def main():
    """Main function to fetch all audio URLs."""
    print("Fetching audio URLs from lod.lu for 49 Luxembourgish words...")
    print("Using Selenium for JavaScript rendering")
    print("=" * 80)

    # Setup Selenium driver
    driver = setup_driver()
    if driver is None:
        print("\nFailed to setup WebDriver. Exiting.")
        return

    try:
        # First, test with a few sample words
        test_words = ["merci", "haus", "eent"]
        print(f"\nTesting with sample words: {test_words}")
        print("-" * 80)

        test_results = {}
        for word in test_words:
            print(f"\nFetching audio for: {word}")
            audio_url = fetch_audio_url(word, driver)
            test_results[word] = audio_url
            if audio_url:
                print(f"SUCCESS: {word} -> {audio_url}")
            else:
                print(f"FAILED: Could not find audio URL for {word}")

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
            audio_url = fetch_audio_url(word, driver)
            audio_urls[word] = audio_url

            if audio_url:
                print(f"  SUCCESS: {audio_url}")
            else:
                print(f"  FAILED: Could not find audio URL")

            # Small delay between requests
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

    finally:
        # Clean up
        driver.quit()
        print("\nBrowser closed.")

if __name__ == "__main__":
    main()
