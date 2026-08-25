"""Shloka recitation corpus and request detection (FR-3.4 extension).

A third corpus alongside the lexicon ("what is this object called?") and the
phrasebook ("how would a Sanskrit speaker phrase this turn?"). This one answers
"recite something" — and unlike the other two it does not feed the model at
all. The verses reach the speaker exactly as they were written.

That is the whole point. Asked to recite, an 8B model with weak Sanskrit priors
produces something verse-shaped that scans badly and misattributes itself; a
child would learn it as scripture. So recitation is a deterministic path in the
orchestrator (DESIGN §1.4), next to the wake nod and the unintelligible-input
refusal: the model is not consulted, and the reply-side checks are bypassed
because they are the wrong instrument here. ``max_sentences: 1`` would cut the
verse at its internal danda, and the vocabulary check rejects epic Sanskrit
wholesale — correct for generated conversation, nonsense for Bhartṛhari. (The
220-char limit does not clear this corpus at all: three of its 500 verses run
past it, the longest to 237, because a śārdūlavikrīḍita line is four times the
length of an anuṣṭubh half. Which is the point — a gate sized for one spoken
sentence has nothing useful to say about a verse.)

Corpus shape — a JSON array (or JSONL, one object per line) of:

    {"source": "nItizatakam", "source_slug": "nitishatakam",
     "verse_id": "85", "verse_number": 85,
     "verse_text": "आलस्यं हि मनुष्याणां ... कुर्वाणो नावसीदति",
     "attribution": "इति भर्तृहरेः नीतिशतके॥",
     "attribution_iast": "iti bhartṛhareḥ nītiśatake"}

``words`` is accepted and ignored. Only ``verse_text`` and ``attribution`` are
load-bearing.

The two are joined by इति, the quotative particle that already opens every
colophon ("thus, in the Nītiśataka of Bhartṛhari") — no connector is
added, because the corpus ships with the connector built in. What IS added is
the closing ॥ that the verse text omits: the single danda inside a shloka
separates its halves, the double danda closes the whole thing, and that mark is
what the TTS layer turns into the longer silence before the attribution
(``mitra.speech.tts.synthesize_with_pauses``).
"""

from __future__ import annotations

import json
import logging
import random
import re
from collections import deque
from pathlib import Path

logger = logging.getLogger("mitra")

DEFAULT_PATH = "data/shlokas.json"

# How many recent verses to keep out of the draw. A session is short and the
# corpus is ~1000 rows, so this only has to stop the obvious "you just said
# that" — it is not a shuffle-deck.
RECENT_MEMORY = 20

DOUBLE_DANDA = "॥"

# Rows the corpus builder left with editorial apparatus in the verse itself —
# "व्ययं कुर्वन्(र्यात्?)" is an editor asking a question about a manuscript
# reading, not something to recite. No row in the present 500-verse corpus
# trips it — earlier builds had rows that did — but the guard stays:
# it is cheap, it is the next corpus build it protects, and the failure it
# prevents (the robot solemnly reciting a parenthesis) is not cheap.
_APPARATUS = re.compile(r"[()\[\]?*]|[A-Za-z]")

# Trailing terminators are stripped before the closing ॥ is appended. No row in
# the present corpus ends in one, but earlier builds carried rows that did, and
# "... तथा। ॥" would read as a half-verse break immediately followed by a full
# one.
_TRAILING_MARKS = " \t।॥"


# --------------------------------------------------------------- detection

# "Recite a shloka" in the three languages Mitra accepts, plus the romanised
# Sanskrit Whisper actually returns for spoken Sanskrit (it tags it English and
# transliterates without diacritics — see lexicon/phrasebook.py).
#
# Naming the word at all is treated as the request. A person does not say
# "shloka" to a Sanskrit robot for any other reason, and the alternative —
# requiring a verb too — fails on the bare "श्लोकम्?" and on every ASR variant
# of "recite" we have not thought of. False positives cost one verse; false
# negatives cost the feature.
#
# The two optional c's in the romanised branch are that bias applied to what
# Whisper actually returns: asked out loud for a shloka it has transcribed
# "schlocker", hearing a stop on either side of the l. Neither c changes what
# an English word could collide with here, and without them the request misses
# the deterministic path entirely and reaches the model — which then invents a
# verse, exactly the failure this corpus exists to prevent.
_SHLOKA_WORD = re.compile(
    r"श्लोक|सुभाषित"                 # Devanagari: śloka, subhāṣita
    r"|ಶ್ಲೋಕ|ಸುಭಾಷಿತ"                # Kannada
    r"|\b[sśṣ]c?h?l[oō]c?k"      # romanised: shloka, sloka, ślokam, schlocker
    r"|\bsubh[aā][sś]h?it",          # romanised: subhashita, subhāṣita
    re.IGNORECASE,
)

