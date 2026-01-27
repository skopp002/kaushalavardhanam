#!/bin/bash
# Speaking Buddy - Automated Installation Test Script
# Version: 1.5.0
# Run this script to verify your installation is working correctly

set -e  # Exit on error

echo "========================================="
echo "  Speaking Buddy Installation Test"
echo "  Version 1.5.0"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function to print test results
test_result() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $1"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ FAIL${NC}: $1"
        ((TESTS_FAILED++))
        if [ ! -z "$2" ]; then
            echo -e "${YELLOW}   Hint: $2${NC}"
        fi
    fi
}

echo "=== Test 1: Python Version ==="
.venv/bin/python --version
test_result "Python version check" "Ensure Python 3.12+ is installed"
echo ""

echo "=== Test 2: Core Dependencies ==="
.venv/bin/python -c "import streamlit, parselmouth, pydub, scipy, soundfile, requests; print('All dependencies imported successfully')" 2>/dev/null
test_result "Core dependencies installed" "Run: .venv/bin/python -m pip install streamlit streamlit-audiorecorder pydub scipy soundfile requests praat-parselmouth"
echo ""

echo "=== Test 3: ffmpeg Installation ==="
ffmpeg -version | head -n 1
test_result "ffmpeg installed" "Install ffmpeg: brew install ffmpeg (macOS) or sudo apt-get install ffmpeg (Linux)"
echo ""

echo "=== Test 4: Vocabulary Bank Completeness ==="
WORD_COUNT=$(.venv/bin/python -c "from src.config import WORD_BANK; print(len([w for w, i in WORD_BANK.items() if i['url']]))" 2>/dev/null || echo "0")
echo "Words with audio URLs: $WORD_COUNT/50"
if [ "$WORD_COUNT" = "50" ]; then
    ((TESTS_PASSED++))
    echo -e "${GREEN}✅ PASS${NC}: All 50 words have audio URLs"
else
    ((TESTS_FAILED++))
    echo -e "${RED}❌ FAIL${NC}: Only $WORD_COUNT/50 words have audio URLs"
fi
echo ""

echo "=== Test 5: Database Initialization ==="
TABLE_COUNT=$(.venv/bin/python -c "from src import database; import sqlite3; conn = database.get_connection(); cursor = conn.cursor(); cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"'); tables = cursor.fetchall(); print(len(tables)); conn.close()" 2>/dev/null || echo "0")
echo "Database tables created: $TABLE_COUNT"
if [ "$TABLE_COUNT" -ge "4" ]; then
    ((TESTS_PASSED++))
    echo -e "${GREEN}✅ PASS${NC}: Database properly initialized"
else
    ((TESTS_FAILED++))
    echo -e "${RED}❌ FAIL${NC}: Database not properly initialized"
    echo -e "${YELLOW}   Hint: Delete data/speaking_buddy.db and restart Python${NC}"
fi
echo ""

echo "=== Test 6: Session Manager ==="
.venv/bin/python -c "from src.session_manager import SessionManager; s = SessionManager(); assert len(s.word_list) == 50; print('SessionManager initialized with 50 words')" 2>/dev/null
test_result "SessionManager works correctly" "Check src/session_manager.py for errors"
echo ""

echo "=== Test 7: Reference Audio Download ==="
.venv/bin/python -c "from src.reference_manager import ensure_reference_exists; import os; path = ensure_reference_exists('moien'); assert os.path.exists(path); print('Reference audio downloaded and cached')" 2>/dev/null
test_result "Reference audio system works" "Check internet connection and ffmpeg installation"
echo ""

echo ""
echo "========================================="
echo "           Test Summary"
echo "========================================="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    echo ""
    echo "Some tests failed. Please review the hints above."
    echo "See README.md Testing section for detailed troubleshooting."
    exit 1
else
    echo -e "${RED}Failed: $TESTS_FAILED${NC}"
    echo ""
    echo -e "${GREEN}🎉 All tests passed! Speaking Buddy is ready to use.${NC}"
    echo ""
    echo "To start the application, run:"
    echo "  .venv/bin/python -m streamlit run main.py"
    echo ""
    echo "For more detailed tests, see README.md Testing section."
    exit 0
fi
