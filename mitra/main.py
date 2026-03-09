"""Mitra - Multilingual Conversational Robot

Entry point for running Mitra in Edge or Cloud mode.

Usage:
    python main.py --mode cloud
    python main.py --mode edge
    python main.py --mode cloud --test --input sample.wav
"""
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import DeploymentMode, LOG_DIR


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "mitra.log"),
        ],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Mitra - Multilingual Conversational Robot"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["edge", "cloud"],
        default="cloud",
        help="Deployment mode (default: cloud)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use file-based I/O instead of live hardware",
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Input audio file for test mode",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for test mode audio responses",
    )
    parser.add_argument(
        "--vision-backend",
        type=str,
        choices=["yolo", "mock"],
        default="mock",
        help="Vision backend (default: mock)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger("mitra")

    mode = DeploymentMode(args.mode)
    input_file = Path(args.input) if args.input else None
    output_dir = Path(args.output_dir) if args.output_dir else None

    if args.test and not input_file:
        logger.warning("Test mode enabled but no --input file specified")

    logger.info("Starting Mitra in %s mode", mode.value)
    if args.test:
        logger.info("File-based I/O: input=%s, output=%s", input_file, output_dir)

    from src.orchestrator import Orchestrator

    orchestrator = Orchestrator(
        mode=mode,
        use_file_io=args.test,
        input_file=input_file,
        output_dir=output_dir,
        vision_backend=args.vision_backend,
    )

    if args.test and input_file:
        import numpy as np
        from src.audio_io import AudioIO

        audio_io = AudioIO(use_file_io=True, input_file=input_file)
        audio = audio_io.get_utterance()
        if audio is not None:
            response = orchestrator.process_single(audio)
            if response:
                print(f"\nResponse: {response}\n")
            else:
                print("\nNo response generated.\n")
        else:
            logger.error("Failed to load audio from %s", input_file)
    else:
        orchestrator.run()


if __name__ == "__main__":
    main()
