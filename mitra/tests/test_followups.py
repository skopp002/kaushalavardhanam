"""The follow-up layer: verified questions, topical choice, no repeats (FR-3.12)."""

import random

import pytest

from mitra.agent import followups
from mitra.agent.followups import Followups, has_question, join_question


def _fixed() -> Followups:
    """Deterministic draw so a test asserts a question, not a coin flip."""
    return Followups(rng=random.Random(0))


# ----------------------------------------------------------- the list itself

def test_every_row_is_a_devanagari_question():
    from mitra.agent.validator import devanagari_ratio

    for row in followups.ROWS:
        assert row["question"].endswith("?"), row["iast"]
        assert devanagari_ratio(row["question"]) == 1.0, row["iast"]
        assert row["iast"] and row["english"], row["question"]


def test_questions_are_unique():
    questions = [row["question"] for row in followups.ROWS]
    assert len(questions) == len(set(questions))


def test_every_row_would_survive_the_reply_validator():
    """Appended after validation, but never a line the gate would have rejected."""
    from mitra.agent import validator

    for row in followups.ROWS:
        ok, reason = validator.validate(row["question"])
        assert ok, f"{row['iast']}: {reason}"


# --------------------------------------------------------------- detection

@pytest.mark.parametrize("text", [
    "तव नाम किम्?",
    "त्वं कथम् असि",          # Sanskrit marks the question with the word, not "?"
    "एषः श्लोकः तुभ्यं रोचते वा?",
    "What did you mean?",     # the [explain_in_english] path
])
def test_has_question_sees_a_question(text):
    assert has_question(text)


@pytest.mark.parametrize("text", [
    "मम नाम मित्रम्।",
    "एतत् सेवफलम् अस्ति।",
    "अहं कुशली अस्मि।",
    "",
])
def test_has_question_leaves_statements_alone(text):
    assert not has_question(text)


# ----------------------------------------------------------------- joining

def test_join_adds_a_danda_when_the_reply_has_no_terminator():
    assert join_question("नमस्ते", "तव नाम किम्?") == "नमस्ते। तव नाम किम्?"


def test_join_keeps_an_existing_terminator():
    assert join_question("मम नाम मित्रम्।", "त्वं कथम् असि?") == \
        "मम नाम मित्रम्। त्वं कथम् असि?"


# ------------------------------------------------------------------ choice

def test_picks_a_question_about_what_was_just_said():
    picked = _fixed().pick(transcript="What is your favourite food?",
                           reply="मम प्रियं भोजनं नवनीतम् अस्ति।")
    assert picked == "तव प्रियं भोजनं किम्?"


def test_keywords_match_mitras_own_devanagari_reply():
    picked = _fixed().pick(transcript="ನೀನು ಏನು ಮಾಡುತ್ತಿದ್ದೀಯಾ?",
                           reply="अहं पुस्तकं पठामि।")
    assert picked == "त्वं किं पठसि?"


def test_a_topic_selects_its_own_question():
    picked = _fixed().pick(transcript="Recite a shloka", topic="shloka")
    assert picked == "एषः श्लोकः तुभ्यं रोचते वा?"


def test_questions_that_presume_a_context_are_never_drawn_at_random():
    """Observed live: asked where it lives, Mitra asked "what else will you
    show me?" when nothing had been shown."""
    followup = _fixed()
    drawn = {followup.pick(transcript="Where do you live?",
                           reply="अहं नगरे वसामि।")
             for _ in range(len(followups.ROWS) * 3)}
    for row in followups.ROWS:
        if row.get("cue_only"):
            assert row["question"] not in drawn, row["iast"]


def test_a_cued_question_is_available_once_its_cue_appears():
    picked = _fixed().pick(transcript="What is this? Look at it",
                           reply="एतत् सेवफलम् अस्ति।")
    assert picked == "अन्यत् किं दर्शयसि?"


def test_an_unknown_topic_falls_back_to_the_general_pool():
    assert _fixed().pick(topic="quantum-mechanics") is not None


def test_a_question_is_not_repeated_within_a_session():
    followup = _fixed()
    pool_size = sum(1 for r in followups.ROWS if not r.get("cue_only"))
    drawn = [followup.pick() for _ in range(pool_size)]
    assert len(set(drawn)) == pool_size


def test_the_rotation_restarts_rather_than_falling_silent():
    """Running out is not a reason to end a turn without an invitation."""
    followup = _fixed()
    for _ in range(len(followups.ROWS) * 2 + 1):
        assert followup.pick() is not None


# ------------------------------------------- continuing versus opening a topic

@pytest.mark.parametrize("text", [
    "What's your favorite food?",
    "I study computer science. What's your favorite subject?",
    "भवतः नाम किम्",                       # Sanskrit, no punctuation
    "ನಿನ್ನ ಹೆಸರು ಏನು?",                     # Kannada
    "tell me about the sun",
])
def test_a_turn_that_asks_is_recognized(text):
    assert followups.asks_something(text)


