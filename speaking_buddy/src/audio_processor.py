"""Audio processing and feature extraction"""
import librosa
import numpy as np
from pathlib import Path
from typing import Tuple
from .config import SAMPLE_RATE, N_MFCC


def load_audio(filepath: Path, target_sr: int = SAMPLE_RATE) -> Tuple[np.ndarray, int]:
    """
    Load audio file, convert to mono, and resample.

    Args:
        filepath: Path to audio file
        target_sr: Target sample rate in Hz

    Returns:
        Tuple of (audio data as numpy array, sample rate)
    """
    audio, sr = librosa.load(filepath, sr=target_sr, mono=True)
    return audio, sr


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """
    Normalize audio amplitude to [-1, 1] range.

    Args:
        audio: Audio data as numpy array

    Returns:
        Normalized audio array
    """
    if len(audio) == 0:
        return audio

    max_val = np.abs(audio).max()
    if max_val > 0:
        return audio / max_val
    return audio


def trim_silence(audio: np.ndarray, sr: int, top_db: int = 20) -> np.ndarray:
    """
    Remove leading and trailing silence from audio.

    Args:
        audio: Audio data as numpy array
        sr: Sample rate
        top_db: Threshold in dB below reference to consider as silence

    Returns:
        Trimmed audio array
    """
    trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
    return trimmed


def extract_mfcc(audio: np.ndarray, sr: int, n_mfcc: int = N_MFCC) -> np.ndarray:
    """
    Extract MFCC (Mel-Frequency Cepstral Coefficients) features from audio.

    Args:
        audio: Audio data as numpy array
        sr: Sample rate
        n_mfcc: Number of MFCC coefficients to extract

    Returns:
        MFCC features as numpy array of shape (n_mfcc, time_steps)
    """
    mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=n_mfcc)
    return mfcc


def preprocess_audio(filepath: Path) -> Tuple[np.ndarray, int]:
    """
    Complete audio preprocessing pipeline: load, normalize, and trim silence.

    Args:
        filepath: Path to audio file

    Returns:
        Tuple of (preprocessed audio array, sample rate)
    """
    audio, sr = load_audio(filepath)
    audio = normalize_audio(audio)
    audio = trim_silence(audio, sr)
    return audio, sr
