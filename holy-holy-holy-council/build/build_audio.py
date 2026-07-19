#!/usr/bin/env python3
"""
Synthesize a cinematic-worship instrumental bed for
"Holy, Holy, Holy (The Council of the Holy Ones)".

Key: D major.  Tempo: 72 bpm, 4/4.  Follows the arrangement-guide form:
Intro -> V1 -> V2 -> Chorus -> V3 -> Chorus -> Bridge (build) -> Final Chorus -> Outro.

Pure-numpy synthesis: soft pad + sub bass + shimmer arpeggios + gentle
percussion in the fuller sections, glued with a simple multi-tap ambience.
Outputs an int16 stereo WAV.  No external DSP libraries required.
"""
import numpy as np
import wave
import struct
import json
import os

SR = 44100
BPM = 72.0
BEAT = 60.0 / BPM            # 0.8333 s
BAR = 4 * BEAT               # 3.3333 s
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

def midi(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)

# --- Chord voicings (lists of MIDI notes) --------------------------------
CH = {
    "D":     [50, 57, 62, 66],   # D A D F#
    "Bm":    [47, 54, 62, 66],   # B F# D F#
    "G":     [43, 50, 59, 62],   # G D B D
    "A":     [45, 57, 61, 64],   # A A C# E
    "Gsus2": [43, 50, 57, 62],   # G D A D
}
ROOT = {"D": 38, "Bm": 35, "G": 31, "A": 33, "Gsus2": 31}  # sub-bass roots

def env(n, attack, release, sustain=1.0):
    e = np.full(n, sustain, dtype=np.float64)
    a = int(attack * SR)
    r = int(release * SR)
    a = min(a, n); r = min(r, n)
    if a > 0:
        e[:a] *= np.linspace(0, 1, a) ** 1.5
    if r > 0:
        e[-r:] *= np.linspace(1, 0, r) ** 1.5
    return e

def pad_note(freq, dur, level):
    """Warm detuned pad voice."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    # a few slightly-detuned partials for width & warmth
    for det, w in ((0.0, 1.0), (-0.13, 0.7), (0.15, 0.7), (0.0, 0.35)):
        f = freq * (1 + det / 100.0)
        sig += w * np.sin(2 * np.pi * f * t)
    sig += 0.18 * np.sin(2 * np.pi * freq * 2 * t)      # gentle octave sheen
    # slow tremolo/breath
    sig *= 1.0 + 0.05 * np.sin(2 * np.pi * 0.15 * t)
    return sig * level

def sub_note(freq, dur, level):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 2 * t)
    return s * level

def pluck(freq, dur, level):
    """Short decaying shimmer for arpeggios."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 2 * t)
    s += 0.25 * np.sin(2 * np.pi * freq * 3 * t)
    s *= np.exp(-t * 5.5)
    return s * level

def kick(dur, level):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 90 * np.exp(-t * 22) + 42
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8)
    return s * level

def shaker(dur, level):
    n = int(dur * SR)
    noise = np.random.randn(n)
    # crude high-pass via first difference, quick decay
    noise = np.diff(noise, prepend=0.0)
    t = np.arange(n) / SR
    return noise * np.exp(-t * 30) * level

def add(buf, sig, start, pan=0.5):
    """Add mono sig into stereo buf at sample offset start with pan."""
    n = len(sig)
    s = int(start)
    e = s + n
    if e > buf.shape[0]:
        sig = sig[: buf.shape[0] - s]
        e = buf.shape[0]
    lg = np.sqrt(1 - pan)
    rg = np.sqrt(pan)
    buf[s:e, 0] += sig * lg
    buf[s:e, 1] += sig * rg

# --- Song form: (section, [chords per bar], intensity 0..1) ---------------
FORM = [
    ("intro",  ["D", "D", "Gsus2", "Gsus2", "Bm", "Bm", "A", "A"], 0.30),
    ("v1",     ["D", "G", "D", "A", "Bm", "G", "D", "A"],          0.45),
    ("v2",     ["D", "G", "D", "A", "Bm", "G", "D", "A"],          0.58),
    ("chorus1",["D", "Bm", "G", "A", "D", "Bm", "G", "A"],         0.85),
    ("v3",     ["D", "G", "Bm", "A", "G", "D", "A", "A"],          0.50),
    ("chorus2",["D", "Bm", "G", "A", "D", "Bm", "G", "A"],         0.88),
    ("bridge", ["Bm", "G", "D", "A", "Bm", "G", "Gsus2", "Gsus2"], 0.95),
    ("final",  ["D", "Bm", "G", "A", "D", "Bm", "G", "A"],         1.00),
    ("outro",  ["D", "Gsus2", "Bm", "D"],                          0.30),
]

