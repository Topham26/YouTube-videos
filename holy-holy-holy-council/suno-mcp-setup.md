# Suno Integration (CodeKeanu) — Setup

Two ways to drive Suno for this project. **Both require an API key from
[sunoapi.org](https://sunoapi.org)** — a paid API relay for Suno. Important:
this key is **not** your Suno consumer login (`@invitingquarternote8523`). You
register separately at sunoapi.org, buy credits, and copy the API key from your
dashboard there.

`SUNO_API_KEY` = that key · `SUNO_API_BASE_URL` = `https://api.sunoapi.org`

---

## Option 1 — Direct script (used in this repo / this sandbox)

No Docker or MCP restart needed. `build/build_suno.py` calls the same
`api.sunoapi.org` endpoints the CodeKeanu MCP wraps.

```bash
cd build
export SUNO_API_KEY=your_sunoapi_org_key
python3 build_suno.py            # -> vocals.mp3 (+ vocals_take2.mp3)
python3 build_video.py           # re-renders the video over the Suno vocal
```

Options: `--model V5_5|V5|V4_5PLUS` (default `V5`), `--instrumental` for a
backing track only.

---

## Option 2 — CodeKeanu MCP server in Claude Code / Claude Desktop

Runs the actual [CodeKeanu/suno-mcp](https://github.com/CodeKeanu/suno-mcp)
container so Suno appears as MCP tools. Needs a running Docker daemon (works on
your local machine / Claude Desktop; the daemon is **not** running in this
web sandbox, which is why Option 1 is used here).

```bash
docker pull ghcr.io/codekeanu/suno-mcp:latest

mkdir -p ~/suno-mcp-config && cat > ~/suno-mcp-config/.env <<EOF
SUNO_API_KEY=your_sunoapi_org_key
SUNO_API_BASE_URL=https://api.sunoapi.org
EOF
```

Add to your Claude Code MCP config (`~/.config/claude-code/mcp_settings.json`)
or Claude Desktop config:

```json
{
  "mcpServers": {
    "suno": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "--env-file",
               "/home/YOU/suno-mcp-config/.env",
               "ghcr.io/codekeanu/suno-mcp:latest"]
    }
  }
}
```

Restart Claude Code; the `generate_music`, `get_task_status`, `get_music_info`,
`get_credits`, `convert_to_wav`, and `get_wav_conversion_status` tools become
available. Use `generate_music` with `custom_mode=true`, the `style` and
`title` from `suno-prompt.md`, and the tagged lyrics as `prompt`.

---

## After you have a Suno file

However you generate it (script, MCP, or the Suno web app), drop the audio at
`build/vocals.mp3` or `build/vocals.wav` and run `python3 build_video.py`. The
build auto-detects the vocal file and scales the on-screen lyric timing to its
length.
