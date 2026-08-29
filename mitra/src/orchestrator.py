"""Orchestrator state machine (DESIGN §3–§4).

States: ASLEEP → WAKING → LISTENING → THINKING → SPEAKING → LISTENING … → ASLEEP.

Single-threaded core: all transitions happen in ``handle_event`` on the run
loop's thread. Two daemon helpers — the audio pump and the playback watcher —
communicate with the core only by putting events on the queue (DESIGN §3).
Tests drive ``handle_event`` directly with fakes; ``run()`` adds the threads.

The agent may call tools itself, but five paths stay deterministic regardless
of model quality (DESIGN §1.4): ``nod`` fires here on wake, unintelligible
transcripts are refused here before the model ever sees them, a request to
recite a shloka is answered from the verse corpus without consulting the model
at all, every generated reply passes the validator and is spoken here, and the
follow-up question that keeps the conversation going is drawn from a verified
list rather than generated (FR-3.12).
"""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

import numpy as np

from mitra import language_detector
from mitra.agent import followups as followup_list
from mitra.agent import names, prompts, validator
from mitra.agent.tools import END_SESSION_SENTINEL
from mitra.audio import TARGET_SAMPLERATE, resample
from mitra.lexicon import shlokas as shloka_corpus
from mitra.speech.tts import LINE_PAUSE_S, VERSE_PAUSE_S, synthesize_with_pauses


# "explain in English" detection (FR-3.2 exception): explicit request only —
# ordinary English questions still get Sanskrit answers.
_EXPLAIN_IN_ENGLISH_RE = re.compile(
    r"in\s+english|english\s*,?\s*please|(explain|meaning|translate|repeat)"
    r"[\w\s,]{0,30}english", re.IGNORECASE)

# Whisper emits these on silence or near-silence regardless of what was said —
# they are training-data artifacts (YouTube captions), not transcriptions.
# Reaching the model with one produces a confident answer to a question the
# user never asked, which is worse than asking them to repeat.
_ASR_HALLUCINATIONS = {
    "thank you", "thank you.", "thanks for watching", "thank you very much",
    "thank you for watching", "thank you for watching!", "you", "bye",
    "please subscribe", "subtitles by the amara.org community",
}

# Below this many characters a transcript carries too little signal to answer.
_MIN_TRANSCRIPT_CHARS = 3

# ...unless Mitra has just asked something, when the answer is expected to be
# short and the outstanding question supplies the context the words lack. "no"
# and "हा" are two characters, and refusing the answer to a question Mitra
# itself put is the most incoherent thing it could do (FR-3.13).
_MIN_ANSWER_CHARS = 2

# Below this many words, a phrasebook lookup is matching on one word and the
# row it finds can be about anything (see _retrieve_examples).
_MIN_RETRIEVAL_WORDS = 3

# Sentence terminators, Devanagari and Latin. Used to hold the reply to
# ``max_sentences`` (DESIGN §1.4: the model is asked for one sentence, and this
# enforces it whether or not it complies).
_SENTENCE_END = re.compile(r"[।॥?!]")

# Wrapper around retrieved phrasing. The wording is load-bearing: labelled only
# as "reference phrasing", an 8B model pastes the nearest line back verbatim —
# we watched it answer "Sarvam kushalam" with "सर्वं कुशलम्।", which is the
# corpus row, not a reply. Naming what to do beats naming what not to do.
#
# Retrieval now resolves a question to its ANSWER rows, so what arrives here is
# reply-shaped and correctly inflected — the one thing an 8B model is worst at
# inventing. The instruction therefore says adapt, not avoid: copying the
# grammar is the point, copying the content is not. Rows carry "fill" where the
# book left a blank, which must never be spoken.
_REFERENCE_HEADER = (
    "\n[Example Sanskrit replies of the right register. Follow their grammar "
    "and style, but write your OWN sentence about what the user actually said "
    "— never repeat one word-for-word, and never say the word \"fill\"]\n"
)


# Fixed phrases that must never carry a follow-up question. Every one of them
# is Mitra saying it did not understand, and each already asks for the same
# thing a follow-up would: another try. Observed live, the alternative reads as
# a robot that has stopped listening — "क्षम्यताम्, अहं न अवगच्छामि। तव गृहे के
# सन्ति?" ("Sorry, I do not understand. Who is at your home?"). Matched by
# value rather than by call site because these are spoken from four different
# paths (transcript refused, agent raised, validation failed twice, tool error).
_NO_INVITE_AFTER = frozenset({
    prompts.APOLOGY_RETRY, prompts.APOLOGY_SHOW_AGAIN, prompts.SAFE_FALLBACK,
    prompts.FAREWELL,
})


