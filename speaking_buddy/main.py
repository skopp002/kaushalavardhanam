"""Speaking Buddy - Streamlit Pronunciation Learning Tool with User Authentication"""
import streamlit as st
from pathlib import Path
from audiorecorder import audiorecorder
from datetime import datetime

from src.reference_manager import ensure_reference_exists
from src.pronunciation_checker import compare_pronunciations_praat
from src.session_manager import SessionManager
from src.config import USER_RECORDINGS_DIR, MAX_ATTEMPTS_PER_WORD
from src import database


# Page configuration
st.set_page_config(
    page_title="Speaking Buddy",
    page_icon="🗣️",
    layout="centered"
)


def initialize_session_state():
    """Initialize session state variables"""
    # Authentication state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    if 'show_page' not in st.session_state:
        st.session_state.show_page = 'login'  # 'login', 'signup', 'dashboard', 'practice', 'history'

    # Session manager - only if logged in
    if st.session_state.logged_in and 'session_manager' not in st.session_state:
        user_id = st.session_state.user['id'] if st.session_state.user else None
        st.session_state.session_manager = SessionManager(user_id=user_id)

    # Recording state
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


def logout():
    """Log out user and clear session"""
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.show_page = 'login'
    # Clear session manager
    if 'session_manager' in st.session_state:
        del st.session_state.session_manager
    # Clear recording state
    st.session_state.user_audio_bytes = None
    st.session_state.user_audio_path = None
    st.session_state.comparison_done = False


