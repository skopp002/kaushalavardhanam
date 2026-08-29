"""Follow-up questions that keep a session conversational (FR-3.12).

Mitra answers, then invites the next turn. Both halves matter and they come
from different places, which is the whole design here:

- the **answer** is generated (one sentence, FR-3.4) — the model is good at it;
- the **invitation** is retrieved from the hand-verified list below — the model
  is demonstrably bad at it.

That split is not a preference, it is what the logs said. v1.5 removed the
reciprocal question from the prompt because every logged reply appended a stock
"and you?" and *that trailing question carried most of the grammatical errors*
(कथं भवतः? — genitive where nominative belongs) while the answer itself was
usually sound. Asking again by loosening the prompt would buy back the same
bug. So the question is not generated at all: it is drawn from a short list of
sentences a human wrote and checked, appended after validation, and therefore
correct by construction. Same move the lexicon makes for object names and the
shloka corpus makes for verse (DESIGN §1.4) — where the model is weak and the
set of right answers is small, keep the set.

Coherence, not just liveliness. Three things connect the invitation to the
conversation instead of leaving it a non-sequitur:

1. the question is chosen by keyword overlap with what was just said, so an
   exchange about food is followed by a question about food;
2. the orchestrator remembers what was asked and tells the model on the next
   turn (``prompts.ASKED_HEADER``) — without that the model sees a bare "Ravi"
   answering a question it never knew was put, and replies to nothing;
3. when the child ANSWERS, the next question goes one step further into the
   same subject (``deepen``) instead of starting a new one.

Point 3 is what makes a session read as a conversation rather than a form.
A logged run asked "what do you like?", was told, and answered with the stock
"अधिकं वद।" ("tell me more") — true to the thread but empty, and a session of
those is an interviewer with no interest in the answers. The same turn now
asks "तत् तुभ्यं किमर्थं रोचते?" ("why do you like that?"), which can only be
asked because the subject was raised one turn ago. Two steps per subject is
the whole depth on offer, and the generic continuations below take over
afterwards — a third "why?" about the same thing is an interrogation again.

Nothing here is spoken unless the question is on this list, so extending Mitra's
conversational range means adding a row, having a Sanskrit reader check it, and
nothing else.
"""

from __future__ import annotations

import logging
import random
import re

logger = logging.getLogger("mitra")

# Sentence terminators a reply may already carry (Devanagari and Latin).
_TERMINATORS = "।॥?!"

# Interrogatives. Presence of one means the line is already a question and
# needs no invitation appended — Sanskrit questions are marked by the word,
# not by punctuation, so "?" alone would miss most of them.
#
# Whole tokens only: किमपि ("something") is one token and is correctly absent,
# and वा is here because "… वा?" is how a yes/no question is put — it also
# means "or", so a reply listing alternatives is read as a question and goes
# uninvited. Erring that way is right: a missed invitation costs one flat
# turn, a wrongly-appended one asks a question on top of a question.
_QUESTION_WORDS = frozenset("""
किम् किं कः का के कौ कस्य कस्मै कस्मात् केन कया कस्मिन्
कुत्र कुतः कदा कथम् कथं किमर्थम् कति कीदृशम् कीदृशः वा
""".split())

_WORD = re.compile(r"[\u0900-\u0963\u0972-\u097F]+")

# Is the user TELLING us about themselves, or asking us? The distinction decides
# whether a topic is still worth asking about. "What is your favourite food?"
# invites the question back; "My favourite food is milk" has already answered it,
# and asking anyway is what made a live session read as an interrogation:
#
#   user:  My favorite food is milk. What's yours?
#   mitra: … तुभ्यं किं रोचते?          ("what do you like?" — they just said)
#   user:  I will now be working on my project. What will you do?
#   mitra: … त्वं किं करोषि?            ("what are you doing?" — they just said)
#
# Deliberately crude, and biased towards treating a turn as telling: a missed
# topic costs one repeated question, while a false "telling" only steers the
# choice to a different question, all of which are fine to ask.
_CLAUSE = re.compile(r"[.?!;।॥]+")

