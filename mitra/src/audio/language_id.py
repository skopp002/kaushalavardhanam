"""Audio-first language identification with Vakgyata.

Vakgyata labels its classes with BCP-47-ish codes (for example ``kn-IN``).
The rest of Mitra uses the ISO-639-1 language portion, so this module is the
single place where that conversion happens.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LanguagePrediction:
    """The most likely spoken language and its softmax confidence."""

    language: str
    confidence: float


class SpeechLanguageIdentifier:
    """Lazy Hugging Face wrapper for ``onecxi/vakgyata-mini``."""

    def __init__(self, model: str = "onecxi/vakgyata-mini", device: str = "mps"):
        self._model_id = model
        self._device = device
        self._processor = None
        self._model = None
        self._torch = None

    def predict(self, audio_16k_mono: np.ndarray) -> LanguagePrediction:
        self._ensure_loaded()
        audio = np.asarray(audio_16k_mono, dtype=np.float32).reshape(-1)
        inputs = self._processor(audio, sampling_rate=16000, return_tensors="pt")
        inputs = {name: value.to(self._device) for name, value in inputs.items()}
        with self._torch.inference_mode():
            logits = self._model(**inputs).logits
            probabilities = logits.softmax(dim=-1)[0]
        index = int(probabilities.argmax().item())
        label = str(self._model.config.id2label[index])
        return LanguagePrediction(_normalise_label(label), float(probabilities[index]))

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoFeatureExtractor, Wav2Vec2ForSequenceClassification

        self._torch = torch
        self._processor = AutoFeatureExtractor.from_pretrained(self._model_id)
        self._model = Wav2Vec2ForSequenceClassification.from_pretrained(self._model_id)
        self._model.to(self._device)
        self._model.eval()


def _normalise_label(label: str) -> str:
    """Convert Vakgyata labels such as ``kn-IN`` to ``kn``."""
    return label.replace("_", "-").split("-", 1)[0].lower()
