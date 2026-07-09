"""Generate mitram architecture diagrams (local + cloud variants): .excalidraw + .png each."""
import json, random, os

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
W, H = 1580, 880

BASE_NODES = [
    ("user",    15, 390, 145, 110, "User\nspeaks, shows\nobjects, listens", "#fff3bf", "box", 12),
    ("reachy", 190, 140, 210, 590, "Reachy Mini Lite", "#f1f3f5", "container", 15),
    ("mics",   215, 230, 160, 60, "2x microphones", "#ffffff", "box", 13),
    ("camera", 215, 330, 160, 60, "Wide-angle camera", "#ffffff", "box", 13),
    ("speaker",215, 480, 160, 60, "5 W speaker", "#ffffff", "box", 13),
    ("motors", 215, 590, 160, 70, "Head motors\n(6-DOF + body)", "#ffffff", "box", 13),
    ("sdk",    490, 200, 130, 470, "reachy-mini\nSDK\n(media\nbackend:\nOpenCV +\nsounddevice)", "#ffffff", "box", 12),
    ("wake",   660, 130, 190, 65, "openWakeWord\nwake word: 'mitram'", "#ffffff", "box", 12),
    ("vad",    660, 240, 190, 50, "Silero VAD", "#ffffff", "box", 13),
    ("asr",    660, 330, 190, 80, "Whisper ASR\n(en / kn / sa)\n+ language detect", "#ffffff", "box", 12),
    ("orch",   890, 130, 310, 105, "Orchestrator (state machine)\nASLEEP > LISTENING >\nTHINKING > SPEAKING", "#d0ebff", "box", 13),
    ("agent",  890, 290, 310, 175, "Strands Agent (core SDK)\nmodel provider (swappable)\ntools: capture_image |\nspeak_sanskrit | nod |\nend_session", "#d0ebff", "box", 13),
    ("lex",    890, 520, 310, 75, "Sanskrit lexicon cache\n(human-verified names win)", "#ffffff", "box", 12),
    ("tts",    660, 500, 190, 95, "Indic Parler-TTS\nSanskrit voice\n(MPS)", "#ffffff", "box", 12),
]

BASE_EDGES = [
    ("user", "mics",   "speech",            "r", 0.2, "l", 0.5, False, False),
    ("user", "camera", "shows object",      "r", 0.5, "l", 0.5, False, False),
    ("speaker", "user","Sanskrit audio",    "l", 0.5, "r", 0.8, False, False),
    ("mics", "sdk",    "USB audio",         "r", 0.5, "l", 0.15, False, False),
    ("camera", "sdk",  "USB video",         "r", 0.5, "l", 0.35, False, False),
    ("sdk", "speaker", "audio out",         "l", 0.62, "r", 0.5, False, False),
    ("sdk", "motors",  "motor cmds",        "l", 0.9, "r", 0.5, False, False),
    ("sdk", "wake",    "mic stream",        "r", 0.08, "l", 0.5, False, False),
    ("wake", "vad",    "session audio",     "b", 0.5, "t", 0.5, False, False),
    ("vad", "asr",     "utterance",         "b", 0.5, "t", 0.5, False, False),
    ("wake", "orch",   "wake event",        "r", 0.5, "l", 0.3, True,  False),
    ("asr", "orch",    "transcript + lang", "r", 0.15, "l", 0.9, False, False),
    ("orch", "agent",  "run turn",          "b", 0.5, "t", 0.5, False, False),
    ("agent", "lex",   "lookup / store",    "b", 0.5, "t", 0.5, False, True),
    ("agent", "tts",   "speak_sanskrit(text)","b", 0.15, "r", 0.2, False, False),
    ("tts", "sdk",     "wav",               "l", 0.5, "r", 0.75, False, False),
    ("agent", "sdk",   "capture_image() / nod()", "l", 0.9, "r", 0.55, False, False),
]

