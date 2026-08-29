# Mitra — Sanskrit-Speaking Interactive Robot on Reachy Mini

**Status:** Requirements | **Version:** 1.10 (2026-08-29) | **Predecessor:** earlier `mitra/` design study (Cohort 3, in git history at `40639db`)

Mitra (मित्रम्, "friend") is an interactive desktop robot built on the **Reachy Mini Lite**. It wakes when someone says **"mitra"**, recognizes objects shown to its camera and names them in Sanskrit, and holds simple conversations — understanding English, Kannada, or Sanskrit, but always replying in Sanskrit.

**v1.1 change:** inference is **local-first with open-source models** on the host Mac. Cloud APIs are an optional, config-gated fallback that is disabled by default — the robot must be fully functional with no internet access after models are downloaded.

**v1.10 change:** A second live session, longer than the first. New **FR-3.17**: a short list of *constructions* that are wrong whatever words fill them — *अहं X प्रियम् अस्मि* ("I am the dear book") appeared four times in fifteen turns and every existing check passed it. FR-3.6 gains a source: **the words in Mitra's own questions are words Mitra may say** — it asked *तव प्रियः पशुः कः?*, the child named an animal, and the reply was rejected for using पशु. FR-3.12 stops jumping: when nothing in the list relates to the turn, the **open subject's next step** is asked instead of a random new one, and a subject the user asks about is no longer retired by another clause of the same turn. FR-3.15 is narrowed — "I'm fine" and "I am studying" were being read as names.

**v1.9 change:** Three repairs from the first full live session on the branch. FR-3.12 gains **depth** — answering a question is now followed by the *next* question about the same subject (*"what do you like?"* → *"why do you like that?"*), not by a stock *"tell me more"*; the session was coherent but flat, and a robot that only ever says "go on" is not interested in the answer. New **FR-3.15**: the speaker's own **name** survives the Sanskrit checks — Mitra asked *तव नाम किम्?*, was told "My name is Tafik", and answered *"sorry, I do not understand"*, because तफिकः is correctly not a Sanskrit word. New **FR-3.16**: an offer Mitra makes must be one it can honour — *"shall I recite another verse?"* answered "yes" now reaches the corpus, and the verse just recited is carried into the next turn's prompt so a question about it is not answered blind.

**v1.8 change:** New **FR-3.12 conversational turn-taking** — Mitra now answers *and* asks, so a session is a conversation rather than a queue of lookups. The question is retrieved from a hand-verified list, not generated: v1.5 removed the model's reciprocal question because that trailing question carried most of the grammatical errors, and generating it again would buy the defect back. FR-3.5's intelligibility floor is relaxed while a question is outstanding, since the answer to one is often two characters long.

**v1.7 change:** New **FR-3.9 shloka recitation** — asked for a verse, Mitra recites one from a curated corpus rather than generating it, with its source named. Two things this requirement is really about: an 8B model asked for scripture invents metre-adjacent lines under a confident wrong attribution, and the reply-side gates that make ordinary conversation safe (one sentence, everyday-vocabulary whitelist) are exactly wrong for epic Sanskrit. New **FR-4.5** — Devanagari verse punctuation is realized as timed silence, since ॥ has no phonetic value and the TTS engines here accept no SSML.

**v1.6 change:** FR-3.5 promoted from a word blocklist to a **morphological whitelist**. Three sessions of logged replies showed the blocklist losing the race it cannot win: every new Hindi noun the model reached for needed a new entry, and it said nothing at all about invented forms like करोष्यसि or कुरुमि, which are words in no language. Output is now checked against a 30 M-form Sanskrit lexicon — every word must be an attested form, must be on Mitra's vocabulary list, and must agree with its subject in person. New FR-3.8 states the vocabulary boundary explicitly, and FR-7.2's "English glosses for the operator" is now implemented rather than aspirational.

**v1.5 change:** FR-3.4 tightened after a Sanskrit quality assessment of live sessions — replies are now **one** sentence, not two: every logged reply appended a stock "and you?", and that trailing question carried most of the grammatical errors (कथं भवतः?, genitive where nominative belongs) while the answer itself was usually sound. FR-3.5 gains a **Hindi-marker check** — Qwen reaches for Hindi under pressure (आज for अद्य, खेल for क्रीडा) and the Devanagari ratio cannot see it, since Hindi shares the script. New FR-3.7 bounds the conversation window: the model imitates its own recent output more than the few-shot block, so a bad phrasing repeats until it ages out.

**v1.4 change:** FR-3.2 amended — output is Sanskrit by default, but an explicit "explain in English" request is answered in spoken English, explaining the recent Sanskrit exchange (learner support). The Devanagari validator is waived only for such explicitly tagged turns.

