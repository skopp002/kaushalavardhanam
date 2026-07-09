"""Generate mitra diagrams: architecture (local + cloud, numbered + icons) and
the wake sequence diagram. Each emits an .excalidraw + .png pair."""
import json
import os
import random

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
W, H = 1580, 880
SCALE = 1.4  # matplotlib dpi 140 / 100

# ---------------------------------------------------------------- shared spec

BASE_NODES = [
    ("user",    15, 390, 145, 110, "User\nspeaks, shows\nobjects, listens", "#fff3bf", "box", 12),
    ("reachy", 190, 140, 210, 590, "Reachy Mini Lite", "#f1f3f5", "container", 15),
    ("mics",   215, 230, 160, 60, "2x microphones", "#ffffff", "box", 13),
    ("camera", 215, 330, 160, 60, "Wide-angle camera", "#ffffff", "box", 13),
    ("speaker",215, 480, 160, 60, "5 W speaker", "#ffffff", "box", 13),
    ("motors", 215, 590, 160, 70, "Head motors\n(6-DOF + body)", "#ffffff", "box", 13),
    ("sdk",    490, 200, 130, 470, "reachy-mini\nSDK\n(media\nbackend:\nOpenCV +\nsounddevice)", "#ffffff", "box", 12),
    ("wake",   660, 130, 190, 65, "Wake detector\n'mitra' (vocative!)", "#ffffff", "box", 12),
    ("vad",    660, 240, 190, 50, "Silero VAD", "#ffffff", "box", 13),
    ("asr",    660, 330, 190, 80, "Whisper ASR\n(en / kn / sa)\n+ language detect", "#ffffff", "box", 12),
    ("orch",   890, 130, 310, 105, "Orchestrator (state machine)\nASLEEP > LISTENING >\nTHINKING > SPEAKING", "#d0ebff", "box", 13),
    ("agent",  890, 290, 310, 175, "Strands Agent (core SDK)\nmodel provider (swappable)\ntools: capture_image |\nspeak_sanskrit | nod |\nend_session", "#d0ebff", "box", 13),
    ("lex",    890, 520, 310, 75, "Sanskrit lexicon cache\n(human-verified names win)", "#ffffff", "box", 12),
    ("tts",    660, 500, 190, 95, "Indic Parler-TTS\nSanskrit voice\n(MPS)", "#ffffff", "box", 12),
]

# Numbers mark the order of one spoken turn (wake 1-4, then 5-14).
# Unnumbered edges are conditional (vision) or implicit (motor commands).
BASE_EDGES = [
    ("user", "mics",   "1 speech",            "r", 0.2, "l", 0.5, False, False),
    ("user", "camera", "shows object\n(vision turns)", "r", 0.5, "l", 0.5, False, False),
    ("speaker", "user","14 Sanskrit audio",   "l", 0.5, "r", 0.8, False, False),
    ("mics", "sdk",    "2 USB audio",         "r", 0.5, "l", 0.15, False, False),
    ("camera", "sdk",  "USB video",           "r", 0.5, "l", 0.35, False, False),
    ("sdk", "speaker", "13 audio out",        "l", 0.62, "r", 0.5, False, False),
    ("sdk", "motors",  "motor cmds (nod)",    "l", 0.9, "r", 0.5, False, False),
    ("sdk", "wake",    "3 mic stream",        "r", 0.08, "l", 0.5, False, False),
    ("wake", "vad",    "5 session audio",     "b", 0.5, "t", 0.5, False, False),
    ("vad", "asr",     "6 utterance",         "b", 0.5, "t", 0.5, False, False),
    ("wake", "orch",   "4 wake event",        "r", 0.5, "l", 0.3, True,  False),
    ("asr", "orch",    "7 transcript + lang", "r", 0.15, "l", 0.9, False, False),
    ("orch", "agent",  "8 run turn",          "b", 0.5, "t", 0.5, False, False),
    ("agent", "lex",   "10 lexicon lookup / store", "b", 0.5, "t", 0.5, False, True),
    ("agent", "tts",   "11 speak_sanskrit(text)", "b", 0.15, "r", 0.2, False, False),
    ("tts", "sdk",     "12 wav",              "l", 0.5, "r", 0.75, False, False),
    ("agent", "sdk",   "capture_image() / nod()", "l", 0.9, "r", 0.55, False, False),
]

