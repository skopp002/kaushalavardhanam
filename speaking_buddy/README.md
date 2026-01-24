# Speaking Buddy - Pronunciation Learning Tool

A minimal viable Streamlit-based pronunciation learning tool that helps users practice Luxembourgish pronunciation by comparing their recordings against reference audio using MFCC and DTW analysis.

## 🚀 Quickstart

```bash
# 1. Install ffmpeg (required for audio processing)
brew install ffmpeg  # macOS
# sudo apt-get install ffmpeg  # Linux

# 2. Install Python dependencies
.venv/bin/python -m ensurepip
.venv/bin/python -m pip install --only-binary=:all: numba llvmlite
.venv/bin/python -m pip install streamlit streamlit-audiorecorder pydub scipy librosa soundfile requests

# 3. Run the app
.venv/bin/python -m streamlit run main.py
```

Open http://localhost:8501 in your browser and start practicing!

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [How It Works](#-how-it-works)
- [Installation](#-installation)
- [Usage Guide](#-usage-guide)
- [Project Structure](#-project-structure)
- [Technical Details](#-technical-details)
- [Known Limitations](#-known-limitations)
- [Future Enhancements](#-future-enhancements)

---

## ✨ Features

- 🗣️ **Practice pronunciation** of "Moien" (Luxembourgish greeting meaning "Hello")
- 📻 **Reference audio** automatically downloaded from lod.lu (cached locally)
- 🎤 **Browser-based recording** - no external microphone setup needed
- 📊 **Instant feedback** with similarity scores (0-100)
- 🎯 **Color-coded results** (Excellent, Good, Fair, Poor)
- 🔄 **Try again** feature for iterative practice
- 💾 **Automatic caching** of reference audio for offline use
- 🎨 **Clean, intuitive UI** built with Streamlit

---

## 🏗️ Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface                            │
│                      (Streamlit Web App)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Reference   │  │   Record     │  │   Compare    │          │
│  │  Audio       │  │   Audio      │  │ & Results    │          │
│  │  Player      │  │  (Browser)   │  │              │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Application Logic                            │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            reference_manager.py                           │   │
│  │  • Download reference audio from lod.lu                   │   │
│  │  • Cache to data/reference_audio/                         │   │
│  │  • Check if already cached                                │   │
│  └──────────────┬───────────────────────────────────────────┘   │
│                 │                                                 │
│  ┌──────────────▼──────────────────────────────────────────┐   │
│  │            audio_processor.py                            │   │
│  │  • Load audio files (reference & user)                   │   │
│  │  • Normalize audio levels                                │   │
│  │  • Trim silence (top_db=20)                              │   │
│  │  • Extract MFCC features (13 coefficients)               │   │
│  └──────────────┬───────────────────────────────────────────┘   │
│                 │                                                 │
│  ┌──────────────▼──────────────────────────────────────────┐   │
│  │         pronunciation_checker.py                         │   │
│  │  • Compare MFCC sequences using DTW                      │   │
│  │  • Calculate similarity distance                         │   │
│  │  • Convert to 0-100 score                                │   │
│  │  • Generate feedback message                             │   │
│  └──────────────┬───────────────────────────────────────────┘   │
│                 │                                                 │
│  ┌──────────────▼──────────────────────────────────────────┐   │
│  │              config.py                                   │   │
│  │  • Reference URLs                                        │   │
│  │  • Audio processing parameters                           │   │
│  │  • Scoring thresholds                                    │   │
│  │  • Feedback messages                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      External Systems                            │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   lod.lu     │  │   Browser    │  │  Local File  │          │
│  │ (Reference   │  │  Microphone  │  │   System     │          │
│  │   Audio)     │  │     API      │  │   (Cache)    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└───────────────────────────────────────────────────────────────────┘
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

3. COMPARISON PROCESS
   ┌──────────────────────────────────────────┐
   │ Load both audio files                    │
   │           ↓                              │
   │ Normalize amplitude to [-1, 1]           │
   │           ↓                              │
   │ Trim silence (20dB threshold)            │
   │           ↓                              │
   │ Extract MFCC (13 coefficients)           │
   │           ↓                              │
   │ Calculate DTW distance                   │
   │           ↓                              │
   │ Convert to similarity score (0-100)      │
   │           ↓                              │
   │ Generate feedback message                │
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

The app uses **acoustic analysis** to objectively compare pronunciations:

#### 1. **MFCC Feature Extraction**
   - **MFCC** (Mel-Frequency Cepstral Coefficients) represent the short-term power spectrum of sound
   - Extracts 13 coefficients that capture the "shape" of the vocal tract
   - These features are robust to variations in amplitude and pitch

#### 2. **Dynamic Time Warping (DTW)**
   - Measures similarity between two time-series (reference vs. user MFCC)
   - Handles differences in speaking speed
   - Finds the optimal alignment between sequences
   - Returns a distance metric (lower = more similar)

#### 3. **Scoring**
   - DTW distance is normalized by path length
   - Converted to 0-100 scale: `score = max(0, 100 - (distance × scaling_factor))`
   - Scaling factor tuned to provide meaningful scores

#### 4. **Feedback Generation**
   ```python
   if score >= 80:  → "Excellent! Very close to reference!"
   elif score >= 60: → "Good job! Quite similar. Keep practicing!"
   elif score >= 40: → "Not bad! With more practice, you'll improve."
   else:            → "Keep trying! Listen carefully to the reference."
   ```

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
.venv/bin/python -m pip install streamlit streamlit-audiorecorder pydub scipy librosa soundfile requests
```

**3. Run the App**

```bash
.venv/bin/python -m streamlit run main.py
```

The app will open automatically at http://localhost:8501

---

## 📖 Usage Guide

### How to Use

1. **Listen** to the reference pronunciation
2. **Record** your pronunciation by clicking the microphone button
3. **Compare** to get your score (0-100) and feedback
4. **Practice** - try again to improve your score!

### Tips for Best Results

- Record in a quiet environment
- Speak clearly at a normal pace
- Keep microphone distance consistent
- Try to match the reference's intonation
- Aim for scores ≥80 for excellent pronunciation

---

## 📁 Project Structure

```
speaking_buddy/
├── main.py                      # Streamlit app entry point
├── src/
│   ├── config.py                # Configuration & constants
│   ├── reference_manager.py     # Reference audio download/cache
│   ├── audio_processor.py       # Audio preprocessing & MFCC extraction
│   └── pronunciation_checker.py # DTW comparison & scoring
├── data/
│   ├── reference_audio/         # Cached reference files (moien.ogg)
│   └── user_recordings/         # User recordings (*.wav)
├── .venv/                       # Virtual environment
├── pyproject.toml               # Dependencies
└── README.md                    # Documentation
```

---

## 🔧 Technical Details

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | Streamlit 1.53+ | UI and user interaction |
| **Audio Recording** | streamlit-audiorecorder | Browser-based microphone capture |
| **Audio Processing** | Librosa 0.11+ | MFCC extraction and audio analysis |
| **Numerical Computing** | NumPy 2.3+ | Array operations |
| **Scientific Computing** | SciPy 1.17+ | DTW distance calculation |
| **Audio I/O** | Soundfile 0.13+ | Reading/writing audio files |
| **Audio Manipulation** | Pydub 0.25+ | Format conversion |
| **HTTP Requests** | Requests 2.32+ | Download reference audio |
| **JIT Compilation** | Numba 0.62+ | Performance optimization (Librosa dependency) |

### Audio Processing Parameters

```python
SAMPLE_RATE = 22050       # Hz - standard for speech processing
MAX_DURATION = 5          # seconds - max recording length
N_MFCC = 13              # Number of MFCC coefficients
SILENCE_THRESHOLD = 20   # dB - for trimming silence
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
- ✋ **Single word only**: Currently supports "Moien" only
- 🔒 **No user accounts**: No authentication or user profiles
- 💾 **No persistence**: Progress not saved between sessions
- 🎯 **Overall score only**: No phoneme-level feedback
- 🔄 **No history**: Can't review past recordings

### Technical Limitations
- 🌐 **Browser recording requirements**:
  - Requires HTTPS or localhost
  - Microphone permissions needed
  - Not all browsers supported equally
- 📊 **Score calibration**: Thresholds may need tuning with real user data
- 🎤 **Recording quality**: Depends on user's microphone and environment
- 🗣️ **No accent detection**: Can't identify specific pronunciation errors

### Platform Limitations
- 🖥️ **Desktop-focused**: UI optimized for desktop browsers
- 📱 **Mobile limitations**: Recording may not work on all mobile browsers
- 🌍 **Offline mode**: Reference audio must be downloaded at least once

---

## 🚀 Future Enhancements

### Short-term (MVP+)
- [ ] Add 5-10 more words from lod.lu
- [ ] Basic progress tracking (session-based)
- [ ] Score history chart
- [ ] Recording quality check (volume too low warning)
- [ ] Better mobile support

### Medium-term
- [ ] User authentication (optional)
- [ ] Personal progress dashboard
- [ ] Multiple difficulty levels
- [ ] Practice recommendations
- [ ] Export recordings feature
- [ ] Leaderboard (optional)

### Long-term
- [ ] Phoneme-level feedback (which sounds to improve)
- [ ] Multiple languages (French, German, English)
- [ ] Speech recognition integration
- [ ] Gamification (badges, streaks, points)
- [ ] Social features (share progress)
- [ ] Mobile app version
- [ ] AI-powered personalized coaching

### Technical Improvements
- [ ] Optimize MFCC extraction speed
- [ ] Add background noise filtering
- [ ] Implement A/B testing for score thresholds
- [ ] Add telemetry and analytics
- [ ] Improve DTW algorithm performance
- [ ] Add unit tests and CI/CD

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

### v1.1.1 (2026-01-24) - **Current**
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
- **Audio Analysis**: [Librosa](https://librosa.org)

---

## 💬 Support

For issues or questions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Review the [Known Limitations](#-known-limitations-mvp)
3. Open an issue on GitHub (if applicable)

---

**Built with ❤️ for language learners**
