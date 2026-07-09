"""Wake-word detection for "mitram" (FR-1).

openWakeWord scores 16 kHz mono chunks. The custom "mitram" onnx model is
trained in Phase 1 (synthetic speaker/accent/noise variants, FR-1.4); until it
exists, any openWakeWord pretrained model name (e.g. "hey_jarvis_v0.1") can
stand in via config so the rest of the pipeline can be developed.
"""

from __future__ import annotations

import numpy as np


class WakeWordDetector:
    def __init__(self, model: str = "models/mitram.onnx", threshold: float = 0.6):
        try:
            from openwakeword.model import Model
        except ImportError as e:
            raise ImportError(
                "openwakeword is required for wake-word detection. "
                "Install with: pip install 'mitram[wake]' (or openwakeword)"
            ) from e
        self._model = Model(wakeword_models=[model])
        self._threshold = threshold

    def process(self, chunk_16k_mono: np.ndarray) -> bool:
        """Score one 16 kHz mono float32 chunk; True on detection."""
        if len(chunk_16k_mono) == 0:
            return False
        pcm = (np.clip(chunk_16k_mono, -1.0, 1.0) * 32767).astype(np.int16)
        scores = self._model.predict(pcm)
        return max(scores.values()) >= self._threshold

    def reset(self) -> None:
        self._model.reset()
