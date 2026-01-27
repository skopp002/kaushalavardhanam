#!/usr/bin/env python3
"""
Debug script to capture the rendered HTML from lod.lu after JavaScript loads
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
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def main():
    driver = setup_driver()

    word = "haus"
    url = f"https://lod.lu/{word}"

    print(f"Loading: {url}")
    driver.get(url)

    print("Waiting for JavaScript to render...")
    time.sleep(5)  # Wait longer for content to load

    print("\n" + "="*80)
    print("RENDERED PAGE SOURCE (first 10000 chars):")
    print("="*80)
    page_source = driver.page_source
    print(page_source[:10000])

    print("\n" + "="*80)
    print("SEARCHING FOR 'ogg' in page source:")
    print("="*80)

    # Find all occurrences of 'ogg' in the page
    lines_with_ogg = []
    for i, line in enumerate(page_source.split('\n')):
        if 'ogg' in line.lower():
            lines_with_ogg.append((i, line))

    if lines_with_ogg:
        for line_num, line in lines_with_ogg:
            print(f"Line {line_num}: {line.strip()}")
    else:
        print("No occurrences of 'ogg' found")

    print("\n" + "="*80)
    print("SEARCHING FOR 'audio' in page source:")
    print("="*80)

    lines_with_audio = []
    for i, line in enumerate(page_source.split('\n')):
        if 'audio' in line.lower():
            lines_with_audio.append((i, line))

    if lines_with_audio:
        for line_num, line in lines_with_audio[:20]:  # Show first 20 matches
            print(f"Line {line_num}: {line.strip()}")
    else:
        print("No occurrences of 'audio' found")

    # Save full page source
    output_file = "/Users/skoppar/workspace/kaushalavardhanam/speaking_buddy/data/lod_rendered_page.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(page_source)

    print(f"\n{'='*80}")
    print(f"Full page source saved to: {output_file}")

    driver.quit()

if __name__ == "__main__":
    main()
