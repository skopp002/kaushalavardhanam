"""Table-driven state machine tests (DESIGN §3, §9): FakeReachy + canned agent."""

import json
import time

from mitra.agent import prompts
from mitra.orchestrator import Event, Orchestrator, State

SA_REPLY = "मम नाम मित्रम्।"
EN_REPLY = "My name is Mitra, nice to meet you."


def test_wake_from_asleep_nods_and_greets(make_orchestrator, fake_robot, fake_tts):
    orch, _ = make_orchestrator()
    orch.handle_event(Event("wake"))
    assert orch.state == State.WAKING
    assert fake_robot.nods == 1
    assert fake_tts.spoken == [prompts.GREETING]
    orch.handle_event(Event("playback_done"))
    assert orch.state == State.LISTENING


def test_utterance_flows_to_spoken_reply(make_orchestrator, fake_tts):
    orch, agent = make_orchestrator(replies=[SA_REPLY])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    assert orch.state == State.SPEAKING
    assert agent.calls == ["[lang=en] What is your name?"]
    assert fake_tts.spoken == [SA_REPLY]
    orch.handle_event(Event("playback_done"))
    assert orch.state == State.LISTENING


def test_shloka_request_bypasses_the_model(make_orchestrator, fake_tts):
    """Recitation is deterministic (DESIGN §1.4): the corpus answers, not Qwen."""
    from mitra.lexicon.shlokas import Shlokas

    class OneVerse(Shlokas):
        def __init__(self):
            self._rows = [{
                "source_slug": "mahabharatam", "verse_id": "6.70.36",
                "verse_text": "पाण्डवानां कुरूणां च । ते सेने ययतुः स्वं निवेशनम्",
                "attribution": "इति महाभारते भीष्मपर्वणि॥",
            }]
            self._recent = []

        def pick(self):
            return self._rows[0]

        def reset(self):
            pass

    orch, agent = make_orchestrator(shlokas=OneVerse())
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Recite a shloka"))

    assert agent.calls == []                       # the model was never asked
    assert orch.state == State.SPEAKING
    # Spoken in chunks so the dandas can become silence, ending on the colophon.
    assert fake_tts.spoken[0] == "पाण्डवानां कुरूणां च"
    assert fake_tts.spoken[-1] == "इति महाभारते भीष्मपर्वणि"


def test_shloka_request_falls_through_without_a_corpus(make_orchestrator, fake_tts):
    """No corpus == feature absent: the model answers, as it did before."""
    orch, agent = make_orchestrator(replies=[SA_REPLY])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Recite a shloka"))
    assert len(agent.calls) == 1
    assert fake_tts.spoken == [SA_REPLY]


def test_invalid_reply_retries_with_corrective_suffix(make_orchestrator, fake_tts):
    orch, agent = make_orchestrator(replies=[EN_REPLY, SA_REPLY])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "hello"))
    assert len(agent.calls) == 2
    assert agent.calls[1].endswith(prompts.CORRECTIVE_SUFFIX)
    assert fake_tts.spoken == [SA_REPLY]


def test_double_failure_speaks_safe_fallback(make_orchestrator, fake_tts):
    orch, _ = make_orchestrator(replies=[EN_REPLY, EN_REPLY])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "hello"))
    assert fake_tts.spoken == [prompts.SAFE_FALLBACK]


def test_verified_lexicon_overrides_generated_name(make_orchestrator, fake_tts):
    # "apple" is seeded verified as सेवफलम्; the model generated a wrong name.
    vision_json = ('{"object_en": "apple", "name_sa_devanagari": "फलराजम्", '
                   '"name_iast": "phalarājam", "sentence_sa": "एतत् फलराजम् अस्ति।"}')
    orch, _ = make_orchestrator(replies=[vision_json])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "किम् एतत्?"))
    assert fake_tts.spoken == ["एतत् सेवफलम् अस्ति।"]


