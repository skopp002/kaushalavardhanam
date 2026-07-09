"""Table-driven state machine tests (DESIGN §3, §9): FakeReachy + canned agent."""

import time

from mitram.agent import prompts
from mitram.orchestrator import Event, Orchestrator, State

SA_REPLY = "मम नाम मित्रम्।"
EN_REPLY = "My name is Mitram, nice to meet you."


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
