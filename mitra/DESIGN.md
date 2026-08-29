# Mitra — Design Document

**Status:** Design | **Version:** 1.8 (2026-08-29) | **Requirements:** [REQUIREMENTS.md](REQUIREMENTS.md) v1.10

**v1.8 change:** §5 — the validator gains a **construction check** (`validator._WRONG_CONSTRUCTIONS`, FR-3.17): *अहं X प्रियम् अस्मि* passed every existing gate and appeared four times in one session. §5 — the vocabulary is now built from **Mitra's own spoken Sanskrit** as well (`followups.spoken_questions()`, `prompts.SPOKEN_PHRASES`), so a word in a question Mitra asks is a word Mitra may answer with. §4 — a follow-up draw with no keyword match takes the **open subject's next step** rather than a random new topic.

**v1.7 change:** §4/§5 — the follow-up list gains **depth**: each row carries two follow-on questions asked when the child answers it, so a subject gets a second and third turn instead of a stock *अधिकं वद।* (FR-3.12). §5 — a **proper noun** in the user's turn is exempted from the two lexical checks by consonant-skeleton match (`agent/names.py`, FR-3.15); without it Mitra asked for a name, was given one, and refused its own correct reply. §4 — *"shall I recite another verse?"* answered "yes" reaches the corpus, and the recited verse is carried into the next turn's message (`prompts.RECITED_HEADER`, FR-3.16), since the recitation path never let the model see it.

**v1.6 change:** §1.4/§4/§5 — **turn-taking** as a fifth deterministic path (`agent/followups.py`). Mitra answers, then asks: the answer is generated, the question is drawn from a verified list and appended after validation. The split is not stylistic — v1.3 removed the model's reciprocal question because that half of the reply carried most of the grammar errors — so the model keeps the half it does well and the list supplies the half it does not. §5 — the appended question is fed back to the model on the next turn (`prompts.ASKED_HEADER`), without which a one-word answer arrives attached to nothing. §3 — the debug English gloss moves **off the run loop** onto a single worker thread: inline it held the state machine in WAKING/SPEAKING for the length of a model call, and with the microphone routed to the wake detector in those states, the first live session had Mitra ask *त्वं कथम् असि?* and then discard the answer as a failed wake match.

**v1.5 change:** §1.4/§4 — **shloka recitation** as a fourth deterministic path. Asked for a verse, Mitra reads one from a 500-verse corpus (`lexicon/shlokas.py`) and never generates it: the model produces verse-shaped text with a confident wrong attribution, and the reply-side gates meant for one-sentence conversation are the wrong instrument for Bhartṛhari. §5 — the dandas of a recitation become **measured silence** in the waveform (`speech/tts.py`), because ॥ has no phonetic value and neither TTS engine accepts SSML.

**v1.4 change:** §5 — morphology-backed output checks (`mitra.sanskrit`, vidyut): a reply's words must be attested Sanskrit forms, must be on Mitra's vocabulary list, and must agree with their subject in person. This replaces script-only validation as the primary accuracy gate for *language* (the Devanagari ratio cannot see Hindi written in Devanagari). §6 — Cologne dictionaries (Monier-Williams, Apte) behind the lexicon review CLI. §5 — a debug English gloss of every spoken line (FR-7.2).

**v1.3 change:** §5 — replies held to one sentence (deterministic truncation, `session.max_sentences`); the validator gains a Hindi-marker check alongside the Devanagari ratio; the agent keeps a bounded conversation window (`agent.max_history_turns`) so the model stops imitating its own errors. Phrasebook retrieval rebuilt on IDF-weighted trigrams with question→answer resolution (§4).

This document describes *how* Mitra is built: module decomposition, the Strands ↔ Reachy Mini integration, data flows, prompting, and error handling. All inference is local (Ollama, Whisper, Indic Parler-TTS on the M1 Max host) per REQUIREMENTS §1; §1.5 shows the cloud extension path.

**Option A — fully local inference (the v1 target):**

![Mitra architecture — fully local](architecture-local.png)

**Option B — cloud-extended inference (speech and wake word stay local):**

