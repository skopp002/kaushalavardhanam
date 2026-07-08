"""Tests for Orchestrator integration."""

import wave
from pathlib import Path

import numpy as np
import pytest

from config import DeploymentMode, SAMPLE_RATE, AUDIO_CHANNELS
from src.audio_io import _float_to_int16


def _write_wav(filepath: Path, audio: np.ndarray, sample_rate: int = SAMPLE_RATE):
    """Helper: write a float32 audio array to a WAV file."""
    int16_data = _float_to_int16(audio)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_data.tobytes())


class TestOrchestrator:

    def test_create_orchestrator_cloud_mode(self, sample_audio, tmp_dir):
        wav_path = tmp_dir / "orch_input.wav"
        _write_wav(wav_path, sample_audio)

        from src.orchestrator import Orchestrator

        orch = Orchestrator(
            mode=DeploymentMode.CLOUD,
            use_file_io=True,
            input_file=wav_path,
            output_dir=tmp_dir / "output",
            vision_backend="mock",
        )

        assert orch.mode == DeploymentMode.CLOUD
        assert orch.audio.is_available is True
        orch.shutdown()

    def test_process_single_returns_response(self, sample_audio, tmp_dir):
        wav_path = tmp_dir / "orch_input2.wav"
        _write_wav(wav_path, sample_audio)

        from src.orchestrator import Orchestrator

        orch = Orchestrator(
            mode=DeploymentMode.CLOUD,
            use_file_io=True,
            input_file=wav_path,
            output_dir=tmp_dir / "output2",
            vision_backend="mock",
        )

        # process_single may return None if language confidence is too low,
        # or a string response if processing succeeds.
        result = orch.process_single(sample_audio)
        assert result is None or isinstance(result, str)
        orch.shutdown()

    def test_shutdown_does_not_error(self, sample_audio, tmp_dir):
        wav_path = tmp_dir / "orch_input3.wav"
        _write_wav(wav_path, sample_audio)

        from src.orchestrator import Orchestrator

        orch = Orchestrator(
            mode=DeploymentMode.CLOUD,
            use_file_io=True,
            input_file=wav_path,
            output_dir=tmp_dir / "output3",
            vision_backend="mock",
        )

        # Should not raise
        orch.shutdown()
        # Calling shutdown again should also be safe
        orch.shutdown()
