"""Praat-based phonetic feature extraction using Parselmouth"""
import numpy as np
import parselmouth
from parselmouth.praat import call
from pathlib import Path
from typing import Dict, Any, List


# Praat analysis parameters
PITCH_FLOOR = 75  # Hz, typical male lower bound
PITCH_CEILING = 300  # Hz, typical female upper bound
TIME_STEP = 0.01  # seconds
MAX_FORMANT_HZ = 5500  # Hz, suitable for adult speech
NUM_FORMANTS = 5  # Extract F1-F5, use F1-F3 primarily


def load_sound(audio_path: Path) -> parselmouth.Sound:
    """
    Load audio file as Parselmouth Sound object.

    Args:
        audio_path: Path to audio file

    Returns:
        Parselmouth Sound object
    """
    return parselmouth.Sound(str(audio_path))


def extract_pitch_features(sound: parselmouth.Sound) -> Dict[str, Any]:
    """
    Extract pitch (F0) related features for intonation analysis.

    Args:
        sound: Parselmouth Sound object

    Returns:
        Dictionary with pitch features
    """
    pitch = sound.to_pitch(
        time_step=TIME_STEP,
        pitch_floor=PITCH_FLOOR,
        pitch_ceiling=PITCH_CEILING
    )

    # Extract pitch values at regular intervals
    pitch_values = []
    for t in pitch.ts():
        value = pitch.get_value_at_time(t)
        if not np.isnan(value) and value > 0:
            pitch_values.append(value)

    if not pitch_values:
        # No voiced segments found
        return {
            "mean_f0": 0,
            "std_f0": 0,
            "min_f0": 0,
            "max_f0": 0,
            "range_f0": 0,
            "contour": [],
            "voiced_fraction": 0
        }

    return {
        "mean_f0": float(np.mean(pitch_values)),
        "std_f0": float(np.std(pitch_values)),
        "min_f0": float(np.min(pitch_values)),
        "max_f0": float(np.max(pitch_values)),
        "range_f0": float(np.max(pitch_values) - np.min(pitch_values)),
        "contour": pitch_values,  # For DTW comparison
        "voiced_fraction": len(pitch_values) / len(pitch.ts())
    }


def extract_formant_features(sound: parselmouth.Sound) -> Dict[str, Any]:
    """
    Extract formant trajectories for vowel quality analysis.

    Args:
        sound: Parselmouth Sound object

    Returns:
        Dictionary with formant features (F1, F2, F3)
    """
    formants = sound.to_formant_burg(
        time_step=TIME_STEP,
        max_number_of_formants=NUM_FORMANTS,
        maximum_formant=MAX_FORMANT_HZ
    )

    # Sample at regular intervals
    times = np.arange(sound.start_time, sound.end_time, TIME_STEP)

    f1_values = []
    f2_values = []
    f3_values = []

    for t in times:
        f1 = formants.get_value_at_time(1, t)
        f2 = formants.get_value_at_time(2, t)
        f3 = formants.get_value_at_time(3, t)

        if not np.isnan(f1) and f1 > 0:
            f1_values.append(f1)
        if not np.isnan(f2) and f2 > 0:
            f2_values.append(f2)
        if not np.isnan(f3) and f3 > 0:
            f3_values.append(f3)

    # Handle case where no formants detected
    if not f1_values:
        f1_values = [0]
    if not f2_values:
        f2_values = [0]
    if not f3_values:
        f3_values = [0]

    return {
        "f1_mean": float(np.mean(f1_values)),
        "f1_std": float(np.std(f1_values)),
        "f1_trajectory": f1_values,
        "f2_mean": float(np.mean(f2_values)),
        "f2_std": float(np.std(f2_values)),
        "f2_trajectory": f2_values,
        "f3_mean": float(np.mean(f3_values)),
        "f3_std": float(np.std(f3_values)),
        "f3_trajectory": f3_values,
    }