VARIANTS = {
    "local": {
        "file": "architecture-local",
        "title": "Mitram - Option A: fully local inference (offline after model download)",
        "nodes": [
            ("host", 470, 60, 1080, 650, "Host - MacBook Pro M1 Max (everything below runs locally)", "#e7f5ff", "container", 15),
            ("llm", 1280, 290, 250, 175, "Ollama (local server)\nQwen3-VL 8B Q4\nvision + Sanskrit generation\n+ native tool calling", "#d3f9d8", "box", 13),
        ],
        "edges": [
            ("agent", "llm", "chat: text + image\n+ tool calls", "r", 0.4, "l", 0.4, False, True),
        ],
        "notes": [],
    },
    "cloud": {
        "file": "architecture-cloud",
        "title": "Mitram - Option B: cloud-extended inference (speech + wake word stay local)",
        "nodes": [
            ("host", 470, 60, 770, 650, "Host - MacBook Pro M1 Max (speech pipeline stays local)", "#e7f5ff", "container", 15),
            ("cloudzone", 1290, 110, 270, 420, "Cloud", "#fff4e6", "container", 15),
            ("llm", 1310, 190, 230, 170, "Claude API /\nAmazon Bedrock\nfrontier model:\nconversation + vision\n+ tool calls", "#ffe8cc", "box", 13),
            ("guard", 1310, 400, 230, 100, "Only session text +\nrequested frames leave\nthe host; raw mic audio\nnever does", "#ffffff", "dashed", 11),
            ("fallback", 890, 620, 310, 60, "Ollama + Qwen3-VL 8B (kept as offline fallback)", "#ffffff", "dashed", 11),
        ],
        "edges": [
            ("agent", "llm", "HTTPS chat: text + image\n+ tool calls", "r", 0.4, "l", 0.4, False, True),
            ("agent", "fallback", "no network ->\noffline fallback", "b", 0.85, "t", 0.85, True, False),
        ],
        "notes": [
            (1290, 560, "Extension = Strands provider swap (one line):\nOllamaModel -> AnthropicModel / BedrockModel\nAgent, tools, prompts, validator: unchanged", 12),
        ],
    },
}

