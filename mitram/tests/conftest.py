"""Shared fixtures for Mitra test suite."""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Ensure the Mitra project root is on sys.path so that
# `from config import ...` works the same way it does in production code.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_audio():
    """1 second of 440 Hz sine wave as a float32 numpy array at 16 kHz."""
    sample_rate = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)
    return audio


@pytest.fixture
def sample_image():
    """640x480 random RGB image as a uint8 numpy array."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, size=(480, 640, 3), dtype=np.uint8)


@pytest.fixture
def tmp_dir(tmp_path):
    """Temporary directory for output files (pytest built-in tmp_path)."""
    return tmp_path
