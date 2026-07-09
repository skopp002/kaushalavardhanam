# CLAUDE.md — Mitra project context

Context for Claude Code (and human collaborators) working in `mitra/`. Read this before making changes.

## What this project is

Mitra (from मित्रम् "friend"; "mitra" is its vocative — सम्बोधन विभक्ति — the form you call it by) is a Sanskrit-speaking interactive robot on **Reachy Mini Lite**, tethered to a MacBook Pro M1 Max that runs the full pipeline with **local open-source models only** (offline after model download). Wake word "mitra" → recognizes shown objects and names them in Sanskrit → converses (understands English/Kannada/Sanskrit, always replies in Sanskrit).

**Current phase:** code skeleton implemented per DESIGN.md §2 (orchestrator, robot wrapper + FakeReachy, tools, validator, lexicon + seed, audio/TTS modules, main.py) with a green pytest suite using fakes. Heavy dependencies are optional extras with lazy imports. Next: Phase 0/1 bring-up against live models and the sim/robot daemon (REQUIREMENTS.md §10); the seed lexicon awaits Sanskrit-reviewer verification.

## Read these first

| File | What it is |
|---|---|
| `REQUIREMENTS.md` (v1.3) | Functional requirements FR-1..FR-7, memory/latency budgets, risks R1..R7, 8-week phased plan with acceptance criteria |
| `DESIGN.md` (v1.2) | Module decomposition, Strands↔Reachy integration, state machine, prompting/validation, decisions D1..D5 |
| `architecture-local.png` / `architecture-cloud.png` | Option A (fully local, the v1 target) and Option B (cloud-extended) |

## Load-bearing decisions — don't silently reverse these

1. **Local-first is a hard requirement.** The robot must work with no internet at runtime. Cloud (Option B) is a config-gated Strands provider swap (`OllamaModel` → `AnthropicModel`/`BedrockModel`), disabled by default. Raw mic audio never leaves the host in either option.
2. **LLM+vision = Qwen3-VL 8B Instruct via Ollama** (`qwen3-vl:8b-instruct` — the bare `:8b` tag is the *thinking* variant: slow, returns empty content), chosen over Gemma 3 12B because it has **native tool calling in Ollama** (Gemma 3 doesn't) and is smaller. Revisit only via the Phase 3 Sanskrit bake-off, and record scores.
3. **Core `strands` SDK, NOT `strands-robots`.** The lab package targets LeRobot arms (SO-100/101) with VLA policies; Reachy Mini has no driver or manipulation. Robot actions are custom `@tool` functions over the `reachy-mini` SDK (DESIGN §1.1–1.3).
4. **Validation and speech are deterministic.** The model may invoke `capture_image()` itself, but every reply passes the Devanagari validator and is spoken via the orchestrator — never trust the local model to skip guardrails (DESIGN §1.4).
5. **The lexicon cache is the accuracy mechanism.** Human-verified Sanskrit object names always override model generation (FR-2.5/2.6). Don't "simplify" it away.
6. **Speech stack:** wake via ASR-transcript match (whisper-tiny, works today) with openWakeWord (custom "mitra") as the Phase-1 target → Silero VAD → Whisper (mlx/whisper.cpp, en/kn; Sanskrit fine-tune experimental) → Indic Parler-TTS (Sanskrit, MPS; VITS Indic-TTS fallback).

## Conventions

- **Git:** stage with `git add` only — the maintainer commits manually. Never run `git commit` or `git push`.
- **Docs are versioned** (header line in each). Bump the version and add a one-line change note when you materially change REQUIREMENTS.md or DESIGN.md.
- **Diagrams:** regenerate both variants with `python3 scripts/gen_diagrams.py` (needs matplotlib + Pillow). It emits `.excalidraw` + `.png` pairs from one shared spec — edit the spec in the script, not the outputs. If you hand-edit an `.excalidraw` instead, re-export its PNG from Excalidraw itself so they match.
- **Sanskrit in docs/code:** Devanagari with IAST transliteration alongside; simple laukika register.

## History

The predecessor design study (edge Jetson vs AWS Bedrock Nova, translation bridge) was replaced by this design; it's preserved at git commit `40639db` (`git show 40639db:mitra/README.md`). Its key conclusion — edge Sanskrit infeasible — was revisited and reversed for the M1 Max + 2026 models (REQUIREMENTS §7).
