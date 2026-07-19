#!/usr/bin/env python3
"""
Render the lyric video for "Holy, Holy, Holy (The Council of the Holy Ones)".

- Generates a throne-room / starfield background (nebula + golden throne glow).
- Times animated lyric cards to timeline.json, scaled to the actual audio length.
- Composites HD frames in numpy and pipes them to ffmpeg, muxing the audio.

Audio: uses vocals.wav/vocals.mp3 if present (from build_vocals.py),
otherwise falls back to the synthesized track.wav.
"""
import os
import json
import wave
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import imageio_ffmpeg

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(OUT_DIR)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

W, H, FPS = 1920, 1080, 24
BW, BH = 2200, 1240          # oversized bg for slow pan
FONT_DIR = "/mnt/skills/examples/canvas-design/canvas-fonts"
F_TITLE = os.path.join(FONT_DIR, "IBMPlexSerif-Bold.ttf")
F_BODY = os.path.join(FONT_DIR, "IBMPlexSerif-Regular.ttf")
F_ITALIC = os.path.join(FONT_DIR, "IBMPlexSerif-Italic.ttf")

GOLD = (232, 200, 128)
WARM_WHITE = (245, 240, 228)
STAR_BLUE = (200, 214, 245)


# ---------------------------------------------------------------- background
def make_background():
    yy, xx = np.mgrid[0:BH, 0:BW].astype(np.float32)
    # vertical gradient: deep indigo -> near black
    g = yy / BH
    base = np.zeros((BH, BW, 3), np.float32)
    top = np.array([18, 20, 46]); bot = np.array([4, 5, 14])
    for c in range(3):
        base[..., c] = bot[c] + (top[c] - bot[c]) * (1 - g)

    def blob(cx, cy, r, color, strength):
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        m = np.exp(-d2 / (2 * r * r)) * strength
        for c in range(3):
            base[..., c] += color[c] * m

    # nebula clouds
    blob(BW * 0.30, BH * 0.35, 520, (40, 34, 92), 0.9)
    blob(BW * 0.72, BH * 0.55, 620, (24, 44, 90), 0.8)
    blob(BW * 0.55, BH * 0.20, 460, (60, 40, 96), 0.6)
    blob(BW * 0.85, BH * 0.28, 380, (18, 52, 78), 0.5)
    # golden throne glow, upper-center
    blob(BW * 0.50, BH * 0.14, 700, (150, 120, 60), 0.85)
    blob(BW * 0.50, BH * 0.10, 300, (210, 175, 105), 0.7)

    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8))

    # stars on a separate layer, then a blurred copy for glow
    stars = Image.new("RGB", (BW, BH), (0, 0, 0))
    sd = ImageDraw.Draw(stars)
    rng = np.random.default_rng(7)
    for _ in range(1500):
        x = rng.integers(0, BW); y = rng.integers(0, BH)
        b = rng.random()
        v = int(60 + 195 * b ** 2)
        col = (min(255, v + 10), min(255, v + 4), min(255, v + 30))
        sd.point((x, y), fill=col)
    # a few bright feature stars
    for _ in range(60):
        x = int(rng.integers(0, BW)); y = int(rng.integers(0, BH))
        r = rng.integers(1, 3)
        sd.ellipse([x - r, y - r, x + r, y + r], fill=STAR_BLUE)
    glow = stars.filter(ImageFilter.GaussianBlur(3))
    img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.0)
    img = _screen(img, stars)
    img = _screen(img, glow, 0.5)

    # vignette
    d2 = ((xx - BW / 2) / (BW / 2)) ** 2 + ((yy - BH / 2) / (BH / 2)) ** 2
    vig = np.clip(1.0 - 0.55 * d2, 0.35, 1.0).astype(np.float32)
    arr = np.asarray(img).astype(np.float32) * vig[..., None]
    return np.clip(arr, 0, 255).astype(np.uint8)


def _screen(a, b, amt=1.0):
    aa = np.asarray(a).astype(np.float32) / 255
    bb = np.asarray(b).astype(np.float32) / 255 * amt
    out = 1 - (1 - aa) * (1 - bb)
    return Image.fromarray((out * 255).astype(np.uint8))


