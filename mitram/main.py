#!/usr/bin/env python3
"""Mitram entry point: component wiring + run loop (DESIGN §2).

    python main.py --check          # report which components are available
    python main.py                  # run against the reachy daemon (real or --sim)
    python main.py --robot fake     # run without any robot daemon
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _ensure_package() -> None:
    """Make ``import mitram`` resolve to ./src when not pip-installed."""
    try:
        import mitram  # noqa: F401
    except ImportError:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "mitram", _ROOT / "src" / "__init__.py",
            submodule_search_locations=[str(_ROOT / "src")],
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["mitram"] = module
        spec.loader.exec_module(module)


_ensure_package()

import yaml  # noqa: E402

from mitram.logging_subsystem import TurnLogger, setup_logging  # noqa: E402


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
    probe("silero-vad (VAD)", "silero_vad")
    probe("mlx-whisper (ASR)", "mlx_whisper")
    probe("parler-tts (TTS)", "parler_tts")

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

    from mitram.lexicon.store import LexiconStore

    store = LexiconStore()  # in-memory, seeds from the bundled JSON
    print(f"lexicon: {store.count()} seed entries")
    return 0


def build_and_run(config: dict, robot_backend: str, debug: bool) -> int:
    logger = setup_logging(debug or config["logging"].get("debug", False))

    if robot_backend == "fake":
        from mitram.robot.reachy import FakeReachy

        robot = FakeReachy()
        logger.warning("using FakeReachy — no camera/audio/motion")
    else:
        from mitram.robot.reachy import ReachyRobot

        robot = ReachyRobot(mic_chunk_s=config["robot"].get("mic_chunk_s", 0.08))

    from mitram.agent.agent import MitramAgent
    from mitram.agent.tools import build_tools
    from mitram.audio.asr import Transcriber
    from mitram.audio.vad import make_segmenter
    from mitram.audio.wake import WakeWordDetector
    from mitram.lexicon.store import LexiconStore
    from mitram.orchestrator import Orchestrator
    from mitram.speech.tts import SanskritTTS

    models = config["models"]
    tts = SanskritTTS(model=models["tts"]["model"], device=models["tts"]["device"])
    wake = WakeWordDetector(model=models["wake"]["model"],
                            threshold=models["wake"]["threshold"])
    vad_cfg = models["vad"]
    segmenter = make_segmenter(
        vad_cfg.get("engine", "silero"),
        min_silence_s=vad_cfg.get("min_silence_s", 0.8),
        max_utterance_s=vad_cfg.get("max_utterance_s", 15.0),
    )
    asr = Transcriber(default_model=models["asr"]["default"],
                      sanskrit_model=models["asr"].get("sanskrit"),
                      backend=models["asr"].get("backend", "mlx"),
                      device=models["asr"].get("device", "mps"))
    lexicon = LexiconStore(config["lexicon"]["db_path"])
    agent = MitramAgent(models["llm"], build_tools(robot, tts))

    fallback_factory = None
    cloud = config.get("cloud_fallback", {})
    if cloud.get("enabled") and cloud.get("provider"):  # FR-6.3
        fallback_factory = lambda: MitramAgent(  # noqa: E731
            {"provider": cloud["provider"], "id": cloud["model_id"]},
            build_tools(robot, tts),
        )

    orchestrator = Orchestrator(
        robot=robot, agent=agent, tts=tts, lexicon=lexicon,
        wake=wake, segmenter=segmenter, asr=asr,
        turn_logger=TurnLogger(config["logging"]["dir"], logger),
        logger=logger,
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
    parser = argparse.ArgumentParser(prog="mitram")
    parser.add_argument("--config", default=str(_ROOT / "config.yaml"))
    parser.add_argument("--debug", action="store_true",
                        help="mirror the conversation on the console (FR-7.2)")
    parser.add_argument("--check", action="store_true",
                        help="report component availability and exit")
    parser.add_argument("--robot", choices=["reachy", "fake"], default=None,
                        help="override robot backend from config")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.check:
        return check(config)
    backend = args.robot or config["robot"].get("backend", "reachy")
    return build_and_run(config, backend, args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