@pytest.mark.parametrize("text", [
    "I'll do some work today.",
    "at home.",
    "My name is Taufik.",
    "",
])
def test_a_turn_that_only_tells_is_not_an_ask(text):
    assert not followups.asks_something(text)


def test_continuing_asks_about_what_was_said():
    picked = _fixed().pick(transcript="I'll do some work today.", continuing=True)
    assert picked in [row["question"] for row in followups.CONTINUATIONS]


def test_a_continuation_is_not_repeated_twice_running():
    followup = _fixed()
    first = followup.pick(continuing=True)
    assert followup.pick(continuing=True) != first


def test_a_continuation_may_come_back_later_in_the_session():
    """Unlike a topic question: "why?" about two different things is two
    different questions."""
    followup = _fixed()
    drawn = [followup.pick(continuing=True)
             for _ in range(len(followups.CONTINUATIONS) + 2)]
    assert len(drawn) > len(set(drawn))


def test_a_recitation_keeps_its_own_question_even_when_continuing():
    picked = _fixed().pick(transcript="recite a shloka", topic="shloka",
                           continuing=True)
    assert picked == "एषः श्लोकः तुभ्यं रोचते वा?"


def test_continuations_pass_the_reply_validator():
    from mitra.agent import validator

    for row in followups.CONTINUATIONS:
        ok, reason = validator.validate(row["question"])
        assert ok, f"{row['iast']}: {reason}"


# ---------------------------------------------- what the user already told us

def test_a_topic_the_user_volunteered_is_not_asked_back():
    """Observed live: "My favorite food is milk" → "तुभ्यं किं रोचते?"."""
    followup = _fixed()
    followup.observe("My favorite food is milk. What's yours?")
    for _ in range(20):
        assert followup.pick() not in ("तव प्रियं भोजनं किम्?", "तुभ्यं किं रोचते?")


def test_the_memory_lasts_the_whole_session():
    """A name given at turn two must not be asked for at turn nine."""
    followup = _fixed()
    followup.observe("My name is Taufik.")
    for _ in range(20):
        assert followup.pick(transcript="tell me about the sun") != "तव नाम किम्?"


def test_a_question_beside_a_statement_keeps_its_own_topic_open():
    """"I'm fine. What's your favourite food?" — the first person belongs to
    "fine", and the food is being asked about, not told."""
    followup = _fixed()
    followup.observe("I'm fine. What's your favorite food?")
    assert followup.pick(transcript="I'm fine. What's your favorite food?",
                         reply="मम प्रियं भोजनं क्षीरम् अस्ति।") in (
        "तव प्रियं भोजनं किम्?", "तुभ्यं किं रोचते?")
    # …while the clause that did tell us something is retired.
    for _ in range(20):
        assert followup.pick() != "त्वं कथम् असि?"


def test_a_question_from_the_user_leaves_the_topic_open():
    """Asking "what is your favourite food?" invites the question back;
    only telling us closes it."""
    followup = _fixed()
    followup.observe("What is your favourite food?")
    picked = followup.pick(transcript="What is your favourite food?",
                           reply="मम प्रियं भोजनं नवनीतम् अस्ति।")
    assert picked in ("तव प्रियं भोजनं किम्?", "तुभ्यं किं रोचते?")


def test_covering_everything_still_leaves_a_question_to_ask():
    followup = _fixed()
    for row in followups.ROWS:
        followup._covered.add(row["question"])
    assert followup.pick() is not None


def test_reset_forgets_what_the_user_told_us_too():
    followup = _fixed()
    followup.observe("My name is Taufik.")
    followup.reset()
    assert followup._covered == set()


class _AlwaysFirst(random.Random):
    """Removes the tie-break coin flip so the draw order is an assertion."""

    def choice(self, seq):
        return seq[0]


def test_reset_forgets_the_session():
    """A new session may open with the question the last one just used."""
    followup = Followups(rows=followups.ROWS[:2], rng=_AlwaysFirst())
    first = followup.pick()
    assert followup.pick() != first     # not twice inside one session
    followup.reset()
    assert followup.pick() == first     # a new session starts the list over


def test_an_empty_list_asks_nothing():
    assert Followups(rows=()).pick() is None


# ------------------------------------------------ going deeper into a subject

def _deepenings():
    return [d for row in followups.ROWS for d in row.get("deepen", ())]


def test_every_deepening_is_a_devanagari_question_with_a_gloss():
    from mitra.agent.validator import devanagari_ratio, validate

    for entry in _deepenings():
        assert entry["question"].endswith("?"), entry["iast"]
        assert devanagari_ratio(entry["question"]) == 1.0, entry["iast"]
        assert entry["iast"] and entry["english"], entry["question"]
        ok, reason = validate(entry["question"])
        assert ok, f"{entry['iast']}: {reason}"


