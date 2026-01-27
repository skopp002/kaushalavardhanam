#!/usr/bin/env python3
"""
Script to capture API calls made by lod.lu when searching for a word
"""

import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver_with_logging():
    """Setup Chrome driver with network logging enabled."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    # Enable performance logging to capture network requests
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def search_for_word(driver, word):
    """Perform a search on lod.lu and capture network requests."""
    print(f"\nSearching for: {word}")

    # Go to the homepage
    driver.get("https://lod.lu")
    time.sleep(3)

    # Find the search input
    try:
        search_input = driver.find_element(By.CSS_SELECTOR, 'input[placeholder*="sichen"], input[type="search"]')
        print("  Found search input")

        # Type the word
        search_input.clear()
        search_input.send_keys(word)
        time.sleep(1)

        # Submit the search
        search_input.send_keys(Keys.RETURN)
        print("  Submitted search")

        # Wait for results to load
        time.sleep(5)

        # Get page source
        page_source = driver.page_source

        # Check for OGG files in the result page
        if '.ogg' in page_source:
            print("  SUCCESS: Found .ogg in page!")
            import re
            ogg_pattern = re.compile(r'(https?://[^\s"\'<>]+\.ogg)')
            matches = ogg_pattern.findall(page_source)
            if matches:
                for match in matches[:5]:
                    print(f"    - {match}")
                return matches[0]

        # Get performance logs (network requests)
        logs = driver.get_log('performance')

        api_requests = []
        for entry in logs:
            try:
                log = json.loads(entry['message'])['message']
                if 'Network.responseReceived' in log['method']:
                    url = log['params']['response']['url']
                    if 'lod.lu' in url and '/api/' in url:
                        api_requests.append(url)
                        print(f"  API call found: {url}")
            except:
                pass

        return None

    except Exception as e:
        print(f"  Error: {e}")
        return None

def main():
    print("="*80)
    print("Capturing API calls from lod.lu")
    print("="*80)

    driver = setup_driver_with_logging()

    test_words = ["haus", "merci", "eent"]

    for word in test_words:
        audio_url = search_for_word(driver, word)
        if audio_url:
            print(f"\n  FOUND AUDIO URL: {audio_url}")
        else:
            print(f"  No audio URL found")

    driver.quit()

    print("\n" + "="*80)
    print("Testing complete")

if __name__ == "__main__":
    main()