def test_new_object_recorded_unverified(make_orchestrator, fake_tts, lexicon):
    vision_json = ('{"object_en": "croissant", "name_sa_devanagari": "क्रुसाण्टम्", '
                   '"name_iast": "krusāṇṭam", "sentence_sa": "एतत् क्रुसाण्टम् अस्ति।"}')
    orch, _ = make_orchestrator(replies=[vision_json])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "what is this?"))
    assert fake_tts.spoken == ["एतत् क्रुसाण्टम् अस्ति।"]
    row = lexicon.lookup("croissant")
    assert row is not None and row["verified"] == 0


def test_end_session_speaks_farewell_then_sleeps(make_orchestrator, fake_tts):
    orch, agent = make_orchestrator(replies=["session_end"])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "goodbye"))
    assert orch.state == State.SPEAKING
    assert fake_tts.spoken == [prompts.FAREWELL]
    orch.handle_event(Event("playback_done"))
    assert orch.state == State.ASLEEP
    assert agent.resets == 1


# ------------------------------------------------- follow-ups (FR-3.12)

def _followups(*questions, continuations=()):
    """A Followups over just these questions, drawn in order.

    No continuation questions unless a test asks for them, so a test about
    topic choice is not answered with "tell me more".
    """
    import random

    from mitra.agent.followups import Followups

    class InOrder(random.Random):
        def choice(self, seq):
            return seq[0]

    rows = [{"question": q, "iast": q, "english": q, "topics": (), "keywords": ()}
            for q in questions]
    return Followups(rows=rows, rng=InOrder(), continuations=continuations)


FOLLOWUP = "तव नाम किम्?"


def test_reply_ends_with_a_question_back(make_orchestrator, fake_tts):
    """Every turn invites the next one (FR-3.12)."""
    orch, _ = make_orchestrator(replies=[SA_REPLY], followups=_followups(FOLLOWUP))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    assert fake_tts.spoken == [f"{SA_REPLY} {FOLLOWUP}"]


def test_the_greeting_opens_the_conversation(make_orchestrator, fake_tts):
    orch, _ = make_orchestrator(followups=_followups(FOLLOWUP))
    orch.handle_event(Event("wake"))
    assert fake_tts.spoken == [f"{prompts.GREETING}। {FOLLOWUP}"]


def test_the_next_turn_tells_the_model_what_was_asked(make_orchestrator):
    """Without this the model answers "Ravi" with no idea what it asked."""
    second = "त्वं कथम् असि?"
    orch, agent = make_orchestrator(replies=[SA_REPLY, "स्वागतं रवि!"],
                                    followups=_followups(FOLLOWUP, second))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "Ravi"))

    assert agent.calls[1].startswith(
        prompts.ASKED_HEADER.format(question=FOLLOWUP))
    # Consumed, not sticky: each turn carries the question just asked, never
    # the one the user already answered.
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "I am eight"))
    assert agent.calls[2].startswith(
        prompts.ASKED_HEADER.format(question=second))
    assert FOLLOWUP not in agent.calls[2]


def test_no_question_is_appended_when_the_model_already_asked_one(
        make_orchestrator, fake_tts):
    asked = "भवतः नाम किम्?"
    orch, _ = make_orchestrator(replies=[asked], followups=_followups(FOLLOWUP))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "hello"))
    assert fake_tts.spoken == [asked]


def test_the_farewell_does_not_invite_a_reply(make_orchestrator, fake_tts):
    orch, _ = make_orchestrator(replies=["session_end"],
                                followups=_followups(FOLLOWUP))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "goodbye"))
    assert fake_tts.spoken == [prompts.FAREWELL]


def test_an_unintelligible_turn_is_not_given_a_second_question(
        make_orchestrator, fake_tts):
    orch, agent = make_orchestrator(followups=_followups(FOLLOWUP))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Thank you."))   # ASR hallucination
    assert agent.calls == []
    assert fake_tts.spoken == [prompts.APOLOGY_RETRY]