_TELLING = re.compile(
    r"\b(i|i'm|im|i've|my|mine|me|we|our)\b"     # English
    r"|अहं|अहम्|मम|मह्यम्|मे|मया"                    # Sanskrit
    r"|ನಾನು|ನನ್ನ|ನನಗೆ",                             # Kannada
    re.IGNORECASE)

# Rows marked ``cue_only`` are never drawn at random: they presume something
# about the turn, and asked out of nowhere they read as non-sequiturs. Observed
# live — asked "Where do you live?", Mitra answered and then asked "अन्यत् किं
# दर्शयसि?" ("what else will you show me?") when nothing had been shown at all.
# Such a row is eligible only when its own topic is requested or one of its
# keywords actually appears in the turn. Every other row is context-free by
# construction: "तव प्रियं भोजनं किम्?" is a fair question at any moment.

# The list itself. Every row is simple laukika Sanskrit, addressed to the child
# as त्वम् rather than भवान्/भवती — the polite forms carry gender and Mitra does
# not know the speaker's. IAST and English are for the reviewer and the debug
# log; only ``question`` is ever spoken.
#
# ``keywords`` are matched, lowercased, as substrings of the user's transcript
# and of Mitra's own reply — English for what the child said, Devanagari stems
# for what Mitra said. Stems, not words: पठ matches पठामि and पठसि alike.
#
# ``deepen`` holds the questions to ask once this row's own question HAS been
# asked and answered — the second and third turn of the same subject. Each one
# is written to make sense only in that position: "तत् मधुरम् अस्ति वा?" ("is
# it sweet?") is a good question after "what is your favourite food?" and
# nonsense anywhere else, which is why these are not rows in their own right
# and are never drawn at random. Same review bar as the rest of the file:
# hand-written Sanskrit with its gloss, appended after validation, never
# generated.
ROWS: tuple[dict, ...] = (
    {"question": "तव नाम किम्?", "iast": "tava nāma kim?",
     "english": "What is your name?", "topics": ("greeting",),
     "keywords": ("name", "call you", "नाम"),
     "deepen": (
         {"question": "त्वं कुत्र वससि?", "iast": "tvaṃ kutra vasasi?",
          "english": "Where do you live?"},
         {"question": "तव मित्रस्य नाम किम्?", "iast": "tava mitrasya nāma kim?",
          "english": "What is your friend's name?"},
     )},
    {"question": "त्वं कथम् असि?", "iast": "tvaṃ katham asi?",
     "english": "How are you?", "topics": ("greeting",),
     "keywords": ("how are you", "hello", "hi ", "namaste", "i'm fine", "im fine",
                  "i am fine", "कुशल", "नमस्ते"),
     "deepen": (
         {"question": "तव दिनं कथम् अस्ति?", "iast": "tava dinaṃ katham asti?",
          "english": "How is your day?"},
         {"question": "अधुना त्वं कुत्र असि?", "iast": "adhunā tvaṃ kutra asi?",
          "english": "Where are you now?"},
     )},
    {"question": "त्वं किं करोषि?", "iast": "tvaṃ kiṃ karoṣi?",
     "english": "What are you doing?", "topics": (),
     "keywords": ("doing", "do you do", "work", "करोमि", "करोषि", "कार्य"),
     "deepen": (
         {"question": "त्वं तत् प्रतिदिनं करोषि वा?",
          "iast": "tvaṃ tat pratidinaṃ karoṣi vā?",
          "english": "Do you do that every day?"},
         {"question": "तत् कठिनम् अस्ति वा?", "iast": "tat kaṭhinam asti vā?",
          "english": "Is that difficult?"},
     )},
    {"question": "तुभ्यं किं रोचते?", "iast": "tubhyaṃ kiṃ rocate?",
     "english": "What do you like?", "topics": (),
     "keywords": ("like", "favourite", "favorite", "love", "रोचते", "प्रिय"),
     "deepen": (
         {"question": "तत् तुभ्यं किमर्थं रोचते?",
          "iast": "tat tubhyaṃ kimarthaṃ rocate?",
          "english": "Why do you like that?"},
         {"question": "अन्यत् किं तुभ्यं रोचते?",
          "iast": "anyat kiṃ tubhyaṃ rocate?",
          "english": "What else do you like?"},
     )},
    {"question": "तव प्रियं भोजनं किम्?", "iast": "tava priyaṃ bhojanaṃ kim?",
     "english": "What is your favourite food?", "topics": (),
     "keywords": ("food", "eat", "hungry", "fruit", "milk",
                  "भोजन", "खाद", "अन्न", "फल", "दुग्ध"),
     "deepen": (
         {"question": "तत् मधुरम् अस्ति वा?", "iast": "tat madhuram asti vā?",
          "english": "Is it sweet?"},
         {"question": "कः तत् पचति?", "iast": "kaḥ tat pacati?",
          "english": "Who cooks it?"},
     )},
    {"question": "त्वं किं पठसि?", "iast": "tvaṃ kiṃ paṭhasi?",
     "english": "What are you studying?", "topics": (),
     # "subject", "maths" and "science" are here because a child asking
     # "what's your favourite subject?" matched nothing, and a turn that
     # matches nothing is answered by a random question — live, that one drew
     # "who is at your home?".
     "keywords": ("read", "study", "school", "book", "learn", "teacher",
                  "subject", "class", "maths", "math", "science",
                  "पठ", "पुस्तक", "विद्याल", "शाला", "गुरु", "गणित"),
     "deepen": (
         {"question": "तव प्रियः विषयः कः?", "iast": "tava priyaḥ viṣayaḥ kaḥ?",
          "english": "What is your favourite subject?"},
         {"question": "तव गुरोः नाम किम्?", "iast": "tava guroḥ nāma kim?",
          "english": "What is your teacher's name?"},
     )},
    {"question": "त्वं किं क्रीडसि?", "iast": "tvaṃ kiṃ krīḍasi?",
     "english": "What do you play?", "topics": (),
     "keywords": ("play", "game", "sport", "क्रीड"),
     "deepen": (
         {"question": "त्वं केन सह क्रीडसि?", "iast": "tvaṃ kena saha krīḍasi?",
          "english": "Who do you play with?"},
         {"question": "त्वं कुत्र क्रीडसि?", "iast": "tvaṃ kutra krīḍasi?",
          "english": "Where do you play?"},
     )},
    {"question": "तव गृहे के सन्ति?", "iast": "tava gṛhe ke santi?",
     "english": "Who is at your home?", "topics": (),
     "keywords": ("home", "house", "family", "mother", "father", "brother",
                  "sister", "गृह", "माता", "पित", "भ्रात", "भगिन"),
     "deepen": (
         # "What do they do?" goes second: asked first it presumes the answer
         # named people, and live it followed "I love all of my home" — which
         # named nobody.
         {"question": "तव गृहं कुत्र अस्ति?", "iast": "tava gṛhaṃ kutra asti?",
          "english": "Where is your home?"},
         {"question": "ते किं कुर्वन्ति?", "iast": "te kiṃ kurvanti?",
          "english": "What do they do?"},
     )},
    {"question": "तव प्रियः पशुः कः?", "iast": "tava priyaḥ paśuḥ kaḥ?",
     "english": "Which animal do you like?", "topics": (),
     "keywords": ("animal", "dog", "cat", "bird", "cow",
                  "पशु", "श्वान", "मार्जार", "खग", "गौ"),
     "deepen": (
         {"question": "सः कुत्र वसति?", "iast": "saḥ kutra vasati?",
          "english": "Where does it live?"},
         {"question": "तव गृहे पशुः अस्ति वा?", "iast": "tava gṛhe paśuḥ asti vā?",
          "english": "Is there an animal at your home?"},
     )},
    {"question": "अन्यत् किं दर्शयसि?", "iast": "anyat kiṃ darśayasi?",
     "english": "What else will you show me?", "topics": (), "cue_only": True,
     "keywords": ("what is this", "show", "look at", "दर्शय", "एतत्"),
     "deepen": (
         {"question": "एतत् तव अस्ति वा?", "iast": "etat tava asti vā?",
          "english": "Is this yours?"},
     )},
    {"question": "अद्य त्वं किं करिष्यसि?", "iast": "adya tvaṃ kiṃ kariṣyasi?",
     "english": "What will you do today?", "topics": (),
     "keywords": ("today", "tomorrow", "morning", "evening",
                  "अद्य", "श्वः", "प्रातः", "सायं", "दिन"),
     "deepen": (
         {"question": "त्वं तत् कुत्र करिष्यसि?", "iast": "tvaṃ tat kutra kariṣyasi?",
          "english": "Where will you do that?"},
         {"question": "श्वः त्वं किं करिष्यसि?", "iast": "śvaḥ tvaṃ kiṃ kariṣyasi?",
          "english": "What will you do tomorrow?"},
     )},
    {"question": "बहिः किं पश्यसि?", "iast": "bahiḥ kiṃ paśyasi?",
     "english": "What do you see outside?", "topics": (),
     "keywords": ("outside", "sun", "sky", "rain", "tree", "flower",
                  "सूर्य", "आकाश", "वृक्ष", "वृष्टि", "पुष्प"),
     "deepen": (
         {"question": "तत् सुन्दरम् अस्ति वा?", "iast": "tat sundaram asti vā?",
          "english": "Is it beautiful?"},
         {"question": "अद्य वर्षा अस्ति वा?", "iast": "adya varṣā asti vā?",
          "english": "Is it raining today?"},
     )},
    {"question": "एषः श्लोकः तुभ्यं रोचते वा?", "iast": "eṣaḥ ślokaḥ tubhyaṃ rocate vā?",
     "english": "Did you like this verse?", "topics": ("shloka",),
     "cue_only": True, "keywords": (),
     "deepen": (
         # ``offers: verse`` is read by the orchestrator: "आम्" to this one is
         # a request for another verse, and is answered from the corpus rather
         # than by the model (OFFERS_VERSE below).
         {"question": "अन्यं श्लोकं श्रोतुम् इच्छसि वा?",
          "iast": "anyaṃ ślokaṃ śrotum icchasi vā?",
          "english": "Do you want to hear another verse?", "offers": "verse"},
         # NOT "do you know what it means?": measured live, the model
         # answers a request to explain a verse either with the wrong verse
         # or with a wrong meaning, and a wrong gloss taught as scripture is
         # the failure the corpus exists to prevent. This one hands the turn
         # back to the child instead, where the answer is theirs to give.
         {"question": "त्वम् अपि श्लोकं जानासि वा?",
          "iast": "tvam api ślokaṃ jānāsi vā?",
          "english": "Do you know a verse too?"},
     )},
)


