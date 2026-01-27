"""Session management for multi-word pronunciation practice"""
import random
from typing import List, Dict, Any, Optional
from .config import WORD_BANK, WORDS_PER_SESSION, MAX_ATTEMPTS_PER_WORD
from . import database


class SessionManager:
    """Manages a practice session with multiple words"""

    def __init__(self, user_id: Optional[int] = None):
        """
        Initialize a new practice session with randomized word list.

        Args:
            user_id: Optional user ID for database persistence
        """
        self.user_id = user_id
        self.db_session_id = None

        # Create database session if user is logged in
        if self.user_id:
            self.db_session_id = database.create_session(self.user_id)
        # Get all words that have audio URLs
        available_words = [
            word for word, info in WORD_BANK.items()
            if info["url"] is not None
        ]

        # If we have fewer words with URLs, use what we have
        num_words = min(len(available_words), WORDS_PER_SESSION)

        # Randomly select words for this session
        self.word_list = random.sample(available_words, num_words)

        # Current word index
        self.current_word_index = 0

        # Session results: {word: {"attempts": [...], "best_score": float}}
        self.results: Dict[str, Dict[str, Any]] = {}

        # Initialize results for all words
        for word in self.word_list:
            self.results[word] = {
                "attempts": [],
                "best_score": 0,
                "translation": WORD_BANK[word]["translation"],
                "category": WORD_BANK[word]["category"]
            }

    def get_current_word(self) -> Optional[str]:
        """Get the current word to practice"""
        if self.is_session_complete():
            return None
        return self.word_list[self.current_word_index]

    def get_current_word_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the current word"""
        current_word = self.get_current_word()
        if current_word is None:
            return None

        word_info = WORD_BANK[current_word].copy()
        word_info["word"] = current_word
        word_info["attempts_so_far"] = len(self.results[current_word]["attempts"])
        return word_info

    def record_attempt(self, word: str, score: float, feedback: str, insights: Dict[str, Any]):
        """Record a pronunciation attempt for a word"""
        if word not in self.results:
            return

        attempt_data = {
            "score": score,
            "feedback": feedback,
            "insights": insights
        }

        self.results[word]["attempts"].append(attempt_data)

        # Update best score
        if score > self.results[word]["best_score"]:
            self.results[word]["best_score"] = score

        # Save to database if user is logged in
        if self.user_id and self.db_session_id:
            attempt_number = len(self.results[word]["attempts"])
            database.save_word_attempt(
                session_id=self.db_session_id,
                word=word,
                translation=self.results[word]["translation"],
                category=self.results[word]["category"],
                score=score,
                feedback=feedback,
                insights=insights,
                attempt_number=attempt_number
            )

    def can_move_to_next_word(self, word: str) -> bool:
        """Check if user can move to next word"""
        if word not in self.results:
            return False

        # Can move if reached max attempts or if they want to skip
        attempts_count = len(self.results[word]["attempts"])
        return attempts_count >= MAX_ATTEMPTS_PER_WORD or attempts_count > 0

    def move_to_next_word(self):
        """Move to the next word in the session"""
        if not self.is_session_complete():
            self.current_word_index += 1

    def is_session_complete(self) -> bool:
        """Check if all words have been practiced"""
        return self.current_word_index >= len(self.word_list)

    def get_progress(self) -> Dict[str, Any]:
        """Get session progress information"""
        return {
            "current_index": self.current_word_index,
            "total_words": len(self.word_list),
            "percentage": (self.current_word_index / len(self.word_list)) * 100 if self.word_list else 0
        }

    def get_session_summary(self) -> Dict[str, Any]:
        """Get comprehensive session summary with statistics"""
        if not self.is_session_complete():
            return {"complete": False}

        # Calculate statistics
        total_attempts = sum(len(data["attempts"]) for data in self.results.values())
        all_scores = [
            attempt["score"]
            for data in self.results.values()
            for attempt in data["attempts"]
        ]

        best_scores = [data["best_score"] for data in self.results.values()]

        # Category performance
        category_stats = {}
        for word, data in self.results.items():
            category = data["category"]
            if category not in category_stats:
                category_stats[category] = {
                    "scores": [],
                    "count": 0
                }
            category_stats[category]["scores"].append(data["best_score"])
            category_stats[category]["count"] += 1

        # Calculate category averages
        for category, stats in category_stats.items():
            stats["average"] = sum(stats["scores"]) / len(stats["scores"]) if stats["scores"] else 0

        summary = {
            "complete": True,
            "total_words": len(self.word_list),
            "total_attempts": total_attempts,
            "overall_score": sum(best_scores) / len(best_scores) if best_scores else 0,
            "average_score": sum(all_scores) / len(all_scores) if all_scores else 0,
            "best_score": max(best_scores) if best_scores else 0,
            "worst_score": min(best_scores) if best_scores else 0,
            "excellent_count": sum(1 for score in best_scores if score >= 80),
            "good_count": sum(1 for score in best_scores if 60 <= score < 80),
            "fair_count": sum(1 for score in best_scores if 40 <= score < 60),
            "poor_count": sum(1 for score in best_scores if score < 40),
            "category_performance": category_stats,
            "word_results": self.results
        }

        # Save to database if user is logged in
        if self.user_id and self.db_session_id:
            database.complete_session(self.db_session_id, summary)

        return summary

    def get_attempts_for_current_word(self) -> List[Dict[str, Any]]:
        """Get all attempts for the current word"""
        current_word = self.get_current_word()
        if current_word and current_word in self.results:
            return self.results[current_word]["attempts"]
        return []
