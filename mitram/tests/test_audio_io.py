"""Tests for AudioIO in file-based mode."""

import wave
from pathlib import Path

import numpy as np
import pytest

from config import SAMPLE_RATE, AUDIO_CHANNELS
from src.audio_io import AudioIO, _float_to_int16


def _write_wav(filepath: Path, audio: np.ndarray, sample_rate: int = SAMPLE_RATE):
    """Helper: write a float32 audio array to a WAV file."""
    int16_data = _float_to_int16(audio)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())


class TestAudioIOFileMode:
    """AudioIO operating in file-based (no hardware) mode."""

    def test_get_utterance_returns_float32_array(self, sample_audio, tmp_dir):
        wav_path = tmp_dir / "input.wav"
        _write_wav(wav_path, sample_audio)

        aio = AudioIO(use_file_io=True, input_file=wav_path, output_dir=tmp_dir)
        result = aio.get_utterance()

        assert result is not None
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float32

    def test_play_audio_writes_wav_file(self, sample_audio, tmp_dir):
        output_dir = tmp_dir / "output"
        aio = AudioIO(use_file_io=True, input_file=None, output_dir=output_dir)

        aio.play_audio(sample_audio)

        written_files = list(output_dir.glob("output_*.wav"))
        assert len(written_files) == 1

        # Verify it is a valid WAV file
        with wave.open(str(written_files[0]), "rb") as wf:
            assert wf.getnchannels() == AUDIO_CHANNELS
            assert wf.getframerate() == SAMPLE_RATE
            assert wf.getnframes() > 0

    def test_is_available_true_with_valid_input_file(self, sample_audio, tmp_dir):
        wav_path = tmp_dir / "input.wav"
        _write_wav(wav_path, sample_audio)

        aio = AudioIO(use_file_io=True, input_file=wav_path, output_dir=tmp_dir)
        assert aio.is_available is True

    def test_is_available_false_when_no_input_file(self, tmp_dir):
        aio = AudioIO(use_file_io=True, input_file=None, output_dir=tmp_dir)
        # No input file and output_dir alone counts as speaker_available
        # But with no input file, mic_available is False.
        # is_available = mic_available or speaker_available
        # output_dir is set so speaker_available is True.
        assert aio.is_available is True

        # With neither input nor output, nothing is available.
        aio2 = AudioIO(use_file_io=True, input_file=None, output_dir=None)
        assert aio2.is_available is False

    def test_get_utterance_returns_none_when_no_file(self, tmp_dir):
        aio = AudioIO(use_file_io=True, input_file=None, output_dir=tmp_dir)
        result = aio.get_utterance()
        assert result is None
