"""Generate actionable phonetic feedback from feature comparisons"""
from typing import Dict, Any, List


def analyze_pitch_issues(ref_pitch: Dict[str, Any], user_pitch: Dict[str, Any], score: float) -> Dict[str, List[str]]:
    """
    Analyze pitch/intonation issues and generate feedback.

    Args:
        ref_pitch: Reference pitch features
        user_pitch: User pitch features
        score: Pitch comparison score

    Returns:
        Dictionary with issues and suggestions
    """
    issues = []
    suggestions = []

    if score >= 80:
        return {"issues": [], "suggestions": []}

    # Check if pitch range is too flat
    if user_pitch["range_f0"] < ref_pitch["range_f0"] * 0.5:
        issues.append("Intonation too flat")
        suggestions.append("Try varying your pitch more - the reference has more melodic variation")

    # Check if pitch range is too varied
    elif user_pitch["range_f0"] > ref_pitch["range_f0"] * 1.5:
        issues.append("Too much pitch variation")
        suggestions.append("Try to keep your intonation more stable, closer to the reference")

    # Check if average pitch is significantly different
    if ref_pitch["mean_f0"] > 0:
        pitch_ratio = user_pitch["mean_f0"] / ref_pitch["mean_f0"]
        if pitch_ratio > 1.3:
            issues.append("Pitch too high overall")
            suggestions.append("Try speaking in a slightly lower pitch range")
        elif pitch_ratio < 0.7:
            issues.append("Pitch too low overall")
            suggestions.append("Try speaking in a slightly higher pitch range")

    return {"issues": issues, "suggestions": suggestions}


def analyze_vowel_quality(ref_formants: Dict[str, Any], user_formants: Dict[str, Any], score: float) -> Dict[str, List[str]]:
    """
    Analyze vowel pronunciation issues.

    Args:
        ref_formants: Reference formant features
        user_formants: User formant features
        score: Formant comparison score

    Returns:
        Dictionary with issues and suggestions
    """
    issues = []
    suggestions = []

    if score >= 80:
        return {"issues": [], "suggestions": []}

    # F1 differences (mouth openness/tongue height)
    if ref_formants["f1_mean"] > 0:
        f1_diff = user_formants["f1_mean"] - ref_formants["f1_mean"]

        if abs(f1_diff) > 150:  # Significant difference
            if f1_diff > 0:
                issues.append("Vowel too open")
                suggestions.append("The vowel sound is too open - try closing your mouth slightly")
            else:
                issues.append("Vowel too closed")
                suggestions.append("The vowel sound is too closed - try opening your mouth more")

    # F2 differences (tongue position front/back)
    if ref_formants["f2_mean"] > 0:
        f2_diff = user_formants["f2_mean"] - ref_formants["f2_mean"]

        if abs(f2_diff) > 200:  # Significant difference
            if f2_diff > 0:
                issues.append("Tongue too far forward")
                suggestions.append("Move your tongue slightly back in your mouth")
            else:
                issues.append("Tongue too far back")
                suggestions.append("Move your tongue slightly forward in your mouth")

    # If both F1 and F2 have issues, provide combined feedback
    if len(issues) == 0 and score < 70:
        issues.append("Vowel quality differs from reference")
        suggestions.append("Listen carefully to the vowel sound and try to match it exactly")

    return {"issues": issues, "suggestions": suggestions}


def analyze_stress_issues(ref_intensity: Dict[str, Any], user_intensity: Dict[str, Any], score: float) -> Dict[str, List[str]]:
    """
    Analyze stress pattern and emphasis issues.

    Args:
        ref_intensity: Reference intensity features
        user_intensity: User intensity features
        score: Intensity comparison score

    Returns:
        Dictionary with issues and suggestions
    """
    issues = []
    suggestions = []

    if score >= 80:
        return {"issues": [], "suggestions": []}

    # Check overall loudness
    db_diff = user_intensity["mean_db"] - ref_intensity["mean_db"]

    if abs(db_diff) > 5:
        if db_diff < 0:
            issues.append("Speaking too quietly")
            suggestions.append("Speak louder or move closer to the microphone")
        else:
            issues.append("Speaking too loudly")
            suggestions.append("Speak more softly or move back from the microphone")

    # Check dynamic range (stress patterns)
    if user_intensity["range_db"] < ref_intensity["range_db"] * 0.6:
        issues.append("Stress pattern too flat")
        suggestions.append("Add more emphasis variation - some syllables should be louder")
    elif user_intensity["range_db"] > ref_intensity["range_db"] * 1.4:
        issues.append("Too much emphasis variation")
        suggestions.append("Keep your emphasis more consistent with the reference")

    return {"issues": issues, "suggestions": suggestions}


