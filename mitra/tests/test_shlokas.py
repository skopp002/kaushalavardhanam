"""Shloka corpus, request detection, and danda-timed speech."""

import json
import random

import numpy as np
import pytest

from mitra.lexicon import shlokas as sl
from mitra.speech.tts import LINE_PAUSE_S, VERSE_PAUSE_S, synthesize_with_pauses

VERSE = ("पाण्डवानां कुरूणां च परस्परसमागमे । "
         "ते सेने भृशसंविग्ने ययतुः स्वं निवेशनम्")
ROW = {
    "source": "mahAbhAratam", "source_slug": "mahabharatam",
    "verse_id": "6.70.36", "verse_number": 36, "verse_text": VERSE,
    "attribution": "इति महाभारते भीष्मपर्वणि॥",
    "attribution_iast": "iti mahābhārate bhīṣmaparvaṇi",
}


def _corpus(tmp_path, rows, name="shlokas.json"):
    path = tmp_path / name
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


# ----------------------------------------------------------- request detection

@pytest.mark.parametrize("said", [
    "Recite a shloka",
    "can you say a shloka for me",
    "shloka",
    "श्लोकं वद",
    "एकं श्लोकम् उच्चारय",
    "shlokam vada",                      # Whisper's romanised Sanskrit
    "ekam slokam vada",                  # ...without the h
    # Verbatim from a live session: whisper-small hears a stop on either side
    # of the l and spells the word with c's. Undetected, these two reached the
    # model, which invented ungrammatical verse and got refused by the
    # validator — the child heard "sorry, I do not understand".
    "Recite a schlocker.",
    "Reset the schlocker.",
    "ಶ್ಲೋಕ ಹೇಳು",                          # Kannada
    "tell me a subhashita",
    "please recite a verse",
    "Recite a verse",
    # The verb branch is not anchored to the start of the utterance, so the
    # polite framings a person actually uses are prefixes, not special cases.
    "Can you recite a shloka?",
    "Can you recite a verse?",
    "Can you recite a shloka/verse?",
    "could you recite a verse for me",
    "sing me a verse from the Ramayana",
    "recite verses from the Ramayana",     # plural counts too
    # A recite-verb licenses a looser spelling than the bare word may take:
    # whichever mangling comes next, naming a verb still lands on the corpus.
    "sing me a shalokam",
    "chant a subhaashitam",
])
def test_recitation_requests_are_detected(said):
    assert sl.is_recitation_request(said)


@pytest.mark.parametrize("said", [
    "What is your name?",
    "नमस्ते",
    # "verse" alone is not a request — it turns up in ordinary questions.
    "what does the third verse mean in english",
    # The stray c's widen the romanised branch, but not past the word: an s
    # that merely precedes an l or an o still means nothing here.
    "slow down please",
    "close the door",
    # The verb-anchored branch is looser, but still not loose enough to take
    # any s-word that follows a verb.
    "tell me about Slovakia",
    "read the clock please",
    "",
])
def test_ordinary_turns_are_not_recitation_requests(said):
    assert not sl.is_recitation_request(said)


# ------------------------------------------------------------------ near misses

@pytest.mark.parametrize("said", [
    "Recite a schlocker.",
    "Reset the schlocker.",
    "recite a shloka",
    "tell me a subhashita",
])
def test_recognized_requests_are_never_near_misses(said):
    """The breadcrumb is for what the patterns miss, not what they catch."""
    assert not sl.looks_like_a_near_miss(said)


@pytest.mark.parametrize("said", [
    "recite the thing",                   # a verb, and no verse in sight
    "say a shlurka for me",               # an s-l-k skeleton we do not parse
    "sholkam",
])
def test_unrecognized_lookalikes_are_flagged(said):
    assert not sl.is_recitation_request(said)
    assert sl.looks_like_a_near_miss(said)


@pytest.mark.parametrize("said", ["What is your name?", "say hello", "नमस्ते", ""])
def test_ordinary_turns_are_not_near_misses(said):
    assert not sl.looks_like_a_near_miss(said)


# ------------------------------------------------------------------ formatting

def test_format_closes_the_verse_and_appends_the_colophon():
    out = sl.format_recitation(ROW)
    verse_line, attribution = out.split("\n")
    assert verse_line == f"{VERSE} ॥"
    assert attribution == "इति महाभारते भीष्मपर्वणि॥"
    # इति already joins the two — nothing is inserted between them.
    assert out.count("॥") == 2


def test_format_does_not_double_the_terminator():
    """15 of the 629 corpus rows already end in a single danda."""
    row = dict(ROW, verse_text="अध्युवास रथं तत्वरे तथा।")
    assert sl.format_recitation(row).startswith("अध्युवास रथं तत्वरे तथा ॥")