# The English way to ask without using the word: "recite a verse", "say a poem".
# Verb-anchored, because a bare "verse" appears in ordinary questions.
#
# That anchor is also what makes this the right place for a looser spelling of
# the word itself. Standing alone, ``[sśṣ]c?h?[aā]?l[oō]c?kh?`` is more
# licence than _SHLOKA_WORD should take; preceded by "recite", an s-l-o-k
# skeleton can only be one thing, so the second chance costs nothing. It is the
# net under the first pattern: whichever mangling the microphone invents next,
# a request that names a verb still lands on the deterministic path.
_RECITE_VERSE = re.compile(
    r"\b(recite|chant|sing|say|tell|give|read)\b[\w\s,'’’-]{0,30}"
    r"\b(verses?|poems?|couplets?|scriptures?"
    r"|[sśṣ]c?h?[aā]?l[oō]c?kh?\w*"          # shloka, shalokam, schlocker
    r"|subh[aā]?\w{0,2}[sś]h?it\w*)\b",      # subhashita, subhaashitam
    re.IGNORECASE,
)


# Detection is a regex over ASR output, and ASR output is where this feature
# actually breaks. There is no enumerating the manglings in advance, so rather
# than guess the next one, log the turns that came close and missed: a
# recite-verb, or any s-l-k skeleton, in a turn no pattern above claimed. The
# line that results is a list of spellings to add, written by the microphone
# instead of by us. Deliberately loose — "silk", "sleek" and "Slovak" all trip
# it — because a false positive here costs one DEBUG line and a false negative
# costs the next silent miss.
_NEAR_MISS = re.compile(
    r"\b(recite|chant)\b"                 # the verb that means little else
    r"|\b[sśṣ]\w{0,3}l\w{0,3}k\w*",       # schlocker, shalok, sloka
    re.IGNORECASE,
)


def is_recitation_request(text: str) -> bool:
    """True if this turn is asking Mitra to recite a shloka."""
    if not text:
        return False
    return bool(_SHLOKA_WORD.search(text) or _RECITE_VERSE.search(text))


def looks_like_a_near_miss(text: str) -> bool:
    """True if this turn resembles a recitation request nobody recognized.

    Purely diagnostic: the caller logs it and carries on to the model. See
    ``_NEAR_MISS`` for why it is allowed to be wrong.
    """
    if not text:
        return False
    return bool(_NEAR_MISS.search(text)) and not is_recitation_request(text)


# ------------------------------------------------------------- formatting

def format_recitation(row: dict) -> str:
    """One verse plus its colophon, as the line to be spoken.

        पाण्डवानां कुरूणां च ... । ते सेने ... निवेशनम् ॥
        इति महाभारते भीष्मपर्वणि॥

    The newline is for the log and for whoever reads it; the pause that a
    listener hears comes from the ॥, not from the line break.
    """
    verse = row["verse_text"].rstrip(_TRAILING_MARKS)
    attribution = row.get("attribution", "").strip()
    line = f"{verse} {DOUBLE_DANDA}"
    return f"{line}\n{attribution}" if attribution else line


class Shlokas:
    """Random draw over a verse corpus, avoiding recent repeats.

    An absent or unreadable corpus is not an error: ``count() == 0`` and
    ``pick()`` returns None, and the orchestrator then answers the request the
    ordinary way (the model will apologize, which is the honest outcome when
    there is nothing to recite).
    """

    def __init__(self, path: str | Path = DEFAULT_PATH, rng=None):
        self.path = Path(path)
        self._rng = rng or random.Random()
        self._rows: list[dict] = []
        self._recent: deque[str] = deque(maxlen=RECENT_MEMORY)
        self._load()

    # ------------------------------------------------------------- loading

    def _load(self) -> None:
        if not self.path.exists():
            logger.warning("shloka corpus not found at %s — recitation is off",
                           self.path)
            return
        try:
            raw = self._read_rows()
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("shloka corpus at %s is unreadable (%s) — recitation "
                           "is off", self.path, e)
            return

        skipped = 0
        for row in raw:
            if not isinstance(row, dict):
                skipped += 1
                continue
            verse = str(row.get("verse_text", "")).strip()
            if not verse or _APPARATUS.search(verse):
                skipped += 1
                continue
            self._rows.append(row)
        logger.info("shlokas: %d verses loaded from %s", len(self._rows), self.path)
        if skipped:
            logger.info("shlokas: %d rows skipped (empty or editorial apparatus)",
                        skipped)

    def _read_rows(self) -> list:
        """Accept both a JSON array and JSONL — the corpus arrives as either."""
        text = self.path.read_text(encoding="utf-8").strip()
        if text.startswith("["):
            data = json.loads(text)
            return data if isinstance(data, list) else []
        rows = []
        for line_no, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("shloka corpus line %d is not valid JSON", line_no)
        return rows

    # -------------------------------------------------------------- lookup

    def count(self) -> int:
        return len(self._rows)

    def pick(self) -> dict | None:
        """A verse not recited in the last ``RECENT_MEMORY`` draws, or None."""
        if not self._rows:
            return None
        recent = set(self._recent)
        pool = [r for r in self._rows if _row_id(r) not in recent] or self._rows
        row = self._rng.choice(pool)
        self._recent.append(_row_id(row))
        return row

    def reset(self) -> None:
        """Forget what has been recited (called when a session ends)."""
        self._recent.clear()


def _row_id(row: dict) -> str:
    return f"{row.get('source_slug', '')}:{row.get('verse_id', '')}"
