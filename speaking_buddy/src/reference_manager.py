"""Reference audio download and caching manager"""
import requests
from pathlib import Path
from typing import Optional
from .config import REFERENCE_AUDIO_DIR, REFERENCE_URLS


def download_reference_audio(word: str, url: str) -> Path:
    """
    Download reference audio from URL and save to cache directory.

    Args:
        word: The word being downloaded (e.g., "moien")
        url: URL to download the audio from

    Returns:
        Path to the downloaded audio file

    Raises:
        requests.RequestException: If download fails
    """
    # Create filename from word
    filename = f"{word.lower()}.ogg"
    filepath = REFERENCE_AUDIO_DIR / filename

    # Download the file
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    # Save to file
    with open(filepath, 'wb') as f:
        f.write(response.content)

    return filepath


def get_reference_audio_path(word: str) -> Optional[Path]:
    """
    Get path to cached reference audio file.

    Args:
        word: The word to look up (e.g., "moien")

    Returns:
        Path to cached audio file if it exists, None otherwise
    """
    filename = f"{word.lower()}.ogg"
    filepath = REFERENCE_AUDIO_DIR / filename

    if filepath.exists():
        return filepath
    return None


def ensure_reference_exists(word: str) -> Path:
    """
    Ensure reference audio exists, downloading if necessary.

    Args:
        word: The word to ensure reference audio for (e.g., "moien")

    Returns:
        Path to the reference audio file

    Raises:
        ValueError: If word is not in REFERENCE_URLS
        requests.RequestException: If download fails
    """
    word_lower = word.lower()

    # Check if already cached
    cached_path = get_reference_audio_path(word_lower)
    if cached_path:
        return cached_path

    # Get URL for the word
    if word_lower not in REFERENCE_URLS:
        raise ValueError(f"No reference URL configured for word: {word}")

    url = REFERENCE_URLS[word_lower]

    # Download and return path
    return download_reference_audio(word_lower, url)
