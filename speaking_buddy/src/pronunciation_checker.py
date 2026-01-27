"""Pronunciation comparison using MFCC and DTW, or Praat phonetic analysis"""
import numpy as np
from pathlib import Path
from scipy.spatial.distance import euclidean
from scipy.ndimage import uniform_filter1d
from typing import Tuple, Dict, Any
from .audio_processor import preprocess_audio, extract_mfcc
from .config import SCORE_THRESHOLDS, FEEDBACK_MESSAGES
from .praat_analyzer import extract_all_praat_features
from .feature_comparator import calculate_weighted_score
from .feedback_generator import generate_phonetic_feedback


def calculate_dtw_distance(ref_mfcc: np.ndarray, user_mfcc: np.ndarray) -> float:
    """
    Calculate Dynamic Time Warping (DTW) distance between two MFCC sequences.

    Args:
        ref_mfcc: Reference MFCC features (n_mfcc, ref_time_steps)
        user_mfcc: User MFCC features (n_mfcc, user_time_steps)

    Returns:
        DTW distance (normalized by path length)
    """
    # Transpose to (time_steps, n_mfcc) for DTW calculation
    ref_mfcc = ref_mfcc.T
    user_mfcc = user_mfcc.T

    n, m = len(ref_mfcc), len(user_mfcc)

    # Initialize DTW matrix
    dtw_matrix = np.full((n + 1, m + 1), np.inf)
    dtw_matrix[0, 0] = 0

    # Fill DTW matrix
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = euclidean(ref_mfcc[i - 1], user_mfcc[j - 1])
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i - 1, j],      # insertion
                dtw_matrix[i, j - 1],      # deletion
                dtw_matrix[i - 1, j - 1]   # match
            )

    # Return normalized distance
    distance = dtw_matrix[n, m]
    path_length = n + m
    return distance / path_length if path_length > 0 else distance


def distance_to_score(dtw_distance: float, scaling_factor: float = 1.0) -> float:
    """
    Convert DTW distance to a similarity score (0-100 scale).

    Args:
        dtw_distance: The DTW distance value
        scaling_factor: Factor to scale the distance (tuned for MFCC+DTW)

    Returns:
        Similarity score between 0 and 100

    Note:
        Scaling factor of 1.0 gives reasonable scores:
        - DTW ~0 (perfect match) -> score ~100
        - DTW ~40 (good) -> score ~60
        - DTW ~60 (fair) -> score ~40
        - DTW ~100 (poor) -> score ~0
    """
    score = max(0, 100 - (dtw_distance * scaling_factor))
    return min(100, score)


def get_feedback_message(score: float) -> str:
    """
    Get encouraging feedback message based on similarity score.

    Args:
        score: Similarity score (0-100)

    Returns:
        Feedback message string
    """
    if score >= SCORE_THRESHOLDS["excellent"]:
        return FEEDBACK_MESSAGES["excellent"]
    elif score >= SCORE_THRESHOLDS["good"]:
        return FEEDBACK_MESSAGES["good"]
    elif score >= SCORE_THRESHOLDS["fair"]:
        return FEEDBACK_MESSAGES["fair"]
    else:
        return FEEDBACK_MESSAGES["poor"]


def analyze_audio_characteristics(audio: np.ndarray, mfcc: np.ndarray, sr: int) -> Dict[str, float]:
    """
    Analyze various characteristics of the audio.

    Args:
        audio: Audio data as numpy array
        mfcc: MFCC features
        sr: Sample rate

    Returns:
        Dictionary with audio characteristics
    """
    duration = len(audio) / sr
    energy = np.mean(audio ** 2)
    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)

    return {
        "duration": duration,
        "energy": energy,
        "mfcc_mean": mfcc_mean,
        "mfcc_std": mfcc_std,
        "num_frames": mfcc.shape[1]
    }


