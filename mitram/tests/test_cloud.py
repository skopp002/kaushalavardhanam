"""Tests for cloud modules in mock/fallback mode (no AWS credentials)."""

import numpy as np
import pytest

from config import Language, SAMPLE_RATE
from src.cloud.translation_bridge import TranslationBridge, TranslationResult
from src.cloud.nova_sonic_client import NovaSonicClient, SonicResponse
from src.cloud.nova_vision_client import NovaVisionClient, VisionResponse


class TestTranslationBridge:

    def test_mock_translate_to_bridge(self):
        bridge = TranslationBridge()
        result = bridge.translate_to_bridge("namaskara", Language.KANNADA)

        assert isinstance(result, TranslationResult)
        assert len(result.translated_text) > 0
        # Will fall back to mock since no AWS credentials
        assert result.method in ("amazon_translate", "mock")

    def test_mock_translate_from_bridge(self):
        bridge = TranslationBridge()
        result = bridge.translate_from_bridge("namaste", Language.SANSKRIT)

        assert isinstance(result, TranslationResult)
        assert len(result.translated_text) > 0
        assert result.method in ("indictrans2", "mock")

    def test_is_bridge_needed_returns_true_for_both_languages(self):
        bridge = TranslationBridge()
        assert bridge.is_bridge_needed(Language.KANNADA) is True
        assert bridge.is_bridge_needed(Language.SANSKRIT) is True


class TestNovaSonicClient:

    def test_mock_mode_returns_sonic_response(self, sample_audio):
        client = NovaSonicClient()
        # Force mock mode
        client._mock_mode = True

        result = client.process_speech(sample_audio)

        assert isinstance(result, SonicResponse)
        assert result.success is True
        assert result.text is not None
        assert result.audio is not None

    def test_mock_response_audio_is_numpy_array(self, sample_audio):
        client = NovaSonicClient()
        client._mock_mode = True

        result = client.process_speech(sample_audio)
        assert isinstance(result.audio, np.ndarray)

    def test_connectivity_check_returns_false_without_credentials(self):
        client = NovaSonicClient()
        client._mock_mode = True
        assert client.check_connectivity() is False


class TestNovaVisionClient:

    def test_mock_mode_returns_vision_response(self, sample_image):
        client = NovaVisionClient()
        client._mock_mode = True

        result = client.ask_about_image(sample_image, "What is this?")

        assert isinstance(result, VisionResponse)
        assert result.success is True
        assert len(result.answer) > 0

    def test_connectivity_check_returns_false_without_credentials(self):
        client = NovaVisionClient()
        client._mock_mode = True
        assert client.check_connectivity() is False
