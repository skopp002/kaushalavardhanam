#!/usr/bin/env python3
"""A minimal, standalone English conversation app for Reachy Mini — a starter
template, not a scaled-down Mitra. No lexicon, no Devanagari validator. Wake
word -> listen -> think (with a camera tool) -> speak, plus the same state
gestures Mitra uses.

Reuses several already-built, already-tested Mitra pieces (wake/VAD/ASR are
identical to what you'd otherwise have to re-solve yourself), and keeps
everything else as few moving parts as possible:

  - Mic input:  the Mac's built-in mic via sounddevice (mic_source="built_in")
                — same workaround as Mitra, for the same reason: the robot's
                own multichannel USB mic returns all-zero audio on macOS 26
                Tahoe (pollen-robotics/reachy_mini#820).
  - LLM:        Ollama, via the Strands Agent SDK — swap the system prompt or
                the model_id below for anything you want it to be.
  - TTS:        macOS's built-in `say` engine synthesizes to a temp file,
                which then plays through the ROBOT's own speaker via
                robot.speaker_play() — the same path Mitra's TTS uses. The
                robot's speaker is unaffected by the mic bug above.

Run:
    # terminal 1
    reachy-mini-daemon                       # or --sim for the simulator
    # terminal 2
    python tests/mini_conversation_app.py

Say "hey mitra" (or change WAKE_PHRASE below) to start a turn.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

# macOS's `say` engine doesn't silently skip emoji — it speaks their Unicode
# names ("smiling face with smiling eyes and rosy cheeks"), which is what was
# leaking into replies. Stripped from the text that actually reaches `say`
# only; the console print keeps the model's original text, emoji and all.
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002700-\U000027BF\U0001F900-\U0001F9FF\U00002B00-\U00002BFF"
    "\U0000FE0F\U0000200D]+"
)

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

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

WAKE_PHRASE = "mitra"
SILENCE_TIMEOUT_S = 30
VOICE = "Junior"  # macOS's built-in child-like voice — better match for the
                  # playful emotion library than the default adult voice.
                  # `say -v '?'` lists every installed voice if you want another.
SYSTEM_PROMPT = (
    "You are a friendly, helpful voice assistant running on a small desktop "
    "robot with a camera. Keep replies short — one or two spoken sentences — "
    "since they will be read aloud by text-to-speech. Never use emojis or "
    "emoticons: a TTS engine reads them out by name instead of skipping them, "
    "which sounds broken. Be warm and conversational using words only. When "
    "the user shows you something or asks what an object is, call the "
    "capture_image tool and answer from what you see."
)


def main() -> None:
    import soundfile as sf

    from mitra import language_detector
    from mitra.agent.agent import MitraAgent
    from mitra.agent.tools import build_tools
    from mitra.audio.asr import Transcriber
    from mitra.audio.vad import make_segmenter
    from mitra.audio.wake import TranscriptWakeDetector
    from mitra.robot.reachy import ReachyRobot

    print("connecting to the robot daemon...")
    robot = ReachyRobot(mic_source="built_in")  # camera/speaker/motion via the
                                                 # robot; mic via the Mac

    def say(text: str) -> None:
        """Synthesize with macOS's TTS, then play through the ROBOT's speaker
        (robot.speaker_play handles resampling to the robot's output rate —
        same call Mitra's own TTS makes, see src/robot/reachy.py)."""
        print(f"  Mitra: {text}")
        speech_text = _EMOJI_RE.sub("", text).strip() or text
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name
        try:
            subprocess.run(
                ["say", "-v", VOICE, "-o", path, "--data-format=LEI16@22050",
                 speech_text],
                check=True)
            wav, sr = sf.read(path, dtype="float32", always_2d=False)
            robot.speaker_play(wav, sr, block=True)
        finally:
            os.unlink(path)
            # Discard whatever the mic captured while the robot was talking —
            # mic_source="built_in" has no echo cancellation, so without this
            # the robot's own voice gets fed back in as the "next" utterance.
            robot.flush_mic()

    print("loading wake detector, VAD, ASR, agent...")
    wake = TranscriptWakeDetector(phrase=WAKE_PHRASE)
    wake.warmup()
    segmenter = make_segmenter("silero", min_silence_s=0.8, max_utterance_s=15.0)
    asr = Transcriber(default_model="mlx-community/whisper-large-v3-turbo")

    # Only capture_image from Mitra's four tools (src/agent/tools.py) — the
    # other three (speak_sanskrit, nod, end_session) are either Sanskrit-
    # specific or already handled directly in the loop below. tts=None is
    # safe: capture_image's closure never touches it.
    capture_image = build_tools(robot, tts=None)[0]
    agent = MitraAgent(
        {"provider": "ollama", "host": "http://localhost:11434",
         "id": "qwen3-vl:8b-instruct"},
        tools=[capture_image], system_prompt=SYSTEM_PROMPT,
        verbose=False,  # Strands' default callback streams reply tokens to
                        # stdout as they generate — off, or every reply prints twice
    )

    print(f'ready — say "hey {WAKE_PHRASE}" to start\n')
    last_activity = time.monotonic()
    listening = False

    try:
        while True:
            chunk = robot.mic_read()
            if len(chunk) == 0:
                continue

            if not listening:
                if wake.process(chunk):
                    print("* wake word heard *")
                    robot.nod()
                    # block=True: keeps this sequential with the spoken
                    # greeting below rather than overlapping two sounds at
                    # once (both play through the same robot speaker)
                    robot.play_emotion("welcoming1", block=True)
                    robot.pose("neutral")   # face forward to speak the greeting
                    say("Hi! What can I help with?")
                    robot.pose("listening")  # antennas perk up: your turn
                    robot.flush_mic()        # discard any noise from the above
                    listening = True
                    last_activity = time.monotonic()
                    segmenter.reset()
                continue

            if time.monotonic() - last_activity > SILENCE_TIMEOUT_S:
                print("* silence timeout — back to sleep *")
                robot.pose("asleep")
                robot.play_emotion("mini-deep-sleep")
                listening = False
                agent.reset()
                wake.reset()
                continue

            utterance = segmenter.process(chunk)
            if utterance is None:
                continue

            text, hint = asr.transcribe(utterance)
            if not text.strip():
                continue
            lang = language_detector.detect(text, hint)
            print(f"  You: {text.strip()}")
            last_activity = time.monotonic()
            robot.pose("thinking")  # head tilt: processing what you said

            try:
                reply = agent.converse(f"[lang={lang}] {text}")
            except Exception as e:
                print(f"  (agent error: {e})")
                robot.play_emotion("confused1")
                reply = "Sorry, I had trouble with that — could you try again?"
            robot.pose("neutral")  # face forward to speak
            say(reply)
            robot.pose("listening")  # back to "your turn"

    except KeyboardInterrupt:
        print("\nbye")
    finally:
        robot.close()


if __name__ == "__main__":
    main()