def test_mitra_does_not_ask_what_the_user_just_told_it(make_orchestrator, fake_tts):
    """The turn drives the follow-up memory, not just the pick (FR-3.12)."""
    import random

    from mitra.agent.followups import ROWS, Followups

    food, study = "तव प्रियं भोजनं किम्?", "त्वं किं पठसि?"
    rows = [r for r in ROWS if r["question"] in (food, study)]
    orch, _ = make_orchestrator(
        replies=[SA_REPLY],
        followups=Followups(rows=rows, rng=random.Random(0), continuations=()))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "My favourite food is milk."))
    assert fake_tts.spoken == [f"{SA_REPLY} {study}"]


def test_a_fragment_answer_gets_no_phrasebook_rows(make_orchestrator):
    """"at home." matched *Are all well at home?* and the model spoke its
    answer — सर्वं कुशलम् — verbatim at a user who had said nothing of the kind."""

    class LoudPhrasebook:
        def similar(self, transcript, k=3):
            return [{"english": "All is well.", "sanskrit": "सर्वं कुशलम्।"}]

    orch, agent = make_orchestrator(replies=[SA_REPLY, SA_REPLY],
                                    phrasebook=LoudPhrasebook())
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "at home."))
    assert "सर्वं कुशलम्" not in agent.calls[0]

    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "who lives in your house?"))
    assert "सर्वं कुशलम्" in agent.calls[1]      # a real turn still gets grounding


def test_a_statement_gets_a_question_about_it_not_a_new_subject(
        make_orchestrator, fake_tts):
    """Observed live: told "I'll do some work today", Mitra asked "who is at
    your home?" — the thread the person was pulling on just got dropped."""
    more = "अधिकं वद।"
    followups = _followups(FOLLOWUP, continuations=({"question": more,
                                                     "iast": more,
                                                     "english": "Tell me more."},))
    orch, _ = make_orchestrator(replies=[SA_REPLY, SA_REPLY], followups=followups)
    orch.state = State.LISTENING

    orch.handle_event(Event("utterance", "I'll do some work today."))
    assert fake_tts.spoken == [f"{SA_REPLY} {more}"]        # stays on the thread

    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "What is your name?"))
    assert fake_tts.spoken[-1] == f"{SA_REPLY} {FOLLOWUP}"  # a question opens one back


def test_no_question_follows_i_do_not_understand(make_orchestrator, fake_tts):
    """Observed live: "Sorry, I do not understand. Who is at your home?" —
    the apology already asks for another try."""
    orch, _ = make_orchestrator(replies=[EN_REPLY, EN_REPLY],   # fails twice
                                followups=_followups(FOLLOWUP))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "hello"))
    assert fake_tts.spoken == [prompts.SAFE_FALLBACK]


def test_a_slow_gloss_does_not_hold_the_state_machine(make_orchestrator):
    """The bug behind a dropped answer: the gloss ran inline on the run loop,
    so playback_done went unhandled and the mic stayed on the wake detector
    while the user answered the question Mitra had just asked."""

    class SlowGlosser:
        def gloss(self, text):
            time.sleep(1.0)
            return "..."

    orch, _ = make_orchestrator(replies=[SA_REPLY], glosser=SlowGlosser())
    orch.state = State.LISTENING
    started = time.monotonic()
    orch.handle_event(Event("utterance", "hello"))
    orch.handle_event(Event("playback_done"))
    assert orch.state == State.LISTENING
    assert time.monotonic() - started < 0.5


def test_a_short_answer_to_a_question_is_not_refused_as_noise(
        make_orchestrator, fake_tts):
    """"no" carries nothing on its own, and answers "did you like it?"."""
    orch, agent = make_orchestrator(replies=[SA_REPLY, "अस्तु।"],
                                    followups=_followups(FOLLOWUP))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "no"))          # nothing asked yet
    assert agent.calls == []
    assert fake_tts.spoken == [prompts.APOLOGY_RETRY]

    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "What is your name?"))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "no"))          # now it is an answer
    assert len(agent.calls) == 2


