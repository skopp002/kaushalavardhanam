# Mitra (मित्रम्) — Sanskrit-Speaking Robot on Reachy Mini

Mitra ("friend" in Sanskrit) is an interactive desktop robot built on the **Reachy Mini Lite**. Say **"mitra"** to wake it, show it any object and it names the object in Sanskrit, and converse with it — it understands English, Kannada, or Sanskrit, and always replies in spoken Sanskrit. All inference runs **locally** on the host Mac with open-source models; no internet is needed at runtime.

## Architecture

### Option A — fully local inference (v1 target)

![Mitra architecture — fully local](architecture-local.png)

### Option B — cloud-extended inference (speech + wake word stay local)

![Mitra architecture — cloud-extended](architecture-cloud.png)

*Editable diagram sources: [architecture-local.excalidraw](architecture-local.excalidraw) · [architecture-cloud.excalidraw](architecture-cloud.excalidraw) — open at [excalidraw.com](https://excalidraw.com) or with the VS Code Excalidraw extension.*

**Flow in one paragraph:** the robot's microphones stream over USB through the `reachy-mini` SDK to a local **openWakeWord** model listening for "mitra". On wake, the robot nods and greets; **Silero VAD** segments utterances, **Whisper** transcribes them (with language detection across English/Kannada/Sanskrit), and a **Strands Agent** — using the **OllamaModel provider** against a local **Qwen3-VL 8B** (conversation + vision + native tool calling) — produces a short Sanskrit reply. Replies pass a Devanagari validator, get spoken by **AI4Bharat Indic Parler-TTS**, and play through the robot's speaker. Object questions make the model call its `capture_image` tool, with a **human-verified Sanskrit lexicon cache** overriding generated names for accuracy.

**Extending to the cloud (Option B)** is a one-line Strands provider swap — `OllamaModel` → `AnthropicModel`/`BedrockModel`. The agent, tools, prompts, and validator are unchanged; wake word, ASR, and TTS stay on the host so raw microphone audio never leaves it, and the local model remains installed as an offline fallback. Details in [DESIGN.md §1.5](DESIGN.md).

## New to AI? How the Pieces Fit

If words like "model", "Ollama", and "agent" are new to you, read this first — every other document assumes these ideas.

**A model is a file of numbers, not a program (and not a Docker image).** When you run `ollama pull qwen3-vl:8b`, you download ~6 GB of *weights* — billions of numbers learned during training, plus a little metadata. The file does nothing by itself; it can't be "started" any more than a spreadsheet can. Ollama's commands *look* like Docker on purpose (`pull`, `name:tag`, layers with `sha256:` digests, even a "Modelfile") because it borrowed Docker's convenient *distribution* style — but there is no container, no operating system inside, nothing "running in" the model. It's data.

**Ollama is the serving layer — the thing that makes the numbers useful.** `ollama serve` is a small server on your laptop (at `http://localhost:11434`) that loads the weights into memory, runs them on your Mac's GPU, and offers a simple HTTP API: send text in, get generated text back. This is the same shape as ChatGPT or Claude — model weights behind a serving API — except the whole thing lives on your machine. That's the point of Mitra's design: your voice and camera images never leave your laptop.

**The other AI pieces are specialist models, each with its own job:**

| Piece | Job | In one line |
|---|---|---|
| Wake word (openWakeWord) | Hear "mitra" | A tiny always-on model that listens for one word and nothing else — so the big models stay idle (and your privacy stays intact) until you call |
| VAD (Silero) | Detect speech | Notices when you start and stop talking, so we know when an utterance is complete |
| ASR (Whisper) | Speech → text | Turns your audio into written words ("automatic speech recognition") |
| LLM/VLM (Qwen3-VL via Ollama) | Think | The large language model: reads your words (and camera images — the "V" is for vision) and writes the Sanskrit reply |
| TTS (Indic Parler-TTS) | Text → speech | Turns the written Sanskrit into a spoken voice ("text to speech") |

**An "agent" is an LLM that can use tools.** A plain LLM can only write text. The Strands Agents SDK wraps our LLM in a loop where the model may also *call functions we hand it* — Mitra gives it four: `capture_image` (take a photo), `speak_sanskrit` (talk), `nod` (move the head), and `end_session` (go back to sleep). When you ask "what is this?", the model itself decides to call `capture_image`, looks at the frame, and answers. The robot is not an agent and never calls the model — it is the *body* (camera, microphones, speaker, motors); the agent is the *brain*; and a small state machine (the orchestrator) is the *nervous system* connecting them.

## Documents

| Doc | Contents |
|---|---|
| [REQUIREMENTS.md](REQUIREMENTS.md) | Goals, functional requirements, hardware/memory budget, risks, phased plan |
| [DESIGN.md](DESIGN.md) | Module design, Strands ↔ Reachy Mini integration (why core `strands` with custom tools rather than `strands-robots`), state machine, prompting, testing |
| [CLAUDE.md](CLAUDE.md) | Project context for Claude Code sessions: load-bearing decisions, conventions, how to regenerate diagrams |

## Stack at a Glance

| Layer | Component |
|---|---|
| Robot | Reachy Mini Lite (`reachy-mini` Python SDK, USB-tethered) |
| Host | MacBook Pro M1 Max, 32 GB — all models local (~13.5 GB resident) |
| Wake word | openWakeWord (custom "mitra" model) |
| ASR | Whisper large-v3 (en/kn) + Sanskrit fine-tune |
| LLM + vision | Qwen3-VL 8B Instruct Q4 via Ollama (native tool calling) |
| TTS | AI4Bharat Indic Parler-TTS (Sanskrit) |
| Agent | Strands Agents SDK (core) with Ollama provider; robot actions as tools |

## Run in Simulation (no robot needed)

The `reachy-mini` SDK ships a **MuJoCo simulation backend**: the daemon started with `--sim` behaves exactly like a real Reachy Mini Lite on USB — same localhost daemon, same `ReachyMini()` client. Because all hardware access in Mitra goes through `src/robot/reachy.py`, the entire pipeline runs unmodified against the simulator; only which daemon is running changes.

**What maps where:** head motion (`nod`) animates in the MuJoCo viewer; `capture_image` returns frames rendered from the simulated robot's viewpoint (the `minimal` scene includes an apple, a croissant, and a duck on a table — *एतत् सेवफलम् अस्ति* is testable today); microphone and speaker map to the **Mac's own audio devices**, so the full wake-word → VAD → Whisper → Parler-TTS chain runs for real through laptop audio (software echo cancellation via GStreamer replaces the robot's XMOS hardware AEC). Not represented in sim: the Lite's 2-mic far-field acoustics (FR-1.4 accuracy targets), real camera optics/lighting, the 5 W speaker, and sound-source localization — those remain hardware checks in Phases 0–1.

### Setup (macOS)

> **⚠️ Always create and activate the project venv first.** The system `pip`/`python3` on macOS are often broken or too old (Python ≥3.10 is required); every install and run below assumes the venv is active — re-activate it in every new terminal.

1. **Environment** (from this `mitra/` directory; uses [uv](https://docs.astral.sh/uv/) to provision Python 3.12 if the system lacks it):

   ```bash
   cd mitra
   uv venv .venv --python 3.12
   source .venv/bin/activate        # do this in every new terminal
   ```

2. **Install the SDK with the simulation extra** (Pollen recommends plain `pip` over `uv` on macOS for the MuJoCo packages):

   ```bash
   pip install "reachy-mini[mujoco]"
   ```

3. **Start the simulated robot.** On macOS the MuJoCo GUI requires the `mjpython` launcher (Linux/Windows use `reachy-mini-daemon --sim` instead):

   ```bash
   mjpython -m reachy_mini.daemon.app.main --sim --scene minimal
   ```

   A 3D viewer opens (drag to rotate, scroll to zoom). Keep this terminal running — it is the daemon. Verify at <http://localhost:8000/docs>.

   > **Gotcha:** if `mjpython` segfaults in `libgstpython.dylib`, rename that GStreamer plugin so it isn't auto-loaded (official workaround; doesn't affect audio/video):
   >
   > ```bash
   > mv $(python -c "import gstreamer_python, pathlib; print(pathlib.Path(gstreamer_python.__file__).parent / 'lib/gstreamer-1.0/libgstpython.dylib')") \
   >    $(python -c "import gstreamer_python, pathlib; print(pathlib.Path(gstreamer_python.__file__).parent / 'lib/gstreamer-1.0/libgstpython_.dylib')")
   > ```

4. **Smoke test** (second terminal, same venv) — exercises the exact primitives Mitra's tools wrap:

   ```python
   from reachy_mini import ReachyMini
   from reachy_mini.utils import create_head_pose

   with ReachyMini() as mini:              # auto-connects to the sim daemon on localhost
       # "nod" — what robot.head.nod() wraps
       mini.goto_target(head=create_head_pose(z=20, roll=10, mm=True, degrees=True), duration=0.5)
       mini.goto_target(head=create_head_pose(), duration=0.5)

       # "capture_image" — frame of the MuJoCo scene, numpy (H, W, 3) uint8
       frame = mini.media.get_frame()
       print("camera frame:", frame.shape, frame.dtype)
   ```

5. **Switching to hardware:** plug in the Reachy Mini Lite over USB and run `reachy-mini-daemon` (no `--sim`). The same code connects to the real robot.

References: [simulation setup guide](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/platforms/simulation/get_started.md) · [SDK installation](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/SDK/installation.md) · [Python SDK media APIs](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/SDK/python-sdk.md)

## Running

```bash
cd mitra

# Unit tests — no robot, no models, no network needed (fakes throughout)
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python numpy pyyaml pillow pytest
.venv/bin/python -m pytest

# Which components are installed / is Ollama up / lexicon seed count
.venv/bin/python main.py --check

# Full pipeline (after: pip install -e '.[all]', ollama pull qwen3-vl:8b,
# and a running daemon — real robot or the simulator above)
python main.py --debug
```

The lexicon review CLI (FR-2.5) lists model-generated names awaiting human verification: `mitra-lexicon --db data/lexicon.db`.

## Status

Implemented and unit-tested with fakes: orchestrator state machine, robot wrapper (+`FakeReachy`), agent tools, validator, lexicon store (53-entry seed), language detector, audio/TTS module skeletons, `main.py` wiring. Not yet exercised against live models or a daemon — that is Phase 0/1 bring-up (REQUIREMENTS §10): install the extras, `ollama pull qwen3-vl:8b`, train the "mitra" wake model, and run against the simulator or robot. The seed lexicon needs review by a Sanskrit reviewer (FR-2.6).

Predecessor feasibility study (edge Jetson / AWS Bedrock design) is preserved in git history: `git show 40639db:mitra/README.md`.