def _offering(kind: str) -> frozenset:
    """Questions that promise something Mitra must then actually do."""
    return frozenset(entry["question"] for row in ROWS
                     for entry in (row, *row.get("deepen", ()))
                     if entry.get("offers") == kind)


# The invitations whose answer is a verse, not a sentence. An offer nobody can
# accept is worse than no offer: asked "shall I recite another?", a child says
# "yes", and without this the turn reaches the model, which has no verse to
# give and apologizes for a question Mitra itself put.
OFFERS_VERSE = _offering("verse")


# Questions that continue whatever was just said instead of starting a new
# subject. Every one of them refers to the turn by तत् ("that") or by nothing at
# all, so none of them needs to know the topic — which is exactly why they can
# follow a sentence the fixed list above has no question for.
#
# Drawn when the user TELLS rather than asks (see ``asks_something``). They are
# outside ROWS on purpose: they carry no keywords, they are never "covered" by
# what the user has said, and they may recur across a session — "why?" asked
# twice about two different things is two different questions, while "what is
# your name?" asked twice is a robot that was not listening.
# Reached only when the subject has no deepening left (or none was open), so
# these stay what they always were: the floor under the conversation, not its
# usual next step.
CONTINUATIONS: tuple[dict, ...] = (
    {"question": "किमर्थम्?", "iast": "kimartham?", "english": "Why?"},
    {"question": "ततः किम्?", "iast": "tataḥ kim?", "english": "And then?"},
    {"question": "तत् तुभ्यं रोचते वा?", "iast": "tat tubhyaṃ rocate vā?",
     "english": "Do you like that?"},
    {"question": "तत् कीदृशम्?", "iast": "tat kīdṛśam?", "english": "What is that like?"},
    {"question": "अधिकं वद।", "iast": "adhikaṃ vada.", "english": "Tell me more."},
)


