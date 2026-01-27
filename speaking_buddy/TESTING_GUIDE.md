# Speaking Buddy - Testing Guide

## Quick Start Testing

### Option 1: Automated Test (Recommended)

Run the automated test script for instant verification:

```bash
./scripts/test_installation.sh
```

**This will test:**
- ✅ Python 3.12+ installation
- ✅ All required dependencies
- ✅ ffmpeg installation
- ✅ 50/50 words with audio URLs
- ✅ Database initialization (4 tables)
- ✅ SessionManager functionality
- ✅ Reference audio download system

**Expected result:**
```
🎉 All tests passed! Speaking Buddy is ready to use.
```

### Option 2: Manual Quick Test

```bash
# Test core dependencies
.venv/bin/python -c "import streamlit, parselmouth, pydub, scipy, soundfile, requests; print('✅ All dependencies OK')"

# Test vocabulary completeness
.venv/bin/python -c "from src.config import WORD_BANK; print(f'✅ {len([w for w,i in WORD_BANK.items() if i[\"url\"]])}/50 words ready')"

# Test database
.venv/bin/python -c "from src import database; print('✅ Database initialized')"

# Test session manager
.venv/bin/python -c "from src.session_manager import SessionManager; s = SessionManager(); print(f'✅ SessionManager ready with {len(s.word_list)} words')"
```

---

## Detailed Testing Procedures

For comprehensive testing instructions, see the [Testing section](README.md#-testing) in the README.

### Test Categories

1. **Installation Verification** - Python, dependencies, ffmpeg
2. **Configuration Check** - 50 words, categories, URLs
3. **Database Tests** - Tables, schema, connections
4. **Session Manager Tests** - Creation, randomization, attempts
5. **Authentication Tests** - Signup, login, security
6. **Audio System Tests** - Download, conversion, caching
7. **Praat Analysis Tests** - Feature extraction, validation
8. **Application Startup** - UI loading, navigation
9. **End-to-End Flow** - Complete user workflow
10. **Persistence Tests** - Database storage, retrieval

---

## Common Issues and Solutions

### Issue: "No module named 'streamlit'"
**Solution:**
```bash
.venv/bin/python -m pip install streamlit streamlit-audiorecorder pydub scipy soundfile requests praat-parselmouth
```

### Issue: "ffmpeg not found"
**Solution:**
```bash
# macOS
brew install ffmpeg

# Linux
sudo apt-get update && sudo apt-get install ffmpeg
```

### Issue: "Database table missing"
**Solution:**
```bash
# Delete and recreate database
rm data/speaking_buddy.db
.venv/bin/python -c "from src import database; print('Database recreated')"
```

### Issue: "Reference audio download failed"
**Solution:**
```bash
# Check internet connection
ping -c 3 lod.lu

# Verify ffmpeg
ffmpeg -version

# Test download manually
.venv/bin/python -c "from src.reference_manager import ensure_reference_exists; ensure_reference_exists('moien')"
```

### Issue: "Streamlit won't start"
**Solution:**
```bash
# Kill any stuck processes
pkill -f streamlit

# Clear Streamlit cache
rm -rf ~/.streamlit/

# Check port availability
lsof -i :8501

# Start with specific port
.venv/bin/python -m streamlit run main.py --server.port 8502
```

---

## Continuous Integration Testing

The automated test script can be used in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
name: Test Speaking Buddy
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y ffmpeg
          python -m venv .venv
          .venv/bin/pip install streamlit streamlit-audiorecorder pydub scipy soundfile requests praat-parselmouth
      - name: Run tests
        run: ./scripts/test_installation.sh
```

---

## Testing Checklist

Use this checklist when testing a fresh installation:

### Pre-Installation
- [ ] Python 3.12+ installed
- [ ] Virtual environment created
- [ ] ffmpeg installed

### Installation
- [ ] Dependencies installed successfully
- [ ] No installation errors

### Automated Tests
- [ ] Run `./scripts/test_installation.sh`
- [ ] All 7 tests pass
- [ ] No errors in output

### Manual Verification
- [ ] Streamlit starts without errors
- [ ] Can access http://localhost:8501
- [ ] Login page loads correctly
- [ ] Can create new account
- [ ] Can log in successfully
- [ ] Dashboard displays correctly
- [ ] Can start practice session
- [ ] Reference audio plays
- [ ] Can record audio
- [ ] Pronunciation comparison works
- [ ] Score displays correctly
- [ ] Can complete session
- [ ] Session appears in history
- [ ] Can log out

### Data Persistence
- [ ] Database file created
- [ ] User data persists after logout
- [ ] Session history retained
- [ ] Statistics update correctly

---

## Performance Testing

### Expected Performance Metrics

| Operation | Expected Time |
|-----------|--------------|
| Streamlit startup | < 5 seconds |
| Reference audio download | < 2 seconds (first time) |
| Reference audio cached | < 100ms (subsequent) |
| Praat feature extraction | < 1 second |
| Pronunciation comparison | < 3 seconds |
| Database query | < 50ms |
| Session creation | < 100ms |

### How to Measure

```bash
# Measure Praat analysis time
time .venv/bin/python -c "
from src.praat_analyzer import extract_praat_features
from src.reference_manager import ensure_reference_exists
import parselmouth
audio_path = ensure_reference_exists('moien')
sound = parselmouth.Sound(str(audio_path))
features = extract_praat_features(sound)
"

# Measure database query time
time .venv/bin/python -c "
from src import database
user = database.authenticate_user('testuser', 'testpass')
"
```

---

## Security Testing

### Authentication Security
```bash
# Test password requirements
.venv/bin/python -c "
from src import database
# Should fail: password too short
result = database.create_user('user1', 'user1@test.com', '123')
print('Short password test:', 'PASS' if result is None else 'FAIL')
"
```

### SQL Injection Prevention
The application uses parameterized queries throughout, preventing SQL injection attacks.

### Password Storage
Passwords are hashed using SHA256 before storage. For production, consider upgrading to bcrypt.

---

## Test Data Management

### Create Test User
```bash
.venv/bin/python -c "
from src import database
import time
username = f'testuser_{int(time.time())}'
user_id = database.create_user(username, f'{username}@test.com', 'testpass123')
print(f'Created test user: {username} (ID: {user_id})')
"
```

### Clean Test Data
```bash
# Remove test database
rm data/speaking_buddy.db

# Remove cached audio
rm -rf data/reference_audio/*

# Remove user recordings
rm -rf data/user_recordings/*
```

---

## Regression Testing

When making changes to the codebase, run these tests to ensure nothing broke:

1. **Automated Test Suite**
   ```bash
   ./scripts/test_installation.sh
   ```

2. **End-to-End Manual Test**
   - Complete one full practice session
   - Verify score is reasonable
   - Check session saved to history

3. **Database Integrity**
   ```bash
   sqlite3 data/speaking_buddy.db "PRAGMA integrity_check;"
   ```

---

## Test Results Archive

Keep a log of test results:

```bash
# Run tests with timestamp
./scripts/test_installation.sh | tee "test_results_$(date +%Y%m%d_%H%M%S).log"
```

---

## Getting Help

If tests are failing:

1. **Check the README** - [Testing section](README.md#-testing)
2. **Review error messages** - They usually indicate the problem
3. **Check prerequisites** - Python 3.12+, ffmpeg
4. **Verify installation** - Run pip install commands again
5. **Clean and retry** - Delete data directories and recreate

For persistent issues, see the [Troubleshooting](README.md#-troubleshooting) section in the README.

---

**Last Updated:** 2026-01-24 | **Version:** 1.5.0
