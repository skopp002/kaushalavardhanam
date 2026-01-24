"""Speaking Buddy - Streamlit Pronunciation Learning Tool"""
import streamlit as st
import tempfile
from pathlib import Path
from audiorecorder import audiorecorder

from src.reference_manager import ensure_reference_exists
from src.pronunciation_checker import compare_pronunciations
from src.config import USER_RECORDINGS_DIR


# Page configuration
st.set_page_config(
    page_title="Speaking Buddy",
    page_icon="🗣️",
    layout="centered"
)


def initialize_session_state():
    """Initialize session state variables"""
    if 'user_audio_bytes' not in st.session_state:
        st.session_state.user_audio_bytes = None
    if 'user_audio_path' not in st.session_state:
        st.session_state.user_audio_path = None
    if 'comparison_done' not in st.session_state:
        st.session_state.comparison_done = False
    if 'score' not in st.session_state:
        st.session_state.score = None
    if 'feedback' not in st.session_state:
        st.session_state.feedback = None
    if 'insights' not in st.session_state:
        st.session_state.insights = None
    if 'attempt_history' not in st.session_state:
        st.session_state.attempt_history = []


def reset_recording():
    """Reset the recording and comparison state"""
    st.session_state.user_audio_bytes = None
    st.session_state.user_audio_path = None
    st.session_state.comparison_done = False
    # Keep score, feedback, and insights for history
    # Only clear the current attempt data


def main():
    initialize_session_state()

    # Title and header
    st.title("🗣️ Speaking Buddy")
    st.subheader("Pronunciation Practice Tool")

    st.markdown("""
    ### How to use:
    1. Listen to the reference pronunciation
    2. Record your own pronunciation
    3. Compare and get feedback!
    """)

    st.divider()

    # Word display
    st.markdown("### Practice Word: **Moien**")
    st.caption("Luxembourgish greeting meaning 'Hello'")

    st.divider()

    # Reference audio section
    st.markdown("### 📻 Reference Pronunciation")
    st.write("Listen to the correct pronunciation first:")

    try:
        with st.spinner("Loading reference audio..."):
            reference_path = ensure_reference_exists("moien")

        # Display audio player for reference
        with open(reference_path, 'rb') as audio_file:
            st.audio(audio_file.read(), format='audio/ogg')

    except Exception as e:
        st.error(f"Failed to load reference audio: {str(e)}")
        st.stop()

    st.divider()

    # Recording section
    st.markdown("### 🎤 Your Recording")
    st.write("Click the microphone to start recording. Click again to stop.")

    # Audio recorder
    audio_bytes = audiorecorder("Click to record", "Recording...")

    # Handle new recording
    if len(audio_bytes) > 0:
        # Check if this is a new recording
        if st.session_state.user_audio_path is None or audio_bytes != st.session_state.user_audio_bytes:
            st.session_state.user_audio_bytes = audio_bytes
            st.session_state.comparison_done = False

            # Save audio to temporary file
            temp_filepath = USER_RECORDINGS_DIR / f"recording_{id(audio_bytes)}.wav"
            audio_bytes.export(temp_filepath, format="wav")
            st.session_state.user_audio_path = temp_filepath

            st.success("✅ Recording saved!")

    # Display recorded audio
    if st.session_state.user_audio_path and st.session_state.user_audio_path.exists():
        st.write("Your recording:")
        st.audio(str(st.session_state.user_audio_path))

        st.divider()

        # Comparison section
        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("🔍 Compare Pronunciation", type="primary", use_container_width=True):
                with st.spinner("Analyzing your pronunciation..."):
                    try:
                        # Get previous score if available
                        previous_score = st.session_state.score if st.session_state.score else None

                        # Compare with detailed analysis
                        score, feedback, insights = compare_pronunciations(
                            reference_path,
                            st.session_state.user_audio_path,
                            previous_score
                        )

                        # Store results
                        st.session_state.score = score
                        st.session_state.feedback = feedback
                        st.session_state.insights = insights
                        st.session_state.comparison_done = True

                        # Add to attempt history
                        st.session_state.attempt_history.append({
                            "score": score,
                            "insights": insights
                        })

                    except Exception as e:
                        st.error(f"Comparison failed: {str(e)}")

        with col2:
            if st.button("🔄 Try Again", use_container_width=True):
                reset_recording()
                st.rerun()

        # Display results
        if st.session_state.comparison_done and st.session_state.score is not None:
            st.divider()
            st.markdown("### 📊 Results")

            # Score display with color coding
            score = st.session_state.score
            insights = st.session_state.insights

            if score >= 80:
                color = "green"
                emoji = "🎉"
            elif score >= 60:
                color = "blue"
                emoji = "👍"
            elif score >= 40:
                color = "orange"
                emoji = "📚"
            else:
                color = "red"
                emoji = "💪"

            # Large score display
            st.markdown(
                f"<h1 style='text-align: center; color: {color};'>{emoji} {score:.1f}/100</h1>",
                unsafe_allow_html=True
            )

            # Feedback message
            st.info(st.session_state.feedback)

            # Trend analysis (if comparing with previous attempt)
            if insights and "trend" in insights:
                if insights["trend"] == "improving":
                    st.success(f"📈 {insights['trend_message']}")
                elif insights["trend"] == "declining":
                    st.warning(f"📉 {insights['trend_message']}")

                    # Show what went wrong
                    if "decline_reasons" in insights and insights["decline_reasons"]:
                        st.markdown("**What changed:**")
                        for reason in insights["decline_reasons"]:
                            st.markdown(f"- {reason}")
                else:
                    st.info(f"➡️ {insights['trend_message']}")

            # Display improvements and issues
            if insights:
                col1, col2 = st.columns(2)

                with col1:
                    if insights.get("improvements"):
                        st.markdown("**✅ What's Good:**")
                        for improvement in insights["improvements"]:
                            st.markdown(f"- {improvement}")

                with col2:
                    if insights.get("issues"):
                        st.markdown("**⚠️ Areas to Work On:**")
                        issue_labels = {
                            "speaking_too_fast": "Speaking too fast",
                            "speaking_too_slow": "Speaking too slow",
                            "volume_too_low": "Volume too low",
                            "volume_too_high": "Volume too high",
                            "pronunciation_quite_different": "Pronunciation needs work",
                            "pronunciation_somewhat_different": "Pronunciation could be closer"
                        }
                        for issue in insights["issues"]:
                            label = issue_labels.get(issue, issue)
                            st.markdown(f"- {label}")

                # Display actionable suggestions
                if insights.get("suggestions"):
                    st.markdown("---")
                    st.markdown("**💡 Suggestions for Next Attempt:**")
                    for suggestion in insights["suggestions"]:
                        st.markdown(f"- {suggestion}")

            # Attempt history summary
            if len(st.session_state.attempt_history) > 1:
                st.markdown("---")
                st.markdown(f"**📈 Progress: Attempt #{len(st.session_state.attempt_history)}**")

                # Show score progression
                scores = [attempt["score"] for attempt in st.session_state.attempt_history]
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Best Score", f"{max(scores):.1f}")
                with col2:
                    st.metric("Current", f"{scores[-1]:.1f}")
                with col3:
                    avg_score = sum(scores) / len(scores)
                    st.metric("Average", f"{avg_score:.1f}")

            # Encouragement
            st.balloons() if score >= 80 else None

    else:
        st.info("👆 Record your pronunciation to get started!")

    # Footer
    st.divider()
    st.caption("Powered by MFCC + DTW pronunciation analysis")


if __name__ == "__main__":
    main()