def spoken_questions() -> tuple[str, ...]:
    """Every question in this file, in the order they are written.

    Read by the vocabulary builder (``lexicon/vocabulary.py``). Mitra asking
    "तव प्रियः पशुः कः?" and then being unable to SAY पशु is not a defensible
    state, and it is the one this exports to prevent: live, the question was
    asked, the child named an animal, and the reply was rejected for using the
    word the question had just used. Everything here is hand-verified, which
    is the same warrant the phrasebook and the seed lexicon carry.
    """
    return tuple([row["question"] for row in ROWS]
                 + [entry["question"] for row in ROWS
                    for entry in row.get("deepen", ())]
                 + [row["question"] for row in CONTINUATIONS])


def has_question(text: str) -> bool:
    """True if this line already asks something, in Sanskrit or in English."""
    if not text:
        return False
    if "?" in text:
        return True
    return any(word in _QUESTION_WORDS for word in _WORD.findall(text))


def join_question(reply: str, question: str) -> str:
    """``reply`` followed by ``question``, with a danda between them if needed.

    Mitra's shortest lines (नमस्ते) carry no terminator, and running one
    straight into a question would make the two read as a single sentence.
    """
    reply = reply.rstrip()
    if not reply:
        return question
    if reply[-1] not in _TERMINATORS:
        reply += "।"
    return f"{reply} {question}"


