"""The child's own name, and why the grammar checks must let it through.

Observed live, on the one question Mitra itself had just asked:

    mitra: नमस्ते। तव नाम किम्?          ("what is your name?")
    user:  My name is Tafik.
    mitra: क्षम्यताम्, अहं न अवगच्छामि।   ("sorry, I do not understand")

The model answered correctly — the log shows it wrote तफिकः — and the
vocabulary check rejected the reply because तफिकः is not a Sanskrit word.
Which is true, and beside the point: a name is not supposed to be one. Every
check downstream of the model is built on the premise that the set of words
Mitra may say is closed (``lexicon/vocabulary.py``), and a proper noun is the
one kind of word that arrives from outside that set at runtime, from the
person Mitra is talking to.

So this module answers one question: *is this rejected word the name the user
just gave us?* If it is, the reply is spoken. The name is remembered for the
session, because a child says it once and Mitra may use it several turns later.

Matching is by CONSONANT SKELETON, in either script:

    "Tafik"  → t, f, k   → "tpk"          (f folds to p — फ is both)
    तफिकः    → त, फ, क   → "tpk"          (visarga and vowels ignored)
    तफिकम्   → त, फ, क, म → "tpkm"        (a case ending adds consonants)

Vowels are dropped because that is exactly where the two scripts disagree
(Tafik/Taufiq/तौफ़ीक़), and a case ending is allowed to add up to two
consonants at the end because that is what Sanskrit declension does to a
borrowed name — तफिकम्, तफिकाय, तफिकस्य are the same word.

Deliberately fuzzy, and safe to be: nothing is *checked* here. The skeletons
are consulted only for words some other check has already rejected, so the
worst a false match can do is let one odd word through, while a false miss
costs the child the answer to Mitra's own question.
"""

from __future__ import annotations

import re

# Devanagari consonants → a coarse Latin class. Aspirates fold onto their
# plain counterpart (ख→k) and the sibilants onto one letter (श/ष/स→s): the
# distinctions Sanskrit spells out are precisely the ones an English
# transcription of a name does not make.
_DEVANAGARI = {
    "क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n",
    "च": "k", "छ": "k", "ज": "j", "झ": "j", "ञ": "n",
    "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n",
    "त": "t", "थ": "t", "द": "d", "ध": "d", "न": "n",
    "प": "p", "फ": "p", "ब": "b", "भ": "b", "म": "m",
    "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "s", "ष": "s", "स": "s", "ह": "h",
    # Nukta forms — Whisper writes borrowed names with them (तौफ़ीक़).
    "क़": "k", "ख़": "k", "ग़": "g", "ज़": "j", "ड़": "d", "ढ़": "d",
    "फ़": "p", "य़": "y", "ऩ": "n", "ऱ": "r",
    # Anusvara and chandrabindu: a nasal the Latin spelling writes as a
    # letter and Devanagari writes as a mark. Without it बैंगलोरं reduces to
    # b-g-l-r while "Bangalore" gives b-n-g-l-r, and the place the child just
    # named is rejected as a non-Sanskrit word.
    "\u0902": "n", "\u0901": "n",
}

# Latin, folded onto the same classes. च and क both land on "k", so "ch" and
# "c" do too — "Chetan"/चेतन and "Carl"/कार्ल both work, which spelling-faithful
# mapping would not manage.
_DIGRAPHS = {"ph": "p", "bh": "b", "kh": "k", "gh": "g", "ch": "k",
             "th": "t", "dh": "d", "jh": "j", "sh": "s", "ck": "k",
             "qu": "k"}
_LATIN = {"b": "b", "c": "k", "d": "d", "f": "p", "g": "g", "h": "h",
          "j": "j", "k": "k", "l": "l", "m": "m", "n": "n", "p": "p",
          "q": "k", "r": "r", "s": "s", "t": "t", "v": "v", "w": "v",
          "x": "ks", "y": "y", "z": "j"}

# How many consonants a case ending may add: तफिकस्य is name + स् + य.
_ENDING_SLACK = 2

