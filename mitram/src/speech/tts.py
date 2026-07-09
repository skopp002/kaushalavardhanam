"""Sanskrit TTS (FR-4.3): AI4Bharat Indic Parler-TTS on MPS.

Sanskrit is Parler-TTS's top-rated language in native-speaker evaluation. The
parler-tts package is not on PyPI; install with:

    pip install git+https://github.com/huggingface/parler-tts.git

The VITS-based Indic-TTS fallback (lighter, also Sanskrit-capable) hides
behind the same ``synthesize()`` interface if Parler latency on MPS proves
unacceptable (REQUIREMENTS R3, measured in Phase 2).
"""

from __future__ import annotations

import numpy as np

DEFAULT_VOICE = (
    "A female speaker delivers slow, warm, clear speech in a close-sounding "
    "recording with no background noise."
)


class SanskritTTS:
    def __init__(self, model: str = "ai4bharat/indic-parler-tts",
                 device: str = "mps", voice_description: str = DEFAULT_VOICE):
        self._model_id = model
        self._device = device
        self._voice = voice_description
        self._model = None  # ~2 GB — loaded on first synthesize()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer
        except ImportError as e:
            raise ImportError(
                "Indic Parler-TTS needs: pip install 'mitram[speech]' "
                "git+https://github.com/huggingface/parler-tts.git"
            ) from e
        self._torch = torch
        self._model = ParlerTTSForConditionalGeneration.from_pretrained(
            self._model_id
        ).to(self._device)
        self._prompt_tokenizer = AutoTokenizer.from_pretrained(self._model_id)
        self._desc_tokenizer = AutoTokenizer.from_pretrained(
            self._model.config.text_encoder._name_or_path
        )
        self._voice_ids = self._desc_tokenizer(
            self._voice, return_tensors="pt"
        ).to(self._device)

    def synthesize(self, text_devanagari: str) -> tuple[np.ndarray, int]:
        """Devanagari text → (mono float32 waveform, samplerate)."""
        self._ensure_loaded()
        prompt = self._prompt_tokenizer(
            text_devanagari, return_tensors="pt"
        ).to(self._device)
        with self._torch.no_grad():
            generation = self._model.generate(
                input_ids=self._voice_ids.input_ids,
                attention_mask=self._voice_ids.attention_mask,
                prompt_input_ids=prompt.input_ids,
                prompt_attention_mask=prompt.attention_mask,
            )
        wav = generation.cpu().numpy().squeeze().astype(np.float32)
        return wav, int(self._model.config.sampling_rate)