# Did the user ASK something, or TELL us something? The two want opposite
# follow-ups, and getting it backwards is what made a live session read as a
# list of unrelated topics:
#
#   user:  I'll do some work today.        (telling)
#   mitra: … तव गृहे के सन्ति?              ("who is at your home?" — new subject)
#   user:  at home.                        (answering)
#   mitra: … तव नाम किम्?                   ("what is your name?" — new subject again)
#
# A question from the user opens a subject, so answering it and opening one back
# is conversation. A statement continues a subject, and changing it there drops
# the thread the person was pulling on. Whisper punctuates questions reliably,
# and the wh-words are the net under that.
_ASKS = re.compile(
    r"\?"                                                     # any script
    r"|\b(what|which|who|whom|whose|where|when|why|how"
    r"|do you|did you|are you|can you|will you|would you|have you|tell me)\b"
    r"|किम्|किं|कः|का|कुत्र|कदा|कथम्|कथं|किमर्थम्"                  # Sanskrit
    r"|ಏನು|ಯಾರು|ಎಲ್ಲಿ|ಯಾವಾಗ|ಹೇಗೆ|ಏಕೆ",                          # Kannada
    re.IGNORECASE)


def asks_something(text: str) -> bool:
    """True if the user's turn puts a question, in any of the three languages."""
    return bool(text) and bool(_ASKS.search(text))


# "Yes" — to an offer Mitra made, and only ever read in that context (see
# ``OFFERS_VERSE`` and the orchestrator's ``_accepted_a_verse``). A yes/no
# question in Sanskrit is answered with आम् or बाढम्; a child answering an
# English prompt says anything from "yes" to "one more".
_AFFIRMATIVE = re.compile(
    r"\b(yes|yeah|yep|yup|sure|ok|okay|please|another|more|again|go ahead"
    r"|of course|absolutely|do it|i do|i would|why not)\b"
    r"|आम्|बाढम्|अस्तु|आम"
    r"|ಹೌದು|ಸರಿ|ಆಗಲಿ",
    re.IGNORECASE)