# Shortest skeleton worth remembering. One consonant matches far too much —
# "Al" would excuse every rejected word beginning with l.
_MIN_SKELETON = 2

_SENTENCE = re.compile(r"[.!?;।॥\n]+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_DEVANAGARI_WORD = re.compile(r"[ऀ-ॣॲ-ॿ]+")

# "My name is Tafik" — the phrasings that make the next word a name whatever
# its capitalisation, which matters because Whisper lower-cases names it does
# not recognise as often as it capitalises them.
#
# Only leads that can be followed by nothing BUT a name. "I am" and "I'm"
# belonged here for one live session and cost three false names — "I'm fine",
# "I am studying", "I am currently" — and a false name is not harmless: it is
# an exemption from the vocabulary check, and the skeleton of "fine" (p-n)
# would have excused पानम्. A name introduced as "I am Ravi" is capitalised
# and mid-sentence, so the rule below still catches it; a name after "my name
# is" cannot be anything else, so this one can ignore capitalisation.
_INTRODUCTION = re.compile(
    r"\b(?:my name is|name is|name's|call me)\s+"
    r"([A-Za-z][A-Za-z'’-]*)", re.IGNORECASE)

# Capitalised words that are not the speaker's name. Short list on purpose:
# a wrong entry here only means one name is not learned, and the same name
# usually arrives again through _INTRODUCTION.
_NOT_A_NAME = frozenset("""
i i'm im mitra namaste hello hi ok okay yes no english sanskrit kannada hindi
india god monday tuesday wednesday thursday friday saturday sunday
january february march april may june july august september october
november december
""".split())


def skeleton(word: str) -> str:
    """The consonants of ``word``, in either script, as one folded string."""
    if not word:
        return ""
    if _DEVANAGARI_WORD.fullmatch(word.strip()):
        return "".join(_DEVANAGARI.get(ch, "") for ch in word)
    out, text, i = [], word.lower(), 0
    while i < len(text):
        pair = text[i:i + 2]
        if pair in _DIGRAPHS:
            out.append(_DIGRAPHS[pair])
            i += 2
            continue
        out.append(_LATIN.get(text[i], ""))
        i += 1
    return "".join(out)


def heard(transcript: str) -> dict[str, str]:
    """Proper nouns in the user's turn, as ``{as spoken: skeleton}``.

    Two ways in: a capitalised word that is not opening a sentence, and
    whatever follows "my name is". Both are needed — Whisper capitalises
    "Tafik" in the middle of a sentence and writes "ravi" at the start of one.
    """
    found: dict[str, str] = {}

    def remember(token: str) -> None:
        skel = skeleton(token)
        if len(skel) >= _MIN_SKELETON:
            found[token] = skel

    for sentence in _SENTENCE.split(transcript or ""):
        for position, token in enumerate(_WORD.findall(sentence)):
            if position == 0 or token.lower() in _NOT_A_NAME:
                continue
            if token[0].isupper() and not token.isupper():
                remember(token)
    for match in _INTRODUCTION.finditer(transcript or ""):
        token = match.group(1)
        if token.lower() not in _NOT_A_NAME:
            remember(token)
    return found


def echoes(word: str, skeletons) -> bool:
    """True if ``word`` is one of these names wearing a Sanskrit ending."""
    found = skeleton(word)
    if len(found) < _MIN_SKELETON:
        return False
    return any(len(candidate) >= _MIN_SKELETON
               and found.startswith(candidate)
               and len(found) - len(candidate) <= _ENDING_SLACK
               for skel in skeletons
               for candidate in _readings(skel))


def _readings(skel: str) -> tuple[str, ...]:
    """A skeleton and, for a name ending in y, the reading without it.

    "Amy" is a-m-y but एमी is just m — a final y is a vowel as often as it is
    a consonant, and which one it was is not recoverable from the spelling.
    """
    if skel.endswith("y") and len(skel) - 1 >= _MIN_SKELETON:
        return (skel, skel[:-1])
    return (skel,)