**v1.3 change:** renamed Mitram → **Mitra** — मित्र is the vocative (सम्बोधन विभक्ति) of मित्रम्, the correct form of address, and is now the project name and wake word ("hey mitra"). Wake is ASR-transcript matching until the custom openWakeWord model is trained. LLM tag corrected to `qwen3-vl:8b-instruct` (bare `:8b` is the thinking variant).

**v1.2 change:** primary LLM/vision model switched from Gemma 3 12B to **Qwen3-VL 8B Instruct** — Qwen3-VL exposes **native tool calling through Ollama** (Gemma 3 does not), is multimodal, and is smaller (~6 GB vs ~8 GB resident). See DESIGN.md §1.4.

---

## 1. Decisions from Requirements Discussion

| Topic | Decision |
|---|---|
| Robot platform | **Reachy Mini Lite** (wired), tethered to the host that runs the pipeline |
| Host hardware | **MacBook Pro, Apple M1 Max, 32 GB unified memory** (macOS, Metal/MPS acceleration) |
| AI stack | **Local open-source models for all inference** — LLM, vision, ASR, TTS, wake word. Optional cloud fallback (e.g. Claude API) only if explicitly configured; assume unavailable |
| Language behavior | **Bilingual bridge** — user may speak English, Kannada, or Sanskrit; robot always responds in Sanskrit |
| Object recognition | **Open vocabulary** — a local vision-language model names anything shown; Sanskrit name generated on the fly |
| Motion | **Minimal** — wake acknowledgment gesture only; no expressive/idle animation in v1 |
| Runtime | No fixed preference — chosen per component (§6): Ollama for LLM/VLM, whisper.cpp/MLX for ASR, HF Transformers for TTS |
| Codebase | Fresh code in this directory; reuse concepts from the earlier design (orchestrator, language detection, logging, test structure) |

## 2. Goals

1. Hands-free activation via the spoken wake word "mitra", processed **locally** — no audio ever leaves the host.
2. Show the robot any everyday object → it speaks the object's Sanskrit name in a short sentence (e.g. *एतत् सेवफलम् अस्ति* — "this is an apple").
3. Conversational exchange: user speaks English, Kannada, or Sanskrit; Mitra replies in simple, grammatically correct spoken Sanskrit.
4. **Fully offline operation** after initial model downloads — no internet required at runtime.
5. End-to-end spoken response in **≤ 8 s** for conversation, **≤ 10 s** for vision queries on the M1 Max host (see §8).

### Non-Goals (v1)

- No manipulation/locomotion (Reachy Mini has none) and no expressive animation beyond wake acknowledgment.
- No dependence on cloud quality: local Sanskrit generation will be weaker than frontier cloud models; v1 accepts this and mitigates via prompting and a curated cache (§9 R1) rather than requiring an API.
- No Vedic recitation/chandas awareness; classical simple Sanskrit only.
- No multi-user speaker identification.

## 3. Hardware & Host Platform

| Component | Requirement |
|---|---|
| Robot | Reachy Mini Lite: wide-angle camera, 2 microphones, 5 W speaker, 6-DOF head + body rotation, USB connection to host. Requires external computer (macOS or Linux). |
| Host | MacBook Pro **M1 Max, 32 GB unified memory** (development + deployment target). The model set in §6 is sized to fit ~14 GB of inference memory, leaving headroom for macOS and the pipeline. Other hosts must offer ≥ 16 GB free memory for the same models. |
| Network | Required only for initial model downloads. Runtime is offline. |
| SDK | `reachy-mini` Python SDK (PyPI). Camera frames arrive as numpy arrays; audio via the SDK's default media backend (OpenCV + sounddevice). |

### Memory budget (resident, approximate)

| Model | Quant/format | Memory |
|---|---|---|
| Qwen3-VL 8B Instruct (LLM + vision + tools) | Q4_K_M via Ollama | ~6 GB |
| Whisper large-v3 (ASR) | GGML/MLX | ~3 GB |
| Indic Parler-TTS (~880 M) | fp16, MPS | ~2 GB |
| openWakeWord + Silero VAD | onnx | < 0.5 GB |
| **Total** | | **~11.5 GB of 32 GB** |

## 4. Functional Requirements

### FR-1 Wake Word ("mitra")
- FR-1.1 A local, always-on wake-word engine listens on the robot's microphones for "mitra". Candidate engines: **openWakeWord** (open-source, custom word trainable from synthetic speech) or **Picovoice Porcupine** (custom keyword; note: not fully open-source — acceptable only if openWakeWord misses targets). Decision in Phase 1 based on measured accuracy.
- FR-1.2 No audio leaves the host at any time; the entire pipeline is local.
- FR-1.3 On detection, the robot acknowledges with a **single brief head motion (nod)** and a short Sanskrit greeting (e.g. *नमस्ते*), then enters listening mode.
- FR-1.4 Target: ≥ 90 % detection rate at conversational distance (≤ 2 m), ≤ 1 false accept per hour of ambient household audio.
- FR-1.5 The session ends after a configurable silence timeout (default 30 s) or on a spoken farewell; the robot returns to wake-word-only listening.

