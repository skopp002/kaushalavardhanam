#!/usr/bin/env python3
"""Interactive wake-word probe: shows live mic levels and what Whisper hears.

Run it, watch the meter, and say "hey mitra":

    cd mitra && source .venv/bin/activate
    python scripts/wake_probe.py

Requires the reachy daemon (sim or real) to be running. Ctrl-C to stop.
"""

import importlib.util
import pathlib
import sys
import time

import numpy as np

_ROOT = pathlib.Path(__file__).resolve().parents[1]
try:
    import mitra  # noqa: F401
except ImportError:
    spec = importlib.util.spec_from_file_location(
        "mitra", _ROOT / "src" / "__init__.py",
        submodule_search_locations=[str(_ROOT / "src")])
    module = importlib.util.module_from_spec(spec)
    sys.modules["mitra"] = module
    spec.loader.exec_module(module)

from mitra.audio.wake import TranscriptWakeDetector  # noqa: E402
from mitra.robot.reachy import ReachyRobot  # noqa: E402


def main() -> None:
    robot = ReachyRobot()
    detector = TranscriptWakeDetector()
    print("warming up wake ASR...")
    detector.warmup()
    print("listening — say 'hey mitra' (Ctrl-C to stop)")
    print("meter: each # is mic level; SPEECH marks where the gate opens\n")
    try:
        while True:
            chunk = robot.mic_read()
            if len(chunk) == 0:
                continue
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            bar = "#" * min(50, int(rms * 2000))
            state = "SPEECH" if detector._segmenter._in_speech else "      "
            print(f"\r{state} {rms:.4f} {bar:<50}", end="", flush=True)
            woke = detector.process(chunk)
            if detector._segmenter._buf == [] and not detector._segmenter._in_speech:
                pass
            if woke:
                print("\n*** WAKE DETECTED — मित्र heard you! ***\n")
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        robot.close()


if __name__ == "__main__":
    main()