def analyze_timing_issues(ref_duration: Dict[str, Any], user_duration: Dict[str, Any], score: float) -> Dict[str, List[str]]:
    """
    Analyze timing and rhythm issues.

    Args:
        ref_duration: Reference duration features
        user_duration: User duration features
        score: Duration comparison score

    Returns:
        Dictionary with issues and suggestions
    """
    issues = []
    suggestions = []

    if score >= 80:
        return {"issues": [], "suggestions": []}

    if ref_duration["total_duration"] > 0:
        duration_ratio = user_duration["total_duration"] / ref_duration["total_duration"]

        if duration_ratio < 0.8:
            issues.append("Speaking too fast")
            percent_diff = int((1 - duration_ratio) * 100)
            suggestions.append(f"You're speaking about {percent_diff}% too fast - slow down to match the reference pace")
        elif duration_ratio > 1.2:
            issues.append("Speaking too slowly")
            percent_diff = int((duration_ratio - 1) * 100)
            suggestions.append(f"You're speaking about {percent_diff}% too slowly - speed up slightly")

    return {"issues": issues, "suggestions": suggestions}


def analyze_voice_clarity(ref_quality: Dict[str, Any], user_quality: Dict[str, Any], score: float) -> Dict[str, List[str]]:
    """
    Analyze voice quality and clarity issues.

    Args:
        ref_quality: Reference voice quality features
        user_quality: User voice quality features
        score: Voice quality comparison score

    Returns:
        Dictionary with issues and suggestions
    """
    issues = []
    suggestions = []

    if score >= 80:
        return {"issues": [], "suggestions": []}

    # Check harmonicity (voice clarity)
    if user_quality["mean_hnr"] < 10:  # Low HNR indicates breathiness or noise
        issues.append("Voice sounds breathy or unclear")
        suggestions.append("Use more vocal support and speak more clearly")

    # Check jitter (pitch stability)
    if user_quality["jitter"] > 0.02:  # >2% is problematic
        issues.append("Pitch instability")
        suggestions.append("Keep your voice more stable - avoid vocal strain")

    # Check shimmer (amplitude stability)
    if user_quality["shimmer"] > 0.05:  # >5% is problematic
        issues.append("Voice volume instability")
        suggestions.append("Maintain steadier vocal volume")

    return {"issues": issues, "suggestions": suggestions}


def generate_phonetic_feedback(ref_features: Dict[str, Any],
                               user_features: Dict[str, Any],
                               scores: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate comprehensive phonetic feedback with actionable suggestions.

    Args:
        ref_features: Reference audio features
        user_features: User audio features
        scores: Score breakdown

    Returns:
        Dictionary with detailed feedback
    """
    all_issues = []
    all_suggestions = []
    improvements = []

    # Analyze each feature if score is not excellent
    breakdown = scores['breakdown']

    # Pitch analysis
    if breakdown['pitch'] >= 80:
        improvements.append("Excellent intonation")
    else:
        pitch_feedback = analyze_pitch_issues(
            ref_features['pitch'],
            user_features['pitch'],
            breakdown['pitch']
        )
        all_issues.extend(pitch_feedback['issues'])
        all_suggestions.extend(pitch_feedback['suggestions'])

    # Vowel quality analysis (most important)
    if breakdown['formants'] >= 80:
        improvements.append("Excellent vowel pronunciation")
    else:
        vowel_feedback = analyze_vowel_quality(
            ref_features['formants'],
            user_features['formants'],
            breakdown['formants']
        )
        all_issues.extend(vowel_feedback['issues'])
        all_suggestions.extend(vowel_feedback['suggestions'])

    # Stress pattern analysis
    if breakdown['intensity'] >= 80:
        improvements.append("Good stress and emphasis")
    else:
        stress_feedback = analyze_stress_issues(
            ref_features['intensity'],
            user_features['intensity'],
            breakdown['intensity']
        )
        all_issues.extend(stress_feedback['issues'])
        all_suggestions.extend(stress_feedback['suggestions'])

    # Timing analysis
    if breakdown['duration'] >= 80:
        improvements.append("Good timing and pace")
    else:
        timing_feedback = analyze_timing_issues(
            ref_features['duration'],
            user_features['duration'],
            breakdown['duration']
        )
        all_issues.extend(timing_feedback['issues'])
        all_suggestions.extend(timing_feedback['suggestions'])

    # Voice quality analysis
    if breakdown['voice_quality'] >= 80:
        improvements.append("Clear voice quality")
    else:
        clarity_feedback = analyze_voice_clarity(
            ref_features['voice_quality'],
            user_features['voice_quality'],
            breakdown['voice_quality']
        )
        all_issues.extend(clarity_feedback['issues'])
        all_suggestions.extend(clarity_feedback['suggestions'])

    return {
        'improvements': improvements,
        'issues': all_issues,
        'suggestions': all_suggestions,
        'feature_breakdown': breakdown
    }
