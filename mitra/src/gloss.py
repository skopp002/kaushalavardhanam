"""Debug-only English gloss of what Mitra says (FR-7.2).

The console log shows the Devanagari the robot is about to speak, which is
exactly what an operator who does not read Sanskrit cannot check. This
translates each spoken line back into English for the log:

    INFO mitra: speak: मह्यं गणितं रोचते।
    INFO mitra: speak (en): Mathematics is pleasing to me.

Deliberately a SECOND, history-free model call rather than asking the agent
for its own translation, and deliberately not a phrasebook lookup:

* Asking the agent to append an English gloss would put English in the
  conversation history it imitates, and the one hard rule is Sanskrit-only
  output (prompts §1). The gloss must not be able to leak into speech.
* A nearest-phrasebook-row gloss would report the corpus sentence the model
  was steered by, not the sentence it actually produced — so a mangled reply
  would read as correct English. That defeats the only reason to log this.

The translator therefore renders the reply literally, warts included, and
runs off the speaking path AND off the run loop (Orchestrator._gloss_async):
the call happens after playback has started, on a worker thread, so it costs
log latency and nothing else. Inline it cost far more than latency — holding
the run-loop thread for the length of a model call left the state machine in
WAKING/SPEAKING, where the microphone is routed to the wake detector, so a
user answering Mitra's question had that answer discarded as a failed wake
match.

The fixed phrases and the follow-up questions are glossed from a table rather
than by the model, and a line made of both — the wake greeting is — needs no
call at all.
"""

from __future__ import annotations

import logging
import re

from mitra.agent import followups, prompts

GLOSS_SYSTEM_PROMPT = """\
You are a Sanskrit-to-English translation tool. The user sends one Sanskrit \
sentence; you reply with its English translation and nothing else.

Rules:
1. Output ONE line of plain English. No transliteration, no quotes, no notes, \
no explanation, no restating the Sanskrit.
2. Translate LITERALLY what the sentence actually says, including its errors. \
If it is ungrammatical, nonsensical, or says something odd, render that \
faithfully — never repair it into the sentence you think was intended.
3. If a word is not Sanskrit (e.g. Hindi), translate it and mark it, like: \
today [Hindi].

Examples:
मम नाम मित्रम्। -> My name is Mitra.
अहं क्रीडां करोमि। -> I play.
अहं गणितं प्रियम् अस्मि। -> I am dear mathematics.
अहं आज पठामि। -> I read today [आज is Hindi].
"""

# Fixed phrases the orchestrator speaks itself (prompts.py). Glossing them
# through the model would spend a call per turn on strings whose English is
# already known — and known better than an 8B model would render it.
FIXED_GLOSSES = {
    prompts.GREETING: "Hello.",
    prompts.FAREWELL: "See you again.",
    prompts.APOLOGY_RETRY: "Sorry, please say that again.",
    prompts.APOLOGY_SHOW_AGAIN: "Please show me again.",
    prompts.SAFE_FALLBACK: "Sorry, I do not understand.",
    # The follow-up questions ship with their own English (followups.py), so
    # the half of every reply that Mitra did not generate costs nothing to
    # log. This matters most at wake, where the whole line — greeting plus
    # question — is fixed text and needs no model call at all.
    **{row["question"]: row["english"] for row in followups.ROWS},
}

# Trailing dandas are not part of a phrase's identity: join_question() adds one
# to a reply that lacks a terminator, which turned the cached "नमस्ते" into an
# uncached "नमस्ते।" and bought a model call for a line whose English is a
# constant.
_TERMINATORS = " ।॥"

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# One session speaks a bounded number of distinct lines, but nothing enforces
# that — cap the cache so a long run cannot grow it without limit.
_MAX_CACHE = 256


class Glosser:
    """Translates spoken Sanskrit to English for the debug log.

    ``agent_factory`` is called lazily on first use and must return an object
    with ``converse(str) -> str`` and ``reset()`` — a plain MitraAgent with no
    tools. It is lazy so that enabling the gloss costs nothing until Mitra
    actually says something, and reset between calls so each translation sees
    one sentence and no conversation.
    """

    def __init__(self, agent_factory, logger: logging.Logger | None = None):
        self._agent_factory = agent_factory
        self._agent = None
        self.logger = logger or logging.getLogger("mitra")
        self._cache: dict[str, str] = dict(FIXED_GLOSSES)
        self._enabled = True

    def gloss(self, text: str) -> str | None:
        """English for ``text``, or None if unavailable or not needed."""
        text = (text or "").strip()
        if not text or not _DEVANAGARI.search(text):
            # Nothing to translate: an [explain_in_english] turn already
            # answered in English, and the log line carries it verbatim.
            return None
        cached = self._cached(text)
        if cached is not None:
            return cached
        head, tail_en = self._known_question(text)
        if tail_en is not None:
            # "<generated answer> <verified question>" — translate only the half
            # that varies and paste the known English of the other.
            head_en = self.gloss(head) if head else None
            english = f"{head_en} {tail_en}" if head_en else tail_en
            self._remember(text, english)
            return english
        if not self._enabled:
            return None
        try:
            if self._agent is None:
                self._agent = self._agent_factory()
            raw = self._agent.converse(text)
            self._agent.reset()
        except Exception:
            # A gloss is an operator convenience; it must never take a turn
            # down. One failure disables it for the run rather than paying
            # the same failure on every line spoken afterwards.
            self.logger.exception("English gloss failed — disabling for this run")
            self._enabled = False
            return None
        english = _first_line(raw)
        if not english:
            return None
        self._remember(text, english)
        return english

    def _cached(self, text: str) -> str | None:
        return (self._cache.get(text)
                or self._cache.get(text.rstrip(_TERMINATORS)))

    def _remember(self, text: str, english: str) -> None:
        if len(self._cache) < _MAX_CACHE:
            self._cache[text] = english

    @staticmethod
    def _known_question(text: str) -> tuple[str, str | None]:
        """Split a line into (everything else, English of its fixed question).

        Returns ``(text, None)`` when the line does not end in one of the
        verified follow-up questions.
        """
        for row in followups.ROWS:
            question = row["question"]
            if text.endswith(question) and len(text) > len(question):
                return text[:-len(question)].strip(), row["english"]
        return text, None


def _first_line(raw: str) -> str:
    """First non-empty line of the model's output, unquoted and capped.

    Instructed to answer with one line, the model still sometimes adds a
    second ("Literal: ..."). The log wants the translation, not the essay.
    """
    for line in str(raw or "").splitlines():
        line = line.strip().strip('"').strip()
        if line:
            return line[:300]
    return ""
