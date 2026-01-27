#!/usr/bin/env python3
"""
Test script to determine the correct URL format for lod.lu articles
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    """Setup Chrome driver with headless options."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def test_url(driver, url):
    print(f"\nTesting: {url}")
    driver.get(url)
    time.sleep(4)

    page_source = driver.page_source

    # Check if it's a 404
    if 'feeler 404' in page_source.lower() or 'error 404' in page_source.lower():
        print("  Result: 404 NOT FOUND")
        return False

    # Check for audio/ogg
    has_audio = 'audio' in page_source.lower()
    has_ogg = '.ogg' in page_source.lower()

    print(f"  Result: SUCCESS (has_audio: {has_audio}, has_ogg: {has_ogg})")

    if has_ogg:
        # Find the OGG URLs
        import re
        ogg_pattern = re.compile(r'(https?://[^\s"\'<>]+\.ogg)')
        matches = ogg_pattern.findall(page_source)
        if matches:
            print(f"  Found OGG URLs: {matches[:3]}")  # Show first 3

    return True

def main():
    driver = setup_driver()

    test_words = ["haus", "merci", "eent", "HAUS", "MERCI", "EENT"]

    # Try different URL patterns
    patterns = [
        "/artikel/{word}",
        "/artikel/{WORD}",
        "/{word}",
        "/{WORD}",
        "/word/{word}",
        "/query/{word}",
    ]

    print("="*80)
    print("Testing different URL patterns for lod.lu")
    print("="*80)

    for pattern in patterns:
        print(f"\n{'-'*80}")
        print(f"Pattern: https://lod.lu{pattern}")
        print(f"{'-'*80}")

        for word in test_words[:2]:  # Test with first 2 words
            if '{WORD}' in pattern:
                url = f"https://lod.lu{pattern.format(WORD=word.upper())}"
            else:
                url = f"https://lod.lu{pattern.format(word=word)}"

            test_url(driver, url)

    driver.quit()
    print("\n" + "="*80)
    print("Testing complete")

if __name__ == "__main__":
    main()
