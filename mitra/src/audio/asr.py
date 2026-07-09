"""Local ASR (FR-4.2): Whisper via mlx-whisper for en/kn, with an optional
Sanskrit fine-tune rescue pass.

Whisper has no Sanskrit language code — Devanagari output usually comes back
tagged "hi". When the transcript is Devanagari-dominant and a Sanskrit model is
configured, the audio is re-transcribed with the fine-tune and tagged "sa"
(experimental, REQUIREMENTS R7).
"""

from __future__ import annotations

import numpy as np

from mitra import language_detector


class Transcriber:
    def __init__(self, default_model: str = "mlx-community/whisper-large-v3-mlx",
                 sanskrit_model: str | None = None, backend: str = "mlx",
                 device: str = "mps"):
        if backend != "mlx":
            raise ValueError(f"unsupported ASR backend: {backend!r} (v1 uses mlx)")
        self._default_model = default_model
        self._sanskrit_model = sanskrit_model
        self._device = device
        self._sa_pipeline = None  # lazy: only load if Sanskrit is actually spoken

    def transcribe(self, audio_16k_mono: np.ndarray) -> tuple[str, str | None]:
        """Returns (transcript, language hint from the ASR engine)."""
        import mlx_whisper

        audio = np.asarray(audio_16k_mono, dtype=np.float32)
        peak = float(np.abs(audio).max())
        if peak > 0:  # normalize: Whisper mis-hears quiet capture badly
            audio = audio / peak * 0.9
        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self._default_model,
        )
        text = result.get("text", "").strip()
        lang = result.get("language")

        if self._sanskrit_model and language_detector.detect(text, lang) == "sa":
            try:
                text, lang = self._transcribe_sanskrit(audio_16k_mono), "sa"
            except Exception:  # experimental path must not break the turn (R7)
                pass
        return text, lang

    def _transcribe_sanskrit(self, audio: np.ndarray) -> str:
        if self._sa_pipeline is None:
            from transformers import pipeline

            self._sa_pipeline = pipeline(
                "automatic-speech-recognition",
                model=self._sanskrit_model,
                device=self._device,
            )
        out = self._sa_pipeline(
            {"array": np.asarray(audio, dtype=np.float32), "sampling_rate": 16000}
        )
        return out["text"].strip()
