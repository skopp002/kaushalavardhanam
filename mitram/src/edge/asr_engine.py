"""On-device speech-to-text engine for Kannada and Sanskrit."""

import time
import logging
from dataclasses import dataclass

import numpy as np

from config import (
    EDGE_ASR_MODEL,
    SAMPLE_RATE,
    ASR_TIMEOUT_SEC,
    Language,
)

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result of a speech-to-text transcription."""

    text: str
    language: str
    confidence: float
    latency_ms: float
    method: str  # "whisper", "indicwhisper", "mock"


class ASREngine:
    """On-device automatic speech recognition using Whisper-based models.

    Supports Kannada (primary) and Sanskrit (best-effort).
    Falls back to mock mode when model dependencies are unavailable.
    """

    _MOCK_RESPONSES = {
        Language.KANNADA: "ನಮಸ್ಕಾರ, ಇದು ಪರೀಕ್ಷೆ",
        Language.SANSKRIT: "नमस्कारः, इदं परीक्षणम्",
    }

    def __init__(self, model_name: str = EDGE_ASR_MODEL, device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._model = None
        self._processor = None
        self._mock_mode = False
        self._loaded = False

    def load_model(self) -> bool:
        """Load the ASR model. Returns True on success (including mock mode)."""
        if self._loaded:
            return True

        try:
            from transformers import WhisperProcessor, WhisperForConditionalGeneration

            logger.info("Loading ASR model: %s on %s", self._model_name, self._device)
            self._processor = WhisperProcessor.from_pretrained(self._model_name)
            self._model = WhisperForConditionalGeneration.from_pretrained(
                self._model_name
            ).to(self._device)
            self._mock_mode = False
            self._loaded = True
            logger.info("ASR model loaded successfully")
        except Exception as exc:
            logger.warning(
                "Could not load ASR model (%s), falling back to mock mode: %s",
                self._model_name,
                exc,
            )
            self._mock_mode = True
            self._loaded = True

        return True

    def is_loaded(self) -> bool:
        """Check whether the engine is ready to transcribe."""
        return self._loaded

    def unload_model(self) -> None:
        """Release model resources."""
        self._model = None
        self._processor = None
        self._loaded = False
        self._mock_mode = False
        logger.info("ASR model unloaded")

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = SAMPLE_RATE,
        language: str = None,
    ) -> TranscriptionResult:
        """Transcribe audio to text.

        Args:
            audio: Audio waveform as a 1-D float32 numpy array.
            sample_rate: Sample rate of the audio in Hz.
            language: BCP-47 language code (e.g. "kn", "sa"). If None, auto-detect.

        Returns:
            TranscriptionResult with transcription text and metadata.
        """
        if not self._loaded:
            self.load_model()

        start = time.perf_counter()

        if self._mock_mode:
            result = self._transcribe_mock(language)
        else:
            result = self._transcribe_whisper(audio, sample_rate, language)

        result.latency_ms = (time.perf_counter() - start) * 1000

        if result.latency_ms > ASR_TIMEOUT_SEC * 1000:
            logger.warning(
                "ASR latency %.0f ms exceeds target %s s",
                result.latency_ms,
                ASR_TIMEOUT_SEC,
            )

        return result

    def _transcribe_whisper(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str | None,
    ) -> TranscriptionResult:
        """Transcribe using the loaded Whisper model."""
        import torch

        audio = audio.astype(np.float32)
        if audio.ndim > 1:
            audio = audio.mean(axis=-1)

        inputs = self._processor(
            audio, sampling_rate=sample_rate, return_tensors="pt"
        ).input_features.to(self._device)

        forced_decoder_ids = None
        if language:
            forced_decoder_ids = self._processor.get_decoder_prompt_ids(
                language=self._language_code_to_whisper(language), task="transcribe"
            )

        with torch.no_grad():
            predicted_ids = self._model.generate(
                inputs, forced_decoder_ids=forced_decoder_ids
            )

        text = self._processor.batch_decode(predicted_ids, skip_special_tokens=True)[0]
        resolved_language = language or Language.KANNADA.value

        method = (
            "indicwhisper" if "indic" in self._model_name.lower() else "whisper"
        )

        return TranscriptionResult(
            text=text.strip(),
            language=resolved_language,
            confidence=0.85,
            latency_ms=0.0,
            method=method,
        )

    def _transcribe_mock(self, language: str | None) -> TranscriptionResult:
        """Return placeholder transcription for testing without models."""
        lang = Language(language) if language else Language.KANNADA
        text = self._MOCK_RESPONSES.get(lang, self._MOCK_RESPONSES[Language.KANNADA])

        return TranscriptionResult(
            text=text,
            language=lang.value,
            confidence=1.0,
            latency_ms=0.0,
            method="mock",
        )

    @staticmethod
    def _language_code_to_whisper(code: str) -> str:
        """Map BCP-47 language codes to Whisper language identifiers."""
        mapping = {
            "kn": "kannada",
            "sa": "sanskrit",
            "hi": "hindi",
            "en": "english",
        }
        return mapping.get(code, code)
