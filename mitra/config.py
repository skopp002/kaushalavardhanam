"""Configuration constants for Mitra multilingual conversational robot."""
from pathlib import Path
from enum import Enum

# Base paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = DATA_DIR / "logs"
IMAGE_DIR = DATA_DIR / "images"

# Ensure directories exist
LOG_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


class DeploymentMode(str, Enum):
    EDGE = "edge"
    CLOUD = "cloud"


class Language(str, Enum):
    KANNADA = "kn"
    SANSKRIT = "sa"


class Intent(str, Enum):
    CONVERSATION = "conversation"
    VISION = "vision"
    NAVIGATION = "navigation"


# Audio configuration
SAMPLE_RATE = 16000  # Hz - standard for speech models
AUDIO_CHANNELS = 1  # Mono
AUDIO_CHUNK_SIZE = 480  # 30ms at 16kHz (required by webrtcvad)
SILENCE_TIMEOUT_SEC = 1.5  # Seconds of silence to finalize recording
IDLE_TIMEOUT_SEC = 30  # Seconds before entering idle state
VAD_AGGRESSIVENESS = 2  # webrtcvad aggressiveness (0-3, higher = more aggressive)

# Language detection
LANGUAGE_CONFIDENCE_THRESHOLD = 0.75
LANGUAGE_DETECTION_TIMEOUT_SEC = 2.0

# Vision configuration
CAMERA_INDEX = 0
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
OBJECT_CONFIDENCE_THRESHOLD = 0.5
VQA_TIMEOUT_SEC = 6.0

# Edge model configuration (Option A)
EDGE_ASR_MODEL = "ai4bharat/indicwhisper-hi-kn"  # Kannada ASR
EDGE_SLM_MODEL = "microsoft/Phi-3-mini-4k-instruct"
EDGE_SLM_QUANTIZATION = "4bit"
EDGE_TTS_MODEL = "ai4bharat/indic-tts-kn"  # Kannada TTS
EDGE_VISION_MODEL = "yolov8s"  # YOLOv8-small
EDGE_VQA_MODEL = "vikhyatk/moondream2"
ASR_TIMEOUT_SEC = 3.0
TTS_TIMEOUT_SEC = 2.0
MODEL_LOAD_TIMEOUT_SEC = 120

# Cloud configuration (Option B)
AWS_REGION = "us-east-1"
NOVA_SONIC_MODEL_ID = "amazon.nova-sonic-v1:0"
NOVA_VISION_MODEL_ID = "amazon.nova-lite-v1:0"
BRIDGE_LANGUAGE = "hi"  # Hindi as bridge language
BEDROCK_TIMEOUT_SEC = 10.0
BEDROCK_RETRY_COUNT = 1
NOVA_SONIC_RESPONSE_TIMEOUT_SEC = 5.0

# Translation bridge
TRANSLATE_TIMEOUT_SEC = 2.0
# Sanskrit is NOT supported by Amazon Translate - requires self-hosted IndicTrans2
AMAZON_TRANSLATE_SUPPORTED = {Language.KANNADA}
INDICTRANS2_REQUIRED = {Language.SANSKRIT}

# Navigation (locomotion)
NAV_ENABLED = False  # Disabled by default until ROS2 is set up

# Logging
LOG_MAX_SIZE_MB = 100
LOG_DB_PATH = DATA_DIR / "mitra.db"
