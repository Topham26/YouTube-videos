#!/usr/bin/env python3
"""
Generate AI vocals for "Holy, Holy, Holy (The Council of the Holy Ones)"
via ACE-Step on Replicate, and save the result as vocals.wav / vocals.mp3.

Requires:  REPLICATE_API_TOKEN in the environment.
Usage:     python3 build_vocals.py            # generate
           python3 build_vocals.py --duration 200

The lyric text is fixed to the adapted lyrics in lyrics-source.md.
"""
import os
import sys
import time
import json
import urllib.request
import urllib.error

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL = "lucataco/ace-step"          # ACE-Step text-to-song (vocals from lyrics)
API = "https://api.replicate.com/v1"

# Style/genre tags for ACE-Step (comma-separated descriptors, not lyrics).
TAGS = ("cinematic worship anthem, modern hymn, male lead vocal, "
        "stacked choir harmonies, gospel, grand piano, ambient synth pads, "
        "anthemic drums, gang vocals, reverent, awe-filled, epic, "
        "d major, 72 bpm, 4/4")

# Lyrics with ACE-Step structure tags. Instrumental intro/outro are marked.
LYRICS = """[inst]

[verse]
Holy, holy, holy, Lord God Almighty,
Early in the morning our song shall rise to Thee.
Holy, holy, holy, none in the heavens like Thee,
Feared in the assembly of the holy ones on high.

[verse]
Holy, holy, holy, the sons of God adore Thee,
Casting down their crowns before the fiery throne.
Watchers and the seraphs bow within Thy council,
Who among the mighty ones can stand before Thee, Lord?

[chorus]
You divided up the nations,
Set their bounds by heaven's sons,
But Jacob is Your portion,
Israel the one You won.
Rise, O God, and judge the rulers,
Take the nations for Your own,
Every knee in heaven's council
Bends before Your throne alone.

[verse]
Holy, holy, holy, though rebel powers defied Thee,
Though the gods of nations led the peoples far astray,
Thou alone art faithful, the Judge of all the council,
You shall die like mortals, and fall like any prince.

[chorus]
You divided up the nations,
Set their bounds by heaven's sons,
But Jacob is Your portion,
Israel the one You won.
Rise, O God, and judge the rulers,
Take the nations for Your own,
Every knee in heaven's council
Bends before Your throne alone.

[bridge]
God stands in the assembly, He holds court among the gods.
God stands in the assembly, He holds court among the gods.
Arise, O God! Judge the earth!
For all the nations belong to You.

[verse]
Holy, holy, holy, Lord God Almighty,
All Thy works shall praise Thy name in earth and sky and sea.
Holy, holy, holy, the Name above the elim,
God enthroned in glory, and reigning over all.

[chorus]
Rise, O God, and judge the rulers,
Take the nations for Your own,
Every knee in heaven's council
Bends before Your throne alone.

[outro]
"""


def req(method, url, token, data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Authorization", f"Bearer {token}")
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:500])
        raise


def latest_version(token):
    info = req("GET", f"{API}/models/{MODEL}", token)
    return info["latest_version"]["id"]


def main():
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        sys.exit("ERROR: set REPLICATE_API_TOKEN in the environment first.")

    duration = 230
    if "--duration" in sys.argv:
        duration = int(sys.argv[sys.argv.index("--duration") + 1])

    version = latest_version(token)
    print("ace-step version:", version)

    payload = {
        "version": version,
        "input": {
            "tags": TAGS,
            "lyrics": LYRICS,
            "duration": duration,
            "guidance_scale": 15,
            "number_of_steps": 60,
            "seed": -1,
        },
    }
    pred = req("POST", f"{API}/predictions", token, payload)
    pid = pred["id"]
    print("prediction:", pid)

    # poll
    while pred["status"] not in ("succeeded", "failed", "canceled"):
        time.sleep(5)
        pred = req("GET", f"{API}/predictions/{pid}", token)
        print("  status:", pred["status"])

    if pred["status"] != "succeeded":
        sys.exit(f"generation {pred['status']}: {pred.get('error')}")

    out = pred["output"]
    audio_url = out[0] if isinstance(out, list) else out
    print("downloading:", audio_url)
    ext = ".mp3" if audio_url.split("?")[0].endswith(".mp3") else ".wav"
    dest = os.path.join(OUT_DIR, "vocals" + ext)
    urllib.request.urlretrieve(audio_url, dest)
    print("saved:", dest)
    with open(os.path.join(OUT_DIR, "vocals_meta.json"), "w") as f:
        json.dump({"model": MODEL, "version": version, "tags": TAGS,
                   "duration": duration, "output_url": audio_url,
                   "file": os.path.basename(dest)}, f, indent=2)


if __name__ == "__main__":
    main()