def extract_intensity_features(sound: parselmouth.Sound) -> Dict[str, Any]:
    """
    Extract intensity patterns for stress and emphasis analysis.

    Args:
        sound: Parselmouth Sound object

    Returns:
        Dictionary with intensity features
    """
    intensity = sound.to_intensity(
        time_step=TIME_STEP,
        minimum_pitch=PITCH_FLOOR
    )

    intensity_values = [intensity.get_value(t) for t in intensity.xs()]

    # Filter out undefined values
    intensity_values = [v for v in intensity_values if not np.isnan(v)]

    if not intensity_values:
        return {
            "mean_db": 0,
            "std_db": 0,
            "max_db": 0,
            "range_db": 0,
            "contour": []
        }

    return {
        "mean_db": float(np.mean(intensity_values)),
        "std_db": float(np.std(intensity_values)),
        "max_db": float(np.max(intensity_values)),
        "range_db": float(np.max(intensity_values) - np.min(intensity_values)),
        "contour": intensity_values,
    }


def extract_duration_features(sound: parselmouth.Sound) -> Dict[str, Any]:
    """
    Extract timing and rhythm features.

    Args:
        sound: Parselmouth Sound object

    Returns:
        Dictionary with duration features
    """
    duration = sound.get_total_duration()

    # Get voiced segments using pitch
    pitch = sound.to_pitch(
        pitch_floor=PITCH_FLOOR,
        pitch_ceiling=PITCH_CEILING
    )

    voiced_frames = sum(1 for t in pitch.ts()
                       if not np.isnan(pitch.get_value_at_time(t)) and
                       pitch.get_value_at_time(t) > 0)
    total_frames = len(pitch.ts())

    if total_frames == 0:
        total_frames = 1  # Avoid division by zero

    return {
        "total_duration": float(duration),
        "voiced_duration": float(voiced_frames / total_frames * duration),
        "speech_rate": float(voiced_frames / duration if duration > 0 else 0),
        "pause_ratio": float(1 - (voiced_frames / total_frames))
    }


def extract_voice_quality_features(sound: parselmouth.Sound) -> Dict[str, Any]:
    """
    Extract voice quality metrics (harmonicity, jitter, shimmer).

    Args:
        sound: Parselmouth Sound object

    Returns:
        Dictionary with voice quality features
    """
    # Harmonicity (HNR - Harmonics-to-Noise Ratio)
    harmonicity = sound.to_harmonicity(time_step=TIME_STEP)
    hnr_values = [harmonicity.get_value(t) for t in harmonicity.xs()]
    hnr_values = [v for v in hnr_values if not np.isnan(v)]

    if not hnr_values:
        hnr_values = [0]

    try:
        # Point process for jitter/shimmer
        point_process = call(sound, "To PointProcess (periodic, cc)",
                            PITCH_FLOOR, PITCH_CEILING)

        # Jitter (pitch period variability) - lower is better
        jitter = call(point_process, "Get jitter (local)",
                     0, 0, 0.0001, 0.02, 1.3)

        # Shimmer (amplitude variability) - lower is better
        shimmer = call([sound, point_process], "Get shimmer (local)",
                      0, 0, 0.0001, 0.02, 1.3, 1.6)
    except Exception:
        # If point process fails (too short audio, etc.)
        jitter = 0
        shimmer = 0

    return {
        "mean_hnr": float(np.mean(hnr_values)),
        "std_hnr": float(np.std(hnr_values)),
        "jitter": float(jitter),  # < 1% normal
        "shimmer": float(shimmer),  # < 3.81% normal
    }


def extract_all_praat_features(audio_path: Path) -> Dict[str, Any]:
    """
    Extract all Praat-based phonetic features from an audio file.

    Args:
        audio_path: Path to audio file

    Returns:
        Dictionary with all extracted features
    """
    sound = load_sound(audio_path)

    return {
        "pitch": extract_pitch_features(sound),
        "formants": extract_formant_features(sound),
        "intensity": extract_intensity_features(sound),
        "duration": extract_duration_features(sound),
        "voice_quality": extract_voice_quality_features(sound),
    }
