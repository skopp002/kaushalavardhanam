"""Compare and score phonetic features extracted by Praat"""
import numpy as np
from scipy.spatial.distance import euclidean
from typing import Dict, Any, List, Tuple


# Feature weights for final scoring
FEATURE_WEIGHTS = {
    "pitch": 0.20,      # Intonation pattern
    "formants": 0.35,   # Vowel quality (most important for pronunciation)
    "intensity": 0.15,  # Stress patterns
    "duration": 0.15,   # Timing/rhythm
    "voice_quality": 0.15  # Clarity and stability
}

# Tolerance thresholds
PITCH_TOLERANCE_HZ = 30  # ±30 Hz acceptable deviation
FORMANT_TOLERANCE_HZ = 150  # ±150 Hz for F1/F2
INTENSITY_TOLERANCE_DB = 3  # ±3 dB
DURATION_TOLERANCE_RATIO = 0.2  # ±20% timing variation


def dtw_distance(seq1: List[float], seq2: List[float]) -> float:
    """
    Calculate Dynamic Time Warping distance between two sequences.

    Args:
        seq1: First sequence
        seq2: Second sequence

    Returns:
        Normalized DTW distance
    """
    if not seq1 or not seq2:
        return 100.0  # Maximum distance if either sequence is empty

    n, m = len(seq1), len(seq2)

    # Initialize DTW matrix
    dtw_matrix = np.full((n + 1, m + 1), np.inf)
    dtw_matrix[0, 0] = 0

    # Fill DTW matrix
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = abs(seq1[i - 1] - seq2[j - 1])
            dtw_matrix[i, j] = cost + min(
                dtw_matrix[i - 1, j],      # insertion
                dtw_matrix[i, j - 1],      # deletion
                dtw_matrix[i - 1, j - 1]   # match
            )

    # Return normalized distance
    distance = dtw_matrix[n, m]
    path_length = n + m
    return distance / path_length if path_length > 0 else distance


def compare_pitch_contours(ref_pitch: Dict[str, Any], user_pitch: Dict[str, Any]) -> float:
    """
    Compare pitch patterns between reference and user.

    Args:
        ref_pitch: Reference pitch features
        user_pitch: User pitch features

    Returns:
        Similarity score (0-100)
    """
    # If either has no voiced segments, score based on that
    if ref_pitch["mean_f0"] == 0 or user_pitch["mean_f0"] == 0:
        if ref_pitch["mean_f0"] == user_pitch["mean_f0"]:
            return 100.0
        return 0.0

    # Compare mean pitch (allows for different speaker pitch ranges)
    mean_diff_ratio = abs(ref_pitch["mean_f0"] - user_pitch["mean_f0"]) / ref_pitch["mean_f0"]
    mean_score = max(0, 100 - (mean_diff_ratio * 200))  # Penalize >50% difference heavily

    # Compare pitch range (intonation expressiveness)
    if ref_pitch["range_f0"] > 0:
        range_diff_ratio = abs(ref_pitch["range_f0"] - user_pitch["range_f0"]) / ref_pitch["range_f0"]
        range_score = max(0, 100 - (range_diff_ratio * 100))
    else:
        range_score = 100 if user_pitch["range_f0"] == 0 else 50

    # Compare pitch contours using DTW
    if len(ref_pitch["contour"]) > 2 and len(user_pitch["contour"]) > 2:
        # Normalize contours to compare patterns regardless of absolute pitch
        ref_normalized = [(p - ref_pitch["mean_f0"]) / (ref_pitch["std_f0"] + 1)
                         for p in ref_pitch["contour"]]
        user_normalized = [(p - user_pitch["mean_f0"]) / (user_pitch["std_f0"] + 1)
                          for p in user_pitch["contour"]]

        dtw_dist = dtw_distance(ref_normalized, user_normalized)
        contour_score = max(0, 100 - (dtw_dist * 20))
    else:
        contour_score = mean_score  # Fall back to mean if contours too short

    # Weighted combination
    return (mean_score * 0.3 + range_score * 0.3 + contour_score * 0.4)


