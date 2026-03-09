"""Language detection for Sanskrit vs Kannada audio input."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from config import (
    LANGUAGE_CONFIDENCE_THRESHOLD,
    LANGUAGE_DETECTION_TIMEOUT_SEC,
    SAMPLE_RATE,
    Language,
)

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Result of a language detection attempt."""

    language: Language
    confidence: float
    method: str  # "whisper_lid", "mms_lid", or "heuristic"


class LanguageDetector:
    """Detects whether audio contains Sanskrit or Kannada speech.

    Attempts model-based detection first (Whisper or MMS), falling back
    to an MFCC-based acoustic heuristic when models are unavailable.
    """

    def __init__(self):
        self._whisper_model = None
        self._mms_processor = None
        self._mms_model = None
        self._method: Optional[str] = None

        self._try_load_models()

    def _try_load_models(self) -> None:
        """Attempt to load language identification models in priority order."""
        if self._try_load_whisper():
            return
        if self._try_load_mms():
            return
        logger.info("No LID model available; will use acoustic heuristic fallback")
        self._method = "heuristic"

    def _try_load_whisper(self) -> bool:
        """Attempt to load the Whisper model for language identification."""
        try:
            import whisper

            self._whisper_model = whisper.load_model("base")
            self._method = "whisper_lid"
            logger.info("Loaded Whisper model for language identification")
            return True
        except ImportError:
            logger.debug("whisper package not available")
        except Exception as e:
            logger.debug("Failed to load Whisper model: %s", e)
        return False

    def _try_load_mms(self) -> bool:
        """Attempt to load Meta MMS for language identification."""
        try:
            from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

            model_name = "facebook/mms-lid-256"
            self._mms_processor = AutoFeatureExtractor.from_pretrained(model_name)
            self._mms_model = AutoModelForAudioClassification.from_pretrained(model_name)
            self._method = "mms_lid"
            logger.info("Loaded MMS model for language identification")
            return True
        except ImportError:
            logger.debug("transformers package not available")
        except Exception as e:
            logger.debug("Failed to load MMS model: %s", e)
        return False

    def detect(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> DetectionResult:
        """Detect whether the audio contains Sanskrit or Kannada speech.

        Args:
            audio: Float32 audio array, mono.
            sample_rate: Sample rate of the audio.

        Returns:
            DetectionResult with detected language, confidence, and method used.
        """
        start = time.monotonic()
        deadline = start + LANGUAGE_DETECTION_TIMEOUT_SEC

        if self._method == "whisper_lid":
            result = self._detect_whisper(audio, deadline)
        elif self._method == "mms_lid":
            result = self._detect_mms(audio, sample_rate, deadline)
        else:
            result = self._detect_heuristic(audio, sample_rate)

        elapsed = time.monotonic() - start
        logger.info(
            "Language detected: %s (confidence=%.2f, method=%s, time=%.2fs)",
            result.language.value,
            result.confidence,
            result.method,
            elapsed,
        )
        return result

    def _detect_whisper(self, audio: np.ndarray, deadline: float) -> DetectionResult:
        """Use Whisper's built-in language detection."""
        try:
            import whisper

            audio_padded = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio_padded).to(
                self._whisper_model.device
            )

            _, probs = self._whisper_model.detect_language(mel)

            sa_prob = probs.get("sa", 0.0)
            kn_prob = probs.get("kn", 0.0)

            if sa_prob >= kn_prob:
                total = sa_prob + kn_prob if (sa_prob + kn_prob) > 0 else 1.0
                return DetectionResult(
                    language=Language.SANSKRIT,
                    confidence=sa_prob / total,
                    method="whisper_lid",
                )
            else:
                total = sa_prob + kn_prob if (sa_prob + kn_prob) > 0 else 1.0
                return DetectionResult(
                    language=Language.KANNADA,
                    confidence=kn_prob / total,
                    method="whisper_lid",
                )
        except Exception as e:
            logger.warning("Whisper LID failed, falling back to heuristic: %s", e)
            return self._detect_heuristic(audio, SAMPLE_RATE)

    def _detect_mms(
        self, audio: np.ndarray, sample_rate: int, deadline: float
    ) -> DetectionResult:
        """Use Meta MMS model for language identification."""
        try:
            import torch

            inputs = self._mms_processor(
                audio, sampling_rate=sample_rate, return_tensors="pt"
            )

            with torch.no_grad():
                outputs = self._mms_model(**inputs)

            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)[0]

            id2label = self._mms_model.config.id2label

            sa_idx = None
            kn_idx = None
            for idx, label in id2label.items():
                if label == "san":
                    sa_idx = int(idx)
                elif label == "kan":
                    kn_idx = int(idx)

            sa_prob = float(probs[sa_idx]) if sa_idx is not None else 0.0
            kn_prob = float(probs[kn_idx]) if kn_idx is not None else 0.0

            if sa_prob >= kn_prob:
                total = sa_prob + kn_prob if (sa_prob + kn_prob) > 0 else 1.0
                return DetectionResult(
                    language=Language.SANSKRIT,
                    confidence=sa_prob / total,
                    method="mms_lid",
                )
            else:
                total = sa_prob + kn_prob if (sa_prob + kn_prob) > 0 else 1.0
                return DetectionResult(
                    language=Language.KANNADA,
                    confidence=kn_prob / total,
                    method="mms_lid",
                )
        except Exception as e:
            logger.warning("MMS LID failed, falling back to heuristic: %s", e)
            return self._detect_heuristic(audio, sample_rate)

    def _detect_heuristic(
        self, audio: np.ndarray, sample_rate: int
    ) -> DetectionResult:
        """Acoustic heuristic based on spectral features.

        Sanskrit (Indo-Aryan) and Kannada (Dravidian) differ in several
        phonological dimensions that manifest in acoustic features.
        Uses librosa if available, otherwise falls back to numpy-based
        spectral analysis.
        """
        try:
            import librosa
            _has_librosa = True
        except ImportError:
            _has_librosa = False

        if len(audio) < sample_rate * 0.1:
            return DetectionResult(
                language=Language.KANNADA,
                confidence=0.5,
                method="heuristic",
            )

        if _has_librosa:
            mfccs = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=13)
            spectral_centroid = librosa.feature.spectral_centroid(
                y=audio, sr=sample_rate
            )[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(
                y=audio, sr=sample_rate
            )[0]
            zcr = librosa.feature.zero_crossing_rate(audio)[0]

            mfcc_var = np.mean(np.var(mfccs, axis=1))
            centroid_mean = np.mean(spectral_centroid)
            rolloff_mean = np.mean(spectral_rolloff)
            zcr_mean = np.mean(zcr)
            high_mfcc_var = np.mean(np.var(mfccs[7:], axis=1))
        else:
            # Numpy-only fallback: use zero-crossing rate and spectral energy
            zcr_arr = np.abs(np.diff(np.sign(audio)))
            zcr_mean = float(np.mean(zcr_arr)) / 2.0

            # Spectral centroid via FFT
            fft_mag = np.abs(np.fft.rfft(audio))
            freqs = np.fft.rfftfreq(len(audio), d=1.0 / sample_rate)
            centroid_mean = float(np.sum(freqs * fft_mag) / (np.sum(fft_mag) + 1e-10))
            rolloff_mean = centroid_mean * 1.5
            mfcc_var = float(np.var(audio) * 1000)
            high_mfcc_var = mfcc_var * 0.4

        sanskrit_score = 0.0

        centroid_norm = centroid_mean / (sample_rate / 2)
        if centroid_norm > 0.25:
            sanskrit_score += 0.2
        elif centroid_norm < 0.18:
            sanskrit_score -= 0.2

        if mfcc_var > 40.0:
            sanskrit_score += 0.15
        elif mfcc_var < 25.0:
            sanskrit_score -= 0.15

        rolloff_norm = rolloff_mean / (sample_rate / 2)
        if rolloff_norm > 0.6:
            sanskrit_score += 0.15
        elif rolloff_norm < 0.4:
            sanskrit_score -= 0.15

        if zcr_mean > 0.08:
            sanskrit_score += 0.1
        elif zcr_mean < 0.05:
            sanskrit_score -= 0.1

        if high_mfcc_var > 15.0:
            sanskrit_score += 0.15
        elif high_mfcc_var < 8.0:
            sanskrit_score -= 0.15

        raw_confidence = (sanskrit_score + 0.75) / 1.5
        raw_confidence = max(0.0, min(1.0, raw_confidence))

        if raw_confidence >= 0.5:
            return DetectionResult(
                language=Language.SANSKRIT,
                confidence=0.5 + (raw_confidence - 0.5) * 0.6,
                method="heuristic",
            )
        else:
            return DetectionResult(
                language=Language.KANNADA,
                confidence=0.5 + (0.5 - raw_confidence) * 0.6,
                method="heuristic",
            )
