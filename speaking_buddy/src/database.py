"""Database setup and operations for user authentication and progress tracking"""
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import hashlib


# Database path
DB_DIR = Path(__file__).parent.parent / "data"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "speaking_buddy.db"


def get_connection():
    """Get database connection"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn


def init_database():
    """Initialize database with required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    # Sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            overall_score REAL,
            average_score REAL,
            total_words INTEGER,
            total_attempts INTEGER,
            excellent_count INTEGER DEFAULT 0,
            good_count INTEGER DEFAULT 0,
            fair_count INTEGER DEFAULT 0,
            poor_count INTEGER DEFAULT 0,
            completed BOOLEAN DEFAULT 0,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Word attempts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS word_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            word TEXT NOT NULL,
            translation TEXT,
            category TEXT,
            score REAL NOT NULL,
            feedback TEXT,
            insights_json TEXT,
            attempt_number INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id)
        )
    """)

    # User statistics table (cached aggregates)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            total_sessions INTEGER DEFAULT 0,
            completed_sessions INTEGER DEFAULT 0,
            total_words_practiced INTEGER DEFAULT 0,
            total_attempts INTEGER DEFAULT 0,
            average_overall_score REAL DEFAULT 0,
            best_session_score REAL DEFAULT 0,
            last_practice_date TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(username: str, email: str, password: str) -> Optional[int]:
    """
    Create a new user account.

    Returns:
        User ID if successful, None if username/email already exists
    """
    conn = get_connection()
    cursor = conn.cursor()

    password_hash = hash_password(password)

    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, password_hash)
        )
        user_id = cursor.lastrowid

        # Initialize user stats
        cursor.execute(
            "INSERT INTO user_stats (user_id) VALUES (?)",
            (user_id,)
        )

        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        # Username or email already exists
        return None
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate user with username and password.

    Returns:
        User dict if successful, None otherwise
    """
    conn = get_connection()
    cursor = conn.cursor()

    password_hash = hash_password(password)

    cursor.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (username, password_hash)
    )
    user_row = cursor.fetchone()

    if user_row:
        # Update last login
        cursor.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user_row['id'],)
        )
        conn.commit()

        user = dict(user_row)
        conn.close()
        return user

    conn.close()
    return None


def create_session(user_id: int) -> int:
    """
    Create a new practice session for a user.

    Returns:
        Session ID
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO sessions (user_id) VALUES (?)",
        (user_id,)
    )
    session_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return session_id


def save_word_attempt(
    session_id: int,
    word: str,
    translation: str,
    category: str,
    score: float,
    feedback: str,
    insights: Dict[str, Any],
    attempt_number: int
):
    """Save a word pronunciation attempt"""
    conn = get_connection()
    cursor = conn.cursor()

    insights_json = json.dumps(insights)

    cursor.execute(
        """
        INSERT INTO word_attempts
        (session_id, word, translation, category, score, feedback, insights_json, attempt_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, word, translation, category, score, feedback, insights_json, attempt_number)
    )

    conn.commit()
    conn.close()


def complete_session(session_id: int, summary: Dict[str, Any]):
    """Mark session as complete and save summary statistics"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE sessions SET
            overall_score = ?,
            average_score = ?,
            total_words = ?,
            total_attempts = ?,
            excellent_count = ?,
            good_count = ?,
            fair_count = ?,
            poor_count = ?,
            completed = 1,
            completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            summary['overall_score'],
            summary['average_score'],
            summary['total_words'],
            summary['total_attempts'],
            summary['excellent_count'],
            summary['good_count'],
            summary['fair_count'],
            summary['poor_count'],
            session_id
        )
    )

    # Update user stats
    cursor.execute("SELECT user_id FROM sessions WHERE id = ?", (session_id,))
    user_id = cursor.fetchone()['user_id']

    update_user_stats(cursor, user_id)

    conn.commit()
    conn.close()


def update_user_stats(cursor, user_id: int):
    """Update cached user statistics"""
    # Get all completed sessions for user
    cursor.execute(
        """
        SELECT
            COUNT(*) as total_sessions,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_sessions,
            SUM(total_words) as total_words,
            SUM(total_attempts) as total_attempts,
            AVG(overall_score) as avg_score,
            MAX(overall_score) as best_score,
            MAX(session_date) as last_practice
        FROM sessions
        WHERE user_id = ? AND completed = 1
        """,
        (user_id,)
    )
    stats = cursor.fetchone()

    cursor.execute(
        """
        UPDATE user_stats SET
            total_sessions = ?,
            completed_sessions = ?,
            total_words_practiced = ?,
            total_attempts = ?,
            average_overall_score = ?,
            best_session_score = ?,
            last_practice_date = ?
        WHERE user_id = ?
        """,
        (
            stats['total_sessions'] or 0,
            stats['completed_sessions'] or 0,
            stats['total_words'] or 0,
            stats['total_attempts'] or 0,
            stats['avg_score'] or 0,
            stats['best_score'] or 0,
            stats['last_practice'],
            user_id
        )
    )


def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Get user statistics"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM user_stats WHERE user_id = ?", (user_id,))
    stats_row = cursor.fetchone()

    conn.close()

    if stats_row:
        return dict(stats_row)
    return {}


def get_user_sessions(user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Get user's recent sessions"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM sessions
        WHERE user_id = ? AND completed = 1
        ORDER BY completed_at DESC
        LIMIT ?
        """,
        (user_id, limit)
    )

    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return sessions


def get_session_details(session_id: int) -> Dict[str, Any]:
    """Get detailed session information including all word attempts"""
    conn = get_connection()
    cursor = conn.cursor()

    # Get session info
    cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    session_row = cursor.fetchone()

    if not session_row:
        conn.close()
        return {}

    session = dict(session_row)

    # Get all word attempts for this session
    cursor.execute(
        """
        SELECT * FROM word_attempts
        WHERE session_id = ?
        ORDER BY word, attempt_number
        """,
        (session_id,)
    )

    attempts = []
    for row in cursor.fetchall():
        attempt = dict(row)
        # Parse JSON insights
        if attempt['insights_json']:
            attempt['insights'] = json.loads(attempt['insights_json'])
        attempts.append(attempt)

    session['attempts'] = attempts

    conn.close()
    return session


def get_word_history(user_id: int, word: str) -> List[Dict[str, Any]]:
    """Get user's history practicing a specific word"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT wa.*, s.session_date
        FROM word_attempts wa
        JOIN sessions s ON wa.session_id = s.id
        WHERE s.user_id = ? AND wa.word = ?
        ORDER BY wa.created_at DESC
        LIMIT 20
        """,
        (user_id, word)
    )

    history = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return history


def get_category_stats(user_id: int) -> Dict[str, Dict[str, Any]]:
    """Get user's performance statistics by category"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            wa.category,
            COUNT(DISTINCT wa.word) as words_practiced,
            COUNT(*) as total_attempts,
            AVG(wa.score) as average_score,
            MAX(wa.score) as best_score,
            MIN(wa.score) as worst_score
        FROM word_attempts wa
        JOIN sessions s ON wa.session_id = s.id
        WHERE s.user_id = ? AND s.completed = 1
        GROUP BY wa.category
        """,
        (user_id,)
    )

    category_stats = {}
    for row in cursor.fetchall():
        category = row['category']
        category_stats[category] = dict(row)

    conn.close()
    return category_stats


# Initialize database on module import
init_database()
