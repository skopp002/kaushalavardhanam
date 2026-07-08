"""On-device Visual Question Answering combining vision and language models."""

import time
import logging
from dataclasses import dataclass
from typing import List

import numpy as np

from config import (
    EDGE_VQA_MODEL,
    VQA_TIMEOUT_SEC,
    Language,
)
from src.edge.slm import SLM

logger = logging.getLogger(__name__)


@dataclass
class VQAResult:
    """Result of a visual question answering query."""

    answer: str
    language: str
    confidence: float
    latency_ms: float
    method: str  # "moondream", "slm_with_labels", "mock"


class EdgeVQA:
    """On-device Visual Question Answering.

    Uses Moondream VLM when available for direct image understanding.
    Falls back to combining object detection labels with the SLM for
    text-based reasoning about the scene.
    """

    _MOCK_TEMPLATES = {
        Language.KANNADA: "ಚಿತ್ರದಲ್ಲಿ {labels} ಇದೆ.",
        Language.SANSKRIT: "चित्रे {labels} अस्ति।",
    }

    def __init__(self, slm: SLM = None, device: str = "cpu"):
        self._slm = slm
        self._device = device
        self._vlm_model = None
        self._vlm_tokenizer = None
        self._vlm_available = False
        self._mock_mode = False
        self._loaded = False

    def load_model(self) -> bool:
        """Load the VQA model. Returns True on success (including fallback modes)."""
        if self._loaded:
            return True

        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer

            logger.info("Loading VQA model: %s on %s", EDGE_VQA_MODEL, self._device)
            self._vlm_tokenizer = AutoTokenizer.from_pretrained(
                EDGE_VQA_MODEL, trust_remote_code=True
            )
            self._vlm_model = AutoModelForCausalLM.from_pretrained(
                EDGE_VQA_MODEL, trust_remote_code=True
            ).to(self._device)
            self._vlm_available = True
            self._mock_mode = False
            self._loaded = True
            logger.info("VQA model (Moondream) loaded successfully")
        except Exception as exc:
            logger.warning(
                "Could not load VQA model (%s): %s", EDGE_VQA_MODEL, exc
            )
            self._vlm_available = False

            if self._slm is not None:
                if not self._slm.is_loaded():
                    self._slm.load_model()
                self._mock_mode = False
                logger.info("VQA falling back to SLM with object labels")
            else:
                self._mock_mode = True
                logger.info("VQA falling back to mock mode (no SLM provided)")

            self._loaded = True

        return True

    def is_loaded(self) -> bool:
        """Check whether the engine is ready to answer queries."""
        return self._loaded

    def unload_model(self) -> None:
        """Release model resources."""
        self._vlm_model = None
        self._vlm_tokenizer = None
        self._vlm_available = False
        self._loaded = False
        self._mock_mode = False
        logger.info("VQA model unloaded")

    def answer_query(
        self,
        question: str,
        frame: np.ndarray,
        object_labels: List[str] = None,
        language: str = "kn",
    ) -> VQAResult:
        """Answer a question about a visual scene.

        Args:
            question: Natural language question about the image.
            frame: Image frame as a numpy array (H, W, C) in BGR or RGB format.
            object_labels: Optional list of detected object labels in the scene.
            language: Target language code for the answer.

        Returns:
            VQAResult with the answer text and metadata.
        """
        if not self._loaded:
            self.load_model()

        start = time.perf_counter()

        if self._vlm_available:
            result = self._answer_with_vlm(question, frame, language)
        elif self._slm is not None and not self._mock_mode:
            result = self._answer_with_slm(question, object_labels, language)
        else:
            result = self._answer_mock(question, object_labels, language)

        result.latency_ms = (time.perf_counter() - start) * 1000

        if result.latency_ms > VQA_TIMEOUT_SEC * 1000:
            logger.warning(
                "VQA latency %.0f ms exceeds target %s s",
                result.latency_ms,
                VQA_TIMEOUT_SEC,
            )

        return result

    def _answer_with_vlm(
        self, question: str, frame: np.ndarray, language: str
    ) -> VQAResult:
        """Answer using the Moondream VLM directly on the image."""
        from PIL import Image

        if frame.ndim == 3 and frame.shape[2] == 3:
            image = Image.fromarray(frame)
        else:
            image = Image.fromarray(frame)

        encoded_image = self._vlm_model.encode_image(image)
        english_answer = self._vlm_model.answer_question(encoded_image, question, self._vlm_tokenizer)

        answer = self._translate_if_needed(english_answer, language)

        return VQAResult(
            answer=answer,
            language=language,
            confidence=0.8,
            latency_ms=0.0,
            method="moondream",
        )

    def _answer_with_slm(
        self,
        question: str,
        object_labels: List[str] | None,
        language: str,
    ) -> VQAResult:
        """Answer using the SLM with object detection labels as context."""
        labels_text = ", ".join(object_labels) if object_labels else "unknown objects"
        vision_context = f"The image shows: {labels_text}"

        gen_result = self._slm.generate(
            prompt=question,
            language=language,
            vision_context=vision_context,
        )

        return VQAResult(
            answer=gen_result.text,
            language=language,
            confidence=0.6,
            latency_ms=0.0,
            method="slm_with_labels",
        )

    def _answer_mock(
        self,
        question: str,
        object_labels: List[str] | None,
        language: str,
    ) -> VQAResult:
        """Return a simple mock answer incorporating object labels."""
        lang = Language(language) if language in [l.value for l in Language] else Language.KANNADA
        labels_text = ", ".join(object_labels) if object_labels else "objects"

        template = self._MOCK_TEMPLATES.get(lang, self._MOCK_TEMPLATES[Language.KANNADA])
        answer = template.format(labels=labels_text)

        return VQAResult(
            answer=answer,
            language=language,
            confidence=1.0,
            latency_ms=0.0,
            method="mock",
        )

    @staticmethod
    def _translate_if_needed(english_text: str, target_language: str) -> str:
        """Translate English VLM output to the target language if needed.

        Uses a best-effort approach: tries IndicTrans2 or Amazon Translate,
        falls back to returning the English text with a language tag.
        """
        if target_language == "en":
            return english_text

        try:
            from src.edge.slm import SLM

            translate_slm = SLM()
            translate_slm.load_model()
            if translate_slm.is_loaded():
                result = translate_slm.generate(
                    prompt=f"Translate the following to {'Kannada' if target_language == 'kn' else 'Sanskrit'}: {english_text}",
                    language=target_language,
                )
                return result.text
        except Exception as exc:
            logger.debug("Translation fallback failed: %s", exc)

        return english_text