BASE_ICONS = {  # node id -> emoji, drawn at the node's top-left corner
    "user": "🧑", "reachy": "🤗", "mics": "🎤", "camera": "📷",
    "speaker": "🔊", "motors": "⚙️", "sdk": "🔌", "wake": "👂",
    "vad": "✂️", "asr": "📝", "orch": "🚦", "agent": "🧠",
    "lex": "📖", "tts": "🗣️",
}

VARIANTS = {
    "local": {
        "file": "architecture-local",
        "title": "Mitra - Option A: fully local inference (numbers = order of one spoken turn)",
        "nodes": [
            ("host", 470, 60, 1080, 650, "Host - MacBook Pro M1 Max (everything below runs locally)", "#e7f5ff", "container", 15),
            ("llm", 1280, 290, 250, 175, "Ollama (local server)\nQwen3-VL 8B instruct\nvision + Sanskrit generation\n+ native tool calling", "#d3f9d8", "box", 13),
        ],
        "edges": [
            ("agent", "llm", "9 chat: text + image\n+ tool calls", "r", 0.4, "l", 0.4, False, True),
        ],
        "icons": {"host": "💻", "llm": "🦙"},
        "badges": [],
        "notes": [],
    },
    "cloud": {
        "file": "architecture-cloud",
        "title": "Mitra - Option B: cloud-extended inference (speech + wake word stay local)",
        "nodes": [
            ("host", 470, 60, 770, 650, "Host - MacBook Pro M1 Max (speech pipeline stays local)", "#e7f5ff", "container", 15),
            ("cloudzone", 1290, 110, 270, 420, "Cloud", "#fff4e6", "container", 15),
            ("llm", 1310, 190, 230, 170, "Claude API /\nAmazon Bedrock\nfrontier model:\nconversation + vision\n+ tool calls", "#ffe8cc", "box", 13),
            ("guard", 1310, 400, 230, 100, "Only session text +\nrequested frames leave\nthe host; raw mic audio\nnever does", "#ffffff", "dashed", 11),
            ("fallback", 890, 620, 310, 60, "Ollama + Qwen3-VL (kept as offline fallback)", "#ffffff", "dashed", 11),
        ],
        "edges": [
            ("agent", "llm", "9 HTTPS chat: text + image\n+ tool calls", "r", 0.4, "l", 0.4, False, True),
            ("agent", "fallback", "no network ->\noffline fallback", "b", 0.85, "t", 0.85, True, False),
        ],
        "icons": {"host": "💻", "cloudzone": "☁️", "fallback": "🦙"},
        "badges": [(1478, 196, 56, 26, "aws", "#ff9900", "#ffffff")],
        "notes": [
            (1290, 560, "Extension = Strands provider swap (one line):\nOllamaModel -> AnthropicModel / BedrockModel\nAgent, tools, prompts, validator: unchanged", 12),
        ],
    },
}

# ------------------------------------------------------- sequence diagram spec

SEQ_PARTS = [  # (id, label, emoji, lifeline x)
    ("user",  "User",            "🧑", 105),
    ("robot", "Reachy Mini\n(sim or real)", "🤗", 305),
    ("wake",  "Wake detector",   "👂", 505),
    ("asr",   "VAD + Whisper",   "📝", 695),
    ("orch",  "Orchestrator",    "🚦", 895),
    ("agent", "Strands Agent",   "🧠", 1095),
    ("llm",   "Ollama\nQwen3-VL","🦙", 1290),
    ("tts",   "Parler-TTS",      "🗣️", 1475),
]

SEQ_MSGS = [  # (from, to, label, dashed=response)
    ("user",  "robot", '1  "hey mitra"', False),
    ("robot", "wake",  "2  mic audio (always listening)", False),
    ("wake",  "orch",  '3  wake event ("mitra" heard)', False),
    ("orch",  "robot", "4  nod()", False),
    ("orch",  "tts",   "5  synthesize greeting (namaste)", False),
    ("tts",   "robot", "6  greeting wav -> speaker", False),
    ("robot", "user",  '7  "namaste"', True),
    ("user",  "robot", "8  question (English / Kannada / Sanskrit)", False),
    ("robot", "asr",   "9  utterance (VAD end-of-speech)", False),
    ("asr",   "orch",  "10  transcript + language tag", False),
    ("orch",  "agent", "11  turn message  [lang=en] ...", False),
    ("agent", "llm",   "12  chat (+ capture_image if object shown)", False),
    ("llm",   "agent", "13  Sanskrit draft reply", True),
    ("agent", "orch",  "14  reply -> validator + lexicon override", False),
    ("orch",  "tts",   "15  speak validated Sanskrit", False),
    ("tts",   "robot", "16  reply wav -> speaker", False),
    ("robot", "user",  "17  Sanskrit reply", True),
]

