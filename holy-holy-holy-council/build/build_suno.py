#!/usr/bin/env python3
"""
Generate sung vocals for "Holy, Holy, Holy (The Council of the Holy Ones)"
via the Suno API (api.sunoapi.org) — the same backend the CodeKeanu/suno-mcp
server wraps, called directly so it runs in this sandbox without Docker.

Requires:
    SUNO_API_KEY        your key from https://sunoapi.org  (a paid API relay;
                        this is NOT your Suno consumer login)
    SUNO_API_BASE_URL   optional, default https://api.sunoapi.org

Usage:
    export SUNO_API_KEY=sk_xxx
    python3 build_suno.py                 # generate with defaults (V5)
    python3 build_suno.py --model V4_5PLUS
    python3 build_suno.py --instrumental  # backing track only

On success it downloads every returned take to build/ as
vocals.mp3 (best/first) and vocals_take2.mp3, and writes vocals_meta.json.
Then run build_video.py to remux the video over the chosen vocal.
"""
import os
import sys
import time
import json
import urllib.request
import urllib.error

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("SUNO_API_BASE_URL", "https://api.sunoapi.org").rstrip("/")

TITLE = "Holy, Holy, Holy (The Council of the Holy Ones)"

STYLE = ("cinematic modern worship anthem, reverent and awe-filled, "
         "male lead vocal with stacked choir harmonies, grand piano, "
         "ambient synth pads, anthemic drums, gang-vocal bridge, "
         "D major, 72 bpm, 4/4")

# Suno lyrics with section tags (instrumental intro/outro marked).
LYRICS = """[Intro]

[Verse 1]
Holy, holy, holy, Lord God Almighty,
Early in the morning our song shall rise to Thee.
Holy, holy, holy, none in the heavens like Thee,
Feared in the assembly of the holy ones on high.

[Verse 2]
Holy, holy, holy, the sons of God adore Thee,
Casting down their crowns before the fiery throne.
Watchers and the seraphs bow within Thy council,
Who among the mighty ones can stand before Thee, Lord?

[Chorus]
You divided up the nations,
Set their bounds by heaven's sons,
But Jacob is Your portion,
Israel the one You won.
Rise, O God, and judge the rulers,
Take the nations for Your own,
Every knee in heaven's council
Bends before Your throne alone.

[Verse 3]
Holy, holy, holy, though rebel powers defied Thee,
Though the gods of nations led the peoples far astray,
Thou alone art faithful, the Judge of all the council,
"You shall die like mortals, and fall like any prince."

[Chorus]
You divided up the nations,
Set their bounds by heaven's sons,
But Jacob is Your portion,
Israel the one You won.
Rise, O God, and judge the rulers,
Take the nations for Your own,
Every knee in heaven's council
Bends before Your throne alone.

[Bridge]
God stands in the assembly, He holds court among the gods.
God stands in the assembly, He holds court among the gods.
Arise, O God! Judge the earth!
For all the nations belong to You!

[Verse 4]
Holy, holy, holy, Lord God Almighty,
All Thy works shall praise Thy name in earth and sky and sea.
Holy, holy, holy, the Name above the elim,
God enthroned in glory, and reigning over all.

[Final Chorus]
Rise, O God, and judge the rulers,
Take the nations for Your own,
Every knee in heaven's council
Bends before Your throne alone.

[Outro]
"""

SUCCESS = "SUCCESS"
FAIL_STATES = {"CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED",
               "CALLBACK_EXCEPTION", "SENSITIVE_WORD_ERROR"}


def api(method, path, key, data=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Authorization", f"Bearer {key}")
    r.add_header("Content-Type", "application/json")
    r.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:600])
        raise


def main():
    key = os.environ.get("SUNO_API_KEY")
    if not key:
        sys.exit("ERROR: set SUNO_API_KEY (from https://sunoapi.org) first.")

    argv = sys.argv[1:]
    model = "V5"
    if "--model" in argv:
        model = argv[argv.index("--model") + 1]
    instrumental = "--instrumental" in argv

    payload = {
        "customMode": True,
        "instrumental": instrumental,
        "prompt": "" if instrumental else LYRICS,
        "style": STYLE,
        "title": TITLE[:100],
        "model": model,
        "vocalGender": "m",
        "styleWeight": 0.65,
        # We poll record-info, so the callback is a harmless placeholder.
        "callBackUrl": "https://example.com/suno-callback",
    }

    print(f"generating on {BASE}  model={model}  instrumental={instrumental}")
    resp = api("POST", "/api/v1/generate", key, payload)
    if resp.get("code") != 200:
        sys.exit(f"generate failed: {resp}")
    task_id = resp["data"]["taskId"]
    print("taskId:", task_id)

    # poll record-info until SUCCESS (all takes done)
    audio = []
    deadline = time.time() + 600
    while time.time() < deadline:
        time.sleep(8)
        info = api("GET", f"/api/v1/generate/record-info?taskId={task_id}", key)
        d = info.get("data", {}) or {}
        status = d.get("status")
        print("  status:", status)
        if status in FAIL_STATES:
            sys.exit(f"generation failed: {status} :: {info}")
        if status == SUCCESS:
            audio = (d.get("response", {}) or {}).get("sunoData", []) or []
            break
    if not audio:
        sys.exit("timed out or no audio returned")

    meta = {"taskId": task_id, "model": model, "base": BASE,
            "title": TITLE, "takes": []}
    for i, tk in enumerate(audio):
        url = tk.get("audioUrl") or tk.get("streamAudioUrl")
        if not url:
            continue
        name = "vocals.mp3" if i == 0 else f"vocals_take{i+1}.mp3"
        dest = os.path.join(OUT_DIR, name)
        print(f"downloading take {i+1}: {url}")
        urllib.request.urlretrieve(url, dest)
        meta["takes"].append({"file": name, "id": tk.get("id"),
                              "title": tk.get("title"),
                              "duration": tk.get("duration"), "url": url})
    with open(os.path.join(OUT_DIR, "vocals_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("\nsaved:", ", ".join(t["file"] for t in meta["takes"]))
    print("next: python3 build_video.py   (auto-uses vocals.mp3)")


if __name__ == "__main__":
    main()
