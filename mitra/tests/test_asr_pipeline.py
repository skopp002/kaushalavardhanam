"""Unit tests for mlx-whisper unified ASR transcriber."""

import numpy as np

from mitra.audio.asr import Transcriber, _normalise_audio
from mitra.audio.language_id import LanguagePrediction, _normalise_label


def test_vakgyata_label_is_reduced_to_iso_language_code():
    assert _normalise_label("kn-IN") == "kn"
    assert _normalise_label("EN_in") == "en"


def test_transcriber_custom_function():
    def mock_transcribe(audio):
        return ("ನಮಸ್ಕಾರ", "kn")

    asr = Transcriber(transcribe_fn=mock_transcribe)
    text, lang = asr.transcribe(np.ones(160, dtype=np.float32))
    assert text == "ನಮಸ್ಕಾರ"
    assert lang == "kn"


def test_transcriber_with_mlx_whisper(monkeypatch):
    class FakeMLXWhisper:
        @staticmethod
        def transcribe(audio, path_or_hf_repo=None, **kwargs):
            return {"text": " hello world ", "language": "EN"}

    import sys
    monkeypatch.setitem(sys.modules, "mlx_whisper", FakeMLXWhisper)
    asr = Transcriber()
    text, lang = asr.transcribe(np.ones(160, dtype=np.float32))
    assert text == "hello world"
    assert lang == "en"


def test_audio_normalisation_preserves_silence():
    assert np.array_equal(_normalise_audio(np.zeros(4)), np.zeros(4, dtype=np.float32))