def test_the_recitation_is_followed_by_a_question_about_the_verse(
        make_orchestrator, fake_tts):
    from mitra.lexicon.shlokas import Shlokas

    class OneVerse(Shlokas):
        def __init__(self):
            self._rows = [{"source_slug": "s", "verse_id": "1",
                           "verse_text": "आलस्यं हि मनुष्याणाम्",
                           "attribution": "इति भर्तृहरेः॥"}]
            self._recent = []

        def pick(self):
            return self._rows[0]

        def reset(self):
            pass

    verse_question = "एषः श्लोकः तुभ्यं रोचते वा?"
    followups = _followups(verse_question)
    followups._rows[0]["topics"] = ("shloka",)
    orch, _ = make_orchestrator(shlokas=OneVerse(), followups=followups)
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Recite a shloka"))
    # Spoken as chunks either side of the dandas; the invitation comes last.
    assert fake_tts.spoken[-1] == verse_question


def test_a_session_forgets_what_it_asked(make_orchestrator, fake_tts):
    orch, _ = make_orchestrator(followups=_followups(FOLLOWUP, "त्वं कथम् असि?"))
    orch.handle_event(Event("wake"))
    orch._go_to_sleep()
    orch.handle_event(Event("wake"))
    assert fake_tts.spoken == [f"{prompts.GREETING}। {FOLLOWUP}"] * 2
    assert orch._pending_question == FOLLOWUP


def test_without_a_list_the_reply_stands_alone(make_orchestrator, fake_tts):
    """Absent == feature absent, as with the phrasebook and the verse corpus."""
    orch, _ = make_orchestrator(replies=[SA_REPLY])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    assert fake_tts.spoken == [SA_REPLY]


def test_silence_timeout_returns_to_sleep(make_orchestrator):
    orch, agent = make_orchestrator(silence_timeout_s=30)
    orch.state = State.LISTENING
    orch._last_activity = time.monotonic() - 31
    orch.handle_event(Event("tick"))
    assert orch.state == State.ASLEEP
    assert agent.resets == 1


def test_barge_in_stops_playback(make_orchestrator, fake_robot):
    orch, _ = make_orchestrator()
    fake_robot.hold_playback = True
    orch.state = State.SPEAKING
    orch.handle_event(Event("wake"))
    assert fake_robot.stops == 1
    assert orch.state == State.LISTENING


class _CountingWake:
    """Stands in for the wake detector: only reset() is exercised here."""

    def __init__(self):
        self.resets = 0

    def process(self, chunk):
        return False

    def reset(self):
        self.resets += 1


def test_leaving_speaking_resets_the_wake_detector(make_orchestrator, fake_robot):
    """Its energy segmenter is only fed while asleep or speaking, so a state
    change mid-window strands it inside an utterance made of Mitra's own voice."""
    wake = _CountingWake()
    orch, _ = make_orchestrator(wake=wake)
    orch.state = State.SPEAKING
    orch.handle_event(Event("playback_done"))
    assert orch.state == State.LISTENING
    assert wake.resets == 1


def test_playback_end_flushes_the_echo(make_orchestrator, fake_robot):
    """The ordinary case: the buffer holds the robot's own voice, so drop it."""
    orch, _ = make_orchestrator()
    orch._watch_playback()
    assert fake_robot.flushes == 1


def test_barge_in_keeps_what_the_user_is_saying(make_orchestrator, fake_robot):
    """After the wake word cuts playback, the mic buffer is the user mid-
    sentence — flushing it deletes the turn the barge-in was asking for."""
    orch, _ = make_orchestrator()
    fake_robot.hold_playback = True
    orch.state = State.SPEAKING
    orch.handle_event(Event("wake"))          # barge-in
    orch._watch_playback()                    # the watcher thread, now unblocked
    assert fake_robot.flushes == 0


def test_the_next_reply_re_arms_the_flush(make_orchestrator, fake_robot):
    """The barge-in flag is per-playback, not sticky for the rest of the run."""
    orch, _ = make_orchestrator()
    fake_robot.hold_playback = True
    orch.state = State.SPEAKING
    orch.handle_event(Event("wake"))
    assert orch._barge_in.is_set()
    fake_robot.hold_playback = False
    orch._speak("नमस्ते")                      # a new line clears the flag
    assert not orch._barge_in.is_set()


