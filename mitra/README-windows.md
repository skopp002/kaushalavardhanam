# Running Mitra on Windows

The main `README.md` targets a MacBook Pro M1 Max. Three layers of the stack are
Apple-Silicon-only, and the `reachy-mini` daemon has no Windows build at all —
so on this platform Mitra runs as a **model and pipeline host, not a robot
host**. This document covers the differences. Everything not mentioned here
works as the main README describes.

> **Status: this is the verification branch, not a verified path.** The config
> in this branch is the Windows configuration; the steps below are what it
> expects. Section 9 lists what is known to be unavailable on Windows and why.
> Findings from an actual Windows run belong back in this file.

---

## What differs from the macOS path

| Layer | macOS | Windows | Why |
|---|---|---|---|
| Robot / sim daemon | `mjpython -m reachy_mini.daemon.app.main --sim` | **not available** | `reachy-mini` supports macOS and Linux only (REQUIREMENTS §3) |
| Robot backend | `reachy` | `fake` (`--robot fake`) | no daemon to connect to |
| ASR | `mlx-whisper` | `transformers` | mlx has no non-Darwin wheels |
| Wake ASR | `mlx-whisper` | `transformers` | same |
| TTS | Indic Parler-TTS | VITS (`facebook/mms-tts-hin`) | parler-tts pins `transformers<=4.46.1`, which collides with reachy-mini's `huggingface-hub>=1.17` — not co-installable |
| Compute device | `mps` | `cpu` (`cuda:0` optional) | no Metal; on a consumer GPU Ollama already holds most of the VRAM |
| Microphone | robot's USB mic | host mic via sounddevice (WASAPI) | consequence of the missing daemon |
| Speaker | robot's speaker | host default output | same |

The code itself is platform-clean: every file read and write in `src/` is
explicitly `encoding="utf-8"`, so Devanagari corpora and the turn log do not
depend on the system code page. No POSIX-only module (`fcntl`, `termios`,
`signal.SIGALRM`, `select` on stdin) is imported anywhere in the runtime path.

---

## 1. Prerequisites

