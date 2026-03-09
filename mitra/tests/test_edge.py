"""Tests for edge modules (ASR, TTS, SLM) in mock mode."""

import numpy as np
import pytest

from config import Language, SAMPLE_RATE
from src.edge.asr_engine import ASREngine, TranscriptionResult
from src.edge.tts_engine import TTSEngine, SynthesisResult
from src.edge.slm import SLM, GenerationResult


@pytest.fixture(scope="module")
def asr():
    engine = ASREngine()
    engine.load_model()
    return engine


@pytest.fixture(scope="module")
def tts():
    engine = TTSEngine()
    engine.load_model()
    return engine


@pytest.fixture(scope="module")
def slm():
    model = SLM()
    model.load_model()
    return model


class TestASREngine:

    def test_transcribe_returns_transcription_result(self, asr, sample_audio):
        result = asr.transcribe(sample_audio, language="kn")
        assert isinstance(result, TranscriptionResult)

    def test_mock_text_is_non_empty(self, asr, sample_audio):
        result = asr.transcribe(sample_audio, language="kn")
        assert len(result.text) > 0

    def test_method_is_mock(self, asr, sample_audio):
        result = asr.transcribe(sample_audio, language="kn")
        assert result.method == "mock"

    def test_latency_under_1_second(self, asr, sample_audio):
        result = asr.transcribe(sample_audio, language="kn")
        assert result.latency_ms < 1000


class TestTTSEngine:

    def test_synthesize_returns_synthesis_result(self, tts):
        result = tts.synthesize("test text", language="kn")
        assert isinstance(result, SynthesisResult)

    def test_audio_is_float32_array(self, tts):
        result = tts.synthesize("test text")
        assert isinstance(result.audio, np.ndarray)
        assert result.audio.dtype == np.float32

    def test_audio_has_expected_length(self, tts):
        result = tts.synthesize("test text")
        # Mock produces 1 second at SAMPLE_RATE
        assert len(result.audio) == SAMPLE_RATE

    def test_method_is_mock(self, tts):
        result = tts.synthesize("test text")
        assert result.method == "mock"

    def test_latency_under_1_second(self, tts):
        result = tts.synthesize("test text")
        assert result.latency_ms < 1000


class TestSLM:

    def test_generate_returns_generation_result(self, slm):
        result = slm.generate("hello", language="kn")
        assert isinstance(result, GenerationResult)

    def test_mock_text_is_non_empty(self, slm):
        result = slm.generate("hello", language="kn")
        assert len(result.text) > 0

    def test_different_responses_for_kannada_vs_sanskrit(self, slm):
        kn_result = slm.generate("hello", language="kn")
        sa_result = slm.generate("hello", language="sa")
        assert kn_result.text != sa_result.text

    def test_method_is_mock(self, slm):
        result = slm.generate("hello", language="kn")
        assert result.method == "mock"

    def test_latency_under_1_second(self, slm):
        result = slm.generate("hello", language="kn")
        assert result.latency_ms < 1000
