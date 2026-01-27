"""Reference audio download and caching manager"""
import requests
from pathlib import Path
from typing import Optional
from pydub import AudioSegment
from .config import REFERENCE_AUDIO_DIR, REFERENCE_URLS


def download_reference_audio(word: str, url: str) -> Path:
    """
    Download reference audio from URL, convert to WAV, and save to cache directory.

    Args:
        word: The word being downloaded (e.g., "moien")
        url: URL to download the audio from

    Returns:
        Path to the converted WAV audio file

    Raises:
        requests.RequestException: If download fails
    """
    # Create filename from word
    ogg_filename = f"{word.lower()}.ogg"
    ogg_filepath = REFERENCE_AUDIO_DIR / ogg_filename
    wav_filepath = REFERENCE_AUDIO_DIR / f"{word.lower()}.wav"

    # Download the OGG file
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    # Save OGG to temporary file
    with open(ogg_filepath, 'wb') as f:
        f.write(response.content)

    # Convert OGG to WAV for Parselmouth compatibility
    audio = AudioSegment.from_ogg(ogg_filepath)
    audio.export(wav_filepath, format="wav")

    # Clean up OGG file (optional - keep both for now)
    # ogg_filepath.unlink()

    return wav_filepath


def get_reference_audio_path(word: str) -> Optional[Path]:
    """
    Get path to cached reference audio file (WAV format).

    Args:
        word: The word to look up (e.g., "moien")

    Returns:
        Path to cached audio file if it exists, None otherwise
    """
    # Check for WAV file (Parselmouth-compatible format)
    wav_filepath = REFERENCE_AUDIO_DIR / f"{word.lower()}.wav"
    if wav_filepath.exists():
        return wav_filepath

    # Also check for OGG (legacy) and convert if found
    ogg_filepath = REFERENCE_AUDIO_DIR / f"{word.lower()}.ogg"
    if ogg_filepath.exists():
        # Convert existing OGG to WAV
        audio = AudioSegment.from_ogg(ogg_filepath)
        audio.export(wav_filepath, format="wav")
        return wav_filepath

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
