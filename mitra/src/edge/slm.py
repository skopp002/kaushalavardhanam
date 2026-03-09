"""On-device Small Language Model for text generation and conversation."""

import time
import logging
from dataclasses import dataclass

from config import (
    EDGE_SLM_MODEL,
    EDGE_SLM_QUANTIZATION,
    Language,
)

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of a text generation request."""

    text: str
    latency_ms: float
    method: str  # "phi3", "gemma", "mock"


class SLM:
    """Small Language Model for on-device conversational text generation.

    Uses a quantized Phi-3-mini model when available for multilingual
    generation. Falls back to mock mode with canned responses for testing.
    """

    _MOCK_RESPONSES = {
        Language.KANNADA: "ನಾನು ಮಿತ್ರ, ನಿಮ್ಮ ಸಹಾಯಕ. ನಾನು ನಿಮಗೆ ಹೇಗೆ ಸಹಾಯ ಮಾಡಬಹುದು?",
        Language.SANSKRIT: "अहं मित्रः, भवतः सहायकः। कथं भवन्तं साहाय्यं कर्तुं शक्नोमि?",
    }

    _MOCK_VQA_TEMPLATES = {
        Language.KANNADA: "ನಾನು ಚಿತ್ರದಲ್ಲಿ {context} ನೋಡುತ್ತಿದ್ದೇನೆ.",
        Language.SANSKRIT: "अहं चित्रे {context} पश्यामि।",
    }

    def __init__(self, model_name: str = EDGE_SLM_MODEL, device: str = "cpu"):
        self._model_name = model_name
        self._device = device
        self._model = None
        self._tokenizer = None
        self._mock_mode = False
        self._loaded = False

    def load_model(self) -> bool:
        """Load the SLM. Returns True on success (including mock mode)."""
        if self._loaded:
            return True

        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

            logger.info("Loading SLM: %s (%s) on %s", self._model_name, EDGE_SLM_QUANTIZATION, self._device)

            quantization_config = None
            if EDGE_SLM_QUANTIZATION == "4bit":
                quantization_config = BitsAndBytesConfig(load_in_4bit=True)

            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_name,
                quantization_config=quantization_config,
                device_map=self._device if self._device != "cpu" else "auto",
            )
            self._mock_mode = False
            self._loaded = True
            logger.info("SLM loaded successfully")
        except Exception as exc:
            logger.warning(
                "Could not load SLM (%s), falling back to mock mode: %s",
                self._model_name,
                exc,
            )
            self._mock_mode = True
            self._loaded = True

        return True

    def is_loaded(self) -> bool:
        """Check whether the model is ready to generate."""
        return self._loaded

    def unload_model(self) -> None:
        """Release model resources."""
        self._model = None
        self._tokenizer = None
        self._loaded = False
        self._mock_mode = False
        logger.info("SLM unloaded")

    def get_memory_usage_mb(self) -> float:
        """Return approximate GPU/CPU memory used by the model in MB."""
        if not self._loaded or self._mock_mode or self._model is None:
            return 0.0

        try:
            import torch

            param_bytes = sum(
                p.nelement() * p.element_size() for p in self._model.parameters()
            )
            buffer_bytes = sum(
                b.nelement() * b.element_size() for b in self._model.buffers()
            )
            return (param_bytes + buffer_bytes) / (1024 * 1024)
        except Exception:
            return 0.0

    def generate(
        self,
        prompt: str,
        language: str = "kn",
        conversation_history: list = None,
        vision_context: str = None,
    ) -> GenerationResult:
        """Generate a text response.

        Args:
            prompt: User input text.
            language: Target language code for the response.
            conversation_history: Optional list of prior {"role": ..., "content": ...} dicts.
            vision_context: Optional text description of detected objects for VQA.

        Returns:
            GenerationResult with generated text and metadata.
        """
        if not self._loaded:
            self.load_model()

        start = time.perf_counter()

        if self._mock_mode:
            result = self._generate_mock(prompt, language, vision_context)
        else:
            result = self._generate_model(prompt, language, conversation_history, vision_context)

        result.latency_ms = (time.perf_counter() - start) * 1000
        return result

    def _build_messages(
        self,
        prompt: str,
        language: str,
        conversation_history: list | None,
        vision_context: str | None,
    ) -> list[dict]:
        """Build the chat message list for the model."""
        lang_name = "Kannada" if language == "kn" else "Sanskrit" if language == "sa" else language

        system_content = (
            f"You are Mitra, a helpful multilingual assistant robot. "
            f"Respond in {lang_name}. Be concise and helpful."
        )

        if vision_context:
            system_content += (
                f" The user is looking at a scene. The image shows: {vision_context}. "
                f"Use this visual context to answer the user's question."
            )

        messages = [{"role": "system", "content": system_content}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": prompt})
        return messages

    def _generate_model(
        self,
        prompt: str,
        language: str,
        conversation_history: list | None,
        vision_context: str | None,
    ) -> GenerationResult:
        """Generate using the loaded language model."""
        import torch

        messages = self._build_messages(prompt, language, conversation_history, vision_context)
        input_text = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(input_text, return_tensors="pt").to(self._model.device)

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=True,
                temperature=0.7,
                top_p=0.9,
            )

        new_tokens = output_ids[0][inputs["input_ids"].shape[-1]:]
        text = self._tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

        method = "phi3" if "phi" in self._model_name.lower() else "gemma"

        return GenerationResult(text=text, latency_ms=0.0, method=method)

    def _generate_mock(
        self,
        prompt: str,
        language: str,
        vision_context: str | None,
    ) -> GenerationResult:
        """Return canned responses for testing without a model."""
        lang = Language(language) if language in [l.value for l in Language] else Language.KANNADA

        if vision_context:
            template = self._MOCK_VQA_TEMPLATES.get(
                lang, self._MOCK_VQA_TEMPLATES[Language.KANNADA]
            )
            text = template.format(context=vision_context)
        else:
            text = self._MOCK_RESPONSES.get(lang, self._MOCK_RESPONSES[Language.KANNADA])

        return GenerationResult(text=text, latency_ms=0.0, method="mock")