### FR-2 Object Recognition & Sanskrit Naming
- FR-2.1 When the user shows an object and asks about it (in any supported language — e.g. "what is this?", *किम् एतत्?*), the host captures a camera frame and sends it to the **local vision-language model** (Qwen3-VL 8B multimodal, §6) with a prompt requesting: object identification, its Sanskrit name in Devanagari, IAST transliteration, and a one-sentence Sanskrit reply.
- FR-2.2 **Open vocabulary:** any object may be shown. The model generates the Sanskrit name; for objects without an attested classical name, it must prefer an established modern-Sanskrit coinage and say so honestly rather than invent silently.
- FR-2.3 The spoken answer is a short Sanskrit sentence naming the object; the console/log shows Devanagari + IAST + English gloss for the operator.
- FR-2.4 If no object is discernible in frame, Mitra says so in Sanskrit and asks the user to hold the object closer.
- FR-2.5 A locally cached, operator-editable lexicon of previously named objects is maintained so repeat objects answer faster and consistently. With a local 12B model this cache is also the primary **accuracy** mechanism: once a name is verified by a human, the cached name always wins over fresh generation.
- FR-2.6 The lexicon ships pre-seeded with ~100 verified everyday objects (fruit, utensils, toys, animals, body parts) so the most common show-and-tell items are correct from day one.