# ...unless it is a refusal wearing the same words ("no, not again"). Read
# first, because "no thanks" contains no affirmative but "not okay" does.
_NEGATIVE = re.compile(
    r"\b(no|nope|not|don't|dont|stop|enough|later|never)\b"
    r"|न इच्छामि|मा"
    r"|ಇಲ್ಲ|ಬೇಡ",
    re.IGNORECASE)


def is_affirmative(text: str) -> bool:
    """True if this turn accepts what Mitra just offered."""
    if not text or _NEGATIVE.search(text):
        return False
    return bool(_AFFIRMATIVE.search(text))


class Followups:
    """The invitation list, with topical choice and no repeats in a session.

    Constructed with no arguments in production; ``rows`` and ``rng`` exist so
    tests can pin both. Like the phrasebook and the shloka corpus, absence is a
    supported state: the orchestrator holds ``None`` here and simply speaks the
    answer on its own, exactly as it did before this layer existed.
    """

    def __init__(self, rows=ROWS, rng=None, continuations=CONTINUATIONS):
        self._rows = [r for r in rows if r.get("question")]
        self._rng = rng or random.Random()
        self._asked: set[str] = set()
        self._covered: set[str] = set()
        self._continuations = [r for r in continuations if r.get("question")]
        self._last_continuation: str | None = None
        # The row whose question is outstanding — the subject currently open.
        # An answer to it is what makes that row's ``deepen`` questions
        # askable, and nothing else does.
        self._last_row: dict | None = None

    def count(self) -> int:
        return len(self._rows)

    def continuation_count(self) -> int:
        return len(self._continuations)

    def deepening_count(self) -> int:
        """Follow-on questions behind the rows: how deep a subject can go."""
        return sum(len(row.get("deepen", ())) for row in self._rows)

    def observe(self, transcript: str) -> None:
        """Note what the user has told us, so we never ask them for it.

        Called once per accepted turn, before ``pick``. Session-scoped: the
        user who says their name at turn two should not be asked for it at turn
        nine, which no per-turn check can prevent.
        """
        # Clause by clause, not turn by turn. "I'm fine. What's your favourite
        # food?" carries both halves at once: the first-person marker belongs
        # to "fine", the food is a QUESTION, and reading the turn as a whole
        # retired the food question the user was inviting.
        clauses = [c.strip() for c in _CLAUSE.split((transcript or "").lower())]

        # A subject the user ASKS about in this turn survives, whatever else
        # they say in it. "I play chess. What games do you play?" tells us
        # about playing in its first clause and asks about it in its second,
        # and retiring the question there left Mitra with nothing on topic to
        # ask — live, it answered a question about games by asking whether the
        # child's food was sweet.
        invited = {row["question"] for clause in clauses if clause
                   and asks_something(clause)
                   for row in self._rows if _hits(row, clause)}

        for clause in clauses:
            if not clause or asks_something(clause) or not _TELLING.search(clause):
                continue
            for row in self._rows:
                if _hits(row, clause) and row["question"] not in invited:
                    self._covered.add(row["question"])

    def pick(self, *, transcript: str = "", reply: str = "",
             topic: str | None = None, continuing: bool = False) -> str | None:
        """The question to ask next, or None when there is nothing to ask.

        ``continuing`` says the user was telling us something rather than
        asking, so the turn wants a question ABOUT what they said, not a new
        subject — that is the difference between a conversation and a
        questionnaire. It is answered first by the open subject's own next
        step (``deepen``) and only then by a generic continuation. A requested
        ``topic`` still wins, since a recitation needs its own question either
        way.

        Otherwise: topic beats keywords beats chance, and an unasked question beats one
        already used this session — a child noticing that Mitra asks the same
        thing twice is the failure this ordering avoids. Questions the user has
        already answered unprompted (``observe``) are out of the running
        altogether.
        """
        if continuing and topic is None:
            deeper = self._deepen()
            if deeper is not None:
                return deeper
            if self._continuations:
                return self._continue()
        haystack = f"{transcript}\n{reply}".lower()
        pool = self._pool(topic, haystack)
        if not pool:
            return None
        fresh = [row for row in pool if row["question"] not in self._asked]
        if not fresh:
            # A requested topic must be answered from that topic, and the
            # recitation topic comes round every verse — so a repeat there is
            # met with the subject's next step rather than the same sentence
            # twice ("did you like this verse?" after every shloka).
            if topic is not None:
                for row in pool:
                    deeper = self._deepen(row)
                    if deeper is not None:
                        return deeper
            # Everything eligible has been asked. Start the rotation over
            # rather than falling silent: a turn that ends without an invitation
            # is the one thing this layer exists to prevent (FR-3.12).
            self._asked.clear()
            fresh = pool
        row, hits = self._best(fresh, haystack)
        if hits == 0 and topic is None:
            # Nothing in the pool has anything to do with this turn, so the
            # draw is about to be a coin flip — and a coin flip is where a
            # session stops being a conversation. Live: asked "how are you?",
            # Mitra answered and asked which animal the child liked; asked
            # "what is your favourite subject?", it asked what they could see
            # outside. The subject already open is a better answer than
            # chance, so its next step wins whenever nothing else connects.
            deeper = self._deepen()
            if deeper is not None:
                return deeper
        return self._ask(row)

    def reset(self) -> None:
        """Forget the session — what was asked and what was told (FR-3.3)."""
        self._asked.clear()
        self._covered.clear()
        self._last_continuation = None
        self._last_row = None

    def _ask(self, row: dict) -> str:
        """Open this row's subject and remember that it is the open one."""
        self._asked.add(row["question"])
        self._last_row = row
        logger.debug("follow-up: %s (%s)", row["iast"], row["english"])
        return row["question"]

    def _deepen(self, row: dict | None = None) -> str | None:
        """The next step into a subject already opened — by default the open one.

        Deepenings are reachable only from here, never from the ordinary draw:
        each is written to follow its own row and would be a non-sequitur cold
        ("तत् मधुरम् अस्ति वा?" asked of nothing). None when the subject is
        spent or none is open, and the caller then falls back to a
        continuation.
        """
        row = row if row is not None else self._last_row
        if row is None:
            return None
        entry = next((d for d in row.get("deepen", ())
                      if d["question"] not in self._asked), None)
        if entry is None:
            return None
        self._asked.add(entry["question"])
        # The subject stays open, so two answers in a row walk two steps down
        # the same list — which is the point.
        self._last_row = row
        logger.debug("follow-up (deeper): %s (%s)", entry["iast"], entry["english"])
        return entry["question"]

    def _continue(self) -> str:
        """A question about what was just said, never the one used last turn."""
        fresh = [r for r in self._continuations
                 if r["question"] != self._last_continuation] or self._continuations
        row = self._rng.choice(fresh)
        self._last_continuation = row["question"]
        # The subject is closed: its deepenings are spent, and a "why?" asked
        # now belongs to whatever the child says next, not to the old row.
        self._last_row = None
        logger.debug("follow-up (continuing): %s (%s)", row["iast"], row["english"])
        return row["question"]

    # ---------------------------------------------------------------- choice

    def _pool(self, topic: str | None, haystack: str) -> list[dict]:
        if topic is not None:
            matching = [r for r in self._rows if topic in r["topics"]]
            if matching:
                return matching
        eligible = [r for r in self._rows
                    if not r.get("cue_only") or _hits(r, haystack)]
        # Covered topics drop out — unless that empties the pool, in which case
        # a question the user has answered still beats no question at all.
        return [r for r in eligible
                if r["question"] not in self._covered] or eligible

    def _best(self, rows: list[dict], haystack: str) -> tuple[dict, int]:
        """Most keyword hits, ties broken at random so sessions do not rhyme.

        The score comes back with the row: zero means nothing in the pool is
        about this turn, and the caller has a better move than a random draw.
        """
        best = max(_hits(r, haystack) for r in rows)
        return self._rng.choice(
            rows if best == 0
            else [r for r in rows if _hits(r, haystack) == best]), best


def _hits(row: dict, haystack: str) -> int:
    return sum(1 for keyword in row["keywords"] if keyword in haystack)
