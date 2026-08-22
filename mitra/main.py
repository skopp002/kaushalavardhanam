#!/usr/bin/env python3
"""Mitra entry point: component wiring + run loop (DESIGN §2).

    python main.py --check          # report which components are available
    python main.py                  # run against the reachy daemon (real or --sim)
    python main.py --robot fake     # run without any robot daemon
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Quiet two harmless-but-scary warnings from the ML stack: the tokenizers
# fork warning, and transformers' full-config dumps during Parler-TTS load.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "0")  # no "Fetching 4 files" spam

_ROOT = Path(__file__).resolve().parent


def _ensure_package() -> None:
    """Make ``import mitra`` resolve to ./src when not pip-installed."""
    try:
        import mitra  # noqa: F401
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "mitra", _ROOT / "src" / "__init__.py",
            submodule_search_locations=[str(_ROOT / "src")],
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["mitra"] = module
        spec.loader.exec_module(module)


_ensure_package()

import yaml  # noqa: E402

from mitra.logging_subsystem import TurnLogger, setup_logging  # noqa: E402


def load_config(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def check(config: dict) -> int:
    """Report availability of every optional layer (Phase 0 helper)."""
    import importlib
    import json
    import urllib.request

    def probe(name: str, module: str) -> bool:
        try:
            importlib.import_module(module)
            print(f"  ok       {name}")
            return True
        except ImportError as e:
            print(f"  MISSING  {name}  ({e.name or e})")
            return False

    print("components:")
    probe("reachy-mini (robot/sim)", "reachy_mini")
    probe("strands-agents (agent)", "strands")
    probe("openwakeword (wake)", "openwakeword")
    probe("mlx-whisper (ASR)", "mlx_whisper")
    probe("transformers (TTS)", "transformers")

    host = config["models"]["llm"]["host"]
    model_id = config["models"]["llm"]["id"]
    print("ollama:")
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=3) as resp:
            models = [m["name"] for m in json.load(resp).get("models", [])]
        state = "ok" if any(m.startswith(model_id) for m in models) else "MISSING"
        print(f"  ok       server at {host}")
        print(f"  {state:8} model {model_id}  (installed: {', '.join(models) or 'none'})")
    except OSError as e:
        print(f"  DOWN     {host}  ({e})")

    from mitra.lexicon.store import LexiconStore

    store = LexiconStore()  # in-memory, seeds from the bundled JSON
    print(f"lexicon: {store.count()} seed entries")
    return 0


def build_and_run(config: dict, robot_backend: str, debug: bool) -> int:
    logger = setup_logging(debug or config["logging"].get("debug", False))

    from mitra.agent.agent import MitraAgent
    from mitra.agent.tools import build_tools
    from mitra.audio.asr import Transcriber
    from mitra.audio.vad import make_segmenter
    from mitra.audio.wake import make_wake_detector
    from mitra.lexicon.store import LexiconStore
    from mitra.orchestrator import Orchestrator
    from mitra.speech.tts import SanskritTTS

    models = config["models"]
    tts_kwargs = {}
    if models["tts"].get("voice_description"):
        tts_kwargs["voice_description"] = models["tts"]["voice_description"]
    if "speaker_id" in models["tts"]:
        tts_kwargs["speaker_id"] = models["tts"]["speaker_id"]
    if "emotion_id" in models["tts"]:
        tts_kwargs["emotion_id"] = models["tts"]["emotion_id"]
    tts_engine = models["tts"].get("engine", "vits")
    tts = SanskritTTS(model=models["tts"]["model"], device=models["tts"].get("device", "mps"),
                      engine=tts_engine,
                      fallback_model=models["tts"].get("fallback", "facebook/mms-tts-hin"),
                      **tts_kwargs)
    logger.info("warming up TTS (%s engine)...", tts_engine)
    try:
        tts.synthesize("नमस्ते")
    except Exception:
        logger.exception("TTS warmup failed — continuing; speech will retry")
    wake = make_wake_detector(**models["wake"])
    if hasattr(wake, "warmup"):
        logger.info("warming up wake ASR (first run downloads whisper-small)...")
        wake.warmup()
    vad_cfg = models["vad"]
    segmenter = make_segmenter(
        vad_cfg.get("engine", "silero"),
        min_silence_s=vad_cfg.get("min_silence_s", 0.4),
        max_utterance_s=vad_cfg.get("max_utterance_s", 15.0),
    )
    asr_cfg = models["asr"]
    asr = Transcriber(
        model=asr_cfg.get("model", "mlx-community/whisper-large-v3-turbo"),
    )
    logger.info("warming up ASR (first run downloads whisper-large-v3-turbo)...")
    try:
        asr.warmup()
    except Exception:
        logger.exception("ASR warmup failed — continuing; the first turn will retry")

    logger.info("warming up LLM...")
    try:
        MitraAgent.warmup_model(models["llm"])
    except Exception:
        logger.exception("LLM warmup failed — continuing; the first turn will retry")
    lexicon = LexiconStore(config["lexicon"]["db_path"])

    # Connect only after all model warmups complete, so audio capture begins
    # with every model resident.
    if robot_backend in ("desktop", "fake"):
        from mitra.robot.reachy import DesktopRobot, FakeReachy

        if robot_backend == "fake":
            robot = FakeReachy()
            logger.warning("using FakeReachy — headless, no audio I/O")
        else:
            mic_device = config["robot"].get("built_in_mic_device", "MacBook Neo Microphone")
            robot = DesktopRobot(device_name=mic_device)
            logger.info("using DesktopRobot — live Mac mic & speaker (no simulator CPU needed)")
    else:
        from mitra.robot.reachy import ReachyRobot

        mic_source = config["robot"].get("mic_source", "robot")
        if mic_source == "built_in":
            logger.warning("mic_source=built_in: listening through the Mac's "
                           "own mic (workaround for reachy_mini#820), not the "
                           "robot's — camera/speaker/motion still go through it")
        logger.info("connecting to the robot daemon...")
        robot = ReachyRobot(
            mic_chunk_s=config["robot"].get("mic_chunk_s", 0.08),
            mic_source=mic_source,
            built_in_mic_device=config["robot"].get(
                "built_in_mic_device", "MacBook Neo Microphone"),
        )

    agent = MitraAgent(models["llm"], build_tools(robot, tts))

    fallback_factory = None
    cloud = config.get("cloud_fallback", {})
    if cloud.get("enabled") and cloud.get("provider"):  # FR-6.3
        fallback_factory = lambda: MitraAgent(  # noqa: E731
            {"provider": cloud["provider"], "id": cloud["model_id"]},
            build_tools(robot, tts),
        )

    orchestrator = Orchestrator(
        robot=robot, agent=agent, tts=tts, lexicon=lexicon,
        wake=wake, segmenter=segmenter, asr=asr,
        turn_logger=TurnLogger(config["logging"]["dir"], logger),
        logger=logger,
        gestures=config["robot"].get("gestures", True),
        silence_timeout_s=config["session"]["silence_timeout_s"],
        max_reply_chars=config["session"]["max_reply_chars"],
        fallback_agent_factory=fallback_factory,
    )
    try:
        orchestrator.run()
    except KeyboardInterrupt:
        pass
    finally:
        orchestrator.stop()
        robot.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="mitra")
    parser.add_argument("--config", default=str(_ROOT / "config.yaml"))
    parser.add_argument("--debug", action="store_true",
                        help="mirror the conversation on the console (FR-7.2)")
    parser.add_argument("--check", action="store_true",
                        help="report component availability and exit")
    parser.add_argument("--robot", choices=["reachy", "desktop", "fake"], default=None,
                        help="robot backend: reachy (daemon/sim), desktop (live Mac mic/speaker, no sim CPU), fake")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.check:
        return check(config)
    backend = args.robot or config["robot"].get("backend", "reachy")
    return build_and_run(config, backend, args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