def compare_formant_trajectories(ref_formants: Dict[str, Any], user_formants: Dict[str, Any]) -> float:
    """
    Compare formant patterns (F1, F2, F3) for vowel quality.

    Args:
        ref_formants: Reference formant features
        user_formants: User formant features

    Returns:
        Similarity score (0-100)
    """
    scores = []

    # Compare F1 (mouth openness)
    if ref_formants["f1_mean"] > 0:
        f1_diff = abs(ref_formants["f1_mean"] - user_formants["f1_mean"])
        f1_score = max(0, 100 - (f1_diff / FORMANT_TOLERANCE_HZ * 100))
        scores.append(f1_score)

    # Compare F2 (tongue position)
    if ref_formants["f2_mean"] > 0:
        f2_diff = abs(ref_formants["f2_mean"] - user_formants["f2_mean"])
        f2_score = max(0, 100 - (f2_diff / FORMANT_TOLERANCE_HZ * 100))
        scores.append(f2_score)

    # Compare F3 (overall resonance)
    if ref_formants["f3_mean"] > 0:
        f3_diff = abs(ref_formants["f3_mean"] - user_formants["f3_mean"])
        f3_score = max(0, 100 - (f3_diff / (FORMANT_TOLERANCE_HZ * 1.5) * 100))
        scores.append(f3_score)

    if not scores:
        return 0.0

    # F1 and F2 are most important for vowel quality
    # Weight: F1=40%, F2=40%, F3=20%
    if len(scores) >= 3:
        return scores[0] * 0.4 + scores[1] * 0.4 + scores[2] * 0.2
    elif len(scores) == 2:
        return scores[0] * 0.5 + scores[1] * 0.5
    else:
        return scores[0]


def compare_intensity_patterns(ref_intensity: Dict[str, Any], user_intensity: Dict[str, Any]) -> float:
    """
    Compare intensity patterns for stress and emphasis.

    Args:
        ref_intensity: Reference intensity features
        user_intensity: User intensity features

    Returns:
        Similarity score (0-100)
    """
    if ref_intensity["mean_db"] == 0 or user_intensity["mean_db"] == 0:
        return 0.0

    # Compare mean intensity (overall loudness)
    mean_diff = abs(ref_intensity["mean_db"] - user_intensity["mean_db"])
    mean_score = max(0, 100 - (mean_diff / INTENSITY_TOLERANCE_DB * 33))

    # Compare intensity range (dynamic variation)
    if ref_intensity["range_db"] > 0:
        range_diff_ratio = abs(ref_intensity["range_db"] - user_intensity["range_db"]) / ref_intensity["range_db"]
        range_score = max(0, 100 - (range_diff_ratio * 100))
    else:
        range_score = 100 if user_intensity["range_db"] == 0 else 70

    # Compare contour patterns using DTW
    if len(ref_intensity["contour"]) > 2 and len(user_intensity["contour"]) > 2:
        # Normalize contours
        ref_normalized = [(i - ref_intensity["mean_db"]) / (ref_intensity["std_db"] + 1)
                         for i in ref_intensity["contour"]]
        user_normalized = [(i - user_intensity["mean_db"]) / (user_intensity["std_db"] + 1)
                          for i in user_intensity["contour"]]

        dtw_dist = dtw_distance(ref_normalized, user_normalized)
        contour_score = max(0, 100 - (dtw_dist * 25))
    else:
        contour_score = mean_score

    return (mean_score * 0.4 + range_score * 0.2 + contour_score * 0.4)