**Python 3.10–3.12** from [python.org](https://www.python.org/downloads/windows/)
(`reachy-mini` caps at 3.12; 3.13 will fail to resolve). Tick *Add python.exe to
PATH* during install. Verify the launcher sees it:

```powershell
py --list
py -3.12 --version
```

**Ollama** — install the native Windows build from
[ollama.com/download](https://ollama.com/download). It registers a background
service on `127.0.0.1:11434` and starts at login, so `ollama serve` will report
that the address is already in use; that is expected, not an error.

**Windows Terminal** (or any UTF-8 console). The legacy `conhost` window cannot
render Devanagari — Mitra's replies will come out as boxes even when everything
works. Windows Terminal ships with Windows 11 and is a free Store install on 10.

**Enable long paths.** The HuggingFace cache builds deep directory names
(`models--mlx-community--whisper-large-v3-turbo\snapshots\<sha>\...`) that
overrun the 260-character `MAX_PATH` limit and fail mid-download with
`OSError: [Errno 2]`. In an **admin** PowerShell:

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
```

**Enable Developer Mode** (*Settings → System → For developers*). Without it
`huggingface_hub` cannot create symlinks and warns on every launch that it is
falling back to full file copies — which works, but silently doubles the disk
each model costs.

`ffmpeg` is **not** needed: audio reaches Whisper as a NumPy array from
sounddevice, never through a decoder.

---

## 2. Disk space

Budget **at least 15 GB free**. Model downloads fail confusingly when space runs
out — HuggingFace warns once and then the process appears to hang.

- Qwen3-VL 8B via Ollama: ~6 GB
- Whisper small (main ASR on this config): ~500 MB
- Whisper small (wake word): shares the same cache entry
- MMS-TTS Hindi: ~250 MB
- PyTorch wheels: ~2.5 GB CPU-only, several GB more for a CUDA build

Ollama stores models under `%USERPROFILE%\.ollama\models` and HuggingFace under
`%USERPROFILE%\.cache\huggingface\hub`; both accept a redirect to another drive
via the `OLLAMA_MODELS` and `HF_HOME` environment variables if `C:` is tight.

```powershell
Get-PSDrive C
Get-ChildItem "$env:USERPROFILE\.cache\huggingface\hub" | Measure-Object Length -Sum
```

---

## 3. Python environment

Pick **one** interpreter and stay on it — a half-activated virtualenv is the
most common failure on this project.

```powershell
cd mitra
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip --version        # must print a path inside .venv
```

If activation dies with *"running scripts is disabled on this system"*, the
execution policy is blocking the activation script. Allow signed-and-local
scripts for your own account only:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

In `cmd.exe` the activation script is `.venv\Scripts\activate.bat` instead. On
Windows the venv interpreter is `python`, never `python3` — any command in the
main README or `README-linux.md` that says `python3` means `python` here.

---

## 4. Install

Quote the extras with **double** quotes. Single quotes are literal characters to
`cmd.exe`, and pip receives a package name that does not exist:

```powershell
pip install -e ".[agent,wake,vad,speech]"
pip install sounddevice
ollama pull qwen3-vl:8b-instruct
```

`sounddevice`'s wheel bundles PortAudio, so there is nothing to install
system-side for audio.

**Do not install `reachy-mini`.** It has no Windows support, and pulling it in
only constrains the dependency solver for a daemon that cannot run. The `robot`
extra is therefore skipped above; `FakeReachy` needs nothing.

**Do not run** the `parler-tts` line from the main README:

```powershell
# pip install git+https://github.com/huggingface/parler-tts.git   # macOS only
```

It downgrades `transformers` to 4.46.1 and breaks the rest of the stack. If you
have already run it:

```powershell
pip uninstall -y parler_tts descript-audio-codec descript-audiotools
pip install --upgrade "transformers>=4.57" "huggingface-hub>=1.17"
```

The `asr` extra is a no-op here — its marker is `platform_machine=='arm64' and
sys_platform=='darwin'` — so including or omitting it makes no difference.

Verify:

```powershell
python main.py --check
```

Expected on Windows (the robot line is the one difference from Linux):

```
components:
  MISSING  reachy-mini (robot/sim)  (reachy_mini)   <- expected: no Windows build
  ok       strands-agents (agent)
  ok       openwakeword (wake)
  ok       silero-vad (VAD)
  ok       transformers (ASR, backend=transformers)
  ok       transformers (TTS, engine=vits)
ollama:
  ok       server at http://localhost:11434
  ok       model qwen3-vl:8b-instruct
lexicon: 53 seed entries
```

---

## 5. The robot backend

`config.yaml` still ships `robot.backend: reachy`, matching every other branch,
but that backend cannot connect on Windows. Run with the override instead:

```powershell
python main.py --robot fake --debug
```

`FakeReachy` is a test double, not a headless robot: `mic_read()` yields an
empty buffer unless a test feeds it, and `speaker_play()` just records what it
was handed, so the conversation loop runs end to end
with no real speech in or out. That is enough to exercise the LLM, the
validator, the Sanskrit checks, the follow-up layer and the shloka corpus — the
whole reasoning half of the pipeline — which is what this branch is for. It is
not enough for a demo.

To make Windows genuinely speak and listen, the missing piece is a robot-free
host backend: `ReachyRobot` already has both halves of it
(`_start_built_in_mic` uses `sounddevice.InputStream`, `_playback_host` uses
`sd.play`/`sd.stop`, and barge-in works through the latter), but both sit behind
a live daemon connection in `__init__`. Lifting those two paths into a third
backend alongside `reachy` and `fake` is the smallest change that would make
this platform demo-capable.

---

## 6. Microphone and speaker

Relevant once a host backend exists (section 5); the settings are already in
place for it.

```powershell
python -c "import sounddevice as sd; print(sd.query_devices())"
```

`built_in_mic_device: null` in `config.yaml` means *the system default input*,
which is the right answer on Windows: device names are machine-specific
(`Microphone (Realtek(R) Audio)`), so there is no portable literal to ship.
Set one only if the default picks the wrong input; sounddevice also accepts the
integer index printed by the command above.

Confirm capture works:

```powershell
python -c "import sounddevice as sd, numpy as np; print('recording 3s, speak now'); a=sd.rec(3*16000, samplerate=16000, channels=1); sd.wait(); print('peak:', float(np.abs(a).max()), 'rms:', float(np.sqrt((a**2).mean())))"
```

Peak should be comfortably above 0.1. If it is near zero, check *Settings →
System → Sound → Input* for the selected device and its level, and *Privacy &
security → Microphone*, where **Let desktop apps access your microphone** must
be on — Windows denies mic access silently, returning digital silence rather
than an error.

---

## 7. Device placement

The shipped config puts all three speech models on CPU, because Ollama with
`keep_alive: 30m` holds Qwen3-VL 8B (~6.5–7 GB) resident on the GPU:

| Component | Q4 size | Device |
|---|---|---|
| Qwen3-VL 8B (+ vision, KV cache) | ~6.5–7 GB | GPU, via Ollama |
| Whisper small (main ASR) | ~500 MB | CPU |
| Whisper small (wake) | same cache entry | CPU |
| MMS-TTS Hindi | ~250 MB | CPU |

If turn latency is unacceptable and you have an NVIDIA card with headroom,
install a CUDA torch build and move the **main ASR** first — it processes the
longest audio, so the speedup is largest:

```powershell
pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu124
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

then set `models.asr.device: "cuda:0"`. Make room by shortening `keep_alive` or
dropping to `qwen3-vl:4b-instruct`. Keep the wake detector on CPU regardless:
it runs on every gated speech window, continuously.

---

## 8. Sanskrit data and corpora

**Grammar data** (one time — ~78 MB, lives outside git). Every reply is checked
against a real inflected lexicon rather than a list of banned words (DESIGN §5);
the same fetch also indexes the Cologne dictionaries used by the lexicon review
CLI:

```powershell
pip install -e ".[sanskrit]"
python scripts\fetch_sanskrit_data.py     # vidyut morphology + Cologne dicts
python scripts\build_dictionary.py        # index MW/Apte for mitra-lexicon
python scripts\eval_grammar.py            # score the checks on real sentences
```

Skip it and Mitra runs exactly as before, logging one warning at startup and
falling back to the Devanagari-ratio check alone.

**Corpora.** The verse corpus for *"recite a shloka"* (`data\shlokas.json`, 500
public-domain verses) is committed, so a fresh clone can recite with no extra
step. The conversational phrasebook is **not** — the source is copyrighted, so
`data\daily.pdf` and `data\phrasebook.jsonl` are gitignored. Copy them from a
machine that has them, or rebuild with `python scripts\build_phrasebook.py
data\daily.pdf`. Without it Mitra still talks; replies are just ungrounded, and
startup says so.

---

## 9. Run

Two processes instead of the macOS three — there is no daemon to start.

**Ollama** is already running as a service. Verify only:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags | Select-Object -Expand models | Select-Object name
```

**Mitra:**

```powershell
python main.py --robot fake --debug
```

`--debug` also mirrors every spoken line in English, so the console is readable
without Devanagari:

```
INFO mitra: speak: मह्यं गणितं रोचते।
INFO mitra: speak (en): Mathematics is pleasing to me.
```

The gloss is a second, history-free call to the same Ollama model (~0.4 s, made
after playback starts, so it never delays speech) and it translates literally —
a mangled reply reads as mangled English rather than being quietly repaired.
Turn it off with `logging.gloss_english: false`.

First run downloads ~1 GB of Whisper and TTS weights. Progress bars are
suppressed by `HF_HUB_DISABLE_PROGRESS_BARS` in `main.py`; to watch progress,
comment that line out, or in a second terminal:

```powershell
while ($true) { (Get-ChildItem "$env:USERPROFILE\.cache\huggingface\hub" -Recurse -File | Measure-Object Length -Sum).Sum / 1GB; Start-Sleep 5 }
```

Loading Whisper onto CPU takes a while even after the download completes.
**Wait for `Mitra asleep — say the wake word` before speaking.** Nothing is
listening until that line appears.

---

## 10. Known limitations on this path

**No robot, real or simulated.** `reachy-mini` has no Windows build, so
`--robot fake` is the only backend that runs. Head motion, antennas and the
state gestures (FR-5.3) have no effect.

**No camera.** `FakeReachy.camera_read()` returns a blank frame, so vision turns
do not work — object recognition, the core of FR-2, cannot be tested here.

**No audio in or out** under `fake`: the mic yields an empty buffer and the
speaker only records what it was handed. Replies appear in the `--debug` console but are never audible, and the
wake word can only be exercised by feeding audio in directly
(`scripts\dry_run.py`, `tests\`). Section 5 describes the change that would fix
this.

What *does* work end to end: the LLM, prompt and history layers, the Devanagari
validator, the vidyut morphology checks, vocabulary and agreement, the follow-up
question layer, name handling, the shloka corpus and its danda pauses, the
gloss, and the full eval harness (`eval\eval_grammar.py`).

---

## 11. Troubleshooting

**`UnicodeEncodeError: 'charmap' codec can't encode character`** — you redirected
output to a file or a pipe, where Python falls back to the system code page
instead of the console's UTF-8. Turn on UTF-8 mode for the run:

```powershell
$env:PYTHONUTF8 = "1"
python main.py --robot fake --debug > run.log 2>&1
```

The turn log (`logs\turns.jsonl`) is unaffected — it opens with an explicit
`encoding="utf-8"`.

**Devanagari renders as boxes** — a font problem in the console, not an encoding
one. Use Windows Terminal, and pick a font with Devanagari coverage (Nirmala UI)
in its profile settings.

**`Activate.ps1 cannot be loaded because running scripts is disabled`** — see
section 3.

**`ModuleNotFoundError: No module named 'yaml'`** — wrong interpreter. `where
python` should print the `.venv\Scripts` path first; if it does not, re-activate.

**`ollama serve` says the address is in use** — expected; the installer already
runs it as a service. Confirm with the `Invoke-RestMethod` call in section 9.

**Download fails with `OSError: [Errno 2] No such file or directory`** on a very
long cache path — long paths are not enabled. See section 1.

**`huggingface_hub` warns about symlinks on every launch** — Developer Mode is
off. Harmless, but each model then costs twice the disk. See section 1.

**`wake check` fires but the transcript is nonsense** — repeated characters,
stock phrases (`Thank you.`), or the wake word in another script are Whisper
hallucinating on short clips, usually because it guessed the wrong language.
`README-linux.md` §10 has the one-line fix in `src/audio/wake.py`; it is
platform-independent and applies unchanged here.