### FR-3 Sanskrit Conversation (Bilingual Bridge)
- FR-3.1 Input languages: English, Kannada, Sanskrit (auto-detected per utterance; concept reused from the earlier `language_detector`).
- FR-3.2 Output language: **Sanskrit by default**, regardless of input language. Exception: an explicit request to explain in English (e.g. "explain that in English") is answered in simple spoken English covering the recent exchange, then replies return to Sanskrit. Register: simple, short sentences (laukika Sanskrit), suitable for learners; avoid heavy sandhi and rare vocabulary.
- FR-3.3 Conversation state (multi-turn context) is kept for the duration of a wake session.
- FR-3.4 The system prompt constrains the local LLM to: reply in Sanskrit; keep replies to **one short sentence** (`session.max_sentences`, default 1) with no reciprocal question *of its own* — since v1.8 the reciprocal question is appended deterministically from a verified list instead (FR-3.12); use Sanskrit vocabulary rather than Hindi (अद्य not आज, क्रीडा not खेल); use a **few-shot block of verified Sanskrit exchanges** (local models need stronger steering than frontier models); never switch to English speech (English may appear only in logs); and never restate the user's own sentence back at them as though it were about Mitra — *"I live in a city"* answered with *अहं नगरे अवस्थितः* is an echo, not a reply, and it dominated one live session. The few-shot block carries three such pairs taken from that session, each correction checked against the FR-3.6 gate before it went in. The orchestrator truncates to `max_sentences` deterministically — the model is asked, not trusted.
- FR-3.5 A post-generation **validation pass** checks output is Devanagari-dominant, within length limits, and free of **unambiguously Hindi words** (Hindi shares the Devanagari script, so the ratio check alone passes it); on failure, one retry with a corrective prompt, then a fixed safe fallback phrase. (Cheap guard against a small model drifting into English, into Hindi, or into rambling.)
- FR-3.6 A **morphological pass** (DESIGN §5) additionally requires every word of a reply to be an attested Sanskrit form, to be within Mitra's vocabulary (FR-3.8), and to agree with its subject in person. The retry names the offending words — a generic "answer in Sanskrit" returns the same sentence. Missing morphology data disables the pass with a warning; it never blocks startup or speech (FR-6.4).
- FR-3.8 **Bounded vocabulary.** Mitra speaks from a fixed everyday word list (a beginner's ~500 words, the closed-class core, the seed lexicon, and the phrasebook corpus it is steered by) rather than from whatever the model produces. This is what makes "no non-Sanskrit words" enforceable: the failures in practice — आज, घरे, खेलानि — are real Sanskrit forms of unrelated words, invisible to any check that asks only whether a word exists. Words outside the list are reported with the reply that used them, so the list grows from evidence.
- FR-3.6 Configurable "explain mode" (off by default): after the Sanskrit reply, optionally append an English gloss in text logs only — never spoken.
- FR-3.9 **Shloka recitation.** Asked to recite a shloka (in English, Sanskrit, or Kannada), Mitra speaks a verse drawn from a curated corpus of classical Sanskrit — never one it generated — and names its source. The verse is quoted verbatim and bypasses FR-3.4's one-sentence limit and FR-3.6's vocabulary check, both of which are calibrated for generated everyday speech and would mangle or reject attested epic Sanskrit. Verses are not repeated within a session. No corpus configured == feature absent: the request is handled as an ordinary turn, where "I do not know" is the honest answer.
- FR-3.10 **The corpus excludes worship of anything besides God.** Mitra recites to a Muslim child, so a verse that invokes a deity, praises one, or prescribes worship or sacrifice to one is not in the corpus — not as quotation and not as narration. The epics are not a safe source by default, so this is subtractive and stated as a term list in `scripts/filter_shlokas.py`, which is the criterion of record: an earlier undocumented pass could not be re-checked when a verse leaked through it. A blocklist over an epic corpus is a floor and not a guarantee (DESIGN §4) — the standing intent is to invert it into a reviewed allowlist of verses about conduct and nature, the same move FR-3.5 made from Hindi blocklist to vocabulary whitelist.
- FR-3.11 **The corpus is filtered for what a child should not be handed at all.** Found by reciting at random from it: Mahābhārata 13.44.13 prescribes the age at which a man should marry a seven-year-old girl. Verses about marriage, sexual content, and servitude are removed by the same script. Battle narration is deliberately **not** removed — where that line falls is the parent's call and not a term list's. The example is from the epic corpus this one replaced; the term list outlived it, which is the argument for having written it down.
- FR-3.12 **Every turn invites the next.** After answering, Mitra asks the speaker one short question in Sanskrit, so the child always has something to say back and the session holds together as a conversation (this is what "interactive" means here — not more speech, but a turn that does not dead-end). Five properties are load-bearing:
  - **Retrieved, not generated.** The questions come from a hand-verified list (`agent/followups.py`) for the reason v1.5 removed the model's own reciprocal question: that trailing question carried most of the grammatical errors (कथं भवतः?) while the answer itself was usually sound. The model keeps the half it is good at.
  - **Appended after validation** (FR-3.5/FR-3.6). The gates are calibrated for generated speech; running verified text through them could only cost a good line, and a retry provoked by Mitra's own fixed phrasing would re-roll the answer to punish a word the model did not write. Same argument as FR-3.9's verse bypass.
  - **Chosen by what was just said,** so the question follows the topic rather than arriving as a non-sequitur, and not repeated within a session.
  - **The open subject beats a coin flip.** When no question in the list has any keyword in common with the turn, the draw is random — and a random question is where a session stops being a conversation: asked *"how are you?"*, Mitra answered and asked which animal the child liked; asked *"what is your favourite subject?"*, it asked what they could see outside. The subject already open is a better answer than chance, so its next step is asked instead whenever nothing connects. A subject the user *asks* about also survives being mentioned elsewhere in the same turn — *"I play chess. What games do you play?"* told us about playing in one clause and asked about it in the next, and retiring it there left nothing on topic to ask.
  - **Going one step deeper, not one step sideways.** A question the child *answers* is a subject they have agreed to talk about, so the next question belongs to that subject: *"तव प्रियं भोजनं किम्?"* answered draws *"तत् मधुरम् अस्ति वा?"* ("is it sweet?"), and that answered draws *"कः तत् पचति?"* ("who cooks it?"). Each row of the list carries its own two follow-on questions, written to make sense in that position and nowhere else, and reachable only from it — asked cold, *"is it sweet?"* is a non-sequitur. Two steps is the whole depth on offer; the generic continuations below take over afterwards, because a third *"why?"* about one thing is an interrogation. Live, the session was coherent and flat: every answer drew *अधिकं वद।* ("tell me more"), which is true to the thread and says nothing.
  - **Continuing the thread when the user is not opening one.** A turn that *asks* something opens a subject, and answering it plus opening one back is conversation; a turn that only *tells* — or answers what Mitra asked — is a thread being pulled, and a new subject there drops it. Live, every turn opened a new subject and the session read as a questionnaire: *"I'll do some work today."* → *"तव गृहे के सन्ति?"* ("who is at your home?"). Statements and answers now draw from a short set of **continuation** questions that refer to what was just said without naming it (*किमर्थम्?*, *ततः किम्?*, *अधिकं वद।*), so the subject only changes when the user changes it.
  - **Never asking for what the user has already volunteered.** Topical choice on its own produces the opposite of conversation: told *"my favourite food is milk"*, Mitra asked *"तुभ्यं किं रोचते?"* ("what do you like?"). A turn in which the user *tells* us something (first-person markers, in any of the three input languages) retires that question for the rest of the session; a turn that *asks* about a topic leaves it open, since asking back is reciprocation rather than repetition. The child who gives their name at turn two must not be asked for it at turn nine.
  - **Carried into the next turn's prompt.** The model never saw the appended question, so without this it reads a bare "Ravi" as an opening remark and answers nothing. This is the difference between interactive and merely talkative.
  - **Not asked where a question is wrong:** after any of the fixed phrases that already ask for another try ("say that again", "I do not understand"), and after the farewell. Live, the alternative read as a robot that had stopped listening — *"क्षम्यताम्, अहं न अवगच्छामि। तव गृहे के सन्ति?"* ("Sorry, I do not understand. Who is at your home?"). A question that presumes a context it cannot check — "what else will you show me?" — is likewise offered only when the turn actually mentions showing something. `conversation.follow_up: false` == the feature does not exist at runtime, and Mitra answers and waits as before.
- FR-3.17 **Some constructions are wrong whatever words fill them.** *अहं X प्रियम् अस्मि* — *अहं वानरं प्रियं अस्मि*, *अहं पुस्तकं प्रियम् अस्मि*, *अहं गणितं प्रियम् अस्मि* — says "I AM the dear monkey": प्रियम् is neuter and cannot describe अहम्. It appeared four times in one fifteen-turn session and passed every check we had, because each word is attested, in vocabulary, and agreeing. This is not the general case government FR-3.6 declines (that needs a parse, and a wrong parse rejects correct Sanskrit) but a short list of exact shapes, each narrow enough to be certain about: this one matches only where प्रियम् sits directly before अस्मि, so *अहं तव प्रियं मित्रम् अस्मि* ("I am your dear friend") is untouched. The retry is handed the template **and its replacement** (*मह्यं X रोचते*) — told only that it was wrong, the model returns the same sentence with a synonym in it.
- FR-3.15 **A person's name is not a vocabulary error.** Every check downstream of the model rests on a closed word list (FR-3.6), and a proper noun is the one word that arrives from outside it at runtime — from the person Mitra is talking to. Live, Mitra asked *तव नाम किम्?*, was told "My name is Tafik", generated the correct *स्वागतं तफिकः*, and spoke *"क्षम्यताम्, अहं न अवगच्छामि"* instead, twice over, because तफिकः is not a Sanskrit word. It is not supposed to be one. Proper nouns in the user's turn — a capitalised word that is not opening a sentence, or whatever follows "my name is" — are matched against rejected words by **consonant skeleton** across scripts (Tafik/Taufiq/तफिकः/तफिकम् all reduce to t-p-k), and a match exempts the word from the two lexical checks for the rest of the session. Deliberately fuzzy and safe to be: the skeletons are consulted only for words already rejected, so a false match costs one odd word while a false miss costs the child the answer to Mitra's own question. Agreement checking is untouched — a name is not a verb.
- FR-3.16 **An invitation must be one Mitra can honour.** *"अन्यं श्लोकं श्रोतुम् इच्छसि वा?"* ("shall I recite another verse?") answered with "yes" is a recitation request, and is answered from the corpus (FR-3.9) rather than by the model, which has no verse to give and would apologize for a question Mitra itself put. Read only while that offer is the outstanding question, so an agreeable turn elsewhere in the session does not produce a verse. Conversely, because the recitation path never calls the model, the verse is absent from its history: the text and colophon are carried into the *next* turn's prompt, so *"what does that mean?"* is answered about the verse actually recited — with an explicit instruction to admit ignorance rather than invent a meaning, since a confident wrong gloss taught as scripture is the failure FR-3.9 exists to prevent.
- FR-3.14 **No phrasebook grounding for a fragment.** Retrieval over a one- or two-word turn is a match on a single word, and the resolved block can be about anything: *"at home."*, answering *"who is at your home?"*, scored 0.53 against *Are all well at home?*, whose answer block is *सर्वं कुशलम्* — which Mitra then spoke verbatim. Fragments became common the moment Mitra started asking questions (FR-3.12), and for them the grounding that matters is the outstanding question, not a row sharing one word. Turns under three words run ungrounded, which FR-3.5's retrieval already treats as the correct outcome for a turn the corpus cannot answer.
- FR-3.13 With a question outstanding, the FR-3.5 intelligibility floor drops from three characters to two. Answers to a question are short — "no", "हा" — and refusing to hear the answer to a question Mitra itself asked is the least coherent thing it could do. The ASR-hallucination and unknown-script refusals are unchanged.
- FR-3.7 The agent retains a bounded window of recent exchanges (`agent.max_history_turns`, default 4) within a session. Unbounded history lets the model imitate its own earlier output more strongly than the few-shot block, so one bad phrasing repeats for the rest of the session; a window lets it age out. Complements FR-3.3, which clears context between sessions.

### FR-4 Speech Pipeline
- FR-4.1 **VAD:** Silero VAD segments user utterances after wake.
- FR-4.2 **ASR:** local Whisper large-v3 (via whisper.cpp or mlx-whisper for Metal acceleration) covers English and Kannada; Sanskrit uses a Sanskrit fine-tune (Whisper-Sanskrit transfer-learning checkpoints / AI4Bharat IndicWhisper lineage) run via HF Transformers on MPS. Sanskrit ASR is **experimental** — see Risks (§9).
- FR-4.3 **TTS:** **AI4Bharat Indic Parler-TTS** — Sanskrit is one of its 21 supported languages with the highest native-speaker evaluation score (99.79) among them. Runs on MPS; one fixed voice chosen for warmth/clarity. Fallback if MPS latency is unacceptable: AI4Bharat **Indic-TTS** (VITS-based, lighter, also supports Sanskrit).
- FR-4.4 All spoken output plays through the robot's speaker; all input comes from the robot's microphones (not the laptop's).
- FR-4.5 **Verse pacing.** The Devanagari dandas — `।` between the halves of a verse, `॥` closing it and separating it from its colophon — are realized as **timed silence** (defaults 0.35 s and 0.8 s, `shlokas.line_pause_s` / `shlokas.verse_pause_s`), not passed to the engine as text. Neither mark has phonetic value and neither engine here accepts SSML, so the pause has to be cut into the waveform between separately-synthesized chunks. Measured on `facebook/mms-tts-hin`, both marks tokenize to zero tokens: the engine cannot read them aloud, and equally leaves no gap at all without this.

### FR-5 Motion (Minimal)
- FR-5.1 Wake acknowledgment: single nod via the `reachy-mini` SDK.
- FR-5.2 Optional (stretch, off by default): face the sound source when woken, using the SDK's sound-localization support if available on Lite's 2-mic array.
- FR-5.3 No other motion in v1. Motion code must be isolated behind a small interface so expressive behaviors can be added later without touching the pipeline.

### FR-6 Orchestration
- FR-6.1 A single **orchestrator** owns the state machine: `ASLEEP → WAKING → LISTENING → THINKING → SPEAKING → LISTENING … → ASLEEP`.
- FR-6.2 The agent layer is built on the **Strands Agents SDK** (core `strands` package) using its **Ollama model provider** — so the same orchestration code runs against local models, and could point at a cloud provider later without rework. Robot capabilities are exposed as **custom Strands tools**: `capture_image()`, `speak_sanskrit(text)`, `nod()`, `end_session()`. Note: the `strands-robots` lab package targets LeRobot arms (SO-100/SO-101) with VLA manipulation policies and does **not** support Reachy Mini — we use core Strands only, wrapping the `reachy-mini` SDK ourselves. If Strands proves heavier than needed, fallback is a plain tool-use loop against the Ollama API; the tool interface is identical either way.
- FR-6.3 **Optional cloud fallback (disabled by default):** if an API key is configured, the orchestrator may route Sanskrit generation to a cloud model when local validation (FR-3.5) fails twice. No key configured → the feature does not exist at runtime; nothing else depends on it.
- FR-6.4 Errors (model timeout, ASR failure, camera error) produce a short spoken Sanskrit apology (e.g. *क्षम्यताम्, पुनः वदतु*) and a logged diagnostic; the session continues.

### FR-7 Logging & Observability
- FR-7.1 Structured per-turn logs: timestamps, detected language, ASR transcript, LLM prompt/response, TTS text (Devanagari + IAST), per-stage latency and memory. (Concept reused from the earlier `logging_subsystem`.)
- FR-7.2 A `--debug` console mode mirrors the conversation live with English glosses for the operator. The gloss is produced on a worker thread, never on the run loop: a model call on the run loop holds the state machine in SPEAKING, and a robot that is not LISTENING cannot hear the answer to the question it just asked.
- FR-7.3 No audio recordings persisted by default; opt-in flag for collecting evaluation clips.

## 5. System Architecture

```
                 Reachy Mini Lite (USB)
        ┌───────────┬──────────────┬───────────┐
        │ 2× mics   │ wide camera  │ 5W speaker│ + head motors
        └─────┬─────┴──────┬───────┴─────▲─────┘
              │            │             │
══════════════╪════════════╪═════════════╪═══ Host: MacBook Pro M1 Max ═══
              ▼            │             │            (all local)
   openWakeWord ("mitra") │             │
              ▼            │             │
        Silero VAD         │      Indic Parler-TTS (sa)
              ▼            │             ▲
   Whisper ASR (en/kn/sa)  │             │
   + language detection    │             │
              ▼            ▼             │
   ┌─────────────────────────────────────┴───┐
   │  Orchestrator (state machine)           │
   │  Strands agent (Ollama provider)        │
   │  tools: capture_image, speak_sanskrit,  │
   │         nod, end_session                │
   └─────────────────┬───────────────────────┘
                     ▼
        Ollama: Qwen3-VL 8B (Q4)
        conversation + vision, Sanskrit generation,
        few-shot system prompt (FR-3.4) + lexicon cache (FR-2.5)

   [optional, off by default: cloud fallback per FR-6.3]
```

Everything runs on the host; the runtime has no network dependency.

## 6. Technology Stack

| Layer | Choice | Notes |
|---|---|---|
| Robot SDK | `reachy-mini` (PyPI) | Camera → numpy frames; audio I/O; head motion |
| Wake word | openWakeWord (primary) / Porcupine (alt) | Custom "mitra" model; local |
| VAD | Silero VAD | Local, lightweight |
| ASR | Whisper large-v3 via **whisper.cpp / mlx-whisper** (en, kn) + Sanskrit fine-tune via HF Transformers (MPS) | All local |
| LLM + vision | **Qwen3-VL 8B Instruct (multimodal), Q4 via Ollama** — one model serves conversation, open-vocab object naming, and **native tool calling** | Alternatives to evaluate in Phase 3: Qwen3-VL 32B Q4 (~20 GB, quality escalation but memory-tight), Gemma 3 12B (strong multilingual but no native tool calling in Ollama → needs orchestrator-mediated tools) |
| TTS | AI4Bharat **Indic Parler-TTS** (HF Transformers, MPS); fallback AI4Bharat Indic-TTS (VITS) | Sanskrit supported, top-rated language in Parler-TTS eval; local |
| Agent framework | Strands Agents SDK (core) with **Ollama provider** | Robot actions as tools (FR-6.2) |
| Language | Python 3.11+ | Matches Reachy SDK and prior code |

## 7. Reuse from the Earlier `mitra/` Design (git history, `40639db`)

Reuse as **concepts/ported modules**, not dependencies: orchestrator state-machine design, `language_detector` approach, `logging_subsystem` structure, `audio_io` patterns, and the pytest layout in the old `mitra/tests/`. The AWS-specific code (`nova_sonic_client`, `nova_vision_client`, `translation_bridge`) is superseded — the local LLM generates Sanskrit directly, so **no translation bridge is needed**. Notably, the earlier study judged edge-only Sanskrit infeasible on a 16 GB Jetson; the M1 Max with 32 GB unified memory and 2026-era open models (multimodal 12B at Q4, Sanskrit-capable TTS) changes that calculus, though Sanskrit *quality* remains the top risk (§9 R1).

## 8. Latency Budget (targets, M1 Max)

| Stage | Conversation | Vision query |
|---|---|---|
| VAD end-of-utterance | 0.5 s | 0.5 s |
| ASR (local, Metal) | 1–2 s | 1–2 s |
| LLM (Qwen3-VL 8B Q4, short reply) | 1.5–3 s | 3–4 s (image prefill) |
| TTS (Parler-TTS, MPS) | 1–3 s | 1–3 s |
| **Total** | **≤ 8 s** | **≤ 10 s** |

Levers if over budget: sentence-streamed TTS (start speaking on first sentence), smaller Whisper for en/kn, VITS-based Indic-TTS, keeping the Ollama model resident (`keep_alive`) to avoid reload latency.

## 9. Risks & Mitigations

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | **Local-model Sanskrit quality** — an 8B open model's Sanskrit is markedly weaker than frontier cloud models; grammar/vocabulary errors likely | Robot teaches wrong Sanskrit | Few-shot prompt of verified exchanges (FR-3.4); output validation + retry (FR-3.5); human-verified lexicon cache wins over generation (FR-2.5/2.6); simple-register constraint; evaluate Qwen3-VL 32B / Gemma 3 12B in Phase 3; optional cloud fallback if a key is ever available (FR-6.3) |
| R2 | **Open-vocab Sanskrit naming errors** — invented or awkward coinages | Teaches wrong words | Pre-seeded verified lexicon (FR-2.6); cache-first answers; honesty instruction (FR-2.2); operator can correct cache entries |
| R3 | **TTS pronunciation of rare words**, and Parler-TTS speed on MPS is unproven | Garbled or slow speech | Prefer simple vocabulary; test lexicon top-100 words and measure TTS latency in Phase 2; VITS fallback ready |
| R4 | Wake-word false accepts/rejects for a custom word | Annoyance / unresponsiveness | Train openWakeWord on synthetic "mitra" variants (speaker/accent/noise); Porcupine fallback if accuracy < FR-1.4 |
| R5 | **Memory pressure** — ~13.5 GB resident models + pipeline on a 32 GB shared-memory machine also used for development | Swapping, latency spikes | Memory budget (§3); load Sanskrit-ASR fine-tune lazily; unload nothing mid-session but allow single-model mode for development |
| R6 | Reachy Mini Lite 2-mic far-field pickup | Poor ASR at distance | Specify ≤ 2 m interaction distance; evaluate simple noise suppression (RNNoise) |
| R7 | **Sanskrit ASR quality** — fine-tunes are research-grade | Users speaking Sanskrit are misheard | Bilingual bridge means English/Kannada input always works; treat Sanskrit input as progressive enhancement; LLM can repair noisy transcripts from context |

## 10. Phased Plan & Acceptance Criteria

**Phase 0 — Bring-up (week 1):** Reachy Mini Lite connected; SDK smoke tests (camera frame, speaker tone, nod). Ollama + Qwen3-VL 8B installed; measure tokens/sec and memory on the M1 Max. ✅ *Scripted demo runs end-to-end on the host; LLM benchmark recorded.*

**Phase 1 — Wake + speech loop (weeks 2–3):** "mitra" wake word, VAD, ASR (English), Indic Parler-TTS Sanskrit output; robot nods and greets on wake. ✅ *FR-1.4 accuracy met; say "mitra", ask in English, hear any fixed Sanskrit reply in ≤ 8 s.*

**Phase 2 — Object naming (weeks 4–5):** Qwen3-VL vision integration, Sanskrit naming prompt, pre-seeded lexicon + cache. ✅ *20-object live test: ≥ 16 correctly identified; Sanskrit names verified by a Sanskrit-knowing reviewer; ≤ 10 s.*

**Phase 3 — Conversation (weeks 6–7):** Strands agent (Ollama provider) with tools, multi-turn context, language detection, Kannada + experimental Sanskrit ASR; **Sanskrit quality bake-off** between Qwen3-VL 8B / Qwen3-VL 32B / Gemma 3 12B on a fixed prompt set scored by a Sanskrit reviewer. ✅ *5-turn mixed English/Kannada conversation with coherent Sanskrit replies; model choice locked with recorded scores.*

**Phase 4 — Hardening (week 8):** Error paths (FR-6.4), latency tuning (streamed TTS), memory profiling, logging polish, README + demo script. ✅ *30-minute unattended offline demo (Wi-Fi off) without crash.*

## 11. Open Questions

1. Which local model wins the Phase 3 Sanskrit bake-off — Qwen3-VL 8B, Qwen3-VL 32B (memory-tight), or Gemma 3 12B (needs orchestrator-mediated tools)?
2. Which Sanskrit ASR checkpoint performs best on conversational (non-Vedic) speech? (Evaluate in Phase 3.)
3. Is Parler-TTS latency on MPS acceptable, or does v1 ship with the lighter VITS Indic-TTS? (Measure in Phase 2.)
4. Should the vision flow trigger on question intent only, or also proactively when an object is held up close? (v1: question intent only.)
5. Sound-source localization on the Lite's 2-mic array (FR-5.2) — feasible or wireless-only? Check SDK capabilities in Phase 0.

## 12. References

- Reachy Mini SDK & docs: [github.com/pollen-robotics/reachy_mini](https://github.com/pollen-robotics/reachy_mini) · [Python SDK reference](https://huggingface.co/docs/reachy_mini/SDK/python-sdk) · [`reachy-mini` on PyPI](https://pypi.org/project/reachy-mini/)
- Indic Parler-TTS (Sanskrit TTS): [huggingface.co/ai4bharat/indic-parler-tts](https://huggingface.co/ai4bharat/indic-parler-tts) · [Indic-TTS (VITS)](https://github.com/AI4Bharat/Indic-TTS)
- Sanskrit ASR research: [ASR for Sanskrit with Transfer Learning (2025)](https://arxiv.org/pdf/2501.10024) · [Vedavani benchmark](https://arxiv.org/pdf/2506.00145) · [AI4Bharat models](https://models.ai4bharat.org/)
- Local runtime: [Ollama](https://ollama.com/) · [qwen3-vl:8b on Ollama](https://ollama.com/library/qwen3-vl:8b) (tagged `tools` + `vision`) · [mlx-whisper](https://github.com/ml-explore/mlx-examples)
- Strands Agents: [strandsagents.com](https://strandsagents.com/) — core SDK with Ollama provider; robots lab ([docs](https://strandsagents.com/docs/labs/robots/)) targets SO-10x arms via LeRobot, not used
- Cloud-inference Reachy Mini reference (Option B, DESIGN §1.5): [cagataycali/tiny-the-reachy](https://github.com/cagataycali/tiny-the-reachy) — Strands agent on Reachy Mini with cloud STT/LLM (OpenAI Realtime, Nova Sonic, Gemini) by default; source for the motion safety-envelope pattern and MCP dev-tooling idea, not for its multi-persona/cloud-STT design
- Predecessor design: earlier `mitra/README.md` — view with `git show 40639db:mitra/README.md`
