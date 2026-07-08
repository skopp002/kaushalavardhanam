"""Tests for LanguageDetector using heuristic fallback (no ML models installed)."""

import numpy as np
import pytest

from config import Language, SAMPLE_RATE
from src.language_detector import LanguageDetector, DetectionResult


@pytest.fixture(scope="module")
def detector():
    """Shared LanguageDetector instance (models will not load, heuristic used)."""
    return LanguageDetector()


class TestLanguageDetector:

    def test_detect_returns_detection_result(self, detector, sample_audio):
        result = detector.detect(sample_audio)
        assert isinstance(result, DetectionResult)

    def test_confidence_between_0_and_1(self, detector, sample_audio):
        result = detector.detect(sample_audio)
        assert 0.0 <= result.confidence <= 1.0

    def test_language_is_kannada_or_sanskrit(self, detector, sample_audio):
        result = detector.detect(sample_audio)
        assert result.language in (Language.KANNADA, Language.SANSKRIT)

    def test_method_is_heuristic_when_no_models(self, detector, sample_audio):
        result = detector.detect(sample_audio)
        assert result.method == "heuristic"

    def test_very_short_audio_returns_low_confidence(self, detector):
        # Less than 0.1 seconds at 16 kHz -> triggers early return with 0.5 confidence
        short_audio = np.zeros(100, dtype=np.float32)
        result = detector.detect(short_audio)
        assert result.confidence == 0.5
        assert result.language == Language.KANNADA