def test_agent_exception_apologizes_and_keeps_session(make_orchestrator, fake_tts):
    class ExplodingAgent:
        def converse(self, message):
            raise RuntimeError("ollama down")

        def reset(self):
            pass

    orch, _ = make_orchestrator()
    orch.agent = ExplodingAgent()
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "hello"))
    assert fake_tts.spoken == [prompts.APOLOGY_RETRY]
    assert orch.state == State.SPEAKING  # → LISTENING on playback_done (FR-6.4)


def test_empty_transcript_asks_to_repeat(make_orchestrator, fake_tts):
    orch, agent = make_orchestrator()
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "   "))
    assert agent.calls == []
    assert fake_tts.spoken == [prompts.APOLOGY_RETRY]


def test_wake_ignored_while_listening(make_orchestrator, fake_robot):
    orch, _ = make_orchestrator()
    orch.state = State.LISTENING
    orch.handle_event(Event("wake"))
    assert orch.state == State.LISTENING
    assert fake_robot.nods == 0


def test_run_loop_stops_cleanly(make_orchestrator):
    import threading

    orch, _ = make_orchestrator()
    thread = threading.Thread(target=orch.run, daemon=True)
    thread.start()
    orch.stop()
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_state_gestures_follow_transitions(make_orchestrator, fake_robot):
    orch, _ = make_orchestrator(replies=[SA_REPLY])
    orch.handle_event(Event("wake"))
    orch.handle_event(Event("playback_done"))          # WAKING -> LISTENING
    assert fake_robot.poses[-1] == "listening"
    orch.handle_event(Event("utterance", "hello"))     # -> THINKING -> SPEAKING
    assert "thinking" in fake_robot.poses
    assert fake_robot.poses[-1] == "neutral"           # face forward to speak
    orch.state = State.LISTENING
    orch._last_activity = time.monotonic() - 31
    orch.handle_event(Event("tick"))                   # timeout -> ASLEEP
    assert fake_robot.poses[-1] == "asleep"


def test_gestures_can_be_disabled(make_orchestrator, fake_robot):
    orch, _ = make_orchestrator(replies=[SA_REPLY], gestures=False)
    orch.handle_event(Event("wake"))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "hello"))
    assert fake_robot.poses == []


def test_explain_in_english_allows_english_reply(make_orchestrator, fake_tts):
    english = "I said that the sun shines in the sky and gives us light."
    orch, agent = make_orchestrator(replies=[english])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Can you explain that in English?"))
    assert fake_tts.spoken == [english]              # Devanagari check waived
    assert "[explain_in_english]" in agent.calls[0]  # model told it may switch


def test_plain_english_question_still_requires_sanskrit(make_orchestrator, fake_tts):
    orch, agent = make_orchestrator(replies=[EN_REPLY, EN_REPLY])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Tell me about the sun."))
    assert "[explain_in_english]" not in agent.calls[0]
    assert fake_tts.spoken == [prompts.SAFE_FALLBACK]  # English reply rejected


def test_wake_plays_welcoming_emotion(make_orchestrator, fake_robot):
    orch, _ = make_orchestrator()
    orch.handle_event(Event("wake"))
    assert fake_robot.emotions == ["welcoming1"]


def test_sleep_plays_deep_sleep_emotion(make_orchestrator, fake_robot):
    orch, _ = make_orchestrator(silence_timeout_s=30)
    orch.state = State.LISTENING
    orch._last_activity = time.monotonic() - 31
    orch.handle_event(Event("tick"))
    assert "mini-deep-sleep" in fake_robot.emotions


def test_agent_exception_plays_confused_emotion(make_orchestrator, fake_robot):
    class ExplodingAgent:
        def converse(self, message):
            raise RuntimeError("ollama down")

        def reset(self):
            pass

    orch, _ = make_orchestrator()
    orch.agent = ExplodingAgent()
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "hello"))
    assert fake_robot.emotions == ["confused1"]