def generate_detailed_insights(
    score: float,
    ref_chars: Dict[str, Any],
    user_chars: Dict[str, Any],
    previous_score: float = None
) -> Dict[str, Any]:
    """
    Generate detailed insights about the pronunciation.

    Args:
        score: Current similarity score
        ref_chars: Reference audio characteristics
        user_chars: User audio characteristics
        previous_score: Previous attempt score (if any)

    Returns:
        Dictionary with detailed insights
    """
    insights = {
        "score": score,
        "issues": [],
        "improvements": [],
        "suggestions": []
    }

    # Duration comparison
    duration_ratio = user_chars["duration"] / ref_chars["duration"]
    if duration_ratio < 0.7:
        insights["issues"].append("speaking_too_fast")
        insights["suggestions"].append("Try speaking more slowly to match the reference pace")
    elif duration_ratio > 1.3:
        insights["issues"].append("speaking_too_slow")
        insights["suggestions"].append("Try speaking a bit faster to match the reference pace")
    else:
        insights["improvements"].append("Good pacing")

    # Energy comparison
    energy_ratio = user_chars["energy"] / (ref_chars["energy"] + 1e-10)
    if energy_ratio < 0.3:
        insights["issues"].append("volume_too_low")
        insights["suggestions"].append("Speak louder or move closer to the microphone")
    elif energy_ratio > 3.0:
        insights["issues"].append("volume_too_high")
        insights["suggestions"].append("Speak more softly or move back from the microphone")
    else:
        insights["improvements"].append("Good volume level")

    # MFCC similarity (pronunciation quality)
    mfcc_diff = np.mean(np.abs(user_chars["mfcc_mean"] - ref_chars["mfcc_mean"]))
    if mfcc_diff > 15:
        insights["issues"].append("pronunciation_quite_different")
        insights["suggestions"].append("Listen carefully to the reference and try to mimic the exact sound")
    elif mfcc_diff > 8:
        insights["issues"].append("pronunciation_somewhat_different")
        insights["suggestions"].append("You're close! Focus on matching the vowel sounds more precisely")
    else:
        insights["improvements"].append("Pronunciation sounds very similar")

    # Comparison with previous attempt
    if previous_score is not None:
        score_change = score - previous_score
        insights["score_change"] = score_change

        if score_change > 5:
            insights["trend"] = "improving"
            insights["trend_message"] = f"Great! You improved by {score_change:.1f} points!"
        elif score_change < -5:
            insights["trend"] = "declining"
            insights["trend_message"] = f"Your score dropped by {abs(score_change):.1f} points"

            # Analyze what got worse
            prev_duration_saved = getattr(generate_detailed_insights, '_prev_duration_ratio', None)
            if prev_duration_saved:
                duration_change = abs(duration_ratio - 1.0) - abs(prev_duration_saved - 1.0)
                if duration_change > 0.1:
                    insights["decline_reasons"] = insights.get("decline_reasons", [])
                    insights["decline_reasons"].append("Your pacing changed from the previous attempt")
        else:
            insights["trend"] = "stable"
            insights["trend_message"] = f"Similar to last time ({score_change:+.1f} points)"

    # Store for next comparison
    generate_detailed_insights._prev_duration_ratio = duration_ratio

    return insights


