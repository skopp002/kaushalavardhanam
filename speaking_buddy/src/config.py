"""Configuration constants for Speaking Buddy"""
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
REFERENCE_AUDIO_DIR = DATA_DIR / "reference_audio"
USER_RECORDINGS_DIR = DATA_DIR / "user_recordings"

# Ensure directories exist
REFERENCE_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
USER_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Reference audio URLs (lod.lu)
# Using the formal greeting example from https://lod.lu/artikel/MOIEN2
REFERENCE_URLS = {
    "moien": "https://lod.lu/uploads/examples/OGG/9b/9bb3ff56b0168aa51fe1737239761208.ogg"
}

# Audio processing parameters
SAMPLE_RATE = 22050  # Hz
MAX_DURATION = 5  # seconds
N_MFCC = 13  # Number of MFCC coefficients

# Similarity score thresholds
SCORE_THRESHOLDS = {
    "excellent": 80,
    "good": 60,
    "fair": 40,
    "poor": 0
}

# Feedback messages
FEEDBACK_MESSAGES = {
    "excellent": "Excellent! Your pronunciation is very close to the reference! 🎉",
    "good": "Good job! Your pronunciation is quite similar. Keep practicing! 👍",
    "fair": "Not bad! With more practice, you'll improve. Listen to the reference again. 📚",
    "poor": "Keep trying! Listen carefully to the reference and try again. 💪"
}
