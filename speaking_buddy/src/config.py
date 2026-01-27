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

# Word bank for pronunciation practice
# Each word includes: luxembourgish word, english translation, category, and audio URL
# Format: {word: {"translation": str, "category": str, "url": str}}
WORD_BANK = {
    # Greetings & Courtesy (10 words)
    "moien": {
        "translation": "hello",
        "category": "greetings",
        "url": "https://lod.lu/uploads/examples/OGG/9b/9bb3ff56b0168aa51fe1737239761208.ogg"
    },
    "äddi": {
        "translation": "goodbye",
        "category": "greetings",
        "url": "https://lod.lu/uploads/OGG/addi2.ogg"
    },
    "merci": {
        "translation": "thank you",
        "category": "greetings",
        "url": "https://lod.lu/uploads/OGG/merci2.ogg"
    },
    "wëllkomm": {
        "translation": "welcome",
        "category": "greetings",
        "url": "https://lod.lu/uploads/OGG/wellkomm1.ogg"
    },
    "pardon": {
        "translation": "excuse me",
        "category": "greetings",
        "url": "https://lod.lu/uploads/OGG/pardon2.ogg"
    },
    "jo": {
        "translation": "yes",
        "category": "greetings",
        "url": "https://lod.lu/uploads/OGG/jo1.ogg"
    },
    "nee": {
        "translation": "no",
        "category": "greetings",
        "url": "https://lod.lu/uploads/OGG/nee1.ogg"
    },
    "wéi": {
        "translation": "how",
        "category": "greetings",
        "url": "https://lod.lu/uploads/OGG/wei3.ogg"
    },
    "gär": {
        "translation": "gladly",
        "category": "greetings",
        "url": "https://lod.lu/uploads/OGG/gar1.ogg"
    },
    "bis": {
        "translation": "until",
        "category": "greetings",
        "url": "https://lod.lu/uploads/OGG/bis1.ogg"
    },

    # Numbers (10 words)
    "eent": {
        "translation": "one",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/eent1.ogg"
    },
    "zwee": {
        "translation": "two",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/zwee2.ogg"
    },
    "dräi": {
        "translation": "three",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/drai1.ogg"
    },
    "véier": {
        "translation": "four",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/veier1.ogg"
    },
    "fënnef": {
        "translation": "five",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/fennef1.ogg"
    },
    "sechs": {
        "translation": "six",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/sechs1.ogg"
    },
    "siwen": {
        "translation": "seven",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/siwen1.ogg"
    },
    "aacht": {
        "translation": "eight",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/aacht1.ogg"
    },
    "néng": {
        "translation": "nine",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/neng1.ogg"
    },
    "zéng": {
        "translation": "ten",
        "category": "numbers",
        "url": "https://lod.lu/uploads/OGG/zeng1.ogg"
    },

    # Family (10 words)
    "papp": {
        "translation": "father",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/papp1.ogg"
    },
    "mamm": {
        "translation": "mother",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/mamm1.ogg"
    },
    "kand": {
        "translation": "child",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/kand1.ogg"
    },
    "jong": {
        "translation": "boy",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/jong2.ogg"
    },
    "meedchen": {
        "translation": "girl",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/meedchen1.ogg"
    },
    "frau": {
        "translation": "woman",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/fra1.ogg"
    },
    "mann": {
        "translation": "man",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/mann3.ogg"
    },
    "brudder": {
        "translation": "brother",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/brudder1.ogg"
    },
    "schwëster": {
        "translation": "sister",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/schwester1.ogg"
    },
    "grousselteren": {
        "translation": "grandparents",
        "category": "family",
        "url": "https://lod.lu/uploads/OGG/grousselteren1.ogg"
    },

    # Common Objects (10 words)
    "haus": {
        "translation": "house",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/haus1.ogg"
    },
    "dier": {
        "translation": "door",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/dier2.ogg"
    },
    "fënster": {
        "translation": "window",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/fenster1.ogg"
    },
    "buch": {
        "translation": "book",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/buch2.ogg"
    },
    "stull": {
        "translation": "chair",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/stull1.ogg"
    },
    "dësch": {
        "translation": "table",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/desch1.ogg"
    },
    "auto": {
        "translation": "car",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/auto1.ogg"
    },
    "telefon": {
        "translation": "phone",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/telefon1.ogg"
    },
    "waasser": {
        "translation": "water",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/waasser2.ogg"
    },
    "kaffi": {
        "translation": "coffee",
        "category": "objects",
        "url": "https://lod.lu/uploads/OGG/kaffi1.ogg"
    },

    # Time & Nature (10 words)
    "dag": {
        "translation": "day",
        "category": "time",
        "url": "https://lod.lu/uploads/OGG/dag1.ogg"
    },
    "nuecht": {
        "translation": "night",
        "category": "time",
        "url": "https://lod.lu/uploads/OGG/nuecht1.ogg"
    },
    "mëtteg": {
        "translation": "noon",
        "category": "time",
        "url": "https://lod.lu/uploads/OGG/metteg1.ogg"
    },
    "owes": {
        "translation": "evening",
        "category": "time",
        "url": "https://lod.lu/uploads/OGG/owes1.ogg"
    },
    "sonn": {
        "translation": "sun",
        "category": "nature",
        "url": "https://lod.lu/uploads/OGG/sonn1.ogg"
    },
    "mound": {
        "translation": "moon",
        "category": "nature",
        "url": "https://lod.lu/uploads/OGG/mound1.ogg"
    },
    "stierm": {
        "translation": "star",
        "category": "nature",
        "url": "https://lod.lu/uploads/OGG/stiermen2.ogg"
    },
    "reen": {
        "translation": "rain",
        "category": "nature",
        "url": "https://lod.lu/uploads/OGG/reen1.ogg"
    },
    "schnéi": {
        "translation": "snow",
        "category": "nature",
        "url": "https://lod.lu/uploads/OGG/schnei1.ogg"
    },
    "loft": {
        "translation": "air",
        "category": "nature",
        "url": "https://lod.lu/uploads/OGG/loft1.ogg"
    }
}

# Total words per session
WORDS_PER_SESSION = 50
# Maximum attempts allowed per word before moving on
MAX_ATTEMPTS_PER_WORD = 3

# Legacy reference URLs (for backward compatibility)
REFERENCE_URLS = {word: info["url"] for word, info in WORD_BANK.items() if info["url"] is not None}

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