def build(variant):
    v = VARIANTS[variant]
    NODES = BASE_NODES[:6] + v["nodes"][:1] + BASE_NODES[6:] + v["nodes"][1:]
    EDGES = BASE_EDGES + v["edges"]
    nodes = {n[0]: n for n in NODES}

    def anchor(nid, side, frac):
        _, x, y, w, h, *_ = nodes[nid]
        if side == "l": return (x, y + h * frac)
        if side == "r": return (x + w, y + h * frac)
        if side == "t": return (x + w * frac, y)
        return (x + w * frac, y + h)

    # ---- excalidraw ----
    random.seed(7)
    def seed(): return random.randint(1, 2**31 - 1)
    def base(el_id, etype, x, y, w, h, stroke="#1e1e1e", bg="transparent", style="solid"):
        return {"id": el_id, "type": etype, "x": x, "y": y, "width": w, "height": h,
                "angle": 0, "strokeColor": stroke, "backgroundColor": bg, "fillStyle": "solid",
                "strokeWidth": 1, "strokeStyle": style, "roughness": 1, "opacity": 100,
                "groupIds": [], "frameId": None, "seed": seed(), "version": 1,
                "versionNonce": seed(), "isDeleted": False, "boundElements": [],
                "updated": 1751970000000, "link": None, "locked": False}

    elements = []
    def add_text(el_id, x, y, text, fs, container_id=None, valign="middle", color="#1e1e1e"):
        lines = text.split("\n")
        tw = max(len(l) for l in lines) * fs * 0.6
        th = len(lines) * fs * 1.25
        t = base(el_id, "text", x - tw / 2, y, tw, th, stroke=color)
        t.update({"text": text, "fontSize": fs, "fontFamily": 1, "textAlign": "center",
                  "verticalAlign": valign, "containerId": container_id,
                  "originalText": text, "autoResize": True, "lineHeight": 1.25,
                  "roundness": None})
        elements.append(t)
        return t

    for nid, x, y, w, h, label, bg, kind, fs in NODES:
        rect_id = "rect_" + nid
        rect = base(rect_id, "rectangle", x, y, w, h, bg=bg,
                    style="dashed" if kind == "dashed" else "solid")
        rect["roundness"] = {"type": 3}
        if kind == "container":
            elements.append(rect)
            add_text("txt_" + nid, x + w / 2, y + 12, label, fs, valign="top")
        else:
            lines = label.split("\n")
            th = len(lines) * fs * 1.25
            rect["boundElements"] = [{"id": "txt_" + nid, "type": "text"}]
            elements.append(rect)
            add_text("txt_" + nid, x + w / 2, y + h / 2 - th / 2, label, fs, container_id=rect_id)

    for i, (f, t_, label, fs_, ff, ts, tf, dashed, both) in enumerate(EDGES):
        (x1, y1), (x2, y2) = anchor(f, fs_, ff), anchor(t_, ts, tf)
        a = base(f"arr_{i}", "arrow", x1, y1, x2 - x1, y2 - y1,
                 stroke="#868e96" if dashed else "#1e1e1e",
                 style="dashed" if dashed else "solid")
        a.update({"roundness": {"type": 2}, "points": [[0, 0], [x2 - x1, y2 - y1]],
                  "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
                  "startArrowhead": "arrow" if both else None, "endArrowhead": "arrow"})
        elements.append(a)
        add_text(f"arrlbl_{i}", (x1 + x2) / 2, (y1 + y2) / 2 - 14, label, 10, color="#495057")

    for j, (nx, ny, ntext, nfs) in enumerate(v["notes"]):
        add_text(f"note_{j}", nx + 135, ny, ntext, nfs, valign="top", color="#e8590c")

    doc = {"type": "excalidraw", "version": 2, "source": "mitram-design",
           "elements": elements,
           "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None}, "files": {}}
    with open(os.path.join(OUT_DIR, v["file"] + ".excalidraw"), "w") as fh:
        json.dump(doc, fh, indent=1)

    # ---- png ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=140)
    ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis("off")
    PT = 0.72

    for nid, x, y, w, h, label, bg, kind, fs in NODES:
        dashed = kind == "dashed"
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=8",
                     linewidth=1.2, edgecolor="#868e96" if dashed else "#343a40",
                     facecolor=bg, linestyle="--" if dashed else "-",
                     zorder=1 if kind == "container" else 2))
        if kind == "container":
            ax.text(x + w / 2, y + 20, label, ha="center", va="center",
                    fontsize=fs * PT + 1, fontweight="bold", color="#343a40", zorder=4)
        else:
            ax.text(x + w / 2, y + h / 2, label, ha="center", va="center",
                    fontsize=fs * PT, color="#212529", zorder=4)

    for f, t_, label, fs_, ff, ts, tf, dashed, both in EDGES:
        (x1, y1), (x2, y2) = anchor(f, fs_, ff), anchor(t_, ts, tf)
        color = "#868e96" if dashed else "#343a40"
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="<->" if both else "->", color=color,
                                    lw=1.1, linestyle="--" if dashed else "-"), zorder=3)
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 - 7, label, ha="center", va="center",
                fontsize=7.5, color="#495057", zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))

    for nx, ny, ntext, nfs in v["notes"]:
        ax.text(nx + 135, ny + 20, ntext, ha="center", va="center",
                fontsize=nfs * PT, color="#e8590c", zorder=5, fontweight="bold")

    ax.text(20, 30, v["title"], fontsize=13, fontweight="bold", color="#212529")
    png_path = os.path.join(OUT_DIR, v["file"] + ".png")
    fig.savefig(png_path, facecolor="white")
    plt.close(fig)

    # sanity: PNG must not be blank
    from PIL import Image
    import numpy as np
    im = np.asarray(Image.open(png_path).convert("L"))
    dark = (im < 200).mean()
    print(f"{v['file']}: {len(elements)} excalidraw elements, png {im.shape[1]}x{im.shape[0]}, "
          f"{dark:.1%} non-white pixels {'OK' if dark > 0.01 else 'BLANK?!'}")

for variant in ("local", "cloud"):
    build(variant)