def render_login_page():
    """Render login page"""
    st.title("🗣️ Speaking Buddy")
    st.subheader("Login to Your Account")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Login", use_container_width=True, type="primary")
        with col2:
            signup_link = st.form_submit_button("Create Account", use_container_width=True)

        if submit:
            if not username or not password:
                st.error("Please enter both username and password")
            else:
                user = database.authenticate_user(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user = user
                    st.session_state.show_page = 'dashboard'
                    st.success(f"Welcome back, {user['username']}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

        if signup_link:
            st.session_state.show_page = 'signup'
            st.rerun()

    st.divider()
    st.caption("Practice Luxembourgish pronunciation with AI-powered feedback")


def render_signup_page():
    """Render signup page"""
    st.title("🗣️ Speaking Buddy")
    st.subheader("Create Your Account")

    with st.form("signup_form"):
        username = st.text_input("Username", help="Choose a unique username")
        email = st.text_input("Email", help="We'll never share your email")
        password = st.text_input("Password", type="password", help="Choose a strong password")
        password_confirm = st.text_input("Confirm Password", type="password")

        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Sign Up", use_container_width=True, type="primary")
        with col2:
            back = st.form_submit_button("Back to Login", use_container_width=True)

        if submit:
            # Validation
            if not username or not email or not password:
                st.error("Please fill in all fields")
            elif password != password_confirm:
                st.error("Passwords do not match")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters")
            elif "@" not in email:
                st.error("Please enter a valid email address")
            else:
                # Create user
                user_id = database.create_user(username, email, password)
                if user_id:
                    st.success("Account created successfully! Please login.")
                    st.session_state.show_page = 'login'
                    st.rerun()
                else:
                    st.error("Username or email already exists. Please try different credentials.")

        if back:
            st.session_state.show_page = 'login'
            st.rerun()


def render_user_menu():
    """Render user menu in sidebar"""
    if not st.session_state.logged_in:
        return

    with st.sidebar:
        st.title(f"👤 {st.session_state.user['username']}")

        # Navigation
        st.subheader("Navigation")

        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state.show_page = 'dashboard'
            st.rerun()

        if st.button("🗣️ Practice Session", use_container_width=True):
            st.session_state.show_page = 'practice'
            # Create new session manager if needed
            if 'session_manager' not in st.session_state or st.session_state.session_manager.is_session_complete():
                st.session_state.session_manager = SessionManager(user_id=st.session_state.user['id'])
            st.rerun()

        if st.button("📚 Session History", use_container_width=True):
            st.session_state.show_page = 'history'
            st.rerun()

        st.divider()

        if st.button("🚪 Logout", use_container_width=True):
            logout()
            st.rerun()


def render_dashboard():
    """Render user dashboard with statistics"""
    st.title("📊 Your Dashboard")

    # Get user stats
    user_stats = database.get_user_stats(st.session_state.user['id'])

    # Overall statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sessions", user_stats.get('completed_sessions', 0))
    with col2:
        st.metric("Words Practiced", user_stats.get('total_words_practiced', 0))
    with col3:
        st.metric("Average Score", f"{user_stats.get('average_overall_score', 0):.1f}/100")
    with col4:
        st.metric("Best Session", f"{user_stats.get('best_session_score', 0):.1f}/100")

    st.divider()

    # Recent sessions
    st.subheader("📈 Recent Sessions")
    recent_sessions = database.get_user_sessions(st.session_state.user['id'], limit=5)

    if recent_sessions:
        for session in recent_sessions:
            with st.expander(
                f"Session on {session['completed_at'][:16]} - Score: {session['overall_score']:.1f}/100"
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Words:** {session['total_words']}")
                with col2:
                    st.write(f"**Attempts:** {session['total_attempts']}")
                with col3:
                    st.write(f"**Average:** {session['average_score']:.1f}/100")

                # Score distribution
                st.write("**Performance:**")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write(f"🎉 {session['excellent_count']}")
                with col2:
                    st.write(f"👍 {session['good_count']}")
                with col3:
                    st.write(f"📚 {session['fair_count']}")
                with col4:
                    st.write(f"💪 {session['poor_count']}")
    else:
        st.info("No sessions completed yet. Start practicing to see your progress!")

    st.divider()

    # Category performance
    st.subheader("🎯 Performance by Category")
    category_stats = database.get_category_stats(st.session_state.user['id'])

    if category_stats:
        for category, stats in category_stats.items():
            with st.expander(f"**{category.capitalize()}** - Avg: {stats['average_score']:.1f}/100"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"Words: {stats['words_practiced']}")
                with col2:
                    st.write(f"Best: {stats['best_score']:.1f}")
                with col3:
                    st.write(f"Attempts: {stats['total_attempts']}")
    else:
        st.info("Complete practice sessions to see category performance.")

    st.divider()

    # Quick action buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗣️ Start New Practice Session", use_container_width=True, type="primary"):
            st.session_state.show_page = 'practice'
            st.session_state.session_manager = SessionManager(user_id=st.session_state.user['id'])
            st.rerun()
    with col2:
        if st.button("📚 View All Sessions", use_container_width=True):
            st.session_state.show_page = 'history'
            st.rerun()


def render_session_history():
    """Render session history page"""
    st.title("📚 Session History")

    # Get all sessions
    sessions = database.get_user_sessions(st.session_state.user['id'], limit=20)

    if not sessions:
        st.info("No session history yet. Complete your first practice session!")
        if st.button("🗣️ Start Practicing", use_container_width=True, type="primary"):
            st.session_state.show_page = 'practice'
            st.session_state.session_manager = SessionManager(user_id=st.session_state.user['id'])
            st.rerun()
        return

    # Filter options
    st.subheader("Filters")
    show_count = st.slider("Number of sessions to show", 5, 50, 20)

    st.divider()

    # Display sessions
    for i, session in enumerate(sessions[:show_count], 1):
        with st.expander(
            f"#{i} - {session['completed_at'][:16]} | Score: {session['overall_score']:.1f}/100 | {session['total_words']} words"
        ):
            # Basic stats
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Overall Score", f"{session['overall_score']:.1f}/100")
            with col2:
                st.metric("Words", session['total_words'])
            with col3:
                st.metric("Attempts", session['total_attempts'])
            with col4:
                st.metric("Average", f"{session['average_score']:.1f}/100")

            # Performance breakdown
            st.write("**Score Distribution:**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.write(f"🎉 Excellent: {session['excellent_count']}")
            with col2:
                st.write(f"👍 Good: {session['good_count']}")
            with col3:
                st.write(f"📚 Fair: {session['fair_count']}")
            with col4:
                st.write(f"💪 Needs Work: {session['poor_count']}")

            # Detailed view button
            if st.button(f"View Detailed Results", key=f"detail_{session['id']}"):
                st.session_state.show_session_detail = session['id']
                st.rerun()

    # Show session detail if requested
    if 'show_session_detail' in st.session_state and st.session_state.show_session_detail:
        show_session_detail(st.session_state.show_session_detail)


def show_session_detail(session_id: int):
    """Show detailed session results"""
    session = database.get_session_details(session_id)

    st.divider()
    st.subheader(f"📋 Detailed Results - Session {session_id}")

    # Group attempts by word
    words_data = {}
    for attempt in session['attempts']:
        word = attempt['word']
        if word not in words_data:
            words_data[word] = {
                'translation': attempt['translation'],
                'category': attempt['category'],
                'attempts': []
            }
        words_data[word]['attempts'].append(attempt)

    # Display each word
    for word, data in words_data.items():
        best_score = max(att['score'] for att in data['attempts'])
        with st.expander(f"**{word}** ({data['translation']}) - Best: {best_score:.1f}/100"):
            st.write(f"**Category:** {data['category']}")
            st.write(f"**Total Attempts:** {len(data['attempts'])}")

            for i, attempt in enumerate(data['attempts'], 1):
                st.write(f"**Attempt {i}:** {attempt['score']:.1f}/100")
                if attempt.get('insights') and attempt['insights'].get('suggestions'):
                    st.write("Suggestions:")
                    for sug in attempt['insights']['suggestions'][:2]:
                        st.write(f"  - {sug}")

    if st.button("Close Details"):
        del st.session_state.show_session_detail
        st.rerun()


def reset_recording():
    """Reset the recording and comparison state for new attempt"""
    st.session_state.user_audio_bytes = None
    st.session_state.user_audio_path = None
    st.session_state.comparison_done = False


def move_to_next_word():
    """Move to the next word and reset recording state"""
    st.session_state.session_manager.move_to_next_word()
    reset_recording()
    st.session_state.score = None
    st.session_state.feedback = None
    st.session_state.insights = None


def render_final_summary():
    """Render the final session summary page"""
    st.title("🎉 Session Complete!")

    summary = st.session_state.session_manager.get_session_summary()

    # Overall performance
    st.markdown("## 📊 Overall Performance")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Overall Score", f"{summary['overall_score']:.1f}/100")
    with col2:
        st.metric("Total Words", summary['total_words'])
    with col3:
        st.metric("Best Score", f"{summary['best_score']:.1f}")
    with col4:
        st.metric("Total Attempts", summary['total_attempts'])

    st.divider()

    # Score distribution
    st.markdown("## 📈 Score Distribution")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎉 Excellent (80+)", summary['excellent_count'])
    with col2:
        st.metric("👍 Good (60-79)", summary['good_count'])
    with col3:
        st.metric("📚 Fair (40-59)", summary['fair_count'])
    with col4:
        st.metric("💪 Needs Work (<40)", summary['poor_count'])

    st.divider()

    # Category performance
    st.markdown("## 🎯 Performance by Category")
    for category, stats in summary['category_performance'].items():
        with st.expander(f"**{category.capitalize()}** - Avg: {stats['average']:.1f}/100 ({stats['count']} words)"):
            category_words = [
                (word, data) for word, data in summary['word_results'].items()
                if data['category'] == category
            ]
            for word, data in sorted(category_words, key=lambda x: x[1]['best_score'], reverse=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{word}** ({data['translation']})")
                with col2:
                    score = data['best_score']
                    color = "green" if score >= 80 else "blue" if score >= 60 else "orange" if score >= 40 else "red"
                    st.markdown(f"<span style='color: {color};'>{score:.1f}/100</span>", unsafe_allow_html=True)

    st.divider()

    # Top performers
    st.markdown("## 🏆 Top Performers")
    word_scores = [(word, data['best_score'], data['translation'])
                   for word, data in summary['word_results'].items()]
    top_words = sorted(word_scores, key=lambda x: x[1], reverse=True)[:5]

    for i, (word, score, translation) in enumerate(top_words, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "⭐"
        st.write(f"{emoji} **{word}** ({translation}): {score:.1f}/100")

    st.divider()

    # Action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 Start New Session", use_container_width=True, type="primary"):
            st.session_state.session_manager = SessionManager(user_id=st.session_state.user['id'])
            st.session_state.show_page = 'practice'
            reset_recording()
            st.rerun()

    with col2:
        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state.show_page = 'dashboard'
            del st.session_state.session_manager
            st.rerun()

    with col3:
        if st.button("📚 History", use_container_width=True):
            st.session_state.show_page = 'history'
            del st.session_state.session_manager
            st.rerun()


def render_practice_word():
    """Render the practice interface for current word"""
    session_mgr = st.session_state.session_manager
    current_word_info = session_mgr.get_current_word_info()

    if current_word_info is None:
        return

    current_word = current_word_info['word']

    # Title and progress
    st.title("🗣️ Speaking Buddy")
    st.subheader("Pronunciation Practice")

    # Progress bar
    progress = session_mgr.get_progress()
    st.progress(progress['percentage'] / 100)
    st.write(f"**Progress:** Word {progress['current_index'] + 1} of {progress['total_words']}")

    st.divider()

    # Current word display
    st.markdown(f"### Practice Word: **{current_word}**")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.caption(f"English: {current_word_info['translation']}")
    with col2:
        st.caption(f"Category: {current_word_info['category']}")

    # Attempt counter
    attempts = current_word_info['attempts_so_far']
    st.write(f"**Attempts:** {attempts}/{MAX_ATTEMPTS_PER_WORD}")

    st.divider()

    # Reference audio section
    st.markdown("### 📻 Reference Pronunciation")
    st.write("Listen to the correct pronunciation:")

    try:
        with st.spinner("Loading reference audio..."):
            reference_path = ensure_reference_exists(current_word)

        # Display audio player
        with open(reference_path, 'rb') as audio_file:
            st.audio(audio_file.read(), format='audio/wav')

    except Exception as e:
        st.error(f"Failed to load reference audio: {str(e)}")
        st.info("Audio not available for this word yet. You can skip to the next word.")

        if st.button("⏭️ Skip to Next Word"):
            move_to_next_word()
            st.rerun()
        return

    st.divider()

    # Recording section
    st.markdown("### 🎤 Your Recording")
    st.write("Click the microphone to start recording. Click again to stop.")

    # Audio recorder
    audio_bytes = audiorecorder("Click to record", "Recording...")

    # Handle new recording
    if len(audio_bytes) > 0:
        if st.session_state.user_audio_path is None or audio_bytes != st.session_state.user_audio_bytes:
            st.session_state.user_audio_bytes = audio_bytes
            st.session_state.comparison_done = False

            # Save audio
            temp_filepath = USER_RECORDINGS_DIR / f"recording_{current_word}_{id(audio_bytes)}.wav"
            audio_bytes.export(temp_filepath, format="wav")
            st.session_state.user_audio_path = temp_filepath

            st.success("✅ Recording saved!")

    # Display recorded audio
    if st.session_state.user_audio_path and st.session_state.user_audio_path.exists():
        st.write("Your recording:")
        st.audio(str(st.session_state.user_audio_path))

        st.divider()

        # Action buttons
        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("🔍 Compare Pronunciation", type="primary", use_container_width=True):
                with st.spinner("Analyzing your pronunciation..."):
                    try:
                        # Get previous attempts for trend analysis
                        previous_attempts = session_mgr.get_attempts_for_current_word()
                        previous_score = previous_attempts[-1]["score"] if previous_attempts else None

                        # Compare pronunciations
                        score, feedback, insights = compare_pronunciations_praat(
                            reference_path,
                            st.session_state.user_audio_path,
                            previous_score
                        )

                        # Store results
                        st.session_state.score = score
                        st.session_state.feedback = feedback
                        st.session_state.insights = insights
                        st.session_state.comparison_done = True

                        # Record in session manager (will save to database)
                        session_mgr.record_attempt(current_word, score, feedback, insights)

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

            score = st.session_state.score
            insights = st.session_state.insights

            # Score display
            if score >= 80:
                color, emoji = "green", "🎉"
            elif score >= 60:
                color, emoji = "blue", "👍"
            elif score >= 40:
                color, emoji = "orange", "📚"
            else:
                color, emoji = "red", "💪"

            st.markdown(
                f"<h1 style='text-align: center; color: {color};'>{emoji} {score:.1f}/100</h1>",
                unsafe_allow_html=True
            )

            st.info(st.session_state.feedback)

            # Trend analysis
            if insights and "trend" in insights:
                if insights["trend"] == "improving":
                    st.success(f"📈 {insights['trend_message']}")
                elif insights["trend"] == "declining":
                    st.warning(f"📉 {insights['trend_message']}")
                    if "decline_reasons" in insights:
                        for reason in insights["decline_reasons"]:
                            st.markdown(f"- {reason}")
                else:
                    st.info(f"➡️ {insights['trend_message']}")

            # Feature breakdown
            if insights and "breakdown" in insights:
                st.markdown("---")
                st.markdown("**🎯 Phonetic Feature Scores:**")

                breakdown = insights["breakdown"]
                feature_labels = {
                    "pitch": "🎵 Intonation",
                    "formants": "🗣️ Vowel Quality",
                    "intensity": "💪 Stress Patterns",
                    "duration": "⏱️ Timing/Rhythm",
                    "voice_quality": "✨ Voice Clarity"
                }

                for feature, label in feature_labels.items():
                    if feature in breakdown:
                        feature_score = breakdown[feature]
                        st.markdown(f"{label}: {feature_score:.1f}/100")
                        st.progress(feature_score / 100)

            # Improvements and issues
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
                        for issue in insights["issues"]:
                            st.markdown(f"- {issue}")

                # Suggestions
                if insights.get("suggestions"):
                    st.markdown("---")
                    st.markdown("**💡 Suggestions:**")
                    for suggestion in insights["suggestions"]:
                        st.markdown(f"- {suggestion}")

            # Next word button
            st.divider()

            if session_mgr.can_move_to_next_word(current_word):
                if attempts >= MAX_ATTEMPTS_PER_WORD:
                    st.warning(f"You've reached the maximum of {MAX_ATTEMPTS_PER_WORD} attempts for this word.")

                if st.button("⏭️ Next Word", use_container_width=True, type="primary"):
                    move_to_next_word()
                    st.rerun()
            else:
                st.info("Complete at least one attempt before moving to the next word.")

    else:
        st.info("👆 Record your pronunciation to get started!")

    # Footer
    st.divider()
    st.caption("Powered by Praat phonetic analysis | Progress saved automatically")


def main():
    initialize_session_state()

    # Show appropriate page based on authentication state
    if not st.session_state.logged_in:
        if st.session_state.show_page == 'signup':
            render_signup_page()
        else:
            render_login_page()
    else:
        # Show user menu in sidebar
        render_user_menu()

        # Show main content based on selected page
        if st.session_state.show_page == 'dashboard':
            render_dashboard()
        elif st.session_state.show_page == 'history':
            render_session_history()
        elif st.session_state.show_page == 'practice':
            # Check if session is complete
            if 'session_manager' in st.session_state and st.session_state.session_manager.is_session_complete():
                render_final_summary()
            else:
                render_practice_word()
        else:
            # Default to dashboard
            render_dashboard()


if __name__ == "__main__":
    main()
