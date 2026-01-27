#!/usr/bin/env python3
"""
Helper script to add audio URLs for words in the word bank.

Usage:
    python scripts/add_word_urls.py <word> <url>

Example:
    python scripts/add_word_urls.py äddi "https://lod.lu/uploads/examples/OGG/ab/abc123.ogg"

This script updates src/config.py to add the audio URL for a specified word.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import WORD_BANK


def add_word_url(word: str, url: str):
    """Add or update audio URL for a word in config.py"""

    # Check if word exists
    if word not in WORD_BANK:
        print(f"❌ Error: Word '{word}' not found in WORD_BANK")
        print(f"\nAvailable words: {', '.join(sorted(WORD_BANK.keys()))}")
        return False

    # Read config file
    config_path = project_root / "src" / "config.py"
    with open(config_path, 'r') as f:
        lines = f.readlines()

    # Find the word entry and update URL
    in_word_entry = False
    word_found = False
    updated_lines = []

    for i, line in enumerate(lines):
        if f'"{word}":' in line and '{' in line:
            in_word_entry = True
            word_found = True
            updated_lines.append(line)
        elif in_word_entry and '"url":' in line:
            # Replace the URL line
            indent = len(line) - len(line.lstrip())
            updated_lines.append(f'{" " * indent}"url": "{url}"\n')
            in_word_entry = False
        else:
            updated_lines.append(line)

    if not word_found:
        print(f"❌ Error: Could not find word entry for '{word}' in config.py")
        return False

    # Write back to file
    with open(config_path, 'w') as f:
        f.writelines(updated_lines)

    print(f"✅ Successfully updated URL for '{word}'")
    print(f"   Word: {word}")
    print(f"   Translation: {WORD_BANK[word]['translation']}")
    print(f"   Category: {WORD_BANK[word]['category']}")
    print(f"   URL: {url}")

    return True


def list_words_without_urls():
    """List all words that don't have audio URLs yet"""
    words_without_urls = [
        (word, info['translation'], info['category'])
        for word, info in WORD_BANK.items()
        if info['url'] is None
    ]

    if not words_without_urls:
        print("✅ All words have audio URLs!")
        return

    print(f"📋 Words without audio URLs ({len(words_without_urls)}):\n")

    # Group by category
    by_category = {}
    for word, translation, category in words_without_urls:
        if category not in by_category:
            by_category[category] = []
        by_category[category].append((word, translation))

    for category, words in sorted(by_category.items()):
        print(f"\n{category.upper()}:")
        for word, translation in words:
            print(f"  - {word} ({translation})")


def main():
    if len(sys.argv) == 1:
        # No arguments - show words without URLs
        print("Speaking Buddy - Word URL Manager\n")
        list_words_without_urls()
        print("\n" + "=" * 60)
        print("Usage:")
        print('  python scripts/add_word_urls.py <word> "<url>"')
        print("\nExample:")
        print('  python scripts/add_word_urls.py äddi "https://lod.lu/uploads/examples/OGG/ab/abc123.ogg"')
        return

    if len(sys.argv) != 3:
        print("❌ Error: Invalid arguments")
        print('Usage: python scripts/add_word_urls.py <word> "<url>"')
        sys.exit(1)

    word = sys.argv[1]
    url = sys.argv[2]

    # Validate URL
    if not url.startswith('http'):
        print("❌ Error: URL must start with http:// or https://")
        sys.exit(1)

    # Add the URL
    if add_word_url(word, url):
        print("\n✅ Config updated successfully!")
        print("\nRemaining words without URLs:")
        list_words_without_urls()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