def test_emotions_disabled_alongside_gestures(make_orchestrator, fake_robot):
    orch, _ = make_orchestrator(replies=[SA_REPLY], gestures=False)
    orch.handle_event(Event("wake"))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "hello"))
    assert fake_robot.emotions == []


def test_reply_truncated_to_one_sentence(make_orchestrator, fake_tts):
    """The stock trailing question carried most of the observed grammar
    errors (कथं भवतः?), so the answer is spoken without it."""
    orch, _ = make_orchestrator(replies=["अहं क्रीडामि। कथं भवतः?"])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Do you play?"))
    assert fake_tts.spoken == ["अहं क्रीडामि।"]


def test_max_sentences_is_configurable(make_orchestrator, fake_tts):
    orch, _ = make_orchestrator(replies=["अहं क्रीडामि। अहं पठामि। अहं वदामि।"],
                                max_sentences=2)
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Do you play?"))
    assert fake_tts.spoken == ["अहं क्रीडामि। अहं पठामि।"]


def test_single_sentence_reply_is_untouched(make_orchestrator, fake_tts):
    orch, _ = make_orchestrator(replies=["अहं पुस्तकं पठामि।"])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What are you reading?"))
    assert fake_tts.spoken == ["अहं पुस्तकं पठामि।"]


def test_hindi_reply_is_retried_then_falls_back(make_orchestrator, fake_tts):
    """Pure-Devanagari Hindi passes the script check, so only the marker
    check can catch it; a failing retry must reach the safe fallback."""
    orch, agent = make_orchestrator(
        replies=["अहं आज पठामि।", "अहं आज पठामि।"])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What will you do today?"))
    assert len(agent.calls) == 2                      # one corrective retry
    assert fake_tts.spoken == [prompts.SAFE_FALLBACK]


def test_hindi_retry_that_recovers_is_spoken(make_orchestrator, fake_tts):
    orch, _ = make_orchestrator(replies=["अहं आज पठामि।", "अद्य अहं पठामि।"])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What will you do today?"))
    assert fake_tts.spoken == ["अद्य अहं पठामि।"]


class RecordingGlosser:
    """Stands in for mitra.gloss.Glosser: returns a fixed English line."""

    def __init__(self, english="My name is Mitra."):
        self.english = english
        self.seen: list[str] = []

    def gloss(self, text: str) -> str:
        self.seen.append(text)
        return self.english


def test_gloss_logs_english_and_lands_in_the_turn_log(make_orchestrator, tmp_path):
    from mitra.logging_subsystem import TurnLogger

    glosser = RecordingGlosser()
    orch, _ = make_orchestrator(replies=[SA_REPLY], glosser=glosser,
                                turn_logger=TurnLogger(tmp_path))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    # The gloss runs off the run loop (it is a second model call, and inline it
    # held the state machine in SPEAKING while the user answered) — so the turn
    # record is written by that thread, not by handle_event.
    orch.flush_logs()
    assert glosser.seen == [SA_REPLY]
    record = json.loads((tmp_path / "turns.jsonl").read_text(encoding="utf-8"))
    assert record["reply"] == SA_REPLY
    assert record["reply_en"] == "My name is Mitra."
    assert "tts" in record["stages"]            # gloss did not replace the timing


def test_gloss_failure_never_breaks_a_turn(make_orchestrator, fake_tts):
    class BrokenGlosser:
        def gloss(self, text):
            raise RuntimeError("translator exploded")

    orch, _ = make_orchestrator(replies=[SA_REPLY], glosser=BrokenGlosser())
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    assert fake_tts.spoken == [SA_REPLY]
    assert orch.state == State.SPEAKING


class WordChecker:
    """Stands in for mitra.sanskrit.grammar.Checker: rejects listed words."""

    def __init__(self, *bad):
        self.bad = set(bad)

    def __call__(self, text, allow=None):
        from mitra.sanskrit.grammar import Finding

        allowed = allow or (lambda word: False)
        hits = [w for w in self.bad if w in text and not allowed(w)]
        return [Finding("vocabulary", "outside Mitra's vocabulary: "
                        + ", ".join(hits), hits)] if hits else []

    @staticmethod
    def reason(findings):
        return "; ".join(f.detail for f in findings)

    @staticmethod
    def offending_words(findings):
        return [w for f in findings for w in f.words]