![Mitra architecture — cloud-extended](architecture-cloud.png)

**Execution sequence on wake (time flows downward; same numbering as the architecture arrows):**

![Mitra wake flow](flow-wake.png)

*Editable sources: [architecture-local.excalidraw](architecture-local.excalidraw) · [architecture-cloud.excalidraw](architecture-cloud.excalidraw) · [flow-wake.excalidraw](flow-wake.excalidraw) (open at excalidraw.com or with the VS Code Excalidraw extension).*

---

## 1. Strands + Reachy Mini: How They Connect

This is the question at the heart of the design, so it comes first.

### 1.1 What the Strands robots SDK (`strands-robots`) actually is

The [`strands-robots` lab](https://strandsagents.com/docs/labs/robots/) wraps a **manipulation robot as a Strands agent tool**. Its `Robot` class is built on the **LeRobot** hardware layer and a **Policy** abstraction for vision-language-action (VLA) models:

- `Robot(tool_name=..., robot="so101_follower", cameras={...}, port="/dev/ttyACM0", data_config=...)` — supported robot types are LeRobot arms (SO-100/SO-101).
- The control loop sends *observations* (camera frames + joint states) to a *policy* (e.g. NVIDIA GR00T behind a ZMQ inference server) and executes the returned *action chunks* (joint trajectories) at ~50 Hz.
- The tool exposes four actions to the agent: `execute` (blocking), `start` (background), `status`, `stop`.

### 1.2 Why Mitra doesn't use `strands-robots` directly

| `strands-robots` assumes | Reachy Mini / Mitra reality |
|---|---|
| LeRobot driver for the robot type | No Reachy Mini driver; the robot speaks its own `reachy-mini` SDK |
| Actions = joint trajectories from a VLA policy | Mitra's "actions" are *speak*, *nod*, *capture image* — no manipulation, no policy inference |
| GPU VLA inference server (GR00T, TensorRT/ZMQ) | Nothing to run a VLA on; Qwen3-VL via Ollama is a *language* model, not an action policy |

Forcing Reachy Mini into the `Robot`/`Policy` interface would mean writing a LeRobot driver and a fake policy for a robot with no arms — machinery without benefit.

### 1.3 What Mitra takes from it: the robot-as-tool pattern

Mitra uses the **core `strands` SDK** and applies `strands-robots`' central idea — *the robot is a tool the agent can call* — with tools we define ourselves over the `reachy-mini` SDK:

```python
# src/agent/tools.py
from strands import tool
from mitra.robot.reachy import robot      # singleton wrapper over reachy_mini SDK
from mitra.speech.tts import synthesize   # Indic Parler-TTS on MPS

@tool
def capture_image() -> dict:
    """Capture one frame from Reachy Mini's camera (use when the user shows an object)."""
    frame = robot.camera.read()             # numpy (H, W, 3) uint8 via reachy-mini SDK
    return {"format": "jpeg", "source": {"bytes": jpeg_bytes(frame)}}

@tool
def speak_sanskrit(text_devanagari: str) -> str:
    """Speak Sanskrit text (Devanagari) through the robot's speaker."""
    wav = synthesize(text_devanagari)
    robot.speaker.play(wav)                 # plays via SDK media backend
    return "spoken"

@tool
def nod() -> str:
    """Briefly nod the head (wake acknowledgment)."""
    robot.head.nod()
    return "ok"

@tool
def end_session() -> str:
    """End the conversation and return to wake-word listening."""
    return "session_end"                    # orchestrator interprets this sentinel
```

```python
# src/agent/agent.py
from strands import Agent
from strands.models.ollama import OllamaModel
from .tools import capture_image, speak_sanskrit, nod, end_session
from .prompts import SANSKRIT_SYSTEM_PROMPT

model = OllamaModel(host="http://localhost:11434",
                    model_id="qwen3-vl:8b-instruct", temperature=0.3)
agent = Agent(model=model,
              tools=[capture_image, speak_sanskrit, nod, end_session],
              system_prompt=SANSKRIT_SYSTEM_PROMPT)
```

The `OllamaModel` provider keeps orchestration code independent of where inference runs — pointing the same agent at a cloud provider later is a one-line config change (REQUIREMENTS FR-6.3).

We also adopt `strands-robots`' **`execute`/`start`/`status`/`stop` action shape** for the one genuinely long-running robot operation — speaking. `speak_sanskrit` internally starts playback on a worker thread and the orchestrator can `stop` it (barge-in: user says "mitra" again mid-reply → playback stops).

### 1.4 Tool invocation: model-invoked (Qwen3-VL), with deterministic guardrails

The primary model is **Qwen3-VL 8B Instruct**, chosen over Gemma 3 12B precisely because it exposes **native tool calling through Ollama** (use the `:8b-instruct` tag — the bare `:8b` tag is the *thinking* variant, which burns the latency budget on reasoning tokens and returns empty content; its Ollama library entry is tagged `tools` + `vision`; Gemma 3 has no native tool support in Ollama). That makes the Strands agent loop work as designed:

- The **model invokes `capture_image()` itself** when the user asks about an object — the returned frame flows back into the same multimodal turn, and Qwen3-VL answers from the image. A config flag (`agent.deterministic_vision: true|false`) keeps the v1.0 orchestrator-mediated intent-check path available as a reliability fallback and for A/B testing.
- Two calls stay **deterministic regardless of model**: `nod()` fires on the wake event, and every reply is routed through the validator and then `speak_sanskrit()` by the orchestrator — a small local model is never trusted to decide *whether* to validate or speak.
- **Recitation is deterministic too, and for a different reason.** Asked for a shloka, the orchestrator answers from the verse corpus and never consults the model at all (§4). The others guard against a model that answers *badly*; this one guards against a model that answers *plausibly*. An 8B produces something verse-shaped, in metre-adjacent Sanskrit, over a colophon naming a parvan it did not come from — and a child would learn it as scripture. The corpus is quoted verbatim; there is nothing here for the model to add.
- **The follow-up question is deterministic, and for the recitation's reason at a smaller scale.** Every reply ends with a short Sanskrit question so the turn does not dead-end (§5, FR-3.12), and that question is retrieved rather than generated. The evidence is in this project's own history: v1.3 removed the model's reciprocal question after a quality pass found the trailing "and you?" carrying most of the grammar errors while the answer beside it was sound. Generating it again would restore the defect; drawing it from a list a human wrote makes it correct by construction. The pattern is the same one the lexicon and the verse corpus use — where the model is weak and the set of right answers is small, keep the set.
- The Strands `Agent` owns the conversation loop, message history, and provider abstraction.

If the Phase 3 bake-off selects Gemma 3 instead, the same `@tool` definitions keep working via the deterministic path — the tool interface is model-agnostic.

### 1.5 Extending to the cloud: a provider swap

Option B (second diagram above) changes exactly one construction line — the Strands model provider:

```python
# local (Option A)
model = OllamaModel(host="http://localhost:11434", model_id="qwen3-vl:8b-instruct")
# cloud (Option B) — e.g. Claude API or Amazon Bedrock
model = AnthropicModel(model_id="claude-sonnet-5")          # or BedrockModel(...)
```

Everything else — the `Agent`, the four tools, prompts, validator, lexicon, orchestrator — is unchanged. The privacy boundary also holds in Option B: wake word, VAD, ASR, and TTS remain on the host, so only session *text* and explicitly captured frames cross the network; raw microphone audio never does. The local Ollama model is kept installed as an offline fallback (dashed path in the diagram): on network failure the orchestrator swaps the provider back and continues degraded rather than dying.

**Reference for building out Option B:** [cagataycali/tiny-the-reachy](https://github.com/cagataycali/tiny-the-reachy) is a Strands-Agents-on-Reachy-Mini project built cloud-first by default (OpenAI Realtime, Amazon Nova Sonic, or Gemini for STT/LLM), the inverse of Mitra's local-first Option A. Relevant when Option B is actually implemented:
- Its `tools/reachy_*` layer shows a fuller motion/expression vocabulary (14 tools vs. Mitra's 4) with a **safety envelope** (head pitch/roll ±40°, yaw ±180°, body yaw ±160°) clamped in every motion tool — Mitra's `POSES` table (`src/robot/reachy.py`) currently has no such clamp and should adopt one before more gesture tuning.
- It binds expression calls to speech *as it plays* (e.g. antenna wobble during TTS) rather than a single pose per state — a model for evolving Mitra's SPEAKING gesture beyond the current static pose.
- Its `mcp_server_entry.py` exposes robot tools over MCP for direct control from Claude Code/Desktop — useful as a **dev-only** tool for hardware debugging (this session's throwaway probe scripts are exactly what that would replace), not part of Mitra's runtime.
- Not adopted, and deliberately so: its multi-persona identity (Telegram bot, autonomous heartbeat, shared SQLite brain) and default cloud STT — Mitra stays single-purpose and keeps ASR/TTS local even under Option B (per the privacy boundary above).

## 2. Module Decomposition

```
mitra/
├── README.md · REQUIREMENTS.md · DESIGN.md · CLAUDE.md
├── architecture-local.{excalidraw,png} · architecture-cloud.{excalidraw,png}
├── scripts/gen_diagrams.py          # regenerates both diagram pairs from one spec
├── config.yaml                  # models, thresholds, timeouts, feature flags
├── main.py                      # entry point: wiring + run loop
├── src/
│   ├── orchestrator.py          # state machine (§3)
│   ├── robot/reachy.py          # thin wrapper over reachy-mini SDK: camera, speaker, head
│   ├── audio/
│   │   ├── wake.py              # openWakeWord runner ("mitra" model)
│   │   ├── vad.py               # Silero VAD segmentation
│   │   └── asr.py               # whisper.cpp/mlx-whisper (en, kn) + HF Sanskrit fine-tune
│   ├── language_detector.py     # per-utterance en/kn/sa detection (ported concept)
│   ├── speech/tts.py            # Indic Parler-TTS (MPS); VITS fallback behind same interface
│   ├── agent/
│   │   ├── agent.py             # Strands Agent + OllamaModel construction
│   │   ├── tools.py             # @tool wrappers over robot + TTS (§1.3)
│   │   ├── prompts.py           # system prompt, few-shot exchanges, vision prompt
│   │   ├── followups.py         # verified questions that keep a turn going (§5)
│   │   └── validator.py         # Devanagari/length validation + retry (§5)
│   ├── lexicon/store.py         # SQLite object-name cache (§6)
│   ├── lexicon/shlokas.py       # verse corpus + "recite a shloka" detection (§4)
│   ├── lexicon/vocabulary.py    # the words Mitra may say — lemma whitelist (§5)
│   ├── lexicon/dictionary.py    # Cologne MW/Apte lookups for review (§6)
│   ├── sanskrit/analyzer.py     # vidyut kosha: attestation + morphology (§5)
│   ├── sanskrit/grammar.py      # attestation/vocabulary/agreement checks (§5)
│   ├── gloss.py                 # --debug English gloss of each spoken line (FR-7.2)
│   └── logging_subsystem.py     # structured per-turn logs (ported concept)
└── tests/                       # pytest; module-per-module, mocks for robot + Ollama
```

Every hardware- or model-touching module hides behind a small interface so tests run with fakes: `robot/reachy.py` has a `FakeReachy` twin; `agent/agent.py` accepts any Strands model provider.

## 3. Orchestrator State Machine

| State | Entered on | Active components | Exits |
|---|---|---|---|
| `ASLEEP` | startup, session end | openWakeWord only | wake word → `WAKING` |
| `WAKING` | wake detection | `nod()`, greeting via TTS | done → `LISTENING` |
| `LISTENING` | greeting/reply finished | VAD + ASR | utterance → `THINKING`; 30 s silence → `ASLEEP` |
| `THINKING` | transcript ready | language detect, intent check, optional `capture_image()`, Strands agent → Ollama, validator | reply valid → `SPEAKING`; `end_session` → `ASLEEP` |
| `SPEAKING` | validated reply | TTS + speaker playback | playback done → `LISTENING`; wake word (barge-in) → stop playback → `LISTENING` |

Single-threaded core with three daemon threads: the always-on wake-word listener, the TTS playback worker, and (in `--debug` only) the gloss worker. State transitions are the only cross-thread communication (queue of events), which keeps the concurrency surface tiny.

**Nothing slow may run on the run-loop thread.** The states are what route the microphone — `_audio_loop` feeds the wake detector while `ASLEEP`/`WAKING`/`SPEAKING` and the segmenter only while `LISTENING` — so a blocked loop is a deaf robot, not merely a slow one. This was found the expensive way: the English gloss (FR-7.2) was a second model call made inline after playback started, and its first invocation of a session takes ~14 s. `playback_done` sat unhandled for all of it, the state stayed `WAKING`, and the user's answer to Mitra's opening question went to the wake matcher and was thrown away. The gloss now runs on its own worker, which also writes the turn record once it has `reply_en` (`TurnLogger.take`/`write`); `Orchestrator.flush_logs()` drains it at shutdown so a short run does not lose the tail of `turns.jsonl`. One worker, not one thread per line — the `Glosser` owns a single model agent and two concurrent `converse()` calls fail.

## 4. Turn Flows

**Wake:** mic stream → openWakeWord fires → orchestrator: `nod()` + speak *नमस्ते* → `LISTENING`.

**Conversation turn:** VAD end-of-utterance → ASR (Whisper, language auto-detect en/kn; Sanskrit model when detector says `sa`) → orchestrator builds turn message `[lang=kn] <transcript>` → Strands agent → Ollama/Qwen3-VL → validator (§5) → `speak_sanskrit()` → back to `LISTENING`.

**Every turn, before it is spoken:** the validated reply is joined to one short question from `agent/followups.py` — chosen by keyword overlap with the transcript and the reply, not repeated within the session, and never asking for something the user has already volunteered (a turn that *tells* us about a topic retires that question; a turn that *asks* about it leaves it open, since asking back is reciprocation rather than repetition) — and the question is remembered so the *next* turn's message opens with `[You asked a moment ago: "…"]`. **A draw with no keyword match takes the open subject's next step instead** — a random question is where a session stops being a conversation. **Which question depends on who opened the subject:** a turn that asks something gets a new topic back (reciprocation), while a turn that only tells, or that answers what Mitra asked, gets the open subject's **next step** — each row carries two follow-on questions written for that position (`तव प्रियं भोजनं किम्?` → `तत् मधुरम् अस्ति वा?` → `कः तत् पचति?`) — and only when those are spent, a generic *continuation* — `किमर्थम्?`, `ततः किम्?`, `अधिकं वद।` — which refers to what was just said without naming it, and so cannot change the subject. Depth is what separates a conversation from a form: the first live session was coherent and flat, every answer drawing *अधिकं वद।*. Without that split every turn opened a new topic and the session read as a questionnaire. Fragments of one or two words also skip phrasebook retrieval entirely: matching on a single word, `"at home."` resolved to `सर्वं कुशलम्` and the model spoke it verbatim. Skipped after a refusal and after the farewell, where a question is the wrong move. The greeting takes the same path, so a session opens with something to answer rather than an announcement.

**Recitation turn:** *"tell me a shloka"* — or **"yes" to Mitra's own offer of another verse**, which is a request only while that offer is the outstanding question — never reaches the model: the corpus answers (§1.4, FR-3.9). Because the model therefore never sees the verse, the text and colophon are prepended to the *next* turn's message (`prompts.RECITED_HEADER`), so *"what does that mean?"* is answered about the verse actually recited, with an explicit instruction to admit ignorance rather than invent a gloss.

**Vision turn:** same until the model (or, with `deterministic_vision`, the intent check) triggers `capture_image()` → **lexicon lookup first**: if the recognized object (Qwen3-VL asked for an English identification + Sanskrit name in one JSON response) is already in the verified lexicon, the cached Sanskrit name replaces the generated one → reply assembled (*एतत् … अस्ति*) → validator → spoken. New objects are written to the lexicon as `unverified` for later human review.

**Recitation turn:** transcript mentions a shloka (`श्लोक` / romanised `shlok…` / Kannada `ಶ್ಲೋಕ`, or an English "recite a verse") → orchestrator draws a verse from `data/shlokas.json`, avoiding the last 20 → the verse is closed with ॥ and its colophon appended → spoken **without** the model, the sentence limit, or the morphology checks. The corpus is 500 verses across seven works of nīti and kāvya — Kṣemendra's Cārucaryā, Bhartṛhari's Nīti- and Vairāgya-śataka, Śāntideva's Bodhicaryāvatāra, Aśvaghoṣa's Saundarananda, and Kālidāsa's Kumārasambhava and Ṛtusaṃhāra — each carrying its own attribution; the colophons already open with **इति** ("thus, in …"), so nothing is inserted to join verse to source. No corpus configured == feature absent: the request reaches the model like any other turn, and the honest "I cannot" is the right answer when there is nothing to recite.

**What may be in the corpus (FR-3.10).** Nothing that invokes, praises, or prescribes worship of a deity. `scripts/filter_shlokas.py` carries the term list and writes what it removed to `data/shlokas-rejected.json` with the term each verse tripped, so the call is auditable rather than folklore. Two properties of the matching are load-bearing: terms match as bare substrings, because sandhi fuses them into their neighbours, and each vowel-initial term is matched again in its sandhi forms — 12.220.107 hid उपास inside त्वमात्मानमुपाससे, where the उ has become the ु of मु and the literal string never occurs. The list is tuned against its own false positives (स्तव was matching ...ाः + तव, "your sons"; इन्द्र is half of इन्द्रिय and the tail of every नरेन्द्र), and it still over-removes narration — सहदेव contains देव — which is the correct direction for the trade: a lost verse costs variety, a missed one costs the reason the filter exists. **It is a floor.** A verse can praise a deity with an epithet the list lacks, or with a pronoun whose referent is two verses back; no blocklist closes that, which is why FR-3.10 records the intent to invert it into a reviewed allowlist. The same script carries the FR-3.11 categories (marriage, sexual content, servitude) — a random draw produced Mbh 13.44.13, on marrying a seven-year-old — and deliberately leaves battle narration alone.

## 5. Prompting & Output Validation

- **System prompt** (in `prompts.py`): persona (friendly Sanskrit-speaking robot friend), hard rules (reply only in Sanskrit/Devanagari, **one** short sentence with no reciprocal question of its own, Sanskrit not Hindi vocabulary, simple laukika register, no sandhi-heavy constructions, and — added after a live session where it dominated the transcript — never translate the user's own statement back at them as Mitra's answer), followed by ~8 **few-shot exchanges** covering greetings, object naming, simple Q&A, and graceful "I don't know" — few-shot steering matters far more for a 12B local model than for frontier models.
- **Vision prompt**: asks for strict JSON — `{"object_en": ..., "name_sa_devanagari": ..., "name_iast": ..., "sentence_sa": ...}` — parsed, then only `sentence_sa` (with lexicon substitution) is spoken.
- **Validator** (`validator.py`): checks the reply is ≥ 80 % Devanagari codepoints, ≤ 220 chars, and non-empty. Failure → one retry with a corrective suffix ("उत्तरं संस्कृतेन एव देहि …"); second failure → fixed safe phrase, and (only if an API key is configured) the optional cloud fallback path (FR-6.3).
- **Morphology checks** (`mitra.sanskrit`, backed by [vidyut](https://github.com/ambuda-org/vidyut) — a 30 M-form inflected lexicon with Pāṇinian tags, MIT, ~78 MB, offline). The script ratio above is blind to the dominant failure: Hindi written in Devanagari scores 1.00. Three checks run on every reply, each rejecting into the same retry path, which now names the offending words rather than repeating a generic instruction:

  | check | catches | measured false-positive rate |
  |---|---|---|
  | `unattested` | words that are no Sanskrit form at all — करोष्यसि, कुरुमि, मक्खनम्, दालः | 0/20 in Mitra's register; ~17 % on the adult phrasebook |
  | `vocabulary` | real Sanskrit words that are not on Mitra's list — आज, घरे, खेलानि (`lexicon/vocabulary.jsonl`, 558 words: Open Pathshala's beginner list + closed-class core + the prompt's own examples, widened by the seed lexicon and the phrasebook) | 0/20; ~32 % on the adult phrasebook |
  | `agreement` | subject and verb disagreeing in person — भवान् … पठसि, अहं … चलन्ति, त्वम् … अस्मि | 0/20; 0.7 % on the phrasebook |

  Both false-positive columns matter: a rejected reply costs a retry and can end in the safe phrase, so `scripts/eval_grammar.py` scores every change against 924 human-authored sentences before it ships. The whitelist is stored as **lemmas**, so one entry covers a paradigm (क्रीडति admits क्रीडामि, क्रीडिष्यामि), and it is built from stem readings while membership is tested against all readings — the asymmetry is what stops आज entering through अजा's shared root.

- **The follow-up question bypasses all of the above too, and downstream of it.** It is appended after validation and after the morphology checks, never before: the text is hand-verified, so the gates could only cost a good line — and worse, a rejection triggered by Mitra's own fixed phrasing would send the *answer* back for a retry to punish a word the model never wrote. The turn log keeps the two apart (`reply` and `followup`) so `eval/eval_grammar.py` goes on scoring the model rather than the list. The list is 13 rows of simple laukika Sanskrit addressed as त्वम् — the polite भवान्/भवती carry gender, and Mitra does not know the speaker's — each with two follow-on questions for when the child answers it.
- **A short list of whole constructions is rejected outright** (`validator.wrong_construction`, FR-3.17). *अहं X प्रियम् अस्मि* is the list so far: every word attested, in vocabulary, and agreeing, and the sentence still says Mitra IS the thing it means to like. Matched only where प्रियम् sits directly before अस्मि — with a noun between them the neuter is describing that noun and the sentence is correct. The retry suffix carries the replacement template, not a complaint.
- **The vocabulary includes what Mitra says in its own voice** — the follow-up questions and the fixed phrases, alongside the beginner word list, the seed lexicon and the phrasebook. A robot that asks *तव प्रियः पशुः कः?* and then cannot say पशु is not a defensible state; it was a live turn.
- **A name the user gives is exempt from the two lexical checks** (`agent/names.py`, FR-3.15). Those checks rest on a closed word list, and a proper noun is the one word that arrives from outside it at runtime: Mitra asked *तव नाम किम्?*, was told "My name is Tafik", generated the correct *स्वागतं तफिकः*, and spoke the safe fallback twice instead. Proper nouns in the transcript (capitalised mid-sentence, or after "my name is") are reduced to a **consonant skeleton** and matched against rejected words across scripts — Tafik, Taufiq, तफिकः and तफिकम् all reduce to t-p-k, with a case ending allowed to add up to two consonants. Consulted only for words some check has already rejected, so the blast radius of a false match is one word; the agreement check is untouched.
- **Recited verse bypasses all of the above** and takes a different path to the speaker. `speech/tts.synthesize_with_pauses()` splits the line at its dandas, synthesizes each chunk separately, and joins them with real silence — **0.35 s** at `।` (between the halves of a verse) and **0.8 s** at `॥` (verse end, and verse → colophon). Both marks have zero phonetic value and neither engine here takes SSML, so a pause can only be *made*, not spelled. Measured on `facebook/mms-tts-hin`: `।` and `॥` each tokenize to **zero tokens**, which is good news and bad news — the engine will never read the mark aloud as a word, and it leaves no gap whatsoever where a reciter needs one. (Zero tokens also crashes the VITS forward pass, so a chunk with no letters in it is dropped before synthesis.) The split is gated on `॥`, which appears in recitation and nowhere else Mitra speaks, so ordinary replies keep their single synthesis call.

## 6. Lexicon Store

SQLite table `lexicon(object_en TEXT PRIMARY KEY, name_devanagari TEXT, name_iast TEXT, gloss_en TEXT, verified INTEGER, updated_at TEXT)`. Ships pre-seeded with ~100 human-verified everyday objects (FR-2.6). Verified rows always override model output; unverified rows are review candidates surfaced by a `mitra-lexicon review` CLI helper. This is the primary accuracy mechanism compensating for local-model Sanskrit (REQUIREMENTS R1/R2).

`mitra-lexicon` shows each pending name alongside the **Cologne Digital Sanskrit Lexicon** (`lexicon/dictionary.py`): what Monier-Williams says the coined word means — "not in Monier-Williams" is itself the signal that the model invented it — and what Apte's English-Sanskrit dictionary offers for the same object. Asked for "butter", Apte answers नवनीतम्, the word the model missed when it said मक्खनम्. This stays on the review path and out of the speaking path deliberately: Apte carries idioms as well as words, so "apple" leads with तारा (from "apple of the eye"). A dictionary that is right about butter and wrong about apples is a suggestion for a human, not an authority over the child's answer.

## 7. Configuration (`config.yaml`)

```yaml
models:
  llm: {provider: ollama, host: "http://localhost:11434", id: "qwen3-vl:8b-instruct", keep_alive: "30m"}
  asr: {default: "whisper-large-v3", sanskrit: "<hf-sanskrit-finetune>", backend: "mlx"}
  tts: {engine: "indic-parler-tts", fallback: "indic-tts-vits", device: "mps"}
  wake: {engine: "openwakeword", model: "models/mitra.onnx", threshold: 0.6}
cloud_fallback: {enabled: false, provider: null}   # FR-6.3; absent key == feature absent
session: {silence_timeout_s: 30, max_reply_chars: 220}
conversation: {follow_up: true}                     # FR-3.12; false == replies do not invite a next turn
```

`keep_alive: 30m` keeps Qwen3-VL resident in Ollama between turns — reload latency would otherwise dominate the turn budget (REQUIREMENTS §8).

## 8. Error Handling

| Failure | Detection | Behavior |
|---|---|---|
| Ollama down / timeout | HTTP error, 20 s deadline | Spoken apology (*क्षम्यताम्, पुनः वदतु*), log, stay in `LISTENING` |
| ASR empty/garbage | empty transcript, low confidence | Sanskrit "please repeat" prompt |
| Camera read failure | SDK exception | Sanskrit "show me again" + log |
| Validator double-failure | §5 | Safe phrase; optional cloud fallback if configured |
| Robot disconnected (USB) | SDK heartbeat | Console alert, pipeline pauses in `ASLEEP` |

## 9. Testing Strategy

- **Unit:** validator (property tests on Devanagari ratio), lexicon store, intent matcher, state-machine transitions (table-driven, `FakeReachy`, canned agent).
- **Integration (no robot):** full turn with recorded WAV fixtures → wake → ASR → mocked Ollama → TTS to file; asserts latency budget instrumentation fires.
- **Hardware smoke (`tests/hw/`, skipped in CI):** camera frame shape, speaker tone, nod — Phase 0's checklist, kept runnable forever.
- **Sanskrit quality harness:** fixed prompt set + scoring sheet for the Phase 3 model bake-off; results committed alongside the chosen model id.

## 10. Design Decisions & Alternatives Considered

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| D1 | Core `strands` + custom tools | `strands-robots` `Robot`/`Policy` | No LeRobot driver or VLA policy applies to Reachy Mini (§1.2) |
| D2 | Model-invoked tool calls (Qwen3-VL native tools) with deterministic speech/validation path | Orchestrator-only mediation | Qwen3-VL supports tools natively in Ollama; validator + speak stay deterministic so model quality can't skip guardrails (§1.4) |
| D3 | One multimodal tool-capable model (Qwen3-VL 8B) | Gemma 3 12B (no Ollama tool support); Qwen3 text + separate VLM (two resident models) | Single ~6 GB model covers conversation, vision, and tools; bake-off in Phase 3 may revise (REQUIREMENTS §6) |
| D4 | SQLite lexicon, verified-wins | Pure generation | Deterministic correctness for repeat objects; human-in-the-loop quality (R1/R2) |
| D5 | Wake word + VAD gating before any model | Always-on ASR | Privacy (FR-1.2) and keeps the Mac's memory/compute idle when asleep |
