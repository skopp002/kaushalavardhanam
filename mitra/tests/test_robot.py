import numpy as np

from mitra.audio import resample
from mitra.robot.reachy import FakeReachy


def test_nod_counts(fake_robot):
    fake_robot.nod()
    fake_robot.nod()
    assert fake_robot.nods == 2


def test_mic_feed_and_read(fake_robot):
    chunk = np.ones(160, dtype=np.float32)
    fake_robot.feed_mic(chunk)
    assert len(fake_robot.mic_read()) == 160
    assert len(fake_robot.mic_read()) == 0  # queue drained


def test_speaker_play_and_stop():
    robot = FakeReachy()
    robot.hold_playback = True
    robot.speaker_play(np.zeros(100, dtype=np.float32), 16000, block=False)
    assert robot.speaker_busy()
    robot.speaker_stop()
    assert not robot.speaker_busy()
    assert robot.stops == 1
    assert len(robot.played) == 1


def test_camera_returns_frame(fake_robot):
    frame = fake_robot.camera_read()
    assert frame.shape == (480, 640, 3) and frame.dtype == np.uint8


def test_resample_halves_length():
    wav = np.zeros(32000, dtype=np.float32)
    assert len(resample(wav, 32000, 16000)) == 16000
    assert resample(wav, 16000, 16000) is wav or len(resample(wav, 16000, 16000)) == 32000
