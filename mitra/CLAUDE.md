# CLAUDE.md — Mitra project context

Context for Claude Code (and human collaborators) working in `mitra/`. Read this before making changes.

## What this project is

Mitra (from मित्रम् "friend"; "mitra" is its vocative — सम्बोधन विभक्ति — the form you call it by) is a Sanskrit-speaking interactive robot on **Reachy Mini Lite**, tethered to a MacBook Pro M1 Max that runs the full pipeline with **local open-source models only** (offline after model download). Wake word "mitra" → recognizes shown objects and names them in Sanskrit → converses (understands English/Kannada/Sanskrit, always replies in Sanskrit, and always asks something back so the turn does not dead-end).

**Current branch (`coherent-convo`):** turn-taking (FR-3.12) — Mitra answers *and* asks, so every interaction stays a conversation. New `src/agent/followups.py`, wired in the orchestrator between validation and speech; `conversation.follow_up` in config.yaml turns it off. Second increment, from the first full live session: each question now carries **two follow-on questions** for when the child answers it, so a subject gets a second and third turn instead of a stock *"tell me more"*; the speaker's **name** is exempt from the Sanskrit checks (`src/agent/names.py`, FR-3.15) — Mitra asked for it, was told, and answered *"sorry, I do not understand"*; and **"yes" to "shall I recite another verse?"** reaches the corpus (FR-3.16). `docs/demo-script.md` is the verified question list for driving a live demo — every line in it was produced by the real pipeline. Third increment, from a longer session: the *अहं X प्रियम् अस्मि* construction is rejected outright (FR-3.17), Mitra's own questions feed the vocabulary so it can answer with the words it asks with, and a follow-up draw with no keyword match takes the open subject's next step rather than a random new topic.

**Current phase:** code skeleton implemented per DESIGN.md §2 (orchestrator, robot wrapper + FakeReachy, tools, validator, lexicon + seed, audio/TTS modules, main.py) with a green pytest suite using fakes. Heavy dependencies are optional extras with lazy imports. Next: Phase 0/1 bring-up against live models and the sim/robot daemon (REQUIREMENTS.md §10); the seed lexicon awaits Sanskrit-reviewer verification.

## Read these first

| File | What it is |
|---|---|
| `REQUIREMENTS.md` (v1.9) | Functional requirements FR-1..FR-7, memory/latency budgets, risks R1..R7, 8-week phased plan with acceptance criteria |
| `DESIGN.md` (v1.7) | Module decomposition, Strands↔Reachy integration, state machine, prompting/validation, decisions D1..D5 |
| `architecture-local.png` / `architecture-cloud.png` | Option A (fully local, the v1 target) and Option B (cloud-extended) |
| `flow-wake.png` | Numbered order of execution for a wake + conversation turn |
| `docs/demo-script.md` | The verified question list for a live demo: what to say, what Mitra answers, what to avoid and why |

## Load-bearing decisions — don't silently reverse these

1. **Local-first is a hard requirement.** The robot must work with no internet at runtime. Cloud (Option B) is a config-gated Strands provider swap (`OllamaModel` → `AnthropicModel`/`BedrockModel`), disabled by default. Raw mic audio never leaves the host in either option.
2. **LLM+vision = Qwen3-VL 8B Instruct via Ollama** (`qwen3-vl:8b-instruct` — the bare `:8b` tag is the *thinking* variant: slow, returns empty content), chosen over Gemma 3 12B because it has **native tool calling in Ollama** (Gemma 3 doesn't) and is smaller. Revisit only via the Phase 3 Sanskrit bake-off, and record scores.
3. **Core `strands` SDK, NOT `strands-robots`.** The lab package targets LeRobot arms (SO-100/101) with VLA policies; Reachy Mini has no driver or manipulation. Robot actions are custom `@tool` functions over the `reachy-mini` SDK (DESIGN §1.1–1.3).
4. **Validation and speech are deterministic.** The model may invoke `capture_image()` itself, but every reply passes the Devanagari validator and is spoken via the orchestrator — never trust the local model to skip guardrails (DESIGN §1.4). One deliberate exception: turns the orchestrator tags [explain_in_english] (explicit user request, FR-3.2 v1.4) waive the Devanagari check for that single reply.
5. **Mitra's questions are retrieved, not generated** (FR-3.12, `agent/followups.py`). Every reply ends with a short Sanskrit question so the conversation keeps going, and that question comes from a hand-verified list, appended *after* validation. Don't "simplify" this into a prompt instruction — that is exactly what v1.5 removed, because the model's own reciprocal question carried most of the grammar errors while the answer beside it was sound. Adding a question means adding a row to the list and having a Sanskrit reader check it. The same goes for each row's `deepen` questions, and for anything Mitra *offers* to do: an offer it cannot honour ("shall I recite another verse?") needs a deterministic path behind it, not a hope that the model will cope.
6. **The lexicon cache is the accuracy mechanism.** Human-verified Sanskrit object names always override model generation (FR-2.5/2.6). Don't "simplify" it away.
7. **Speech stack:** wake via ASR-transcript match (whisper-tiny, works today) with openWakeWord (custom "mitra") as the Phase-1 target → Silero VAD → Whisper (mlx/whisper.cpp, en/kn; Sanskrit fine-tune experimental) → Indic Parler-TTS (Sanskrit, MPS; VITS Indic-TTS fallback).
8. **The prompt's few-shot examples must pass the Sanskrit checks.** They are what the model imitates, so an example using a word outside the vocabulary teaches a reply that will be rejected — we shipped one (*क्षीरं बलं ददाति*) and it cost a live turn. `tests/test_sanskrit.py::GOOD` is where the invariant is enforced; add new examples there.

## Conventions

- **Git:** stage with `git add` only — the maintainer commits manually. Never run `git commit` or `git push`.
- **Docs are versioned** (header line in each). Bump the version and add a one-line change note when you materially change REQUIREMENTS.md or DESIGN.md.
- **Diagrams:** regenerate all three variants with `python3 scripts/gen_diagrams.py` (needs matplotlib + Pillow). It emits `.excalidraw` + `.png` pairs from one shared spec — edit the spec in the script, not the outputs. If you hand-edit an `.excalidraw` instead, re-export its PNG from Excalidraw itself so they match.
- **Sanskrit in docs/code:** Devanagari with IAST transliteration alongside; simple laukika register.

## History

The predecessor design study (edge Jetson vs AWS Bedrock Nova, translation bridge) was replaced by this design; it's preserved at git commit `40639db` (`git show 40639db:mitra/README.md`). Its key conclusion — edge Sanskrit infeasible — was revisited and reversed for the M1 Max + 2026 models (REQUIREMENTS §7).