class State(str, Enum):
    ASLEEP = "ASLEEP"
    WAKING = "WAKING"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"


@dataclass
class Event:
    kind: str  # wake | utterance | playback_done | tick | stop
    payload: object = None


class Orchestrator:
    def __init__(self, *, robot, agent, tts, lexicon,
                 wake=None, segmenter=None, asr=None, phrasebook=None,
                 shlokas=None, followups=None,
                 turn_logger=None, glosser=None, grammar_checker=None,
                 logger: logging.Logger | None = None,
                 silence_timeout_s: float = 30.0,
                 max_reply_chars: int = validator.MAX_REPLY_CHARS,
                 max_sentences: int = 1,
                 verse_pause_s: float = VERSE_PAUSE_S,
                 line_pause_s: float = LINE_PAUSE_S,
                 fallback_agent_factory=None, gestures: bool = True):
        self.robot = robot
        self.agent = agent
        self.tts = tts
        self.lexicon = lexicon
        self.wake = wake
        self.segmenter = segmenter
        self.asr = asr
        # Optional: retrieval over the everyday-phrase corpus. Without it the
        # model has only the few-shot examples to fall back on, and an 8B with
        # weak Sanskrit priors answers an unclear turn by reciting one of them
        # verbatim — which is what makes three exchanges read as one.
        self.phrasebook = phrasebook
        # Optional: verse corpus for "recite a shloka" (lexicon/shlokas.py).
        # A deterministic path — the model is not asked to produce scripture.
        self.shlokas = shlokas
        # Optional: the verified follow-up questions that turn an answer into
        # an exchange (agent/followups.py, FR-3.12). Deterministic for the same
        # reason the verses are: the model's own reciprocal questions were where
        # its grammar failed (कथं भवतः?), which is why v1.5 removed them. Absent
        # == feature absent: Mitra answers and waits, as it did before.
        self.followups = followups
        self.turn_logger = turn_logger
        # Optional (debug runs only): translates every spoken line back into
        # English for the log, so an operator who does not read Devanagari can
        # see what Mitra actually said (FR-7.2).
        self.glosser = glosser
        # Optional: morphology-backed checks over the generated reply
        # (mitra.sanskrit.grammar). The Devanagari ratio in validator.py is
        # blind to Hindi written in Devanagari and to invented verb forms;
        # this is what sees them. Absent, the pipeline behaves exactly as it
        # did before — the checks add rejections, they never add replies.
        self.grammar_checker = grammar_checker
        self.logger = logger or logging.getLogger("mitra")
        self.gestures = gestures
        self.silence_timeout_s = silence_timeout_s
        self.max_reply_chars = max_reply_chars
        # Every logged reply appended a stock "and you?" — and that trailing
        # question, not the answer, carried most of the grammatical errors
        # (कथं भवतः?, genitive where nominative is needed). The prompt asks for
        # one sentence; this is what makes it true. Set to 2 to allow a
        # follow-up question back.
        self.max_sentences = max_sentences
        # Silence at the dandas, in seconds (mitra.speech.tts).
        self.verse_pause_s = verse_pause_s
        self.line_pause_s = line_pause_s
        self._fallback_agent_factory = fallback_agent_factory
        self._fallback_agent = None

        self.state = State.ASLEEP
        self.events: queue.Queue[Event] = queue.Queue()
        self._stop = threading.Event()
        self._sleep_after_speaking = False
        self._last_activity = time.monotonic()
        self._consecutive_retries = 0
        # The follow-up question appended to the last spoken reply, if any. The
        # model never saw it — it is added after generation — so the next turn
        # has to carry it back in (_build_message), or the answer to it arrives
        # with nothing to attach to.
        self._pending_question: str | None = None
        # Proper nouns the user has given us this session, as {spelling:
        # consonant skeleton} (agent/names.py). The checks downstream of the
        # model are built on a closed word list, and a name is the one word
        # that arrives from outside it at runtime — without this, Mitra asks
        # "तव नाम किम्?", is told, and answers "sorry, I do not understand".
        self._heard_names: dict[str, str] = {}
        # The verse just recited, if the last turn was a recitation. Same
        # repair as _pending_question: the corpus answered, so the model never
        # saw the verse, and the next turn is about a verse it does not know.
        self._recited: tuple[str, str] | None = None
        # Work queue for the English gloss (FR-7.2), drained by one worker
        # started on first use. One worker, not a thread per line: the Glosser
        # owns a single model agent, and two turns glossing at once had them
        # calling converse() on it concurrently — which failed, and one failure
        # disables the gloss for the whole run. Serialising also keeps
        # turns.jsonl in turn order. Callers that need the gloss before
        # continuing (tests) can ``_gloss_queue.join()``; nothing on the
        # speaking path ever waits.
        self._gloss_queue: queue.Queue = queue.Queue()
        self._gloss_worker: threading.Thread | None = None
        # Set when the wake word cuts playback short, so the playback watcher
        # knows not to flush the mic out from under the user (see _speak).
        self._barge_in = threading.Event()

    # ------------------------------------------------------------------ run

    def run(self) -> None:
        self._stop.clear()
        threading.Thread(target=self._audio_loop, daemon=True).start()
        self.logger.info("Mitra asleep — say the wake word")
        while not self._stop.is_set():
            try:
                event = self.events.get(timeout=0.5)
            except queue.Empty:
                event = Event("tick")
            try:
                self.handle_event(event)
            except Exception:  # FR-6.4: log, apologize, keep the session alive
                self.logger.exception("error handling %s in %s", event.kind, self.state)
                if self.state == State.THINKING:
                    self._emotion("confused1")
                    self._speak(prompts.APOLOGY_RETRY)
                    self.state = State.SPEAKING

    def stop(self) -> None:
        self.events.put(Event("stop"))

    def flush_logs(self, timeout: float = 10.0) -> None:
        """Wait for queued glosses and their turn records to be written.

        Turn records are written by the gloss worker (FR-7.2), so a process
        that exits the moment the last question is answered loses the tail of
        turns.jsonl — which is exactly what the eval harness reads. Bounded:
        a log is never worth hanging a shutdown for.
        """
        waiter = threading.Thread(target=self._gloss_queue.join, daemon=True)
        waiter.start()
        waiter.join(timeout)

    # ------------------------------------------------------- event dispatch

    def handle_event(self, event: Event) -> None:
        kind = event.kind
        if kind == "stop":
            self._stop.set()
        elif kind == "tick":
            self._check_silence_timeout()
        elif kind == "wake":
            if self.state == State.ASLEEP:
                self._on_wake()
            elif self.state in (State.SPEAKING, State.WAKING):
                # barge-in (DESIGN §1.3): stop playback, listen again. The flag
                # goes up first: _watch_playback is a live thread about to see
                # the speaker fall idle, and its echo flush would take the rest
                # of this sentence with it.
                self._barge_in.set()
                self.robot.speaker_stop()
                self._to_listening()
        elif kind == "utterance" and self.state == State.LISTENING:
            self._on_utterance(event.payload)
        elif kind == "playback_done":
            if self._sleep_after_speaking:
                self._go_to_sleep()
            elif self.state in (State.WAKING, State.SPEAKING):
                self._to_listening()

    # ---------------------------------------------------------- transitions

    def _pose(self, name: str) -> None:
        """State-feedback gesture (FR-5.3): best-effort, config-gated."""
        if self.gestures and hasattr(self.robot, "pose"):
            self.robot.pose(name)

    def _emotion(self, name: str) -> None:
        """Recorded emotion from Pollen's library (FR-5.3 extension):
        best-effort, config-gated, purely additive to _pose() above — fired
        only at occasional "moments" (wake, sleep, confusion), not every turn."""
        if self.gestures and hasattr(self.robot, "play_emotion"):
            self.robot.play_emotion(name)

    def _on_wake(self) -> None:
        self.state = State.WAKING
        self.logger.info("wake word detected")
        self.robot.nod()                      # deterministic (DESIGN §1.4)
        self._emotion("welcoming1")
        self._consecutive_retries = 0
        # The greeting opens the conversation rather than just announcing that
        # Mitra is awake: "नमस्ते। तव नाम किम्?" gives the child something to
        # answer, which is the whole of FR-3.12 at the one moment there is no
        # transcript to take a cue from.
        greeting = self._invite(prompts.GREETING, topic="greeting")
        self._speak(greeting)
        self._gloss_async(greeting)

    def _to_listening(self) -> None:
        self.state = State.LISTENING
        self._last_activity = time.monotonic()
        self._pose("listening")               # antennas perk up: "your turn"
        if self.segmenter:
            self.segmenter.reset()
        if self.wake:
            # The wake detector runs its own energy segmenter, and _audio_loop
            # only feeds it while asleep or speaking. Leaving SPEAKING mid-window
            # strands it inside an utterance — buffer half full, _in_speech still
            # true — and nothing clears that until the session ends. The next
            # barge-in is then judged on a window that opens with the tail of
            # Mitra's own voice, which is exactly the audio it must not hear.
            self.wake.reset()

    def _check_silence_timeout(self) -> None:
        if (self.state == State.LISTENING
                and time.monotonic() - self._last_activity > self.silence_timeout_s):
            self.logger.info("silence timeout — session ends (FR-1.5)")
            self._go_to_sleep()

    def _go_to_sleep(self) -> None:
        self.state = State.ASLEEP
        self._pose("asleep")                  # head droops: session over
        self._emotion("mini-deep-sleep")
        self._sleep_after_speaking = False
        self._consecutive_retries = 0
        self.agent.reset()                    # context is per-session (FR-3.3)
        if self.shlokas:
            self.shlokas.reset()              # so does "don't repeat a verse"
        if self.followups:
            self.followups.reset()            # and "don't ask the same thing twice"
        self._pending_question = None
        self._recited = None
        self._heard_names.clear()             # and who we were talking to
        if self.wake:
            self.wake.reset()
        if self.segmenter:
            self.segmenter.reset()
        self.logger.info("asleep")

    # ------------------------------------------------------ turn processing

    def _is_unintelligible(self, transcript: str, lang: str) -> str | None:
        """Return a reason string if this transcript must not reach the model.

        Whisper always returns *something*: on silence it emits a stock caption
        phrase, and on speech in a language it wasn't expecting it transliterates
        into whatever script it guessed (we have seen Korean, Japanese, Arabic
        and Tamil renderings of spoken Sanskrit). Both look like valid input to
        the agent, which then answers confidently — or, worse, echoes the noise
        back as if it were Sanskrit. Refusing here is the only place the
        pipeline can tell the difference.

        The length bar moves with the conversation: a bare "no" carries nothing
        on its own, and answers a question Mitra asked a moment ago.
        """
        cleaned = transcript.strip()
        minimum = (_MIN_ANSWER_CHARS if self._pending_question
                   else _MIN_TRANSCRIPT_CHARS)
        if len(cleaned) < minimum:
            return "too short"
        if cleaned.lower().strip(" .!?") in _ASR_HALLUCINATIONS:
            return "known ASR hallucination"
        if lang == "unknown":
            # Script matched none of en/kn/sa: the words may well be right but
            # they are in an alphabet the model has no reason to connect to
            # this conversation.
            return "unrecognized script"
        return None

    def _retrieve_examples(self, transcript: str) -> list:
        """Nearest everyday phrases for this turn, or [] if unavailable.

        A turn of one or two words gets none. Retrieval over a fragment is a
        match on a single word, and the resolved block can be about anything:
        "at home." — two words answering "who is at your home?" — scored 0.53
        against *Are all well at home?*, whose answer block is सर्वं कुशलम्, and
        the model spoke that back verbatim ("Everything is well"). Fragments
        became common the moment Mitra started asking questions (FR-3.12), and
        for them the context that matters is the question itself
        (``prompts.ASKED_HEADER``), not a phrasebook row sharing one word.
        Ungrounded is the right outcome for a turn this corpus cannot answer.
        """
        if self.phrasebook is None or len(transcript.split()) < _MIN_RETRIEVAL_WORDS:
            return []
        try:
            return self.phrasebook.similar(transcript, k=3)
        except Exception:
            self.logger.exception("phrasebook lookup failed; continuing ungrounded")
            return []

    def _build_message(self, transcript: str, lang: str, explain_en: bool) -> str:
        """Assemble the turn message: what Mitra asked, tags, transcript,
        retrieved phrasing.

        The examples go after the transcript so the user's turn stays the most
        recent thing in the message — context that follows a question tends to
        get answered instead of the question.
        """
        header = f"[lang={lang}]"
        if explain_en:
            header += " [explain_in_english]"
        message = f"{header} {transcript}"

        # Consumed, not kept: it describes the exchange that just happened, and
        # a stale copy on the next turn would have the model answering a
        # question two turns old.
        if self._pending_question:
            message = prompts.ASKED_HEADER.format(
                question=self._pending_question) + message
            self._pending_question = None
        if self._recited:
            verse, attribution = self._recited
            message = prompts.RECITED_HEADER.format(
                verse=verse, attribution=attribution) + message
            self._recited = None

        examples = self._retrieve_examples(transcript)
        if examples:
            lines = "\n".join(
                f"  {row.get('english', '')} → {row.get('sanskrit', '')}"
                for row in examples
            )
            message += _REFERENCE_HEADER + lines
        return message

    def _on_utterance(self, payload) -> None:
        self.state = State.THINKING
        self._pose("thinking")                # head tilt: "processing..."
        self._last_activity = time.monotonic()
        tl = self.turn_logger
        if tl:
            tl.start_turn()

        transcript, hint = self._transcribe(payload)
        lang = language_detector.detect(transcript, hint) if transcript.strip() else "unknown"

        if tl:
            tl.set("lang", lang)
            tl.set("transcript", transcript)

        reason = self._is_unintelligible(transcript, lang)
        if reason:
            # Do NOT call the model. "Sorry, say that again" is a coherent
            # conversational move; answering noise is not.
            self._consecutive_retries += 1
            self.logger.info("transcript rejected (%s): %r", reason, transcript)
            if tl:
                tl.set("rejected", reason)
                tl.set("explain_in_english", False)
            self._emotion("confused1")
            self._finish_turn(prompts.APOLOGY_RETRY)
            return

        self._consecutive_retries = 0
        self._note_names(transcript)
        if self.followups is not None:
            # Before anything is chosen: what the user just volunteered is not
            # something to ask them about (FR-3.12).
            self.followups.observe(transcript)

        # A turn that asks something opens a subject, and answering it plus
        # opening one back is conversation. A turn that only tells us something
        # — or answers what Mitra asked — is a thread being pulled, and a new
        # subject there drops it (FR-3.12).
        continuing = not followup_list.asks_something(transcript)

        recitation = self._recite_if_asked(transcript)
        if recitation is not None:
            # Consumed like any other turn: the verse is the answer to the
            # outstanding question, and carrying it into the next message
            # would have the model answering a question two turns old.
            self._pending_question = None
            self._finish_turn(recitation, transcript=transcript, topic="shloka")
            return

        explain_en = bool(_EXPLAIN_IN_ENGLISH_RE.search(transcript))
        message = self._build_message(transcript, lang, explain_en)
        if tl:
            tl.set("explain_in_english", explain_en)

        try:
            reply, session_end = self._generate_reply(message, explain_en)
        except Exception:
            self.logger.exception("agent failure (FR-6.4)")
            self._emotion("confused1")
            reply, session_end = prompts.APOLOGY_RETRY, False

        if session_end:
            self._sleep_after_speaking = True
            self._finish_turn(prompts.FAREWELL)
            return
        self._finish_turn(reply, transcript=transcript, continuing=continuing)

    def _recite_if_asked(self, transcript: str) -> str | None:
        """A verse from the corpus if this turn asked for one, else None.

        Deterministic on purpose (DESIGN §1.4). Asked to recite, the model
        invents something verse-shaped and misattributes it — and a child would
        take that for scripture. The corpus is the answer, verbatim.

        Falling through to None when there is no corpus is deliberate too: the
        model will then say it cannot, which is true.
        """
        if self.shlokas is None:
            return None
        if not (shloka_corpus.is_recitation_request(transcript)
                or self._accepted_a_verse(transcript)):
            if shloka_corpus.looks_like_a_near_miss(transcript):
                # Not a refusal — the turn goes on to the model as usual. This
                # is the breadcrumb for the next spelling whisper invents (it
                # has said "schlocker"): grep the log for it and widen the
                # patterns in lexicon/shlokas.py from what was actually heard.
                self.logger.debug("possible recitation request not recognized: %r",
                                  transcript)
            return None
        row = self.shlokas.pick()
        if row is None:
            self.logger.info("shloka requested but the corpus is empty")
            return None
        verse_id = f"{row.get('source_slug', '?')} {row.get('verse_id', '?')}"
        self.logger.info("reciting shloka %s", verse_id)
        # Kept for exactly one turn (see _build_message): whatever the child
        # says next — "what does it mean?", "say it again" — is about this.
        self._recited = (row.get("verse_text", ""), row.get("attribution", ""))
        if self.turn_logger:
            self.turn_logger.set("shloka", verse_id)
        return shloka_corpus.format_recitation(row)

    def _accepted_a_verse(self, transcript: str) -> bool:
        """True when "yes" is an answer to Mitra's own offer of another verse.

        A bare "आम्" means recite only because Mitra just asked whether to
        (``followups.OFFERS_VERSE``), so the offer has to be the outstanding
        question — otherwise every agreeable turn in the session would produce
        a shloka. Without this the invitation is a dead end: the child says
        yes, the model has no verse to give, and it apologizes for a question
        Mitra itself put.
        """
        return (self._pending_question in followup_list.OFFERS_VERSE
                and followup_list.is_affirmative(transcript))

    # -------------------------------------------------------------- names

    def _note_names(self, transcript: str) -> None:
        """Remember the proper nouns in this turn for the rest of the session.

        Session-scoped, because a child gives their name once and Mitra may
        greet them by it several turns later (agent/names.py).
        """
        for name, skeleton in names.heard(transcript).items():
            if name not in self._heard_names:
                self._heard_names[name] = skeleton
                self.logger.debug("name heard: %s (%s)", name, skeleton)

    def _is_a_name(self, word: str) -> bool:
        """True if a word the checks rejected is a name the user gave us."""
        return bool(self._heard_names) and names.echoes(
            word, self._heard_names.values())

    def _finish_turn(self, reply: str, *, transcript: str = "",
                     topic: str | None = None, continuing: bool = False) -> None:
        tl = self.turn_logger
        if tl:
            # Logged before the invitation is appended, and the invitation
            # logged beside it as "followup": the grammar eval scores this
            # field, and a hand-verified question mixed into it would measure
            # the list rather than the model (eval/README.md). The spoken line
            # is the two joined.
            tl.set("reply", reply)
        reply = self._invite(reply, transcript=transcript, topic=topic,
                             continuing=continuing)
        self._pose("neutral")                 # face forward while speaking
        self._speak(reply)                    # times the tts stage itself
        # The record is detached here and written by the gloss thread, which
        # adds reply_en when it has it. Detaching now is what keeps the run
        # loop free: waiting for a translation would hold the state machine in
        # SPEAKING, and a robot that is not LISTENING cannot hear the answer to
        # the question it just asked.
        if tl:
            self._gloss_async(reply, tl.take(), tl)
        self.state = State.SPEAKING

    # ---------------------------------------------------- keeping it going

    def _invite(self, reply: str, *, transcript: str = "",
                topic: str | None = None, continuing: bool = False) -> str:
        """``reply`` plus a verified follow-up question (FR-3.12).

        Runs after validation, never before: the questions are hand-checked
        Sanskrit, so putting them through the morphology gate could only cost a
        good line — and a retry triggered by Mitra's own fixed phrasing would
        re-roll the answer to punish a word the model did not write.

        Left alone when the reply already asks something (the child is never
        handed two questions at once), when it is one of the fixed phrases that
        already asks for another try, and when there is no list configured.
        """
        if self.followups is None or not reply.strip():
            return reply
        if reply.strip() in _NO_INVITE_AFTER:
            return reply
        if topic is None and followup_list.has_question(reply):
            # The model asked its own question, against instructions. Nothing to
            # carry forward either: unlike an appended one, that question IS in
            # the model's history, so the next turn already makes sense to it.
            #
            # Not applied to a recitation (``topic``), which is not Mitra
            # speaking for itself: classical verse is full of interrogatives —
            # *तथेदं कुत्र कुप्यते* ("at what, then, is one angry?") — and read
            # as a question to the child it cost the verse its invitation, and
            # the next two turns with it. A verse asks the poet's question, not
            # Mitra's.
            return reply
        try:
            question = self.followups.pick(
                transcript=transcript, reply=reply, topic=topic,
                continuing=continuing)
        except Exception:
            # A flat reply is a worse conversation, not a broken one (FR-6.4).
            self.logger.exception("follow-up selection failed; replying flat")
            return reply
        if not question:
            return reply
        self._pending_question = question
        if self.turn_logger:
            self.turn_logger.set("followup", question)
        return followup_list.join_question(reply, question)

    def _transcribe(self, payload) -> tuple[str, str | None]:
        if isinstance(payload, str):          # tests / text console mode
            return payload, None
        tl = self.turn_logger
        if tl:
            with tl.stage("asr"):
                return self.asr.transcribe(payload)
        return self.asr.transcribe(payload)

    # ------------------------------------------------------------ thinking

    def _generate_reply(self, message: str,
                        explain_en: bool = False) -> tuple[str, bool]:
        """Agent call + lexicon substitution + validation with one retry
        (FR-3.5), then the config-gated cloud fallback (FR-6.3).

        When the user explicitly asked for an English explanation (FR-3.2
        exception), the Devanagari check is waived for this one turn — the
        reply must merely be non-empty and not a ramble."""
        tl = self.turn_logger

        def generate(msg: str) -> str:
            if tl:
                with tl.stage("llm"):
                    return self.agent.converse(msg)
            return self.agent.converse(msg)

        raw = generate(message)
        if END_SESSION_SENTINEL in raw:
            return raw, True

        if explain_en:
            reply = raw.strip()
            if reply and len(reply) <= 3 * self.max_reply_chars:
                return reply, False
            return prompts.SAFE_FALLBACK, False

        reply = _limit_sentences(self._apply_lexicon(raw), self.max_sentences)
        ok, reason, suffix = self._check(reply)
        if ok:
            return reply, False

        self.logger.warning("reply failed validation (%s); retrying", reason)
        reply = _limit_sentences(
            self._apply_lexicon(generate(message + "\n" + suffix)),
            self.max_sentences,
        )
        ok, reason, _ = self._check(reply)
        if ok:
            return reply, False

        self.logger.warning("retry failed validation (%s)", reason)
        cloud = self._try_cloud_fallback(message)
        return (cloud if cloud is not None else prompts.SAFE_FALLBACK), False

    def _check(self, reply: str) -> tuple[bool, str, str]:
        """Validate a candidate reply. Returns (ok, reason, retry suffix).

        Two layers, deliberately separate: ``validator`` is the cheap, always-on
        gate (length, Devanagari, known Hindi markers), and the grammar checker
        is the one that needs the morphology data. The retry suffix differs by
        layer — naming the specific words that failed is what turns a retry
        into a correction rather than a re-roll (DESIGN §5).
        """
        ok, reason = validator.validate(reply, self.max_reply_chars)
        if not ok:
            # A bad construction is not a bad word: the retry has to name the
            # shape and its replacement, not a list of words that are each
            # fine on their own.
            construction = validator.wrong_construction(reply)
            if construction:
                return False, reason, prompts.CONSTRUCTION_CORRECTION_SUFFIX.format(
                    wrong=construction[0], right=construction[1])
            # Name the words when we know them, here too: a reply rejected for
            # Hindi comes back unchanged from a generic "answer in Sanskrit".
            hindi = validator.hindi_markers(reply)
            return False, reason, _correction_suffix(hindi)
        if self.grammar_checker is None:
            return True, "", ""
        try:
            findings = self.grammar_checker(reply, allow=self._is_a_name)
        except Exception:
            # A checker fault must not cost the child an answer: the reply has
            # already passed the deterministic gate (FR-6.4).
            self.logger.exception("grammar check failed; accepting the reply")
            return True, "", ""
        if not findings:
            return True, "", ""
        words = self.grammar_checker.offending_words(findings)
        return (False, self.grammar_checker.reason(findings),
                _correction_suffix(words))

    def _try_cloud_fallback(self, message: str) -> str | None:
        if self._fallback_agent_factory is None:
            return None
        try:
            if self._fallback_agent is None:
                self._fallback_agent = self._fallback_agent_factory()
            reply = _limit_sentences(
                self._apply_lexicon(self._fallback_agent.converse(message)),
                self.max_sentences)
            ok, _, _ = self._check(reply)
            return reply if ok else None
        except Exception:
            self.logger.exception("cloud fallback failed (FR-6.3)")
            return None

    # ------------------------------------------------------- vision/lexicon

    def _apply_lexicon(self, reply: str) -> str:
        """Vision turns answer in strict JSON (DESIGN §5). Verified lexicon
        names always override the generated name (FR-2.5); new names are
        recorded unverified for review (DESIGN §4)."""
        data = _extract_json(reply)
        if not data or "object_en" not in data:
            return reply
        object_en = str(data["object_en"])
        generated = str(data.get("name_sa_devanagari", "")).strip()
        sentence = str(data.get("sentence_sa", "")).strip()
        if not sentence and generated:
            sentence = f"एतत् {generated} अस्ति।"

        row = self.lexicon.lookup(object_en)
        if row and row["verified"]:
            verified_name = row["name_devanagari"]
            if generated and generated in sentence:
                sentence = sentence.replace(generated, verified_name)
            else:
                sentence = f"एतत् {verified_name} अस्ति।"
        elif row is None and generated:
            self.lexicon.add_unverified(
                object_en, generated, str(data.get("name_iast", "")), object_en
            )
        return sentence or reply

    # ------------------------------------------------------------- speaking

    def _speak(self, text: str) -> None:
        """Deterministic speech path (DESIGN §1.4): synthesize, play without
        blocking (for barge-in), post playback_done when the speaker frees up.

        Returns as soon as playback has started. Nothing slow may be added
        after that point: this runs on the run-loop thread, and every
        millisecond spent here is a millisecond in which ``playback_done``
        sits unhandled and the microphone is still routed to the wake
        detector rather than to the segmenter.
        """
        self.logger.info("speak: %s", text)
        self._barge_in.clear()
        try:
            with self._tts_stage():
                wav, samplerate = self._synthesize(text)
            self.robot.speaker_play(wav, samplerate, block=False)
        except Exception:
            self.logger.exception("TTS/playback failure (FR-6.4)")
            self.events.put(Event("playback_done"))
        else:
            threading.Thread(target=self._watch_playback, daemon=True).start()

    def _synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Waveform for a line, with the dandas of a recitation made audible.

        ॥ marks recited verse and nothing else Mitra says, so it is the gate:
        below it, ordinary replies take the single-call path they always have.
        Above it, the line is synthesized in chunks joined by real silence —
        the pause a reciter leaves before the colophon cannot be spelled,
        because ॥ has no phonetic value and neither engine here accepts SSML.
        Splitting also keeps the mark out of the tokenizer, where some engines
        read it aloud as a word.
        """
        if shloka_corpus.DOUBLE_DANDA not in text:
            return self.tts.synthesize(text)
        return synthesize_with_pauses(
            self.tts.synthesize, text,
            verse_pause_s=self.verse_pause_s, line_pause_s=self.line_pause_s)

    @contextmanager
    def _tts_stage(self):
        """Time synthesis into the turn log, when there is a turn to log."""
        if self.turn_logger is None or self.state != State.THINKING:
            yield
            return
        with self.turn_logger.stage("tts"):
            yield

    def _gloss_async(self, text: str, record=None, turn_logger=None) -> None:
        """Mirror the spoken line in English on the console (FR-7.2).

        Off the run loop, always. The gloss is a second model call, and when it
        ran inline it held the state machine in WAKING/SPEAKING for as long as
        the call took — 14 s on the first one of a session, while the mic was
        still routed to the wake detector. Mitra greeted, asked "त्वं कथम्
        असि?", and discarded the answer as a failed wake match. A log
        convenience must never cost a turn (FR-6.4), and being late costs
        nothing: the audio is already playing.

        ``record``, when given, is a detached turn record this thread finishes
        and writes once the gloss is in.
        """
        if self.glosser is None:
            # Nothing to translate — write the record here rather than paying
            # for a worker on every turn of a non-debug run.
            if record is not None and turn_logger is not None:
                turn_logger.write(record)
            return
        if self._gloss_worker is None:
            self._gloss_worker = threading.Thread(target=self._gloss_loop,
                                                  daemon=True)
            self._gloss_worker.start()
        self._gloss_queue.put((text, record, turn_logger))

    def _gloss_loop(self) -> None:
        """Drain the gloss queue, one line at a time, for the whole session."""
        while True:
            text, record, turn_logger = self._gloss_queue.get()
            try:
                english = None
                try:
                    english = self.glosser.gloss(text)
                except Exception:
                    self.logger.exception("English gloss failed; continuing")
                if english:
                    self.logger.info("speak (en): %s", english)
                if record is not None and turn_logger is not None:
                    if english:
                        record["reply_en"] = english
                    turn_logger.write(record)
            finally:
                self._gloss_queue.task_done()

    def _watch_playback(self) -> None:
        started = time.monotonic()
        time.sleep(0.05)
        while self.robot.speaker_busy() and not self._stop.is_set():
            time.sleep(0.05)
        # How long the mic was routed away from the segmenter. Ordinary replies
        # are about a second; a recited verse is ten, and anything said into
        # that window is gone. When someone reports "I asked and it ignored me",
        # this is the number that says whether they were talking over it.
        self.logger.debug("playback done after %.1fs (mic was not listening)",
                          time.monotonic() - started)
        # Discard whatever the mic captured during playback before resuming
        # listening — with mic_source="built_in" there's no echo cancellation,
        # so without this the robot's own voice gets fed back in as if it
        # were the next user utterance. Unless the wake word cut playback off:
        # then the buffer holds the user mid-sentence, not an echo, and the
        # flush would delete the very turn the barge-in was asking for.
        if not self._barge_in.is_set() and hasattr(self.robot, "flush_mic"):
            self.robot.flush_mic()
        self.events.put(Event("playback_done"))

    # ------------------------------------------------------------ audio I/O

    def _audio_loop(self) -> None:
        """Pump mic chunks to the wake detector or segmenter by state."""
        while not self._stop.is_set():
            try:
                chunk = self.robot.mic_read()
            except Exception:
                self.logger.exception("microphone read failure")
                time.sleep(0.5)
                continue
            if chunk is None or len(chunk) == 0:
                continue
            if self.robot.mic_samplerate != TARGET_SAMPLERATE:
                chunk = resample(chunk, self.robot.mic_samplerate, TARGET_SAMPLERATE)

            state = self.state
            if state in (State.ASLEEP, State.SPEAKING, State.WAKING):
                if self.wake and self.wake.process(chunk):
                    self.events.put(Event("wake"))
            elif state == State.LISTENING and self.segmenter is not None:
                utterance = self.segmenter.process(chunk)
                if utterance is not None:
                    self.events.put(Event("utterance", utterance))


def _correction_suffix(words: list[str]) -> str:
    """Retry instruction: name the offending words when there are any."""
    if not words:
        return prompts.CORRECTIVE_SUFFIX
    return prompts.WORD_CORRECTION_SUFFIX.format(words=", ".join(words))


def _limit_sentences(text: str, limit: int) -> str:
    """Keep at most ``limit`` sentences, terminator included.

    A reply with no terminator at all is left alone: truncating mid-clause
    would produce worse Sanskrit than the model wrote.
    """
    if limit <= 0:
        return text.strip()
    ends = [m.end() for m in _SENTENCE_END.finditer(text)]
    if len(ends) <= limit:
        return text.strip()
    return text[:ends[limit - 1]].strip()


def _extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a reply (tolerates ``` fences)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