def test_grammar_rejection_retries_with_the_word_named(make_orchestrator, fake_tts):
    """घरे is 100% Devanagari and is not on any Hindi stoplist — only the
    morphology checks see it. The retry must name it, or the model re-rolls
    the same sentence."""
    orch, agent = make_orchestrator(
        replies=["अहं घरे अस्मि।", "अहं गृहे वसामि।"],
        grammar_checker=WordChecker("घरे"))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Where do you live?"))
    assert len(agent.calls) == 2
    assert "घरे" in agent.calls[1]                   # the retry names it
    assert fake_tts.spoken == ["अहं गृहे वसामि।"]


def test_hindi_marker_rejection_also_names_the_word(make_orchestrator):
    """The stoplist path gained the same treatment: खेलानि is caught by
    validator._HINDI_STEMS, and that retry now says which word to drop."""
    orch, agent = make_orchestrator(replies=["अहं खेलानि करोमि।", SA_REPLY])
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Do you play?"))
    assert "खेलानि" in agent.calls[1]


def test_grammar_failure_twice_falls_back(make_orchestrator, fake_tts):
    orch, _ = make_orchestrator(
        replies=["अहं घरे अस्मि।", "अहं घरे वसामि।"],
        grammar_checker=WordChecker("घरे"))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Where do you live?"))
    assert fake_tts.spoken == [prompts.SAFE_FALLBACK]


def test_a_broken_checker_never_costs_the_child_an_answer(make_orchestrator,
                                                          fake_tts):
    class BrokenChecker:
        def __call__(self, text, allow=None):
            raise RuntimeError("kosha exploded")

    orch, _ = make_orchestrator(replies=[SA_REPLY], grammar_checker=BrokenChecker())
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    assert fake_tts.spoken == [SA_REPLY]


# ------------------------------------------------- the child's name (names.py)

def test_the_users_own_name_is_not_rejected_as_a_non_sanskrit_word(
        make_orchestrator, fake_tts):
    """Observed live: Mitra asked तव नाम किम्?, was told, and apologized.

    The vocabulary check is right that तफिकः is not a Sanskrit word, and that
    is beside the point — a name arrives from outside the word list by
    definition (agent/names.py).
    """
    orch, agent = make_orchestrator(replies=["स्वागतं तफिकः।"],
                                    grammar_checker=WordChecker("तफिकः"))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "My name is Tafik."))
    assert len(agent.calls) == 1                   # no corrective retry
    assert fake_tts.spoken == ["स्वागतं तफिकः।"]


def test_a_rejected_word_that_is_not_the_name_still_fails(
        make_orchestrator, fake_tts):
    """The allowance is for the name, not a hole in the vocabulary check."""
    orch, _ = make_orchestrator(replies=["अहं घरे अस्मि।", "अहं गृहे अस्मि।"],
                                grammar_checker=WordChecker("घरे"))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "My name is Tafik."))
    assert fake_tts.spoken == ["अहं गृहे अस्मि।"]


def test_a_name_is_remembered_for_the_session_and_forgotten_after_it(
        make_orchestrator, fake_tts):
    orch, _ = make_orchestrator(
        replies=["नमस्ते तफिक।", "स्वागतं तफिकः।",
                 "स्वागतं तफिकः।", "स्वागतं तफिकः।"],
        grammar_checker=WordChecker("तफिकः"))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "My name is Tafik."))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "What do you play?"))
    assert fake_tts.spoken[-1] == "स्वागतं तफिकः।"   # turns later, still fine

    orch._go_to_sleep()
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What do you play?"))
    assert fake_tts.spoken[-1] == prompts.SAFE_FALLBACK


# ------------------------------------------- accepting the offer of a verse