def compare_duration_alignment(ref_duration: Dict[str, Any], user_duration: Dict[str, Any]) -> float:
    """
    Compare timing and rhythm.

    Args:
        ref_duration: Reference duration features
        user_duration: User duration features

    Returns:
        Similarity score (0-100)
    """
    if ref_duration["total_duration"] == 0:
        return 0.0

    # Compare total duration
    duration_ratio = user_duration["total_duration"] / ref_duration["total_duration"]
    duration_diff = abs(1.0 - duration_ratio)

    duration_score = max(0, 100 - (duration_diff / DURATION_TOLERANCE_RATIO * 100))

    # Compare speech rate
    if ref_duration["speech_rate"] > 0:
        rate_ratio = user_duration["speech_rate"] / ref_duration["speech_rate"]
        rate_diff = abs(1.0 - rate_ratio)
        rate_score = max(0, 100 - (rate_diff / DURATION_TOLERANCE_RATIO * 100))
    else:
        rate_score = duration_score

    return (duration_score * 0.6 + rate_score * 0.4)


def compare_voice_quality(ref_quality: Dict[str, Any], user_quality: Dict[str, Any]) -> float:
    """
    Compare voice quality metrics.

    Args:
        ref_quality: Reference voice quality features
        user_quality: User voice quality features

    Returns:
        Similarity score (0-100)
    """
    scores = []

    # Compare HNR (harmonicity) - higher is clearer voice
    # Both should be reasonably high (>10 dB is good)
    if ref_quality["mean_hnr"] > 0:
        hnr_diff = abs(ref_quality["mean_hnr"] - user_quality["mean_hnr"])
        hnr_score = max(0, 100 - (hnr_diff / 5 * 25))  # 5 dB difference = 25 point penalty
        scores.append(hnr_score)

    # Compare jitter - lower is better (<1% normal)
    # Give high score if both are low
    jitter_avg = (ref_quality["jitter"] + user_quality["jitter"]) / 2
    if jitter_avg < 0.01:  # Both have good jitter
        scores.append(100)
    else:
        jitter_diff = abs(ref_quality["jitter"] - user_quality["jitter"])
        jitter_score = max(0, 100 - (jitter_diff / 0.01 * 50))
        scores.append(jitter_score)

    # Compare shimmer - lower is better (<3.81% normal)
    shimmer_avg = (ref_quality["shimmer"] + user_quality["shimmer"]) / 2
    if shimmer_avg < 0.0381:  # Both have good shimmer
        scores.append(100)
    else:
        shimmer_diff = abs(ref_quality["shimmer"] - user_quality["shimmer"])
        shimmer_score = max(0, 100 - (shimmer_diff / 0.0381 * 50))
        scores.append(shimmer_score)

    if not scores:
        return 50.0  # Neutral score if no comparisons possible

    return float(np.mean(scores))


def calculate_weighted_score(ref_features: Dict[str, Any], user_features: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate final weighted score from all phonetic features.

    Args:
        ref_features: Reference audio features
        user_features: User audio features

    Returns:
        Dictionary with total score and breakdown
    """
    # Calculate individual feature scores
    pitch_score = compare_pitch_contours(ref_features['pitch'], user_features['pitch'])
    formant_score = compare_formant_trajectories(ref_features['formants'], user_features['formants'])
    intensity_score = compare_intensity_patterns(ref_features['intensity'], user_features['intensity'])
    duration_score = compare_duration_alignment(ref_features['duration'], user_features['duration'])
    voice_quality_score = compare_voice_quality(ref_features['voice_quality'], user_features['voice_quality'])

    # Weighted aggregation
    final_score = (
        pitch_score * FEATURE_WEIGHTS['pitch'] +
        formant_score * FEATURE_WEIGHTS['formants'] +
        intensity_score * FEATURE_WEIGHTS['intensity'] +
        duration_score * FEATURE_WEIGHTS['duration'] +
        voice_quality_score * FEATURE_WEIGHTS['voice_quality']
    )

    # Ensure score is in valid range
    final_score = max(0.0, min(100.0, final_score))

    return {
        'total_score': final_score,
        'breakdown': {
            'pitch': pitch_score,
            'formants': formant_score,
            'intensity': intensity_score,
            'duration': duration_score,
            'voice_quality': voice_quality_score
        }
    }