SEQ_PHASES = [  # (msg index it starts at, label, band color)
    (0, "WAKE + GREET  (from ASLEEP)", "#fff3bf"),
    (7, "CONVERSATION TURN  (repeats from 8; 30 s of silence -> back to ASLEEP)", "#d0ebff"),
]

SEQ_Y0, SEQ_DY = 225, 38
SEQ_H = 960

# ------------------------------------------------------------ excalidraw bits

random.seed(7)


def _seed():
    return random.randint(1, 2**31 - 1)


def _el(el_id, etype, x, y, w, h, stroke="#1e1e1e", bg="transparent", style="solid"):
    return {"id": el_id, "type": etype, "x": x, "y": y, "width": w, "height": h,
            "angle": 0, "strokeColor": stroke, "backgroundColor": bg, "fillStyle": "solid",
            "strokeWidth": 1, "strokeStyle": style, "roughness": 1, "opacity": 100,
            "groupIds": [], "frameId": None, "seed": _seed(), "version": 1,
            "versionNonce": _seed(), "isDeleted": False, "boundElements": [],
            "updated": 1751970000000, "link": None, "locked": False}


def _text(elements, el_id, x, y, text, fs, container_id=None, valign="middle",
          color="#1e1e1e"):
    lines = text.split("\n")
    tw = max(len(line) for line in lines) * fs * 0.6
    th = len(lines) * fs * 1.25
    t = _el(el_id, "text", x - tw / 2, y, tw, th, stroke=color)
    t.update({"text": text, "fontSize": fs, "fontFamily": 1, "textAlign": "center",
              "verticalAlign": valign, "containerId": container_id,
              "originalText": text, "autoResize": True, "lineHeight": 1.25,
              "roundness": None})
    elements.append(t)
    return t


def _arrow(elements, el_id, x1, y1, x2, y2, dashed=False, both=False,
           color=None):
    a = _el(el_id, "arrow", x1, y1, x2 - x1, y2 - y1,
            stroke=color or ("#868e96" if dashed else "#1e1e1e"),
            style="dashed" if dashed else "solid")
    a.update({"roundness": {"type": 2}, "points": [[0, 0], [x2 - x1, y2 - y1]],
              "lastCommittedPoint": None, "startBinding": None, "endBinding": None,
              "startArrowhead": "arrow" if both else None, "endArrowhead": "arrow"})
    elements.append(a)


def _save_excalidraw(path, elements):
    doc = {"type": "excalidraw", "version": 2, "source": "mitra-design",
           "elements": elements,
           "appState": {"viewBackgroundColor": "#ffffff", "gridSize": None},
           "files": {}}
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=1)


# ------------------------------------------------------------------ png emoji

_EMOJI_CACHE = {}


def _emoji_img(ch, size):
    """Render one emoji via Apple Color Emoji (bitmap strike 137 -> resized)."""
    from PIL import Image, ImageDraw, ImageFont

    key = (ch, size)
    if key not in _EMOJI_CACHE:
        font = None
        for strike in (160, 137, 96, 64, 48, 40, 32, 26, 20):  # bitmap strikes vary by macOS
            try:
                font = ImageFont.truetype(
                    "/System/Library/Fonts/Apple Color Emoji.ttc", strike)
                break
            except OSError:
                continue
        if font is None:
            raise OSError("no usable Apple Color Emoji strike")
        img = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((16, 16), ch, font=font, embedded_color=True)
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        img.thumbnail((size, size))
        _EMOJI_CACHE[key] = img
    return _EMOJI_CACHE[key]


def paste_icons(png_path, items):
    """items: (canvas_x, canvas_y, emoji, canvas_size). Best-effort."""
    try:
        from PIL import Image

        im = Image.open(png_path).convert("RGBA")
        for x, y, ch, s in items:
            glyph = _emoji_img(ch, int(s * SCALE))
            im.alpha_composite(glyph, (int(x * SCALE), int(y * SCALE)))
        im.convert("RGB").save(png_path)
    except Exception as e:  # icons are decoration — never fail the build
        print(f"  (icon pass skipped: {e})")


def _check_png(path, n_elements, name):
    from PIL import Image
    import numpy as np

    im = np.asarray(Image.open(path).convert("L"))
    dark = (im < 200).mean()
    print(f"{name}: {n_elements} excalidraw elements, png {im.shape[1]}x{im.shape[0]}, "
          f"{dark:.1%} non-white pixels {'OK' if dark > 0.01 else 'BLANK?!'}")


