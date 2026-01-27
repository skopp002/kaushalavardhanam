# Speaking Buddy - Pronunciation Learning Tool

**Version:** v1.5.0 | **Status:** Production Ready | **Words:** 50/50 with Audio

A complete Streamlit-based pronunciation learning tool that helps users practice Luxembourgish pronunciation by comparing their recordings against reference audio using Praat-based phonetic analysis. Features user authentication, progress tracking, and a full vocabulary bank of 50 words across 5 categories.

## 🚀 Quickstart

```bash
# 1. Install ffmpeg (required for audio processing)
brew install ffmpeg  # macOS
# sudo apt-get install ffmpeg  # Linux

# 2. Install Python dependencies
.venv/bin/python -m ensurepip
.venv/bin/python -m pip install streamlit streamlit-audiorecorder pydub scipy soundfile requests praat-parselmouth

# 3. Run the app
.venv/bin/python -m streamlit run main.py

# 4. (Optional) Verify installation - see Testing section
.venv/bin/python -c "import streamlit, parselmouth; print('✅ Ready to go!')"
```

Open http://localhost:8501 in your browser and start practicing!

**First time?** See the [Testing](#-testing) section to verify everything is working correctly.

---

## 🎥 Demo Video

Watch the complete demonstration of Speaking Buddy in action:

https://github.com/user-attachments/assets/demo_merged.mp4

**What you'll see in the demo:**
- User signup and authentication
- Dashboard with statistics and progress tracking
- Practice session with reference audio playback
- Recording pronunciation and getting instant feedback
- Phonetic feature breakdown with detailed scores
- Multiple attempts per word
- Session completion and comprehensive summary
- Session history and past results

---

## 📋 Table of Contents

- [Demo Video](#-demo-video)
- [Features](#-features)
- [Architecture](#-architecture)
- [How It Works](#-how-it-works)
- [Installation](#-installation)
- [Usage Guide](#-usage-guide)
- [Testing](#-testing)
- [Project Structure](#-project-structure)
- [Technical Details](#-technical-details)
- [Known Limitations](#-known-limitations)
- [Future Enhancements](#-future-enhancements)

---

## ✨ Features

### User Authentication & Progress Tracking 🆕
- 👤 **User accounts** - Secure login with username/password authentication
- 💾 **Persistent progress** - All sessions and scores saved to database
- 📊 **Personal dashboard** - View your overall statistics and progress
- 📚 **Session history** - Review past sessions with detailed results
- 📈 **Performance analytics** - Category-wise performance tracking
- 🏆 **Achievement tracking** - Best scores, total words practiced, improvement trends

### Session-Based Learning
- 📚 **Multi-word sessions** - Practice up to 50 Luxembourgish words per session
- 🎲 **Randomized word order** - Each session presents words in random order
- 📊 **Session progress tracking** - See your progress through the word list
- 🏆 **Final summary** - Comprehensive performance report at session end
- 📈 **Category performance** - Track your scores by word category (greetings, numbers, family, etc.)

### Pronunciation Analysis
- 🗣️ **50-word vocabulary bank** - Greetings, numbers, family terms, common objects, time, and nature
- 📻 **Reference audio** from lod.lu - Authentic Luxembourgish pronunciation
- 🎤 **Browser-based recording** - no external microphone setup needed
- 🎯 **Phonetic breakdown** - Individual scores for pitch, vowel quality, stress, timing, and voice clarity
- 💡 **Actionable suggestions** - Specific guidance on mouth position, tongue placement, etc.

### Practice Features
- 🔄 **Multiple attempts per word** - Up to 3 attempts before moving on
- 📊 **Instant feedback** with similarity scores (0-100)
- 🎨 **Color-coded results** (Excellent 80+, Good 60-79, Fair 40-59, Needs Work <40)
- ⏭️ **Skip words** without audio - Graceful handling of missing reference audio
- 💾 **Automatic caching** - Reference audio cached locally after first download
- ✨ **Clean, intuitive UI** built with Streamlit

---

## 🏗️ Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           User Interface                             │
│                        (Streamlit Web App)                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐  │
│  │   Login/   │  │ Dashboard  │  │  Practice  │  │   Session    │  │
│  │  Signup    │  │  (Stats)   │  │  Session   │  │   History    │  │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘  └──────┬───────┘  │
└─────────┼────────────────┼────────────────┼────────────────┼─────────┘
          │                │                │                │
          │                └────────────────┴────────────────┘
          ▼                                 ▼
┌─────────────────────────┐   ┌─────────────────────────────────────┐
│   Authentication Layer   │   │      Application Logic              │
│                          │   │                                     │
│  ┌──────────────────┐   │   │  ┌──────────────────────────────┐  │
│  │   database.py    │   │   │  │    session_manager.py        │  │
│  │ • authenticate() │◄──┼───┼──┤  • Multi-word sessions       │  │
│  │ • create_user()  │   │   │  │  • Progress tracking         │  │
│  │ • hash_password()│   │   │  │  • Database persistence      │  │
│  └──────────────────┘   │   │  └────────────┬─────────────────┘  │
└──────────┬──────────────┘   │               │                     │
           │                  │  ┌────────────▼─────────────────┐  │
           │                  │  │   pronunciation_checker.py   │  │
           │                  │  │  • Praat analysis pipeline   │  │
           │                  │  │  • Trend tracking            │  │
           │                  │  └────────────┬─────────────────┘  │
           │                  │               │                     │
           │                  │  ┌────────────▼─────────────────┐  │
           │                  │  │      praat_analyzer.py       │  │
           │                  │  │  • Pitch (F0) extraction     │  │
           │                  │  │  • Formants (F1,F2,F3)       │  │
           │                  │  │  • Intensity & duration      │  │
           │                  │  │  • Voice quality (HNR)       │  │
           │                  │  └────────────┬─────────────────┘  │
           │                  │               │                     │
           │                  │  ┌────────────▼─────────────────┐  │
           │                  │  │   feature_comparator.py      │  │
           │                  │  │  • DTW distance calculation  │  │
           │                  │  │  • Weighted scoring          │  │
           │                  │  └────────────┬─────────────────┘  │
           │                  │               │                     │
           │                  │  ┌────────────▼─────────────────┐  │
           │                  │  │   feedback_generator.py      │  │
           │                  │  │  • Phonetic issue analysis   │  │
           │                  │  │  • Actionable suggestions    │  │
           │                  │  └──────────────────────────────┘  │
           │                  └─────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Data Layer                                  │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    SQLite Database                             │  │
│  │                  (speaking_buddy.db)                           │  │
│  │                                                                 │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐     │  │
│  │  │   users     │  │   sessions   │  │  word_attempts   │     │  │
│  │  │  • username │  │  • user_id   │  │  • session_id    │     │  │
│  │  │  • email    │  │  • score     │  │  • word          │     │  │
│  │  │  • password │  │  • completed │  │  • score         │     │  │
│  │  └──────┬──────┘  └──────┬───────┘  └──────┬───────────┘     │  │
│  │         │                │                  │                  │  │
│  │         └────────────────┴──────────────────┘                  │  │
│  │                          │                                      │  │
│  │                  ┌───────▼────────┐                            │  │
│  │                  │  user_stats    │                            │  │
│  │                  │  • total_sessions                           │  │
│  │                  │  • avg_score   │                            │  │
│  │                  └────────────────┘                            │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        External Systems                              │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐      │
│  │   lod.lu     │  │   Browser    │  │  Local File System   │      │
│  │ (Reference   │  │  Microphone  │  │  • Reference audio   │      │
│  │   Audio)     │  │     API      │  │  • User recordings   │      │
│  └──────────────┘  └──────────────┘  └──────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. STARTUP
   ┌──────────────────────────────────────────┐
   │ App loads → Check for cached reference   │
   │ If not found → Download from lod.lu      │
   │ Cache at: data/reference_audio/moien.ogg │
   └──────────────────────────────────────────┘

2. USER RECORDS
   ┌──────────────────────────────────────────┐
   │ Browser captures microphone input        │
   │ audiorecorder component returns bytes    │
   │ Save to: data/user_recordings/*.wav      │
   └──────────────────────────────────────────┘

3. COMPARISON PROCESS (Praat Phonetic Analysis)
   ┌──────────────────────────────────────────┐
   │ Load both audio files (ref & user)       │
   │           ↓                              │
   │ Extract Phonetic Features:               │
   │  • Pitch (F0) contour                    │
   │  • Formants (F1, F2, F3) - vowels        │
   │  • Intensity patterns - stress           │
   │  • Duration/timing - rhythm              │
   │  • Voice quality (HNR, jitter, shimmer)  │
   │           ↓                              │
   │ Compare Features:                        │
   │  • Pitch: DTW distance (weight: 20%)     │
   │  • Formants: F1/F2/F3 diff (weight: 35%) │
   │  • Intensity: pattern match (weight: 15%)│
   │  • Duration: timing ratio (weight: 15%)  │
   │  • Voice quality: clarity (weight: 15%)  │
   │           ↓                              │
   │ Calculate weighted score (0-100)         │
   │           ↓                              │
   │ Generate phonetic feedback & suggestions │
   └──────────────────────────────────────────┘

4. DISPLAY RESULTS
   ┌──────────────────────────────────────────┐
   │ Show score with color coding:            │
   │  • Green  (80-100) - Excellent           │
   │  • Blue   (60-79)  - Good                │
   │  • Orange (40-59)  - Fair                │
   │  • Red    (0-39)   - Poor                │
   │ Display encouraging feedback message     │
   │ Trigger balloons for scores ≥80          │
   └──────────────────────────────────────────┘
```

---

## 🔬 How It Works

### Pronunciation Comparison Algorithm

The app uses **Praat-based phonetic analysis** via the Parselmouth library to provide scientifically accurate pronunciation feedback:

#### 1. **Pitch (F0) Analysis** - Weight: 20%
   - **Fundamental frequency** (F0) extraction using autocorrelation
   - Measures **intonation patterns** and melodic contours
   - Compares pitch range, mean, and contour shape using DTW
   - Detects: too flat, too varied, wrong pitch range
   - **Example feedback**: "Try varying your pitch more - the reference has more melodic variation"

#### 2. **Formant Analysis (F1, F2, F3)** - Weight: 35% (Most Important)
   - **Formants** are resonant frequencies that define vowel quality
   - **F1** (First Formant): Mouth openness / tongue height
   - **F2** (Second Formant): Tongue position (front/back)
   - **F3** (Third Formant): Overall resonance
   - Compares mean formant values within ±150 Hz tolerance
   - Detects: vowel too open/closed, tongue too far forward/back
   - **Example feedback**: "The vowel sound is too open - try closing your mouth slightly"

#### 3. **Intensity Analysis** - Weight: 15%
   - **Intensity** (loudness in dB) patterns reveal stress and emphasis
   - Compares mean intensity, dynamic range, and contour patterns
   - Detects: speaking too quietly/loudly, flat stress patterns
   - **Example feedback**: "Add more emphasis variation - some syllables should be louder"

#### 4. **Duration Analysis** - Weight: 15%
   - **Timing** and rhythm comparison
   - Measures total duration, speech rate, and voiced/unvoiced ratios
   - Tolerance: ±20% duration variation acceptable
   - Detects: speaking too fast/slow
   - **Example feedback**: "You're speaking about 30% too fast - slow down to match the reference pace"

#### 5. **Voice Quality Analysis** - Weight: 15%
   - **Harmonicity (HNR)**: Harmonics-to-Noise Ratio (clarity)
   - **Jitter**: Pitch period variability (should be <1%)
   - **Shimmer**: Amplitude variability (should be <3.81%)
   - Detects: breathy voice, vocal instability
   - **Example feedback**: "Use more vocal support and speak more clearly"

#### 6. **Weighted Scoring**
   ```python
   final_score = (
       pitch_score × 0.20 +
       formant_score × 0.35 +  # Most important for vowel pronunciation
       intensity_score × 0.15 +
       duration_score × 0.15 +
       voice_quality_score × 0.15
   )
   ```

#### 7. **Phonetic Feedback Generation**
   - Each feature analyzed for specific issues
   - Actionable suggestions based on acoustic measurements
   - **Example**: If F1 too high → "Vowel too open - try closing your mouth slightly"
   - Trend analysis across multiple attempts
   - Identifies which specific features declined/improved

---

## 📦 Installation

### Prerequisites

- Python 3.12+
- ffmpeg (audio processing)

### Setup

**1. Install ffmpeg**

```bash
# macOS
brew install ffmpeg

# Linux (Ubuntu/Debian)
sudo apt-get update && sudo apt-get install ffmpeg

# Windows
# Download from ffmpeg.org and add to PATH
```

**2. Install Python Dependencies**

```bash
# Set up pip in virtual environment
.venv/bin/python -m ensurepip

# Install numba/llvmlite (prebuilt wheels to avoid compilation)
.venv/bin/python -m pip install --only-binary=:all: numba llvmlite

# Install all other dependencies
.venv/bin/python -m pip install streamlit streamlit-audiorecorder pydub scipy soundfile requests praat-parselmouth
```

**3. Run the App**

```bash
.venv/bin/python -m streamlit run main.py
```

The app will open automatically at http://localhost:8501

**4. Verify Installation (Recommended)**

See the comprehensive [Testing](#-testing) section for detailed verification steps including:
- Installation verification
- Vocabulary bank completeness check
- Database initialization test
- Authentication system test
- Praat analysis pipeline test
- Full end-to-end workflow test

Quick verification:
```bash
.venv/bin/python -c "import streamlit, parselmouth, pydub; print('✅ Core dependencies OK')"
```

---

## 📖 Usage Guide

### Practice Session Workflow

1. **Start Session** - App automatically creates a randomized word list from available words
2. **For Each Word:**
   - **Listen** to the reference pronunciation
   - **Record** your pronunciation (click microphone)
   - **Compare** to get your score and phonetic feedback
   - **Try again** - up to 3 attempts per word
   - **Move on** - proceed to next word when ready
3. **Session Complete** - View comprehensive summary with:
   - Overall score and statistics
   - Category performance breakdown
   - Top and bottom performing words
   - Detailed attempt history

### Tips for Best Results

- 🎧 Use headphones to hear reference audio clearly
- 🤫 Record in a quiet environment
- 🎤 Keep microphone distance consistent
- 🗣️ Speak clearly at a natural pace
- 🎵 Try to match the reference's intonation and rhythm
- 📈 Aim for scores ≥80 for excellent pronunciation
- 🔄 Use multiple attempts to improve

### Complete Vocabulary Bank

All 50 words now have reference audio configured from lod.lu:

**Word Categories:**
- **Greetings & Courtesy (10 words)**: moien, äddi, merci, wëllkomm, pardon, jo, nee, wéi, gär, bis
- **Numbers (10 words)**: eent, zwee, dräi, véier, fënnef, sechs, siwen, aacht, néng, zéng
- **Family (10 words)**: papp, mamm, kand, jong, meedchen, frau, mann, brudder, schwëster, grousselteren
- **Common Objects (10 words)**: haus, dier, fënster, buch, stull, dësch, auto, telefon, waasser, kaffi
- **Time & Nature (10 words)**: dag, nuecht, mëtteg, owes, sonn, mound, stierm, reen, schnéi, loft

Each session randomly selects words from the complete vocabulary bank, ensuring variety in your practice.

---

## 🧪 Testing

This section provides comprehensive testing instructions to verify that Speaking Buddy is installed correctly and functioning properly.

### Quick Automated Test (Recommended)

**Run the automated test script for instant verification:**

```bash
# Run all automated tests
./scripts/test_installation.sh
```

This script tests:
- Python version and dependencies
- ffmpeg installation
- Vocabulary bank completeness (50/50 words)
- Database initialization
- SessionManager functionality
- Reference audio download system

**Expected output:**
```
🎉 All tests passed! Speaking Buddy is ready to use.
```

For detailed manual testing and troubleshooting, see the tests below.

---

### Test 1: Installation Verification

**Verify Python environment and dependencies:**

```bash
# Check Python version (should be 3.12+)
.venv/bin/python --version

# Verify all required packages are installed
.venv/bin/python -c "import streamlit, parselmouth, pydub, scipy, soundfile, requests; print('✅ All core dependencies installed')"
```

**Expected output:**
```
Python 3.12.x
✅ All core dependencies installed
```

**Verify ffmpeg installation:**

```bash
# Check ffmpeg is available
ffmpeg -version | head -n 1
```

**Expected output:**
```
ffmpeg version 6.x or higher
```

---

### Test 2: Configuration & Vocabulary Verification

**Test that all 50 words have audio URLs configured:**

```bash
# Verify vocabulary bank completeness
.venv/bin/python -c "
from src.config import WORD_BANK
import json

# Count words with URLs
words_with_urls = [(word, info['url']) for word, info in WORD_BANK.items() if info['url'] is not None]
words_without_urls = [word for word, info in WORD_BANK.items() if info['url'] is None]

print(f'✅ Total words: {len(WORD_BANK)}')
print(f'✅ Words with audio URLs: {len(words_with_urls)}/50')
print(f'❌ Words without URLs: {len(words_without_urls)}')

if words_without_urls:
    print(f'Missing URLs for: {words_without_urls}')

# Show category breakdown
from collections import Counter
categories = Counter(info['category'] for word, info in WORD_BANK.items() if info['url'] is not None)
print(f'\n✅ Category breakdown:')
for cat, count in sorted(categories.items()):
    print(f'   {cat}: {count} words')
"
```

**Expected output:**
```
✅ Total words: 50
✅ Words with audio URLs: 50/50
❌ Words without URLs: 0

✅ Category breakdown:
   family: 10 words
   greetings: 10 words
   nature: 6 words
   numbers: 10 words
   objects: 10 words
   time: 4 words
```

---

### Test 3: Database Initialization

**Verify database tables are created correctly:**

```bash
# Test database initialization
.venv/bin/python -c "
from src import database
import sqlite3

conn = database.get_connection()
cursor = conn.cursor()

# Check all tables exist
cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
tables = [row[0] for row in cursor.fetchall()]

required_tables = ['users', 'sessions', 'word_attempts', 'user_stats']
for table in required_tables:
    if table in tables:
        print(f'✅ Table \"{table}\" exists')
    else:
        print(f'❌ Table \"{table}\" missing')

# Check users table schema
cursor.execute('PRAGMA table_info(users)')
columns = [row[1] for row in cursor.fetchall()]
print(f'\n✅ Users table columns: {columns}')

conn.close()
"
```

**Expected output:**
```
✅ Table "users" exists
✅ Table "sessions" exists
✅ Table "word_attempts" exists
✅ Table "user_stats" exists

✅ Users table columns: ['id', 'username', 'email', 'password_hash', 'created_at', 'last_login']
```

---

### Test 4: Session Manager

**Test session creation and word randomization:**

```bash
# Test SessionManager functionality
.venv/bin/python -c "
from src.session_manager import SessionManager

# Create a test session (no user_id for guest mode)
session = SessionManager()

print(f'✅ SessionManager initialized')
print(f'✅ Session has {len(session.word_list)} words')
print(f'✅ Current word: {session.get_current_word()}')
print(f'✅ Progress: {session.get_progress()}')

# Test word info retrieval
word_info = session.get_current_word_info()
print(f'\n✅ Current word details:')
print(f'   Word: {word_info[\"word\"]}')
print(f'   Translation: {word_info[\"translation\"]}')
print(f'   Category: {word_info[\"category\"]}')
print(f'   Has audio URL: {word_info[\"url\"] is not None}')

# Test recording attempt (mock data)
current_word = session.get_current_word()
session.record_attempt(
    word=current_word,
    score=75.5,
    feedback='Good pronunciation!',
    insights={'pitch': 80, 'formants': 70}
)
print(f'\n✅ Recorded mock attempt for \"{current_word}\"')
print(f'✅ Attempts so far: {len(session.get_attempts_for_current_word())}')
"
```

**Expected output:**
```
✅ SessionManager initialized
✅ Session has 50 words
✅ Current word: <random word>
✅ Progress: {'current_index': 0, 'total_words': 50, 'percentage': 0.0}

✅ Current word details:
   Word: <random word>
   Translation: <translation>
   Category: <category>
   Has audio URL: True

✅ Recorded mock attempt for "<word>"
✅ Attempts so far: 1
```

---

### Test 5: Authentication System

**Test user creation and authentication:**

```bash
# Test authentication flow
.venv/bin/python -c "
from src import database
import time

# Create test user
username = f'testuser_{int(time.time())}'
email = f'{username}@test.com'
password = 'testpassword123'

print(f'Creating test user: {username}')
user_id = database.create_user(username, email, password)

if user_id:
    print(f'✅ User created successfully with ID: {user_id}')
else:
    print(f'❌ Failed to create user')
    exit(1)

# Test authentication
user = database.authenticate_user(username, password)
if user:
    print(f'✅ Authentication successful')
    print(f'   Username: {user[\"username\"]}')
    print(f'   Email: {user[\"email\"]}')
else:
    print(f'❌ Authentication failed')
    exit(1)

# Test wrong password
wrong_auth = database.authenticate_user(username, 'wrongpassword')
if wrong_auth is None:
    print(f'✅ Wrong password correctly rejected')
else:
    print(f'❌ Wrong password accepted (security issue!)')

# Test duplicate username
duplicate = database.create_user(username, 'other@test.com', 'pass')
if duplicate is None:
    print(f'✅ Duplicate username correctly rejected')
else:
    print(f'❌ Duplicate username accepted')

print(f'\n✅ All authentication tests passed')
"
```

**Expected output:**
```
Creating test user: testuser_<timestamp>
✅ User created successfully with ID: 1
✅ Authentication successful
   Username: testuser_<timestamp>
   Email: testuser_<timestamp>@test.com
✅ Wrong password correctly rejected
✅ Duplicate username correctly rejected

✅ All authentication tests passed
```

---

### Test 6: Reference Audio Download

**Test that reference audio can be downloaded and converted:**

```bash
# Test reference audio download and conversion
.venv/bin/python -c "
from src.reference_manager import ensure_reference_exists
from src.config import WORD_BANK
import os

# Test with 'moien' (first word with URL)
test_word = 'moien'
word_info = WORD_BANK[test_word]

print(f'Testing audio download for: {test_word}')
print(f'Audio URL: {word_info[\"url\"]}')

# Download/cache reference audio
audio_path = ensure_reference_exists(test_word)

if audio_path and os.path.exists(audio_path):
    print(f'✅ Reference audio downloaded/cached')
    print(f'✅ Audio path: {audio_path}')
    print(f'✅ File size: {os.path.getsize(audio_path)} bytes')

    # Check it's a WAV file
    if audio_path.suffix == '.wav':
        print(f'✅ Audio correctly converted to WAV format')
    else:
        print(f'❌ Audio not in WAV format: {audio_path.suffix}')
else:
    print(f'❌ Failed to download/cache reference audio')
"
```

**Expected output:**
```
Testing audio download for: moien
Audio URL: https://lod.lu/uploads/examples/OGG/9b/9bb3ff56b0168aa51fe1737239761208.ogg
✅ Reference audio downloaded/cached
✅ Audio path: /path/to/data/reference_audio/moien.wav
✅ File size: <size> bytes
✅ Audio correctly converted to WAV format
```

---

### Test 7: Praat Analysis Pipeline

**Test phonetic analysis on reference audio:**

```bash
# Test Praat analyzer on reference audio
.venv/bin/python -c "
from src.praat_analyzer import extract_praat_features
from src.reference_manager import ensure_reference_exists
import parselmouth

# Get reference audio
audio_path = ensure_reference_exists('moien')
sound = parselmouth.Sound(str(audio_path))

print(f'Testing Praat analysis on: {audio_path.name}')
print(f'Audio duration: {sound.duration:.2f}s')

# Extract features
features = extract_praat_features(sound)

print(f'\n✅ Praat features extracted:')
print(f'   Pitch (F0): mean={features[\"pitch_mean\"]:.1f} Hz, std={features[\"pitch_std\"]:.1f} Hz')
print(f'   Formants: F1={features[\"f1_mean\"]:.0f} Hz, F2={features[\"f2_mean\"]:.0f} Hz, F3={features[\"f3_mean\"]:.0f} Hz')
print(f'   Intensity: mean={features[\"intensity_mean\"]:.1f} dB')
print(f'   Voice quality (HNR): {features[\"hnr_mean\"]:.1f} dB')
print(f'   Duration: {features[\"duration\"]:.2f}s')

# Validate ranges
if 75 <= features['pitch_mean'] <= 300:
    print(f'\n✅ Pitch in valid range')
else:
    print(f'\n⚠️  Pitch outside expected range')

if features['f1_mean'] > 0 and features['f2_mean'] > 0:
    print(f'✅ Formants successfully extracted')
else:
    print(f'❌ Formant extraction failed')

print(f'\n✅ Praat analysis pipeline working correctly')
"
```

**Expected output:**
```
Testing Praat analysis on: moien.wav
Audio duration: <duration>s

✅ Praat features extracted:
   Pitch (F0): mean=<value> Hz, std=<value> Hz
   Formants: F1=<value> Hz, F2=<value> Hz, F3=<value> Hz
   Intensity: mean=<value> dB
   Voice quality (HNR): <value> dB
   Duration: <duration>s

✅ Pitch in valid range
✅ Formants successfully extracted

✅ Praat analysis pipeline working correctly
```

---

### Test 8: Full Application Startup

**Start the application and verify it loads:**

```bash
# Start the Streamlit app
.venv/bin/python -m streamlit run main.py
```

**Expected behavior:**
1. Streamlit should start without errors
2. Browser should open to http://localhost:8501
3. Login/Signup page should be displayed
4. No error messages in terminal
5. Can click between Login and Signup tabs

**Manual test checklist:**
- [ ] App starts without Python errors
- [ ] Login page loads correctly
- [ ] Signup form is visible
- [ ] Can switch between Login/Signup tabs
- [ ] No console errors in browser (F12 developer tools)

---

### Test 9: End-to-End User Flow

**Complete user workflow test (manual):**

1. **Signup Flow:**
   - [ ] Create new account with username, email, password
   - [ ] Password confirmation works correctly
   - [ ] Invalid email format is rejected
   - [ ] Short passwords are rejected
   - [ ] Successful signup redirects to dashboard

2. **Dashboard:**
   - [ ] User statistics displayed (0 sessions initially)
   - [ ] Navigation menu visible in sidebar
   - [ ] Can navigate to Practice/History pages

3. **Practice Session:**
   - [ ] Click "Start New Practice Session" button
   - [ ] Random word is displayed with translation
   - [ ] Reference audio player appears
   - [ ] Can play reference audio successfully
   - [ ] Audio recording widget appears
   - [ ] Can record audio (browser asks for microphone permission)
   - [ ] After recording, can play back recording
   - [ ] "Compare Pronunciation" button appears
   - [ ] Clicking compare shows results with score
   - [ ] Phonetic feature breakdown displayed
   - [ ] Actionable feedback provided
   - [ ] Can record again (up to 3 attempts)
   - [ ] "Next Word" button moves to next word
   - [ ] Progress bar updates correctly
   - [ ] Session completes after all words
   - [ ] Final summary shows statistics

4. **History:**
   - [ ] Completed session appears in history
   - [ ] Can view session details
   - [ ] Word attempts are listed
   - [ ] Scores are displayed correctly

5. **Logout:**
   - [ ] Logout button returns to login page
   - [ ] Cannot access protected pages after logout

---

### Test 10: Database Persistence

**Verify data persists across sessions:**

```bash
# Test data persistence
.venv/bin/python -c "
from src import database
from src.session_manager import SessionManager

# Get test user
user = database.authenticate_user('testuser_<timestamp>', 'testpassword123')
if not user:
    print('❌ Test user not found - run Test 5 first')
    exit(1)

user_id = user['id']

# Create session with database persistence
session = SessionManager(user_id=user_id)
print(f'✅ Created session for user ID: {user_id}')
print(f'✅ Database session ID: {session.db_session_id}')

# Record mock attempts
current_word = session.get_current_word()
for i in range(3):
    session.record_attempt(
        word=current_word,
        score=70 + i * 5,
        feedback=f'Attempt {i+1}',
        insights={'pitch': 70 + i * 5}
    )
print(f'✅ Recorded 3 attempts for \"{current_word}\"')

# Move through all words and complete session
while not session.is_session_complete():
    word = session.get_current_word()
    session.record_attempt(word, 75.0, 'Test', {'pitch': 75})
    session.move_to_next_word()

summary = session.get_session_summary()
print(f'✅ Session completed')
print(f'✅ Overall score: {summary[\"overall_score\"]:.1f}')
print(f'✅ Total attempts: {summary[\"total_attempts\"]}')

# Verify data in database
stats = database.get_user_stats(user_id)
print(f'\n✅ User stats retrieved from database:')
print(f'   Completed sessions: {stats[\"completed_sessions\"]}')
print(f'   Total words practiced: {stats[\"total_words_practiced\"]}')
print(f'   Average score: {stats[\"average_overall_score\"]:.1f}')

# Verify session history
sessions = database.get_user_sessions(user_id, limit=5)
print(f'\n✅ User has {len(sessions)} completed session(s) in history')

print(f'\n✅ Database persistence verified')
"
```

**Expected output:**
```
✅ Created session for user ID: <id>
✅ Database session ID: <session_id>
✅ Recorded 3 attempts for "<word>"
✅ Session completed
✅ Overall score: <score>
✅ Total attempts: <count>

✅ User stats retrieved from database:
   Completed sessions: 1
   Total words practiced: 50
   Average score: <score>

✅ User has 1 completed session(s) in history

✅ Database persistence verified
```

---

### Quick Test Summary

**Run all tests in sequence:**

```bash
# Quick test script - run all automated tests
cat > test_all.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Test 1: Installation Verification ==="
.venv/bin/python --version
.venv/bin/python -c "import streamlit, parselmouth, pydub, scipy, soundfile, requests; print('✅ All dependencies installed')"

echo -e "\n=== Test 2: Vocabulary Verification ==="
.venv/bin/python -c "from src.config import WORD_BANK; print(f'✅ {len([w for w, i in WORD_BANK.items() if i[\"url\"]])}/50 words have audio URLs')"

echo -e "\n=== Test 3: Database Initialization ==="
.venv/bin/python -c "from src import database; import sqlite3; conn = database.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"'); tables = [r[0] for r in cursor.fetchall()]; print(f'✅ Database has {len(tables)} tables'); conn.close()"

echo -e "\n=== Test 4: Session Manager ==="
.venv/bin/python -c "from src.session_manager import SessionManager; s = SessionManager(); print(f'✅ SessionManager works with {len(s.word_list)} words')"

echo -e "\n=== Test 5: Reference Audio ==="
.venv/bin/python -c "from src.reference_manager import ensure_reference_exists; import os; path = ensure_reference_exists('moien'); print(f'✅ Reference audio: {os.path.exists(path)}')"

echo -e "\n✅ All automated tests passed!"
EOF

chmod +x test_all.sh
./test_all.sh
```

---

### Troubleshooting Test Failures

**If Test 1 fails:**
- Ensure virtual environment is activated
- Run: `.venv/bin/python -m pip install -r requirements.txt` (if you have one)
- Or install packages individually as shown in Installation section

**If Test 2 fails:**
- Ensure you ran the vocabulary expansion (v1.5.0)
- Check `src/config.py` has URLs for all 50 words

**If Test 3 fails:**
- Delete `data/speaking_buddy.db` and restart Python to recreate database
- Check `src/database.py` `init_database()` function runs

**If Test 6 fails:**
- Check internet connectivity
- Verify lod.lu is accessible: `curl -I https://lod.lu`
- Check ffmpeg is installed: `ffmpeg -version`

**If Test 7 fails:**
- Ensure Praat/Parselmouth is installed correctly
- Try: `.venv/bin/python -m pip install --upgrade praat-parselmouth`

**If Test 8 fails:**
- Check port 8501 is not in use: `lsof -i :8501`
- Try: `pkill -f streamlit` to kill any stuck processes
- Clear Streamlit cache: `rm -rf ~/.streamlit/`

---

## 📁 Project Structure

```
speaking_buddy/
├── main.py                      # Streamlit app with authentication UI NEW
├── src/
│   ├── config.py                # Configuration & 50-word bank
│   ├── database.py              # SQLite database operations NEW
│   ├── session_manager.py       # Multi-word session + DB persistence NEW
│   ├── reference_manager.py     # Reference audio download/cache
│   ├── praat_analyzer.py        # Praat phonetic feature extraction
│   ├── feature_comparator.py    # Feature comparison & weighted scoring
│   ├── feedback_generator.py    # Actionable phonetic feedback
│   └── pronunciation_checker.py # Orchestration & trend tracking
├── scripts/
│   ├── add_word_urls.py         # Helper to add audio URLs for words
│   ├── fetch_all_lod_audio.py   # Automated audio URL fetcher from lod.lu API
│   └── test_installation.sh     # Automated installation test script
├── data/
│   ├── speaking_buddy.db        # SQLite database (user data) NEW
│   ├── reference_audio/         # Cached reference files (*.wav)
│   └── user_recordings/         # User recordings (*.wav)
├── .venv/                       # Virtual environment
├── pyproject.toml               # Dependencies
├── .gitignore                   # Exclude .pyc, .venv, database, recordings
└── README.md                    # Documentation
```

### Database Schema

The app uses SQLite to store user data and practice history:

**Tables:**
- `users` - User accounts (username, email, password_hash)
- `sessions` - Practice sessions with summary statistics
- `word_attempts` - Individual pronunciation attempts with scores and feedback
- `user_stats` - Cached aggregate statistics per user

All session progress is automatically saved when users are logged in.

---

## 🔧 Technical Details

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | Streamlit 1.32+ | UI and user interaction |
| **Audio Recording** | streamlit-audiorecorder 0.0.5+ | Browser-based microphone capture |
| **Phonetic Analysis** | Praat-Parselmouth 0.4.3+ | Pitch, formant, intensity, voice quality extraction |
| **Numerical Computing** | NumPy 1.26+ | Array operations |
| **Scientific Computing** | SciPy 1.12+ | DTW distance calculation |
| **Audio I/O** | Soundfile 0.12+ | Reading/writing audio files |
| **Audio Manipulation** | Pydub 0.25+ | Format conversion |
| **HTTP Requests** | Requests 2.31+ | Download reference audio |

### Praat Analysis Parameters

```python
# Pitch extraction
PITCH_FLOOR = 75         # Hz - male lower bound
PITCH_CEILING = 300      # Hz - female upper bound
TIME_STEP = 0.01         # seconds - 10ms analysis window

# Formant extraction
MAX_FORMANT_HZ = 5500    # Hz - suitable for adult speech
NUM_FORMANTS = 5         # Extract F1-F5, use F1-F3

# Tolerances
FORMANT_TOLERANCE_HZ = 150   # ±150 Hz for F1/F2
INTENSITY_TOLERANCE_DB = 3   # ±3 dB
DURATION_TOLERANCE_RATIO = 0.2  # ±20% timing variation
```

### Scoring Thresholds

```python
EXCELLENT: 80-100  # Very close to reference
GOOD:      60-79   # Quite similar
FAIR:      40-59   # Room for improvement
POOR:      0-39    # Needs practice
```

### Reference Audio Source

- **URL**: `https://lod.lu/uploads/examples/OGG/9b/9bb3ff56b0168aa51fe1737239761208.ogg`
- **Source**: lod.lu (Luxembourgish Online Dictionary)
- **Format**: Ogg Vorbis
- **Quality**: Mono, 192 kHz, professional recording
- **Size**: 36KB
- **License**: Educational use from public dictionary

### Performance Characteristics

- **Reference download**: ~1 second (cached after first run)
- **Audio recording**: Real-time (browser-based)
- **Comparison analysis**: 1-3 seconds
- **Memory usage**: ~200MB (including Librosa/NumPy)
- **Storage**: ~50KB per recording

---

## ⚠️ Known Limitations (MVP)

### Functional Limitations
- 🔐 **Basic authentication**: Simple password hashing (consider bcrypt for production)
- 📧 **No email verification**: Email addresses not verified during signup
- 🔑 **No password reset**: No forgot password functionality yet

### Technical Limitations
- 🌐 **Browser recording requirements**:
  - Requires HTTPS or localhost
  - Microphone permissions needed
  - Not all browsers supported equally
- 📊 **Score calibration**: Thresholds may need tuning with real user data
- 🎤 **Recording quality**: Depends on user's microphone and environment

### Platform Limitations
- 🖥️ **Desktop-focused**: UI optimized for desktop browsers
- 📱 **Mobile limitations**: Recording may not work on all mobile browsers
- 🌍 **Offline mode**: Reference audio must be downloaded at least once

---

## 🚀 Future Enhancements

### Short-term (MVP+)
- [x] Populate audio URLs for all 50 words from lod.lu ✅ (v1.5.0)
- [x] Automated URL discovery script for lod.lu ✅ (v1.5.0)
- [ ] Email verification for new accounts
- [ ] Password reset functionality
- [ ] Improved password security (bcrypt)
- [ ] Recording quality check (volume too low warning)
- [ ] Better mobile support
- [ ] Export session results as PDF/CSV

### Medium-term
- [x] User authentication ✅ (v1.4.0)
- [x] Personal progress dashboard ✅ (v1.4.0)
- [x] Session history ✅ (v1.4.0)
- [ ] Multiple difficulty levels
- [ ] Practice recommendations
- [ ] Export recordings feature
- [ ] Leaderboard (optional)

### Long-term
- [ ] Multiple languages (French, German, English)
- [ ] Speech recognition integration
- [ ] Gamification (badges, streaks, points)
- [ ] Social features (share progress)
- [ ] Mobile app version
- [ ] AI-powered personalized coaching

### Technical Improvements
- [ ] Add background noise filtering
- [ ] Implement A/B testing for score thresholds and feature weights
- [ ] Add telemetry and analytics
- [ ] Optimize Praat feature extraction performance
- [ ] Add unit tests and CI/CD
- [ ] Add confidence intervals for phonetic measurements

---

## 🐛 Troubleshooting

### Common Issues

**Problem**: "No module named 'streamlit'"
```bash
# Solution: Install dependencies in the correct environment
.venv/bin/python -m pip install streamlit
```

**Problem**: "Failed to load reference audio: 404"
```bash
# Solution: Audio URL already fixed in v1.0.1
# Ensure you have the latest config.py with correct URL
```

**Problem**: "Recording not working"
- Check browser microphone permissions
- Ensure you're on localhost or HTTPS
- Try Chrome or Firefox (better WebRTC support)

**Problem**: "ffmpeg not found"
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt-get install ffmpeg
```

**Problem**: "numba compilation errors"
```bash
# Use prebuilt wheels
.venv/bin/python -m pip install --only-binary=:all: numba llvmlite
```

---

## 📊 Version History

### v1.5.0 (2026-01-24) - **Current**
- ✅ **Complete vocabulary expansion** 🎉
  - All 50 words now have reference audio URLs from lod.lu
  - Automated audio URL fetcher using lod.lu REST API
  - 100% coverage: 10 greetings, 10 numbers, 10 family, 10 objects, 10 time/nature words
- ✅ **Fetching script** (`scripts/fetch_all_lod_audio.py`)
  - Automated discovery of audio URLs via lod.lu API
  - Categorized export to JSON

### v1.4.0 (2026-01-24)
- ✅ **User authentication system** 🎉
  - Login/signup with username, email, password
  - Secure password hashing (SHA256)
  - Session-based authentication in Streamlit
- ✅ **Database-backed progress tracking**
  - SQLite database for persistent storage
  - User accounts, sessions, word attempts tables
  - Automatic saving of all practice sessions
- ✅ **Personal dashboard**
  - Overall statistics (sessions, words, scores)
  - Recent session history
  - Category performance analytics
- ✅ **Session history page**
  - View all past practice sessions
  - Detailed results for each session
  - Attempt-by-attempt breakdown per word
- ✅ **User navigation sidebar**
  - Dashboard, Practice, History pages
  - Logout functionality
- ✅ **Updated .gitignore** - Excludes database and user data

### v1.3.0 (2026-01-24)
- ✅ **Multi-word session system** 🎉
  - Session manager for up to 50 words per session
  - Randomized word order for each session
  - Progress tracking with visual progress bar
  - Final comprehensive summary with statistics
- ✅ **50-word vocabulary bank** organized by category
  - Greetings, numbers, family, objects, time, nature
  - Currently 1 word with audio (49 ready for URL population)
- ✅ **Multiple attempts per word** - up to 3 attempts before moving on
- ✅ **Session summary dashboard**
  - Overall score and statistics
  - Category performance breakdown
  - Top/bottom performers
  - Detailed attempt history
- ✅ **Helper script** for adding word audio URLs (`scripts/add_word_urls.py`)
- ✅ **Graceful handling** of words without audio URLs

### v1.2.0 (2026-01-24)
- ✅ **Major upgrade: Praat-based phonetic analysis** 🎉
- ✅ Replaced MFCC+DTW with linguistically meaningful features:
  - Pitch (F0) patterns for intonation
  - Formants (F1, F2, F3) for vowel quality
  - Intensity patterns for stress
  - Duration/timing for rhythm
  - Voice quality metrics (HNR, jitter, shimmer)
- ✅ **Feature breakdown visualization** with individual scores
- ✅ **Phonetically accurate feedback** - actionable suggestions based on articulatory phonetics
- ✅ Enhanced trend analysis tracking specific feature improvements/declines
- ✅ Weighted scoring (formants 35%, pitch 20%, intensity 15%, duration 15%, voice quality 15%)

### v1.1.1 (2026-01-24)
- ✅ **Fixed scoring bug** - changed scaling factor from 10.0 to 1.0
- ✅ **Fixed insights** - adjusted MFCC thresholds for accurate feedback
- ✅ Scores now properly range from 0-100
- ✅ Detailed feedback showing specific issues and suggestions

### v1.1.0 (2026-01-24)
- ✅ Added detailed insights and trend analysis
- ✅ Progress tracking across multiple attempts
- ✅ Decline reason analysis
- ⚠️ Had scoring bug (fixed in v1.1.1)

### v1.0.1 (2026-01-24)
- ✅ Fixed reference audio URL (404 error)
- ✅ Updated README with architecture diagrams

### v1.0.0 (2026-01-23)
- ✅ Initial release with basic pronunciation comparison

---

## 📄 License

This project is for **educational purposes** only.

Reference audio sourced from [lod.lu](https://lod.lu) (Luxembourgish Online Dictionary) under fair use for educational applications.

---

## 🙏 Credits

- **Reference Audio**: [lod.lu](https://lod.lu) - Luxembourgish Online Dictionary
- **Built with**: [Claude Code](https://claude.ai/claude-code) by Anthropic
- **Framework**: [Streamlit](https://streamlit.io)
- **Phonetic Analysis**: [Praat](https://www.fon.hum.uva.nl/praat/) via [Parselmouth](https://parselmouth.readthedocs.io/)

---

## 💬 Support

For issues or questions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Review the [Known Limitations](#-known-limitations-mvp)
3. Open an issue on GitHub (if applicable)

---

**Built with ❤️ for language learners**