def compare_pronunciations(
    reference_path: Path,
    user_path: Path,
    previous_score: float = None
) -> Tuple[float, str, Dict[str, Any]]:
    """
    Compare user pronunciation against reference audio with detailed analysis.

    Args:
        reference_path: Path to reference audio file
        user_path: Path to user recording file
        previous_score: Previous attempt score for comparison (optional)

    Returns:
        Tuple of (similarity score 0-100, feedback message, detailed insights dict)

    Raises:
        Exception: If audio processing fails
    """
    # Load and preprocess both audio files
    ref_audio, ref_sr = preprocess_audio(reference_path)
    user_audio, user_sr = preprocess_audio(user_path)

    # Extract MFCC features
    ref_mfcc = extract_mfcc(ref_audio, ref_sr)
    user_mfcc = extract_mfcc(user_audio, user_sr)

    # Analyze characteristics
    ref_chars = analyze_audio_characteristics(ref_audio, ref_mfcc, ref_sr)
    user_chars = analyze_audio_characteristics(user_audio, user_mfcc, user_sr)

    # Calculate DTW distance
    dtw_distance = calculate_dtw_distance(ref_mfcc, user_mfcc)

    # Convert to similarity score
    score = distance_to_score(dtw_distance)

    # Get feedback message
    feedback = get_feedback_message(score)

    # Generate detailed insights
    insights = generate_detailed_insights(score, ref_chars, user_chars, previous_score)

    return score, feedback, insights


def compare_pronunciations_praat(
    reference_path: Path,
    user_path: Path,
    previous_score: float = None
) -> Tuple[float, str, Dict[str, Any]]:
    """
    Compare user pronunciation against reference using Praat phonetic analysis.

    This method provides more accurate phonetic comparison using:
    - Pitch (F0) patterns for intonation
    - Formants (F1, F2, F3) for vowel quality
    - Intensity patterns for stress
    - Duration/timing for rhythm
    - Voice quality metrics (HNR, jitter, shimmer)

    Args:
        reference_path: Path to reference audio file
        user_path: Path to user recording file
        previous_score: Previous attempt score for trend analysis (optional)

    Returns:
        Tuple of (similarity score 0-100, feedback message, detailed insights dict)

    Raises:
        Exception: If audio processing or Praat analysis fails
    """
    # Extract Praat phonetic features from both audio files
    ref_features = extract_all_praat_features(reference_path)
    user_features = extract_all_praat_features(user_path)

    # Calculate weighted score with feature breakdown
    scores = calculate_weighted_score(ref_features, user_features)

    # Get total score
    score = scores['total_score']

    # Generate phonetically meaningful feedback
    phonetic_feedback = generate_phonetic_feedback(ref_features, user_features, scores)

    # Get feedback message based on score
    feedback = get_feedback_message(score)

    # Build comprehensive insights dictionary
    insights = {
        "score": score,
        "breakdown": scores['breakdown'],  # Individual feature scores
        "improvements": phonetic_feedback.get('improvements', []),
        "issues": phonetic_feedback.get('issues', []),
        "suggestions": phonetic_feedback.get('suggestions', [])
    }

    # Add trend analysis if previous score provided
    if previous_score is not None:
        score_change = score - previous_score
        insights["score_change"] = score_change

        if score_change > 5:
            insights["trend"] = "improving"
            insights["trend_message"] = f"Great! You improved by {score_change:.1f} points!"
        elif score_change < -5:
            insights["trend"] = "declining"
            insights["trend_message"] = f"Your score dropped by {abs(score_change):.1f} points"

            # Analyze which features declined
            decline_reasons = []
            prev_breakdown = getattr(compare_pronunciations_praat, '_prev_breakdown', {})
            if prev_breakdown:
                for feature, current_score in scores['breakdown'].items():
                    prev_score = prev_breakdown.get(feature, current_score)
                    if current_score < prev_score - 5:
                        feature_name = {
                            'pitch': 'intonation',
                            'formants': 'vowel pronunciation',
                            'intensity': 'stress patterns',
                            'duration': 'timing',
                            'voice_quality': 'voice clarity'
                        }.get(feature, feature)
                        decline_reasons.append(f"Your {feature_name} changed from the previous attempt")

            if decline_reasons:
                insights["decline_reasons"] = decline_reasons
        else:
            insights["trend"] = "stable"
            insights["trend_message"] = f"Similar to last time ({score_change:+.1f} points)"

    # Store breakdown for next comparison
    compare_pronunciations_praat._prev_breakdown = scores['breakdown']

    return score, feedback, insights