def test_no_question_appears_twice_anywhere_in_the_file():
    asked = ([row["question"] for row in followups.ROWS]
             + [entry["question"] for entry in _deepenings()]
             + [row["question"] for row in followups.CONTINUATIONS])
    assert len(asked) == len(set(asked))


def test_answering_a_question_goes_deeper_into_the_same_subject():
    """The logged failure: "what do you like?" answered, then "tell me more"."""
    followup = _fixed()
    opened = followup.pick(transcript="What is your favourite food?",
                           reply="मम प्रियं भोजनं नवनीतम् अस्ति।")
    assert opened == "तव प्रियं भोजनं किम्?"
    assert followup.pick(transcript="I like mangoes.", continuing=True) == \
        "तत् मधुरम् अस्ति वा?"


def test_the_subject_is_walked_one_step_at_a_time_then_let_go():
    followup = _fixed()
    row = next(r for r in followups.ROWS if r["question"] == "त्वं किं क्रीडसि?")
    followup.pick(transcript="What do you play?", reply="अहं क्रीडामि।")
    walked = [followup.pick(transcript="cricket.", continuing=True)
              for _ in range(len(row["deepen"]) + 1)]
    assert walked[:len(row["deepen"])] == [d["question"] for d in row["deepen"]]
    # Exhausted, the turn falls back to a continuation rather than repeating.
    assert walked[-1] in [c["question"] for c in followups.CONTINUATIONS]


def test_a_deepening_never_arrives_before_its_own_question():
    """"Is it sweet?" makes sense after the food question and nowhere else."""
    followup = _fixed()
    deepening_of = {d["question"]: row for row in followups.ROWS
                    for d in row.get("deepen", ())}
    asked: list[str] = []
    for _ in range(len(followups.ROWS) * 4):
        question = followup.pick()
        row = deepening_of.get(question)
        if row is not None:
            assert row["question"] in asked, question
        asked.append(question)


def test_an_unrelated_question_stays_on_the_open_subject():
    """A draw with nothing to go on is a coin flip, and a coin flip is a jump.

    Live: asked "how are you?" — a turn no keyword in the list matches —
    Mitra answered and asked which animal the child liked.
    """
    followup = _fixed()
    opened = followup.pick(transcript="What do you play?", reply="अहं क्रीडामि।")
    assert opened == "त्वं किं क्रीडसि?"
    row = next(r for r in followups.ROWS if r["question"] == opened)
    assert followup.pick(transcript="Tell me something.") == \
        row["deepen"][0]["question"]


def test_a_second_recitation_is_not_followed_by_the_same_question():
    followup = _fixed()
    first = followup.pick(transcript="recite a shloka", topic="shloka")
    second = followup.pick(transcript="another one", topic="shloka")
    assert first == "एषः श्लोकः तुभ्यं रोचते वा?"
    assert second != first
    assert second in followups.OFFERS_VERSE


# ------------------------------------------------------- accepting an offer

def test_the_offer_of_another_verse_is_on_the_list():
    assert followups.OFFERS_VERSE


@pytest.mark.parametrize("text", [
    "Yes", "yes please", "okay", "sure, another one", "आम्", "ಹೌದು",
])
def test_an_acceptance_is_recognized(text):
    assert followups.is_affirmative(text)


@pytest.mark.parametrize("text", [
    "no", "no, not again", "stop", "enough", "ಇಲ್ಲ", "",
])
def test_a_refusal_is_not_an_acceptance(text):
    assert not followups.is_affirmative(text)


# ------------------------------------------ Mitra may say what Mitra asks

def test_every_spoken_question_is_exported_for_the_vocabulary():
    spoken = followups.spoken_questions()
    assert len(spoken) == len(set(spoken))
    for row in followups.ROWS:
        assert row["question"] in spoken
        for entry in row.get("deepen", ()):
            assert entry["question"] in spoken
    for row in followups.CONTINUATIONS:
        assert row["question"] in spoken


def test_a_subject_asked_about_survives_being_mentioned_in_the_same_turn():
    """"I play chess. What games do you play?" — the first clause told us
    about playing, the second asked about it, and retiring it there left
    Mitra asking whether the child's food was sweet."""
    followup = _fixed()
    followup.observe("I play chess. What games do you play?")
    assert followup.pick(transcript="I play chess. What games do you play?",
                         reply="अहं कन्दुकेन क्रीडामि।") == "त्वं किं क्रीडसि?"


def test_a_question_about_a_school_subject_finds_the_studying_row():
    """It matched nothing, so the draw was random: "who is at your home?"."""
    followup = _fixed()
    turn = "I am studying computer science. What's your favorite subject?"
    followup.observe(turn)
    assert followup.pick(transcript=turn, reply="मह्यं गणितं रोचते।") == \
        "त्वं किं पठसि?"