# ------------------------------------------------------- architecture builder

def build_architecture(variant):
    v = VARIANTS[variant]
    NODES = BASE_NODES[:6] + v["nodes"][:1] + BASE_NODES[6:] + v["nodes"][1:]
    EDGES = BASE_EDGES + v["edges"]
    ICONS = {**BASE_ICONS, **v["icons"]}
    nodes = {n[0]: n for n in NODES}

    def anchor(nid, side, frac):
        _, x, y, w, h, *_ = nodes[nid]
        if side == "l":
            return (x, y + h * frac)
        if side == "r":
            return (x + w, y + h * frac)
        if side == "t":
            return (x + w * frac, y)
        return (x + w * frac, y + h)

    elements = []
    for nid, x, y, w, h, label, bg, kind, fs in NODES:
        rect_id = "rect_" + nid
        rect = _el(rect_id, "rectangle", x, y, w, h, bg=bg,
                   style="dashed" if kind == "dashed" else "solid")
        rect["roundness"] = {"type": 3}
        if kind == "container":
            elements.append(rect)
            _text(elements, "txt_" + nid, x + w / 2, y + 12, label, fs, valign="top")
        else:
            th = len(label.split("\n")) * fs * 1.25
            rect["boundElements"] = [{"id": "txt_" + nid, "type": "text"}]
            elements.append(rect)
            _text(elements, "txt_" + nid, x + w / 2, y + h / 2 - th / 2, label, fs,
                  container_id=rect_id)
        if nid in ICONS:  # excalidraw icon: emoji text at the corner
            _text(elements, "icon_" + nid, x + 18, y + 3, ICONS[nid], 18)

    for i, (f, t_, label, fs_, ff, ts, tf, dashed, both) in enumerate(EDGES):
        (x1, y1), (x2, y2) = anchor(f, fs_, ff), anchor(t_, ts, tf)
        _arrow(elements, f"arr_{i}", x1, y1, x2, y2, dashed, both)
        _text(elements, f"arrlbl_{i}", (x1 + x2) / 2, (y1 + y2) / 2 - 14, label, 10,
              color="#495057")

    for bx, by, bw, bh, btext, bbg, bfg in v["badges"]:
        badge = _el("badge_" + btext, "rectangle", bx, by, bw, bh, bg=bbg, stroke=bbg)
        badge["roundness"] = {"type": 3}
        elements.append(badge)
        _text(elements, "badgetxt_" + btext, bx + bw / 2, by + 4, btext, 14, color=bfg)

    for j, (nx, ny, ntext, nfs) in enumerate(v["notes"]):
        _text(elements, f"note_{j}", nx + 135, ny, ntext, nfs, valign="top",
              color="#e8590c")

    _save_excalidraw(os.path.join(OUT_DIR, v["file"] + ".excalidraw"), elements)

    # ---- png ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig = plt.figure(figsize=(W / 100, H / 100), dpi=140)
    ax = fig.add_axes([0, 0, 1, 1])  # fill figure: data coords == pixels/SCALE
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
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

    for bx, by, bw, bh, btext, bbg, bfg in v["badges"]:
        ax.add_patch(FancyBboxPatch((bx, by), bw, bh,
                     boxstyle="round,pad=0,rounding_size=6", linewidth=0,
                     facecolor=bbg, zorder=6))
        ax.text(bx + bw / 2, by + bh / 2, btext, ha="center", va="center",
                fontsize=10, fontweight="bold", color=bfg, zorder=7)

    for nx, ny, ntext, nfs in v["notes"]:
        ax.text(nx + 135, ny + 20, ntext, ha="center", va="center",
                fontsize=nfs * PT, color="#e8590c", zorder=5, fontweight="bold")

    ax.text(20, 30, v["title"], fontsize=13, fontweight="bold", color="#212529")
    png_path = os.path.join(OUT_DIR, v["file"] + ".png")
    fig.savefig(png_path, facecolor="white")
    plt.close(fig)

    paste_icons(png_path, [(nodes[nid][1] + 5, nodes[nid][2] + 4, ch, 20)
                           for nid, ch in ICONS.items()])
    _check_png(png_path, len(elements), v["file"])


# ----------------------------------------------------------- sequence builder

