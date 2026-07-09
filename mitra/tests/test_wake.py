import numpy as np
import pytest

from mitra.audio.wake import TranscriptWakeDetector, make_wake_detector

CHUNK = int(0.1 * 16000)
LOUD = np.full(CHUNK, 0.1, dtype=np.float32)
QUIET = np.zeros(CHUNK, dtype=np.float32)


def _speak_then_pause(detector):
    """Feed ~0.4 s of speech then silence; return the detection result."""
    result = False
    for chunk in [LOUD] * 4 + [QUIET] * 8:
        result = detector.process(chunk) or result
    return result


def test_wakes_on_phrase_in_transcript():
    detector = TranscriptWakeDetector(transcribe_fn=lambda a: " Hey, Mitra! ")
    assert _speak_then_pause(detector) is True


def test_wake_matches_whisper_spelling_variants():
    for text in ("mithra", "MITRA", "मित्र", "hey mit ra."):
        detector = TranscriptWakeDetector(transcribe_fn=lambda a, t=text: t)
        assert _speak_then_pause(detector) is True, text


def test_no_wake_on_other_speech():
    detector = TranscriptWakeDetector(transcribe_fn=lambda a: "hello there robot")
    assert _speak_then_pause(detector) is False


def test_silence_never_transcribes():
    calls = []
    detector = TranscriptWakeDetector(transcribe_fn=lambda a: calls.append(1) or "")
    for _ in range(20):
        assert detector.process(QUIET) is False
    assert calls == []


def test_factory_selects_engine():
    detector = make_wake_detector("asr", phrase="mitra")
    assert isinstance(detector, TranscriptWakeDetector)
    with pytest.raises(ValueError):
        make_wake_detector("sonar")
