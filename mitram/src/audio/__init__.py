"""Audio pipeline: wake word (FR-1), VAD segmentation (FR-4.1), ASR (FR-4.2)."""

from __future__ import annotations

import numpy as np

TARGET_SAMPLERATE = 16000


def resample(wav: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    """Linear-interpolation resampler — good enough for speech pipelines here."""
    wav = np.asarray(wav, dtype=np.float32).reshape(-1)
    if sr_from == sr_to or len(wav) == 0:
        return wav
    n = int(round(len(wav) * sr_to / sr_from))
    x_old = np.linspace(0.0, 1.0, num=len(wav), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n, endpoint=False)
    return np.interp(x_new, x_old, wav).astype(np.float32)