def build_sequence():
    name = "flow-wake"
    title = 'Mitra - sequence: what happens when you say "hey mitra"'
    px = {p[0]: p[3] for p in SEQ_PARTS}
    lifeline_top, lifeline_bottom = 150, SEQ_H - 60

    elements = []
    for pid, label, _emoji, x in SEQ_PARTS:
        rect_id = "head_" + pid
        rect = _el(rect_id, "rectangle", x - 78, 88, 156, 56, bg="#e7f5ff")
        rect["roundness"] = {"type": 3}
        rect["boundElements"] = [{"id": "headtxt_" + pid, "type": "text"}]
        elements.append(rect)
        th = len(label.split("\n")) * 12 * 1.25
        _text(elements, "headtxt_" + pid, x, 116 - th / 2, label, 12,
              container_id=rect_id)
        _text(elements, "headicon_" + pid, x, 56, _emoji, 20)
        line = _el("life_" + pid, "line", x, lifeline_top, 0,
                   lifeline_bottom - lifeline_top, stroke="#adb5bd", style="dashed")
        line.update({"points": [[0, 0], [0, lifeline_bottom - lifeline_top]],
                     "lastCommittedPoint": None, "startBinding": None,
                     "endBinding": None, "startArrowhead": None, "endArrowhead": None,
                     "roundness": None})
        elements.append(line)

    for start_idx, plabel, pcolor in SEQ_PHASES:
        y = SEQ_Y0 + start_idx * SEQ_DY - 30
        band = _el(f"phase_{start_idx}", "rectangle", 40, y, W - 80, 24, bg=pcolor,
                   stroke=pcolor)
        elements.append(band)
        _text(elements, f"phasetxt_{start_idx}", 40 + (W - 80) / 2, y + 3, plabel, 12,
              color="#495057")

    for i, (f, t_, label, dashed) in enumerate(SEQ_MSGS):
        y = SEQ_Y0 + i * SEQ_DY
        x1, x2 = px[f], px[t_]
        _arrow(elements, f"msg_{i}", x1, y, x2, y, dashed=dashed)
        _text(elements, f"msglbl_{i}", (x1 + x2) / 2, y - 17, label, 10.5,
              color="#343a40")

    _save_excalidraw(os.path.join(OUT_DIR, name + ".excalidraw"), elements)

    # ---- png ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig = plt.figure(figsize=(W / 100, SEQ_H / 100), dpi=140)
    ax = fig.add_axes([0, 0, 1, 1])  # fill figure: data coords == pixels/SCALE
    ax.set_xlim(0, W)
    ax.set_ylim(SEQ_H, 0)
    ax.axis("off")

    for pid, label, _emoji, x in SEQ_PARTS:
        ax.plot([x, x], [lifeline_top, lifeline_bottom], linestyle="--",
                color="#adb5bd", lw=1, zorder=1)
        ax.add_patch(FancyBboxPatch((x - 78, 88), 156, 56,
                     boxstyle="round,pad=0,rounding_size=8", linewidth=1.2,
                     edgecolor="#343a40", facecolor="#e7f5ff", zorder=2))
        ax.text(x, 116, label, ha="center", va="center", fontsize=9.5,
                fontweight="bold", color="#212529", zorder=3)

    for start_idx, plabel, pcolor in SEQ_PHASES:
        y = SEQ_Y0 + start_idx * SEQ_DY - 30
        ax.add_patch(FancyBboxPatch((40, y), W - 80, 24,
                     boxstyle="round,pad=0,rounding_size=6", linewidth=0,
                     facecolor=pcolor, zorder=2))
        ax.text(W / 2, y + 12, plabel, ha="center", va="center", fontsize=9,
                fontweight="bold", color="#495057", zorder=3)

    for i, (f, t_, label, dashed) in enumerate(SEQ_MSGS):
        y = SEQ_Y0 + i * SEQ_DY
        x1, x2 = px[f], px[t_]
        color = "#868e96" if dashed else "#343a40"
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.2,
                                    linestyle="--" if dashed else "-"), zorder=3)
        ax.text((x1 + x2) / 2, y - 9, label, ha="center", va="center", fontsize=8,
                color="#343a40", zorder=4,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.9))

    ax.text(20, 30, title, fontsize=13, fontweight="bold", color="#212529")
    png_path = os.path.join(OUT_DIR, name + ".png")
    fig.savefig(png_path, facecolor="white")
    plt.close(fig)

    paste_icons(png_path, [(x - 12, 52, emoji, 26) for _pid, _l, emoji, x in SEQ_PARTS])
    _check_png(png_path, len(elements), name)


for variant in ("local", "cloud"):
    build_architecture(variant)
build_sequence()