def build():
    total_bars = sum(len(c) for _, c, _ in FORM)
    total_s = total_bars * BAR + 2.0  # small tail
    N = int(total_s * SR)
    buf = np.zeros((N, 2), dtype=np.float64)

    timeline = []
    bar_idx = 0
    for name, chords, inten in FORM:
        sec_start_bar = bar_idx
        for b, ch in enumerate(chords):
            bstart = (bar_idx) * BAR
            s0 = int(bstart * SR)
            legato = BAR + 0.35   # overlap into next bar for smooth legato
            # --- pad (whole bar, soft attack) ---
            pad_lvl = 0.16 * (0.5 + 0.5 * inten)
            for i, m in enumerate(CH[ch]):
                f = midi(m)
                voice = pad_note(f, legato, pad_lvl)
                voice *= env(len(voice), attack=0.5 * BEAT, release=0.5 * BEAT)
                pan = 0.5 + (i - 1.5) * 0.12
                add(buf, voice, s0, pan)
            # --- sub bass ---
            bass = sub_note(midi(ROOT[ch]), legato, 0.22 * (0.6 + 0.4 * inten))
            bass *= env(len(bass), attack=0.15, release=0.4)
            add(buf, bass, s0, 0.5)
            # --- shimmer arpeggio (fuller sections) ---
            if inten >= 0.8:
                notes = [m + 12 for m in CH[ch]]  # up an octave
                order = [0, 2, 1, 3, 2, 3, 1, 2]  # eighth-note pattern
                for k, oi in enumerate(order):
                    ns = s0 + int(k * (BEAT / 2) * SR)
                    p = pluck(midi(notes[oi]), 0.6, 0.06 * inten)
                    add(buf, p, ns, pan=0.5 + (0.25 if k % 2 else -0.25))
            elif inten >= 0.55:
                # sparse half-note shimmer
                notes = [m + 12 for m in CH[ch]]
                for k, oi in enumerate([0, 2]):
                    ns = s0 + int(k * 2 * BEAT * SR)
                    p = pluck(midi(notes[oi]), 0.7, 0.04)
                    add(buf, p, ns, pan=0.5 + (0.2 if k % 2 else -0.2))
            # --- gentle percussion (chorus/bridge/final) ---
            if inten >= 0.82:
                for beat in (0, 2):
                    add(buf, kick(0.35, 0.5 * inten),
                        s0 + int(beat * BEAT * SR), 0.5)
                for ei in range(8):
                    add(buf, shaker(0.12, 0.05 * inten),
                        s0 + int(ei * (BEAT / 2) * SR),
                        pan=0.5 + (0.3 if ei % 2 else -0.3))
            bar_idx += 1
        timeline.append({
            "section": name,
            "start_bar": sec_start_bar,
            "end_bar": bar_idx,
            "start_s": round(sec_start_bar * BAR, 3),
            "end_s": round(bar_idx * BAR, 3),
        })

    # --- simple multi-tap ambience for depth ---
    taps = [(0.050, 0.28), (0.090, 0.22), (0.150, 0.18),
            (0.230, 0.13), (0.370, 0.09)]
    wet = np.zeros_like(buf)
    for dt, g in taps:
        d = int(dt * SR)
        wet[d:] += buf[:-d] * g
    out = buf * 0.78 + wet * 0.30

    # --- master: soft limit + normalize ---
    out = np.tanh(out * 1.1)
    peak = np.max(np.abs(out))
    if peak > 0:
        out = out / peak * 0.95
    # global fade in/out
    fi = int(1.5 * SR); fo = int(3.0 * SR)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]

    data = (out * 32767).astype(np.int16)
    path = os.path.join(OUT_DIR, "track.wav")
    with wave.open(path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    meta = {"bpm": BPM, "bar_s": BAR, "total_bars": total_bars,
            "duration_s": round(total_bars * BAR, 3), "sections": timeline}
    with open(os.path.join(OUT_DIR, "timeline.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("wrote", path, "duration", round(total_bars * BAR, 2), "s")
    print("sections:")
    for s in timeline:
        print(f"  {s['section']:8s} {s['start_s']:7.2f} -> {s['end_s']:7.2f}")

if __name__ == "__main__":
    build()
