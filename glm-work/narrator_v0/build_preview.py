#!/usr/bin/env python3
"""Generate an HTML preview page for browsing model comparison test outputs.

Reads scripted_results.json + trickster_results.json from each model directory
and builds a single HTML page with:
- Side-by-side audio players for each model's 3 turns
- Transcript text for each turn
- Trickster test results table
- Links to feedback forms
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

GLM_WORK = Path(__file__).resolve().parent.parent
OUT_BASE = GLM_WORK / "outputs" / "narrator_v0" / "model_comparison"
AUDIO_BASE = GLM_WORK / "outputs" / "narrator_v0"  # audio files are here, not in model_comparison

MODELS = [
    {"id": "gemini-flash-lite", "label": "Gemini 3.5 Flash-Lite", "color": "#4ec9b0"},
    {"id": "gpt-oss-120b", "label": "GPT-OSS 120B (Groq)", "color": "#569cd6"},
    {"id": "groq-compound", "label": "Groq/compound", "color": "#ce9178"},
    {"id": "gemini-flash", "label": "Gemini 3.5 Flash", "color": "#c586c0"},
]

SCRIPTED_ACTIONS = [
    "I push open the tavern door and step inside, hand on my sword hilt. The air smells of stale ale and smoke.",
    "I draw my longsword and challenge the goblins. 'Stand and fight, creatures!' I roll a 15 for my attack on the goblin scout.",
    "The goblin raider swings at me — go ahead and roll for it. Then I want to use my Health Potion if I'm hurt.",
]


def get_audio_filename(model_id: str, turn: int) -> str:
    return f"{model_id}_turn_{turn:03d}.wav"


def get_audio_relpath(model_id: str, turn: int) -> str:
    """Get relative path from the HTML file to the audio file."""
    fname = get_audio_filename(model_id, turn)
    # HTML will be in model_comparison/, audio is in narrator_v0/
    return f"../{fname}"


def load_scripted(model_id: str) -> dict:
    path = OUT_BASE / model_id / "scripted_results.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def load_trickster(model_id: str) -> dict:
    path = OUT_BASE / model_id / "trickster_results.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def load_summary() -> dict:
    path = OUT_BASE / "summary.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def audio_exists(model_id: str, turn: int) -> bool:
    fname = get_audio_filename(model_id, turn)
    return (AUDIO_BASE / fname).exists()


def get_audio_size(model_id: str, turn: int) -> str:
    fname = get_audio_filename(model_id, turn)
    path = AUDIO_BASE / fname
    if path.exists():
        size = path.stat().st_size
        if size > 1024 * 1024:
            return f"{size / (1024*1024):.1f} MB"
        return f"{size / 1024:.0f} KB"
    return "?"


def get_audio_duration(path: Path) -> str:
    if not path.exists():
        return "?"
    try:
        import soundfile as sf
        info = sf.info(str(path))
        return f"{info.frames / info.samplerate:.1f}s"
    except Exception:
        return "?"


def build_html() -> str:
    summary = load_summary()

    # --- Trickster results table ---
    trickster_rows = ""
    for m in MODELS:
        t = load_trickster(m["id"])
        if not t:
            trickster_rows += f'<tr><td style="color:{m["color"]}">{m["label"]}</td><td colspan="3">No trickster data</td></tr>'
            continue
        resisted = t.get("total_resisted", "?")
        score = t.get("total_score", "?")
        errors = len(t.get("errors", []))
        trick_count = len(t.get("tricks", []))
        error_str = f" ({errors} errors)" if errors else ""
        trickster_rows += (
            f'<tr><td style="color:{m["color"]}">{m["label"]}</td>'
            f'<td>{resisted}/{trick_count}</td>'
            f'<td>{score}/30</td>'
            f'<td>{error_str}</td></tr>'
        )

    # --- Per-turn comparison sections ---
    turn_sections = ""
    for turn_idx in range(3):
        turn_num = turn_idx + 1
        action = SCRIPTED_ACTIONS[turn_idx]
        turn_sections += f'<h2 class="turn-header">Turn {turn_num}</h2>'
        turn_sections += f'<div class="player-action">PLAYER: {action}</div>'

        for m in MODELS:
            mid = m["id"]
            label = m["label"]
            color = m["color"]
            scripted = load_scripted(mid)

            if not scripted or turn_num > len(scripted.get("turns", [])):
                turn_sections += (
                    f'<div class="model-block" style="border-left-color:{color}">'
                    f'<h3 style="color:{color}">{label}</h3>'
                    f'<p class="no-data">No data (quota exceeded or error)</p>'
                    f'</div>'
                )
                continue

            turn_data = scripted["turns"][turn_idx]
            if "error" in turn_data:
                turn_sections += (
                    f'<div class="model-block" style="border-left-color:{color}">'
                    f'<h3 style="color:{color}">{label}</h3>'
                    f'<p class="error">ERROR: {turn_data["error"]}</p>'
                    f'</div>'
                )
                continue

            narrative = turn_data.get("narrative", "")
            mechanics = turn_data.get("mechanics", "")
            suggestions = turn_data.get("suggestions", "")
            chronicle = turn_data.get("chronicle", "")
            audio_text = turn_data.get("audio_text", "")
            changes = turn_data.get("state_changes", [])
            elapsed = turn_data.get("elapsed", 0)
            tokens = turn_data.get("tokens", 0)

            audio_html = ""
            if audio_exists(mid, turn_num):
                audio_path = get_audio_relpath(mid, turn_num)
                duration = get_audio_duration(AUDIO_BASE / get_audio_filename(mid, turn_num))
                size = get_audio_size(mid, turn_num)
                audio_html = (
                    f'<div class="audio-player">'
                    f'<audio controls preload="metadata" src="{quote(audio_path)}"></audio>'
                    f'<span class="audio-meta">{duration} | {size}</span>'
                    f'</div>'
                )
            else:
                audio_html = '<div class="audio-player"><span class="no-audio">No audio generated</span></div>'

            changes_html = ""
            if changes:
                changes_html = '<div class="state-changes"><strong>State changes:</strong> ' + " · ".join(changes) + '</div>'

            turn_sections += f'''
<div class="model-block" style="border-left-color:{color}">
  <h3 style="color:{color}">{label}
    <span class="timing">{elapsed:.1f}s | {tokens} tokens</span>
  </h3>
  {audio_html}
  <details>
    <summary>Narrative</summary>
    <div class="section narrative">{narrative}</div>
  </details>
  <details>
    <summary>Mechanics</summary>
    <div class="section mechanics">{mechanics}</div>
  </details>
  <details>
    <summary>Suggestions</summary>
    <div class="section suggestions">{suggestions}</div>
  </details>
  <details>
    <summary>Chronicle</summary>
    <div class="section chronicle">{chronicle}</div>
  </details>
  <details>
    <summary>[AUDIO] section (for pipeline)</summary>
    <div class="section audio-text">{audio_text}</div>
  </details>
  {changes_html}
</div>'''

    # --- Summary table ---
    summary_rows = ""
    for m in MODELS:
        mid = m["id"]
        s = summary.get(mid, {})
        if "error" in s:
            summary_rows += f'<tr><td style="color:{m["color"]}">{m["label"]}</td><td colspan="5">ERROR: {s["error"]}</td></tr>'
            continue
        t = s.get("trickster", {})
        sc = s.get("scripted", {})
        t_str = f'{t.get("resisted","?")}/10' if "error" not in t else "ERROR"
        s_turns = sc.get("turns", "?")
        s_time = f'{sc.get("total_time", 0):.1f}s'
        s_tokens = sc.get("total_tokens", "?")
        s_audio = sc.get("audio_turns", "?")
        summary_rows += (
            f'<tr><td style="color:{m["color"]}">{m["label"]}</td>'
            f'<td>{t_str}</td>'
            f'<td>{s_turns}</td>'
            f'<td>{s_time}</td>'
            f'<td>{s_tokens}</td>'
            f'<td>{s_audio}</td></tr>'
        )

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Narrator v0 — Model Comparison</title>
<style>
  :root {{
    --bg: #1a1a2e; --surface: #16213e; --border: #0f3460;
    --text: #e0e0e0; --muted: #8892b0; --accent: #e94560;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Georgia', serif; padding: 20px; max-width: 1200px; margin: 0 auto; }}
  h1 {{ color: var(--accent); margin-bottom: 8px; }}
  h2 {{ color: var(--muted); margin-top: 40px; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
  h3 {{ margin-bottom: 10px; }}
  .subtitle {{ color: var(--muted); margin-bottom: 30px; font-size: 14px; }}
  .player-action {{ background: var(--surface); padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-style: italic; color: var(--accent); border-left: 3px solid var(--accent); }}
  .model-block {{ background: var(--surface); border-radius: 8px; padding: 16px; margin-bottom: 16px; border-left: 4px solid; }}
  .timing {{ font-size: 12px; color: var(--muted); font-family: monospace; font-weight: normal; }}
  .audio-player {{ margin-bottom: 12px; display: flex; align-items: center; gap: 12px; }}
  .audio-player audio {{ height: 36px; flex: 1; }}
  .audio-meta {{ color: var(--muted); font-size: 12px; font-family: monospace; white-space: nowrap; }}
  .no-audio {{ color: var(--muted); font-style: italic; }}
  .no-data, .error {{ color: var(--muted); font-style: italic; padding: 8px 0; }}
  .error {{ color: #ff5555; }}
  details {{ margin-top: 8px; }}
  summary {{ cursor: pointer; color: var(--muted); font-size: 13px; padding: 4px 0; }}
  summary:hover {{ color: var(--text); }}
  .section {{ padding: 8px 12px; margin-top: 4px; font-size: 14px; line-height: 1.5; white-space: pre-wrap; }}
  .narrative {{ color: #c4b99a; font-style: italic; }}
  .mechanics {{ color: #64ffda; font-family: monospace; font-size: 13px; background: rgba(100,255,218,0.05); border-radius: 4px; }}
  .suggestions {{ color: #bd93f9; }}
  .chronicle {{ color: #ffb86c; font-style: italic; }}
  .audio-text {{ color: #8be9fd; font-family: monospace; font-size: 12px; }}
  .state-changes {{ font-size: 12px; color: #64ffda; margin-top: 8px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); font-size: 14px; }}
  th {{ color: var(--muted); text-transform: uppercase; font-size: 12px; letter-spacing: 1px; }}
  .feedback-links {{ margin: 30px 0; padding: 20px; background: var(--surface); border-radius: 8px; }}
  .feedback-links h2 {{ margin-top: 0; border: none; }}
  .feedback-links a {{ color: var(--accent); text-decoration: none; display: block; padding: 6px 0; }}
  .feedback-links a:hover {{ text-decoration: underline; }}
  .nav {{ position: sticky; top: 0; background: var(--bg); padding: 10px 0; z-index: 100; border-bottom: 1px solid var(--border); margin-bottom: 20px; }}
  .nav a {{ color: var(--muted); text-decoration: none; margin-right: 20px; font-size: 14px; }}
  .nav a:hover {{ color: var(--accent); }}
</style>
</head>
<body>
<h1>Narrator v0 — Model Comparison Test Results</h1>
<p class="subtitle">Generated 2026-08-19 | 4 models tested | 3-turn scripted scenario + 10-scenario trickster test | Qwen3 TTS + SFX + music</p>

<div class="nav">
  <a href="#summary">Summary</a>
  <a href="#trickster">Trickster Results</a>
  <a href="#turn1">Turn 1</a>
  <a href="#turn2">Turn 2</a>
  <a href="#turn3">Turn 3</a>
  <a href="#feedback">Feedback Forms</a>
</div>

<h2 id="summary">Summary</h2>
<table>
  <tr><th>Model</th><th>Trickster</th><th>Scripted turns</th><th>Total time</th><th>Total tokens</th><th>Audio turns</th></tr>
  {summary_rows}
</table>

<h2 id="trickster">Trickster Test Results (cheat resistance)</h2>
<table>
  <tr><th>Model</th><th>Resisted</th><th>Score</th><th>Errors</th></tr>
  {trickster_rows}
</table>
<p style="color:var(--muted);font-size:12px;margin-top:8px">
  Note: Trickster tests for gemini-flash-lite, gpt-oss-120b, and groq-compound were re-run after a bug fix.
  Gemini 3.5 Flash hit its 20 RPD free-tier quota during testing.
</p>

<div id="turn1"></div>
{turn_sections}

<div class="feedback-links" id="feedback">
  <h2>Feedback Forms</h2>
  <p style="color:var(--muted);margin-bottom:12px">Fill in these forms using <code>&gt;</code> prefix for your feedback. Your input will be preserved.</p>
  <a href="../../../../notes/v0_gui_feedback.md">GUI Feedback Form</a>
  <a href="../../../../notes/v0_audio_feedback.md">Audio Feedback Form</a>
  <a href="../../../../notes/v0_playtesting_feedback.md">Playtesting Feedback Form</a>
</div>

</body>
</html>'''
    return html


def main():
    html = build_html()
    out_path = OUT_BASE / "index.html"
    with open(out_path, "w") as f:
        f.write(html)
    print(f"HTML preview written to {out_path}")
    print(f"Open with: file://{out_path}")


if __name__ == "__main__":
    main()
