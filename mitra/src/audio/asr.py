"""Audio-first ASR: mlx-whisper unified multilingual transcription on Apple Silicon.

Extracts both transcript text and detected language directly in a single forward pass.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("mitra")


class Transcriber:
    """Transcribe 16 kHz mono audio and return ``(text, detected_language)``."""

    def __init__(self, *, model: str = "mlx-community/whisper-large-v3-turbo",
                 english_fallback_model: str | None = None,
                 transcribe_fn=None, **kwargs):
        # Support 'model' as well as legacy 'english_fallback_model'
        self._model_id = model or english_fallback_model or "mlx-community/whisper-large-v3-turbo"
        self._transcribe_fn = transcribe_fn

    def transcribe(self, audio_16k_mono: np.ndarray) -> tuple[str, str | None]:
        audio = _normalise_audio(audio_16k_mono)
        peak = float(np.abs(audio_16k_mono).max()) if len(audio_16k_mono) else 0.0
        if peak < 0.008:
            return "", None

        if self._transcribe_fn is not None:
            result = self._transcribe_fn(audio)
            if isinstance(result, tuple):
                return result
            return str(result).strip(), None

        import mlx_whisper

        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self._model_id,
            condition_on_previous_text=False,
            initial_prompt="English, Sanskrit, Kannada conversation with Mitra.",
        )
        text = str(result.get("text", "")).strip()
        language = result.get("language")
        if language:
            language = str(language).lower()
        logger.info("ASR transcript: %r (detected lang: %s)", text, language)
        return text, language

    def warmup(self) -> None:
        """Load the whisper model before microphone processing begins."""
        silence = np.zeros(8000, dtype=np.float32)
        try:
            self.transcribe(silence)
        except Exception:
            logger.exception("ASR warmup failed")


def _normalise_audio(audio_16k_mono: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio_16k_mono, dtype=np.float32).reshape(-1)
    peak = float(np.abs(audio).max()) if audio.size else 0.0
    return audio / peak * 0.9 if peak > 0 else audio
