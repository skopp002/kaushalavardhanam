"""On-device text-to-speech engine for Kannada."""

import time
import logging
from dataclasses import dataclass

import numpy as np

from config import (
    EDGE_TTS_MODEL,
    SAMPLE_RATE,
    TTS_TIMEOUT_SEC,
)

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    """Result of a text-to-speech synthesis."""

    audio: np.ndarray
    sample_rate: int
    latency_ms: float
    method: str  # "indic_tts", "mock"


class TTSEngine:
    """On-device text-to-speech synthesis for Kannada.

    Uses an Indic TTS model when available, otherwise falls back to mock mode
    that generates a simple sine wave tone as placeholder audio.
    """

    def __init__(self, model_name: str = EDGE_TTS_MODEL, device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._model = None
        self._mock_mode = False
        self._loaded = False

    def load_model(self) -> bool:
        """Load the TTS model. Returns True on success (including mock mode)."""
        if self._loaded:
            return True

        try:
            from transformers import AutoTokenizer, AutoModelForTextToWaveform

            logger.info("Loading TTS model: %s on %s", self._model_name, self._device)
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModelForTextToWaveform.from_pretrained(
                self._model_name
            ).to(self._device)
            self._mock_mode = False
            self._loaded = True
            logger.info("TTS model loaded successfully")
        except Exception as exc:
            logger.warning(
                "Could not load TTS model (%s), falling back to mock mode: %s",
                self._model_name,
                exc,
            )
            self._mock_mode = True
            self._loaded = True

        return True

    def is_loaded(self) -> bool:
        """Check whether the engine is ready to synthesize."""
        return self._loaded

    def unload_model(self) -> None:
        """Release model resources."""
        self._model = None
        self._loaded = False
        self._mock_mode = False
        logger.info("TTS model unloaded")

    def synthesize(self, text: str, language: str = "kn") -> SynthesisResult:
        """Synthesize speech from text.

        Args:
            text: Input text to convert to speech.
            language: BCP-47 language code (default "kn" for Kannada).

        Returns:
            SynthesisResult containing the audio waveform and metadata.
        """
        if not self._loaded:
            self.load_model()

        start = time.perf_counter()

        if self._mock_mode:
            result = self._synthesize_mock(text)
        else:
            result = self._synthesize_model(text, language)

        result.latency_ms = (time.perf_counter() - start) * 1000

        if result.latency_ms > TTS_TIMEOUT_SEC * 1000:
            logger.warning(
                "TTS latency %.0f ms exceeds target %s s",
                result.latency_ms,
                TTS_TIMEOUT_SEC,
            )

        return result

    def _synthesize_model(self, text: str, language: str) -> SynthesisResult:
        """Synthesize using the loaded TTS model."""
        import torch

        inputs = self._tokenizer(text, return_tensors="pt").to(self._device)

        with torch.no_grad():
            output = self._model(**inputs)

        audio = output.waveform.squeeze().cpu().numpy().astype(np.float32)

        return SynthesisResult(
            audio=audio,
            sample_rate=SAMPLE_RATE,
            latency_ms=0.0,
            method="indic_tts",
        )

    def _synthesize_mock(self, text: str) -> SynthesisResult:
        """Generate a 1-second 440 Hz sine wave as placeholder audio."""
        duration_sec = 1.0
        t = np.linspace(0, duration_sec, int(SAMPLE_RATE * duration_sec), endpoint=False)
        audio = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

        return SynthesisResult(
            audio=audio,
            sample_rate=SAMPLE_RATE,
            latency_ms=0.0,
            method="mock",
        )