class _OneVerse:
    """Stands in for the corpus: one verse, always."""

    def __init__(self):
        self.picks = 0

    def pick(self):
        self.picks += 1
        return {"source_slug": "s", "verse_id": "1",
                "verse_text": "आलस्यं हि मनुष्याणाम्",
                "attribution": "इति भर्तृहरेः॥"}

    def reset(self):
        pass


def test_yes_to_the_offer_of_another_verse_is_answered_with_one(
        make_orchestrator, fake_tts):
    """The invitation has to be one Mitra can honour, or it is a dead end."""
    from mitra.agent.followups import OFFERS_VERSE

    offer = sorted(OFFERS_VERSE)[0]
    verses = _OneVerse()
    orch, agent = make_orchestrator(replies=[SA_REPLY], shlokas=verses,
                                    followups=_followups(offer))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    assert orch._pending_question == offer
    orch.handle_event(Event("playback_done"))

    orch.handle_event(Event("utterance", "Yes please"))
    assert verses.picks == 1                       # from the corpus…
    assert len(agent.calls) == 1                   # …not from the model
    assert "आलस्यं हि मनुष्याणाम्" in fake_tts.spoken


def test_a_bare_yes_means_nothing_when_no_verse_was_offered(
        make_orchestrator, fake_tts):
    verses = _OneVerse()
    orch, agent = make_orchestrator(replies=[SA_REPLY, SA_REPLY], shlokas=verses,
                                    followups=_followups(FOLLOWUP))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "Yes please"))
    assert verses.picks == 0
    assert len(agent.calls) == 2


def test_no_to_the_offer_of_another_verse_is_left_to_the_model(
        make_orchestrator, fake_tts):
    from mitra.agent.followups import OFFERS_VERSE

    verses = _OneVerse()
    orch, agent = make_orchestrator(replies=[SA_REPLY, SA_REPLY], shlokas=verses,
                                    followups=_followups(sorted(OFFERS_VERSE)[0]))
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "What is your name?"))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "No, not now."))
    assert verses.picks == 0
    assert len(agent.calls) == 2


def test_the_next_turn_knows_which_verse_was_recited(make_orchestrator):
    """The corpus answers the recitation, so the model never saw the verse —
    and the question that follows ("what does it mean?") is about it."""
    orch, agent = make_orchestrator(replies=[SA_REPLY], shlokas=_OneVerse())
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Recite a shloka"))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "What does that mean in English?"))
    assert "आलस्यं हि मनुष्याणाम्" in agent.calls[0]
    assert "[explain_in_english]" in agent.calls[0]


def test_the_verse_is_carried_for_one_turn_only(make_orchestrator):
    orch, agent = make_orchestrator(replies=[SA_REPLY, SA_REPLY],
                                    shlokas=_OneVerse())
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Recite a shloka"))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "I liked that."))
    orch.handle_event(Event("playback_done"))
    orch.handle_event(Event("utterance", "What is your name?"))
    assert "आलस्यं" not in agent.calls[-1]


def test_a_verse_that_contains_an_interrogative_still_invites_a_reply(
        make_orchestrator, fake_tts):
    """*तथेदं कुत्र कुप्यते* is the poet's question, not one put to the child.

    Read as Mitra's own, it cost the recitation its follow-up — and with no
    question outstanding the next turn ("yes, I liked it") reached the model
    as a bare fragment and ended in the safe fallback.
    """
    class _Interrogative(_OneVerse):
        def pick(self):
            self.picks += 1
            return {"source_slug": "s", "verse_id": "1",
                    "verse_text": "मत्कर्मजनिता एव तथेदं कुत्र कुप्यते",
                    "attribution": "इति शान्तिदेवस्य॥"}

    question = "एषः श्लोकः तुभ्यं रोचते वा?"
    followups = _followups(question)
    followups._rows[0]["topics"] = ("shloka",)
    orch, _ = make_orchestrator(shlokas=_Interrogative(), followups=followups)
    orch.state = State.LISTENING
    orch.handle_event(Event("utterance", "Recite a shloka"))
    assert fake_tts.spoken[-1] == question
    assert orch._pending_question == question
