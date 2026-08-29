"""The child's own name survives the Sanskrit checks (agent/names.py)."""

import pytest

from mitra.agent import names


# ------------------------------------------------------------- skeletons

@pytest.mark.parametrize("spelling, devanagari", [
    ("Tafik", "तफिकः"),          # the logged failure: f ↔ फ
    ("Taufiq", "तौफिकम्"),        # q ↔ क, and an accusative ending
    ("Ravi", "रविः"),
    ("Priya", "प्रियायाः"),
    ("Chetan", "चेतनः"),         # ch ↔ च, both folded onto k
    ("Kavya", "काव्यम्"),
])
def test_a_name_is_recognized_across_scripts(spelling, devanagari):
    assert names.echoes(devanagari, {names.skeleton(spelling)})


@pytest.mark.parametrize("word", ["घरे", "खेलानि", "मक्खनम्", "आज"])
def test_the_hindi_words_the_checks_exist_for_are_not_excused(word):
    """A name may not become a hole in the vocabulary check."""
    assert not names.echoes(word, {"tpk", "rv", "pry"})


def test_a_case_ending_may_only_add_so_much():
    """तफिकस्य is the name; तफिकमन्दिरम् is a different word that starts alike."""
    assert names.echoes("तफिकस्य", {"tpk"})
    assert not names.echoes("तफिकमन्दिरम्", {"tpk"})


def test_one_consonant_is_not_a_name():
    """"Al" → l would excuse every rejected word beginning with ल."""
    assert not names.echoes("लभते", {names.skeleton("Al")})


# ------------------------------------------------------- hearing a name

def test_a_name_is_heard_from_an_introduction():
    assert "Tafik" in names.heard("My name is Tafik.")


def test_a_name_is_heard_from_mid_sentence_capitalisation():
    assert set(names.heard("I am Ravi and this is Priya.")) == {"Ravi", "Priya"}


def test_a_lower_case_name_still_lands_when_it_is_introduced():
    """Whisper writes an unfamiliar name lower-case as often as not."""
    assert "tafik" in names.heard("my name is tafik")


@pytest.mark.parametrize("transcript", [
    "Recite a shloka",             # first word of the sentence
    "I like milk.",                # "I" is not a name
    "OK",                          # shouting is not a name either
    "What is your name?",
    "",
])
def test_ordinary_turns_carry_no_names(transcript):
    assert names.heard(transcript) == {}


def test_a_place_name_survives_its_anusvara():
    """"Bangalore" is b-n-g-l-r; बैंगलोरं writes that n as a mark, not a letter."""
    assert names.echoes("बैंगलोरं", {names.skeleton("Bangalore")})


@pytest.mark.parametrize("transcript", [
    "I'm fine. Thanks for asking. How are you?",     # "fine" — excused पानम्
    "I am studying computer science.",
    "I am currently talking with you.",
])
def test_i_am_something_is_not_an_introduction(transcript):
    """Three false names in one live session, each one a hole in the check."""
    assert names.heard(transcript) == {}


def test_a_name_after_i_am_is_still_caught_by_its_capital():
    assert "Ravi" in names.heard("I am Ravi.")
