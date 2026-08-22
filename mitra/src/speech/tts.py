"""Sanskrit TTS (FR-4.3): AI4Bharat Indic Parler-TTS on MPS, with an
automatic VITS fallback.

Indic Parler-TTS is a **gated** HuggingFace repo with auto-approval: open
https://huggingface.co/ai4bharat/indic-parler-tts while logged in, accept the
conditions, and (with `hf auth login` done) the model downloads normally. It
also needs the parler-tts package, which is not on PyPI:

    pip install git+https://github.com/huggingface/parler-tts.git

Until both are in place, synthesize() falls back to facebook/mms-tts-hin — an
ungated Hindi VITS voice that reads Devanagari. Its Sanskrit pronunciation is
approximate (visarga, vocalic ṛ), acceptable as a stopgap only (REQUIREMENTS
R3; the design's quality fallback remains AI4Bharat Indic-TTS VITS).
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("mitra")

DEFAULT_VOICE = (
    "A female speaker delivers slow, warm, clear speech in a close-sounding "
    "recording with no background noise."
)
FALLBACK_MODEL = "facebook/mms-tts-hin"


class SanskritTTS:
    def __init__(self, model: str = "ai4bharat/vits_rasa_13",
                 device: str = "mps", voice_description: str = DEFAULT_VOICE,
                 engine: str = "vits",
                 speaker_id: int = 0,
                 emotion_id: int = 0,
                 fallback_model: str = FALLBACK_MODEL,
                 **kwargs):
        self._model_id = model
        self._device = device
        self._voice = voice_description
        self._engine = engine.lower() if engine else "vits"
        self._speaker_id = speaker_id
        self._emotion_id = emotion_id
        self._fallback_model = fallback_model
        self._parler = None   # ~2 GB — loaded on first synthesize()
        self._vits = None
        self._vits_device = device

    # ------------------------------------------------------------- loading

    def _ensure_loaded(self) -> None:
        if self._parler is not None or self._vits is not None:
            return
        if self._engine == "vits" or "vits" in self._model_id.lower() or "mms-tts" in self._model_id:
            self._load_vits(self._model_id)
            return

        try:
            self._load_parler()
            logger.info("TTS: Indic Parler-TTS loaded (%s)", self._model_id)
        except Exception as e:
            logger.warning(
                "TTS: %s unavailable (%s: %s) — falling back to %s. "
                "For the real Sanskrit voice: accept the conditions at "
                "https://huggingface.co/%s (auto-approved) and install "
                "parler-tts (see src/speech/tts.py docstring).",
                self._model_id, type(e).__name__, str(e)[:120],
                self._fallback_model, self._model_id,
            )
            self._load_vits(self._fallback_model)

    def _load_parler(self) -> None:
        import torch
        from parler_tts import ParlerTTSForConditionalGeneration
        from transformers import AutoTokenizer

        self._torch = torch
        self._parler = ParlerTTSForConditionalGeneration.from_pretrained(
            self._model_id
        ).to(self._device)
        self._prompt_tokenizer = AutoTokenizer.from_pretrained(self._model_id)
        desc_tokenizer = AutoTokenizer.from_pretrained(
            self._parler.config.text_encoder._name_or_path
        )
        self._voice_ids = desc_tokenizer(
            self._voice, return_tensors="pt"
        ).to(self._device)

    def _load_vits(self, model_id: str | None = None) -> None:
        target_model = model_id or self._fallback_model
        import torch
        from transformers import AutoModel, AutoTokenizer, VitsModel

        self._torch = torch
        try:
            try:
                self._vits = AutoModel.from_pretrained(target_model, trust_remote_code=True).to(self._device)
            except Exception:
                self._vits = VitsModel.from_pretrained(target_model).to(self._device)
            self._vits_device = self._device
            self._vits_tokenizer = AutoTokenizer.from_pretrained(target_model, trust_remote_code=True)
            logger.info("TTS: VITS loaded (%s)", target_model)
        except Exception as e:
            if target_model != self._fallback_model:
                logger.warning(
                    "TTS: %s unavailable (%s: %s) — falling back to %s. "
                    "If using a gated model like ai4bharat/vits_rasa_13, make sure to accept access at "
                    "https://huggingface.co/%s and run `huggingface-cli login`.",
                    target_model, type(e).__name__, str(e)[:120],
                    self._fallback_model, target_model,
                )
                self._load_vits(self._fallback_model)
            else:
                # Fall back to CPU for fallback model if MPS failed
                try:
                    self._vits = VitsModel.from_pretrained(target_model)
                    self._vits_device = "cpu"
                    self._vits_tokenizer = AutoTokenizer.from_pretrained(target_model)
                    logger.info("TTS: Fallback VITS loaded on CPU (%s)", target_model)
                except Exception:
                    logger.exception("Failed to load fallback VITS model %s", target_model)
                    raise

    # ---------------------------------------------------------- synthesis

    def synthesize(self, text_devanagari: str) -> tuple[np.ndarray, int]:
        """Devanagari text → (mono float32 waveform, samplerate)."""
        self._ensure_loaded()
        if self._parler is not None:
            return self._synthesize_parler(text_devanagari)
        return self._synthesize_vits(text_devanagari)

    def _synthesize_parler(self, text: str) -> tuple[np.ndarray, int]:
        prompt = self._prompt_tokenizer(text, return_tensors="pt").to(self._device)
        with self._torch.no_grad():
            generation = self._parler.generate(
                input_ids=self._voice_ids.input_ids,
                attention_mask=self._voice_ids.attention_mask,
                prompt_input_ids=prompt.input_ids,
                prompt_attention_mask=prompt.attention_mask,
            )
        wav = generation.cpu().numpy().squeeze().astype(np.float32)
        return wav, int(self._parler.config.sampling_rate)

    def _synthesize_vits(self, text: str) -> tuple[np.ndarray, int]:
        inputs = self._vits_tokenizer(text, return_tensors="pt")
        inputs = {k: v.to(self._vits_device) for k, v in inputs.items() if hasattr(v, "to")}
        with self._torch.no_grad():
            kwargs = {}
            if hasattr(self._vits, "speakers") or "rasa" in self._model_id.lower():
                kwargs["speaker_id"] = self._speaker_id
                kwargs["emotion_id"] = self._emotion_id
            try:
                outputs = self._vits(**inputs, **kwargs)
            except TypeError:
                outputs = self._vits(**inputs)

            if hasattr(outputs, "waveform"):
                wav = outputs.waveform
            elif hasattr(outputs, "audio"):
                wav = outputs.audio
            elif isinstance(outputs, (tuple, list)):
                wav = outputs[0]
            else:
                wav = outputs
        wav = wav.squeeze().cpu().numpy().astype(np.float32)
        sr = int(getattr(self._vits.config, "sampling_rate", 16000))
        return wav, sr