# ------------------------------------------------------------------- cards
def wrap(draw, text, font, maxw):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_card(lines, ref=None, style="verse"):
    """Return (rgb uint8 HxWx3, alpha uint8 HxW) for a lyric card."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if style == "title":
        f = ImageFont.truetype(F_TITLE, 118)
        fsub = ImageFont.truetype(F_ITALIC, 52)
        color = GOLD
    elif style == "chorus":
        f = ImageFont.truetype(F_TITLE, 68)
        color = GOLD
    elif style == "bridge":
        f = ImageFont.truetype(F_TITLE, 74)
        color = WARM_WHITE
    else:  # verse / tag
        f = ImageFont.truetype(F_BODY, 62)
        color = WARM_WHITE

    maxw = int(W * 0.80)
    wrapped = []
    for ln in lines:
        wrapped.extend(wrap(d, ln, f, maxw))
    lh = int(f.size * 1.42)
    block_h = lh * len(wrapped)
    fref = ImageFont.truetype(F_ITALIC, 34)
    if ref:
        block_h += 70
    y0 = (H - block_h) // 2 - 20

    def draw_block(drw, dy=0, fill=color):
        y = y0 + dy
        for ln in wrapped:
            tw = drw.textlength(ln, font=f)
            drw.text(((W - tw) / 2 + 0, y), ln, font=f, fill=fill)
            y += lh
        if style == "title":
            sub = "The Council of the Holy Ones"
            tw = drw.textlength(sub, font=fsub)
            drw.text(((W - tw) / 2, y + 8), sub, font=fsub, fill=WARM_WHITE)
        if ref:
            tw = drw.textlength(ref, font=fref)
            drw.text(((W - tw) / 2, y + 24), ref, font=fref, fill=(180, 170, 150))

    # glow pass
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    draw_block(gd, fill=(*color, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    layer = Image.alpha_composite(layer, glow)
    # crisp pass with subtle drop shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    draw_block(sd, dy=3, fill=(0, 0, 0, 220))
    shadow = shadow.filter(ImageFilter.GaussianBlur(4))
    layer = Image.alpha_composite(layer, shadow)
    d2 = ImageDraw.Draw(layer)
    draw_block(d2)

    arr = np.asarray(layer).astype(np.uint8)
    return arr[..., :3].copy(), arr[..., 3].copy()


# ------------------------------------------------------- lyric timeline
# Cards per section. Each card: (lines, ref, style)
SECTION_CARDS = {
    "intro": [(["HOLY, HOLY, HOLY"], None, "title")],
    "v1": [
        (["Holy, holy, holy — Lord God Almighty,"], None, "verse"),
        (["Early in the morning our song shall rise to Thee."], None, "verse"),
        (["Holy, holy, holy — none in the heavens like Thee,"], None, "verse"),
        (["Feared in the assembly of the holy ones on high."],
         "Psalm 89:6–7", "verse"),
    ],
    "v2": [
        (["Holy, holy, holy — the sons of God adore Thee,"], None, "verse"),
        (["Casting down their crowns before the fiery throne."], None, "verse"),
        (["Watchers and the seraphs bow within Thy council,"], None, "verse"),
        (["Who among the mighty ones can stand before Thee, Lord?"],
         "1 Kings 22:19 · Isaiah 6", "verse"),
    ],
    "chorus1": [
        (["You divided up the nations,", "Set their bounds by heaven's sons —"],
         None, "chorus"),
        (["But Jacob is Your portion,", "Israel the one You won."],
         "Deut 32:8–9", "chorus"),
        (["Rise, O God, and judge the rulers,", "Take the nations for Your own —"],
         None, "chorus"),
        (["Every knee in heaven's council", "Bends before Your throne alone."],
         "Psalm 82:1, 8", "chorus"),
    ],
    "v3": [
        (["Holy, holy, holy — though rebel powers defied Thee,"], None, "verse"),
        (["Though the gods of nations led the peoples far astray,"], None, "verse"),
        (["Thou alone art faithful — the Judge of all the council,"], None, "verse"),
        (["“You shall die like mortals, and fall like any prince.”"],
         "Psalm 82:2–7", "verse"),
    ],
    "chorus2": [
        (["You divided up the nations,", "Set their bounds by heaven's sons —"],
         None, "chorus"),
        (["But Jacob is Your portion,", "Israel the one You won."],
         "Deut 32:8–9", "chorus"),
        (["Rise, O God, and judge the rulers,", "Take the nations for Your own —"],
         None, "chorus"),
        (["Every knee in heaven's council", "Bends before Your throne alone."],
         "Psalm 82:1, 8", "chorus"),
    ],
    "bridge": [
        (["God stands in the assembly —", "He holds court among the gods."],
         "Psalm 82:1", "bridge"),
        (["God stands in the assembly —", "He holds court among the gods."],
         None, "bridge"),
        (["Arise, O God!", "Judge the earth!"], None, "bridge"),
        (["For all the nations belong to You."], "Psalm 82:8", "bridge"),
    ],
    "final": [
        (["Holy, holy, holy — Lord God Almighty,"], None, "verse"),
        (["All Thy works shall praise Thy name",
          "in earth and sky and sea."], None, "verse"),
        (["Holy, holy, holy — the Name above the elim,"],
         "Psalm 97:9", "verse"),
        (["God enthroned in glory, and reigning over all."], None, "verse"),
    ],
    "outro": [
        (["Every knee in heaven's council", "Bends before Your throne alone."],
         None, "chorus"),
    ],
}


def build_timeline(audio_dur):
    with open(os.path.join(OUT_DIR, "timeline.json")) as f:
        meta = json.load(f)
    base_dur = meta["duration_s"]
    scale = audio_dur / base_dur
    cards = []
    for sec in meta["sections"]:
        name = sec["section"]
        s = sec["start_s"] * scale
        e = sec["end_s"] * scale
        clist = SECTION_CARDS.get(name, [])
        if not clist:
            continue
        span = (e - s) / len(clist)
        for i, (lines, ref, style) in enumerate(clist):
            cs = s + i * span
            ce = cs + span
            cards.append((cs, ce, lines, ref, style))
    return cards


def audio_duration(path):
    if path.endswith(".wav"):
        with wave.open(path) as w:
            return w.getnframes() / w.getframerate()
    # decode header via ffmpeg -> null, parse duration
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            hms = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = hms.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError("could not read audio duration")


def pick_audio():
    for name in ("vocals.wav", "vocals.mp3", "track.wav"):
        p = os.path.join(OUT_DIR, name)
        if os.path.exists(p):
            return p
    raise SystemExit("no audio found; run build_audio.py or build_vocals.py")


def main():
    audio = pick_audio()
    dur = audio_duration(audio)
    print("audio:", os.path.basename(audio), f"{dur:.2f}s")

    bg = make_background()
    cards = build_timeline(dur)
    print(f"rendering {len(cards)} lyric cards...")
    rendered = [(cs, ce, *render_card(l, r, st))
                for (cs, ce, l, r, st) in cards]

    n_frames = int(dur * FPS)
    # slow pan path within oversized bg
    max_dx = BW - W
    max_dy = BH - H
    out_path = os.path.join(PROJ, "Holy_Holy_Holy_Council.mp4")

    cmd = [FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", audio,
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
           "-preset", "medium", "-c:a", "aac", "-b:a", "256k",
           "-movflags", "+faststart", "-shortest", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ci = 0
    fade = 0.7
    for fi in range(n_frames):
        t = fi / FPS
        # pan (slow Lissajous)
        px = 0.5 + 0.5 * np.sin(2 * np.pi * t / 90.0)
        py = 0.5 + 0.5 * np.sin(2 * np.pi * t / 130.0 + 1.0)
        ox = int(px * max_dx)
        oy = int(py * max_dy)
        frame = bg[oy:oy + H, ox:ox + W, :].astype(np.float32)
        # subtle breathing brightness
        frame *= 0.93 + 0.07 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 18.0))

        # advance active card pointer
        while ci < len(rendered) and rendered[ci][1] <= t:
            ci += 1
        if ci < len(rendered):
            cs, ce, rgb, alpha = rendered[ci]
            if cs <= t < ce:
                a = 1.0
                if t - cs < fade:
                    a = (t - cs) / fade
                elif ce - t < fade:
                    a = (ce - t) / fade
                a = max(0.0, min(1.0, a))
                if a > 0:
                    al = (alpha.astype(np.float32) / 255.0 * a)[..., None]
                    frame = frame * (1 - al) + rgb.astype(np.float32) * al
        proc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        if fi % (FPS * 15) == 0:
            print(f"  {t:6.1f}s / {dur:.0f}s")

    proc.stdin.close()
    proc.wait()
    print("wrote", out_path)


if __name__ == "__main__":
    main()