def test_format_survives_a_row_with_no_attribution():
    assert sl.format_recitation({"verse_text": VERSE}) == f"{VERSE} ॥"


# --------------------------------------------------------------------- loading

def test_loads_a_json_array(tmp_path):
    corpus = sl.Shlokas(_corpus(tmp_path, [ROW, dict(ROW, verse_id="1.1.1")]))
    assert corpus.count() == 2


def test_loads_jsonl_too(tmp_path):
    path = tmp_path / "shlokas.jsonl"
    path.write_text("\n".join(json.dumps(ROW, ensure_ascii=False) for _ in range(3)),
                    encoding="utf-8")
    assert sl.Shlokas(path).count() == 3


def test_rows_with_editorial_apparatus_are_skipped(tmp_path):
    apparatus = dict(ROW, verse_id="113",
                     verse_text="आयं पश्यन् व्ययं कुर्वन्(र्यात्?) आयादल्पतरं व्ययम्")
    corpus = sl.Shlokas(_corpus(tmp_path, [ROW, apparatus, dict(ROW, verse_text="")]))
    assert corpus.count() == 1
    assert corpus.pick()["verse_id"] == "6.70.36"


def test_missing_corpus_is_not_an_error(tmp_path):
    corpus = sl.Shlokas(tmp_path / "nope.json")
    assert corpus.count() == 0 and corpus.pick() is None


def test_unreadable_corpus_is_not_an_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("[{oops", encoding="utf-8")
    assert sl.Shlokas(path).count() == 0


def test_pick_avoids_recent_verses(tmp_path):
    rows = [dict(ROW, verse_id=str(i)) for i in range(5)]
    corpus = sl.Shlokas(_corpus(tmp_path, rows), rng=random.Random(0))
    drawn = [corpus.pick()["verse_id"] for _ in range(5)]
    assert len(set(drawn)) == 5           # the whole corpus before any repeat
    corpus.reset()
    assert corpus.pick() is not None      # and reset re-opens the pool


# ------------------------------------------------------------- danda → silence

class _Recorder:
    """Synthesizes 0.1 s per call and remembers what it was given."""

    def __init__(self, samplerate=16000):
        self.texts: list[str] = []
        self.samplerate = samplerate

    def __call__(self, text):
        self.texts.append(text)
        return np.ones(self.samplerate // 10, dtype=np.float32), self.samplerate


def test_single_sentence_reply_passes_through_untouched():
    """An ordinary reply has one danda and must cost one synthesis call."""
    rec = _Recorder()
    wav, sr = synthesize_with_pauses(rec, "मम नाम मित्रम्।")
    assert rec.texts == ["मम नाम मित्रम्।"]      # danda intact, no split
    assert len(wav) == 1600 and sr == 16000     # and no trailing silence


def test_recitation_is_chunked_and_gapped():
    rec = _Recorder()
    wav, sr = synthesize_with_pauses(rec, sl.format_recitation(ROW))

    # Three spoken chunks, none of them carrying a danda into the tokenizer —
    # which is what stops an engine reading ॥ aloud as a word.
    assert rec.texts == [
        "पाण्डवानां कुरूणां च परस्परसमागमे",
        "ते सेने भृशसंविग्ने ययतुः स्वं निवेशनम्",
        "इति महाभारते भीष्मपर्वणि",
    ]
    assert not any("।" in t or "॥" in t for t in rec.texts)

    speech = 3 * (sr // 10)
    gaps = int(LINE_PAUSE_S * sr) + int(VERSE_PAUSE_S * sr)
    assert len(wav) == speech + gaps        # no silence after the final ॥
    assert sr == 16000

    # The half-verse gap is the short one, the colophon gap the long one.
    silent = np.flatnonzero(wav == 0.0)
    runs = np.split(silent, np.flatnonzero(np.diff(silent) != 1) + 1)
    assert [len(r) for r in runs] == [int(LINE_PAUSE_S * sr), int(VERSE_PAUSE_S * sr)]


def test_punctuation_only_chunks_never_reach_the_engine():
    """facebook/mms-tts-hin tokenizes "।" to zero tokens, and a zero-length
    sequence crashes the VITS forward pass — so such a chunk is dropped."""
    rec = _Recorder()
    synthesize_with_pauses(rec, "मित्रम् ॥ ... ॥ इति ॥")
    assert rec.texts == ["मित्रम्", "इति"]


def test_pause_lengths_are_configurable():
    rec = _Recorder()
    wav, sr = synthesize_with_pauses(rec, sl.format_recitation(ROW),
                                     verse_pause_s=0.0, line_pause_s=0.0)
    assert len(wav) == 3 * (sr // 10)
