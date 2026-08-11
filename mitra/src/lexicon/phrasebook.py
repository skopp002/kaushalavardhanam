"""Everyday-phrase retrieval for conversational grounding (DESIGN §4).

The lexicon (``store.py``) answers "what is this object called?". This answers
a different question: "how would a Sanskrit speaker phrase this kind of turn?"
Both feed the same agent call, and both exist for the same reason — an 8B
model with weak Sanskrit priors invents word-shaped things when left to
generate freely.

Corpus: संस्कृत व्यवहार साहस्री, ~1000 everyday sentences across 27 situations,
each with an English gloss and (via scripts/build_phrasebook.py) an IAST
transliteration.

Two retrieval keys, because transcripts arrive two ways. Whisper tags spoken
Sanskrit as English and romanises it, so "what is your name" has to match the
English gloss while "Sarvam kushalam" has to match the IAST. Matching on the
gloss alone returns noise for the second kind — which is the kind that matters
most here.

NOTE ON LICENCE: the book is published and copyrighted by Pallava Prakashan
and the transliteration is marked for personal study and research only. Keep
the derived JSONL out of any public repository; ship the loader, not the data.

Deliberately not embeddings: ~1000 rows, one query per turn, and every
megabyte of VRAM is spoken for by the LLM. String similarity is enough and
costs nothing to run.
"""

from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path

logger = logging.getLogger("mitra")

DEFAULT_PATH = "data/phrasebook.jsonl"

# IAST spells with diacritics (kuśalam, bhavān, kathaṃ); Whisper romanises
# without them (kushalam, bhavan, katham). Compared raw, those score too low
# to clear any useful floor, so both sides are folded to plain ASCII first.
# ś/ṣ → "sh" rather than "s" deliberately: that is how Whisper spells them.
_IAST_FOLD = str.maketrans({
    "ā": "a", "ī": "i", "ū": "u", "ṛ": "ri", "ṝ": "ri", "ḷ": "li",
    "ṃ": "m", "ṁ": "m", "ḥ": "h", "ñ": "n", "ṅ": "n", "ṇ": "n",
    "ṭ": "t", "ḍ": "d", "ś": "sh", "ṣ": "sh", "ē": "e", "ō": "o",
})


def _fold(text: str) -> str:
    """Lowercase, strip diacritics, drop punctuation.

    Also removes the danda, which build_phrasebook transliterates as a pipe
    ("dhanyavādaḥ |") and which never appears in a spoken transcript.
    """
    folded = (text or "").lower().translate(_IAST_FOLD)
    return re.sub(r"[^a-z0-9 ]+", " ", folded).strip()


class Phrasebook:
    """Nearest-phrase lookup over (english, iast, sanskrit, chapter) rows.

    Expected JSONL shape, one object per line:
        {"id": "01-0003", "chapter": "शिष्टाचारः",
         "chapter_en": "Common formulas", "sanskrit": "सुप्रभातम्।",
         "iast": "suprabhātam|", "english": "Good morning."}
    """

    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.path = Path(path)
        self._rows: list[dict] = []
        if not self.path.exists():
            # Absent corpus must not break the pipeline: the orchestrator
            # simply runs ungrounded, exactly as it did before this existed.
            logger.warning("phrasebook not found at %s — running ungrounded",
                           self.path)
            return
        no_iast = 0
        with self.path.open(encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("phrasebook line %d is not valid JSON", line_no)
                    continue
                if not (row.get("english") and row.get("sanskrit")):
                    continue
                # Fold once at load, not once per row per query.
                row["_k_en"] = _fold(row.get("english", ""))
                row["_k_ia"] = _fold(row.get("iast", ""))
                if not row["_k_ia"]:
                    no_iast += 1
                self._rows.append(row)
        logger.info("phrasebook: %d entries loaded", len(self._rows))
        if no_iast:
            logger.warning(
                "phrasebook: %d/%d rows have no IAST — romanised Sanskrit "
                "transcripts will not match these. Rebuild with "
                "indic-transliteration installed.", no_iast, len(self._rows))

    def count(self) -> int:
        return len(self._rows)

    def similar(self, query: str, k: int = 3, floor: float = 0.35,
                ceiling: float = 0.82) -> list[dict]:
        """The k closest rows, best first, matched on English gloss OR IAST.

        A row scores as the better of its two keys, so one index serves both
        "how are you" and "kathamasi" without needing to know which kind of
        transcript arrived.

        Utterances often carry more than one sentence ("Namaste. Kathangasi.")
        while rows hold exactly one, and a long query dilutes the ratio against
        every short row. So the query is split on sentence punctuation and each
        part scored separately, with the row keeping its best part.

        ``floor`` matters more than ``k``: three bad matches are worse than
        none, because the model imitates whatever register it is handed.

        ``ceiling`` matters more than either. This corpus holds both halves of
        a conversation, so a near-perfect hit is the user's OWN sentence coming
        back — ask "bhavatah nama kim" and it returns भवतः नाम किं ?. Handing
        that to the model as reference taught it to ask the question back
        instead of answering it. We want the neighbourhood, not the echo.
        """
        parts = [p for p in (_fold(seg) for seg in re.split(r"[.?!।]", query or ""))
                 if len(p) >= 3]
        whole = _fold(query)
        if whole and whole not in parts:
            parts.append(whole)
        if not parts or not self._rows:
            return []

        matcher = SequenceMatcher()
        scored: list[tuple[float, dict]] = []
        for row in self._rows:
            best = 0.0
            for key in (row.get("_k_en"), row.get("_k_ia")):
                if not key:
                    continue
                matcher.set_seq1(key)
                for part in parts:
                    matcher.set_seq2(part)
                    if (matcher.real_quick_ratio() < floor
                            or matcher.quick_ratio() < floor):
                        continue
                    ratio = matcher.ratio()
                    if ratio > best:
                        best = ratio
            if floor <= best <= ceiling:
                scored.append((best, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [row for _score, row in scored[:k]]

    def by_chapter(self, chapter: str) -> list[dict]:
        """All rows from one situation, e.g. for seeding a scripted demo."""
        return [r for r in self._rows if r.get("chapter") == chapter]
