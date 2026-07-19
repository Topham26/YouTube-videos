# Holy, Holy, Holy — The Council of the Holy Ones

A cinematic **lyric video** for a divine-council reworking of Reginald Heber's
1826 hymn "Holy, Holy, Holy." Everything here is generated from
[`lyrics-source.md`](lyrics-source.md) by the scripts in [`build/`](build).

## Deliverables

| File | What it is |
|------|-----------|
| `Holy_Holy_Holy_Council.mp4` | 1920×1080, 24 fps lyric video (throne-room / starfield visuals, animated lyrics with scripture refs) |
| `thumbnail.png` | 1280×720 YouTube thumbnail |
| `youtube-description.md` | Title options, full description, tags, chapter timestamps, copyright checklist |
| `lyrics-source.md` | The original brief (lyrics + arrangement guide) |

## Audio

Two paths, both wired up:

- **Synthesized instrumental** (default, no external services): `build/build_audio.py`
  renders a D-major / 72 bpm cinematic pad bed that follows the arrangement-guide
  form (Intro → V1 → V2 → Chorus → V3 → Chorus → Bridge → Final Chorus → Outro).
- **AI vocals** (optional, needs a key): `build/build_vocals.py` sends the exact
  lyrics + a "cinematic worship, male lead + choir" style prompt to **ACE-Step on
  Replicate** and downloads a full sung take. Requires `REPLICATE_API_TOKEN`.
  When `vocals.wav`/`vocals.mp3` is present, the video build uses it automatically.

## Rebuild

```bash
cd build
pip install pillow numpy imageio-ffmpeg     # ffmpeg comes bundled with imageio-ffmpeg

python3 build_audio.py            # -> track.wav + timeline.json  (instrumental)

# optional — real sung vocals via ACE-Step:
export REPLICATE_API_TOKEN=r8_xxx
python3 build_vocals.py           # -> vocals.wav

python3 build_video.py            # -> ../Holy_Holy_Holy_Council.mp4
python3 build_thumbnail.py        # -> ../thumbnail.png
```

`build_video.py` prefers `vocals.*` and falls back to `track.wav`; lyric timings
are scaled to the actual audio length, so either source stays in sync.

## Credits & licensing

Heber's text (1826) and the NICAEA tune (John B. Dykes, 1861) are public domain.
The adapted lyrics (new verses + chorus) and the generated audio/video are the
project author's own. If using ACE-Step output commercially, check Replicate's /
the model's licence for your use. The chorus follows the Deuteronomy 32:8
LXX / Dead Sea Scrolls reading ("sons of God"); see `youtube-description.md`.
