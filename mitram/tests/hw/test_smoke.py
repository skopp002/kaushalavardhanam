"""Hardware/simulator smoke tests (DESIGN §9, Phase 0 checklist).

Runs against a live reachy-mini daemon — real robot over USB or the MuJoCo
simulator (``mjpython -m reachy_mini.daemon.app.main --sim``). Skipped
automatically when no daemon is reachable, so CI stays green.

    .venv/bin/python -m pytest tests/hw/ -v -s
"""

from __future__ import annotations

import time
import urllib.request

import numpy as np
import pytest


def _daemon_up() -> bool:
    try:
        with urllib.request.urlopen("http://localhost:8000/openapi.json", timeout=2):
            return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _daemon_up(), reason="no reachy daemon on localhost:8000")


@pytest.fixture(scope="module")
def robot():
    from mitram.robot.reachy import ReachyRobot

    robot = ReachyRobot()
    yield robot
    robot.close()


def test_connects(robot):
    assert robot.mic_samplerate > 0


def test_nod_moves_head(robot):
    robot.nod()  # watch the viewer: single brief nod (FR-1.3)


def test_camera_frame(robot, tmp_path):
    frame = None
    for _ in range(20):  # first frames can take a moment to arrive over IPC
        frame = robot.camera_read()
        if frame is not None and getattr(frame, "size", 0) > 0:
            break
        time.sleep(0.25)
    assert frame is not None and frame.size > 0, "no camera frame from daemon"
    assert frame.ndim == 3 and frame.shape[2] == 3 and frame.dtype == np.uint8
    try:
        from PIL import Image

        out = tmp_path / "sim_frame.jpg"
        Image.fromarray(frame[..., ::-1]).save(out)  # SDK frames are BGR
        print(f"\ncamera frame {frame.shape} saved to {out}")
    except ImportError:
        pass


def test_speaker_tone(robot):
    """0.5 s / 440 Hz through the speaker (Mac speakers in simulation)."""
    sr = 16000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    robot.speaker_play(tone, sr, block=True)


def test_speaker_barge_in_stop(robot):
    sr = 16000
    t = np.linspace(0, 3.0, sr * 3, endpoint=False)
    tone = (0.2 * np.sin(2 * np.pi * 330 * t)).astype(np.float32)
    robot.speaker_play(tone, sr, block=False)
    time.sleep(0.4)
    assert robot.speaker_busy()
    robot.speaker_stop()
    time.sleep(0.5)
    assert not robot.speaker_busy()


def test_mic_stream(robot):
    """Mic chunks arrive (Mac microphone in simulation) — validates the
    get_audio_sample() drain pacing that mic_read() relies on."""
    got = 0
    for _ in range(30):
        chunk = robot.mic_read()
        if len(chunk) > 0:
            got += len(chunk)
    seconds = got / robot.mic_samplerate
    print(f"\nmic: {got} samples (~{seconds:.2f}s) at {robot.mic_samplerate} Hz")
    assert got > 0, "no microphone samples — check macOS mic permission for the terminal"
