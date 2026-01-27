# LOD Audio URL Fetching - Summary

## Overview
Successfully fetched audio URLs from lod.lu (Luxembourgish Online Dictionary) for 49 Luxembourgish words across 5 categories.

## Results
- **Success Rate**: 49/49 (100%)
- **Total Words**: 49
- **Failed Initially**: 1 (frau - later resolved manually)

## Categories and Word Count
1. **Greetings** (9 words): äddi, merci, wëllkomm, pardon, jo, nee, wéi, gär, bis
2. **Numbers** (10 words): eent, zwee, dräi, véier, fënnef, sechs, siwen, aacht, néng, zéng
3. **Family** (10 words): papp, mamm, kand, jong, meedchen, frau, mann, brudder, schwëster, grousselteren
4. **Objects** (10 words): haus, dier, fënster, buch, stull, dësch, auto, telefon, waasser, kaffi
5. **Time/Nature** (10 words): dag, nuecht, mëtteg, owes, sonn, mound, stierm, reen, schnéi, loft

## Technical Approach

### Initial Challenges
1. **JavaScript-Rendered Site**: lod.lu is a Vue.js single-page application that doesn't serve content in static HTML
2. **URL Structure**: Initial attempts with various URL patterns (e.g., `/artikel/WORD`) all returned 404 errors
3. **API Discovery**: Used Selenium to capture network traffic and discovered the API endpoints

### Solution
Used the LOD.lu REST API with a two-step process:

#### Step 1: Search API
```
GET https://lod.lu/api/lb/search?_app_name=LOD&lang=lb&query={word}
```
Returns search results with `article_id` for each matching entry.

#### Step 2: Entry API
```
GET https://lod.lu/api/lb/entry/{article_id}?_app_name=LOD
```
Returns full article details including:
- Word pronunciation (IPA)
- Translations in multiple languages (German, French, English, Portuguese, Dutch)
- Audio files in OGG and AAC formats
- Example sentences with audio

### Audio URL Pattern
All audio URLs follow this pattern:
```
https://lod.lu/uploads/OGG/{article_id_lowercase}.ogg
```

For example:
- haus → `https://lod.lu/uploads/OGG/haus1.ogg`
- merci → `https://lod.lu/uploads/OGG/merci2.ogg`
- eent → `https://lod.lu/uploads/OGG/eent1.ogg`

## Special Cases

### "frau" (woman)
- Initial search for "frau" returned no results
- The correct Luxembourgish spelling is "Fra" (not "frau")
- Manual search found article ID: FRA1
- Audio URL: `https://lod.lu/uploads/OGG/fra1.ogg`

## Output Files

### 1. Complete List
**File**: `/Users/skoppar/workspace/kaushalavardhanam/speaking_buddy/data/lod_audio_urls.json`

Contains all 49 words mapped to their audio URLs in a flat dictionary structure.

### 2. Categorized List
**File**: `/Users/skoppar/workspace/kaushalavardhanam/speaking_buddy/data/lod_audio_urls_by_category.json`

Contains words organized by category for easier reference.

## Scripts Created

1. **fetch_all_lod_audio.py** - Main script using LOD API (RECOMMENDED)
2. **fetch_lod_audio.py** - Initial attempt using requests library
3. **fetch_lod_audio_selenium.py** - Selenium-based approach for JavaScript rendering
4. **test_artikel_url.py** - URL pattern testing script
5. **test_article_api.py** - API endpoint discovery script
6. **capture_api_calls.py** - Network traffic capture using Selenium
7. **debug_lod_page.py** - Page source debugging script
8. **inspect_lod_response.py** - HTML response inspection

## Usage Example

```python
import json

# Load the audio URLs
with open('data/lod_audio_urls.json', 'r', encoding='utf-8') as f:
    audio_urls = json.load(f)

# Get audio URL for a specific word
haus_audio = audio_urls['haus']
print(f"Haus pronunciation: {haus_audio}")
# Output: https://lod.lu/uploads/OGG/haus1.ogg
```

## Verification
All audio URLs were verified to be accessible (HTTP 200 status code).

Sample verification:
```bash
curl -I "https://lod.lu/uploads/OGG/haus1.ogg"
# HTTP/2 200
# server: nginx

curl -I "https://lod.lu/uploads/OGG/fra1.ogg"
# HTTP/2 200
# server: nginx
```

## Dependencies Used
- **requests**: HTTP requests to LOD API
- **beautifulsoup4**: HTML parsing (for initial attempts)
- **selenium**: Browser automation for API discovery
- **webdriver-manager**: Automatic ChromeDriver management

## Key Learnings
1. Modern web applications often require API-based approaches rather than HTML scraping
2. Network traffic inspection is valuable for discovering API endpoints
3. Dictionary spellings may differ from common usage (e.g., "Fra" vs "frau")
4. LOD provides high-quality audio recordings for Luxembourgish pronunciation

## Recommendations
- Use the `fetch_all_lod_audio.py` script for future updates
- The API appears stable and well-documented
- Consider caching audio files locally to reduce API calls
- Audio files are available in both OGG and AAC formats (we used OGG)
