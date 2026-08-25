"""Narrator v0 — the merged D&D app web server.

Player types an action → DM brain (LLM) responds with 5 sections →
rules lawyer validates [MECHANICS] → narration pipeline renders [AUDIO]
to a WAV (Qwen3 TTS + SFX + music) → audio plays in the browser →
player sees [SUGGESTIONS], types next action.

Usage:
  # From glm-work/ with venv activated:
  python -m narrator_v0.app --model gemini-3.5-flash-lite
  python -m narrator_v0.app --model openai/gpt-oss-120b --provider groq
  python -m narrator_v0.app --no-audio  # text-only mode (for testing)

  # Or directly:
  python narrator_v0/app.py --model gemini-3.5-flash-lite

Then open http://localhost:5102 in your browser.
"""
import argparse
import json
import os
import sys
import time
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Ensure glm-work/ is on the path
GLM_WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GLM_WORK))

from dotenv import load_dotenv

from . import config
from .dm_engine import (
    GameState,
    parse_response_v0,
    make_initial_state,
    make_client_v0,
    dm_turn_v0,
    SYSTEM_PROMPT_V0,
)


# ---------------------------------------------------------------------------
# Audio generation — runs in a background thread so the text response
# can be sent to the browser immediately, and audio follows when ready.
# ---------------------------------------------------------------------------

_audio_pipeline = None
_elevenlabs_key = None

def _init_audio():
    """Lazy-init the audio pipeline (loads Qwen3 model on first call)."""
    global _audio_pipeline, _elevenlabs_key
    if _audio_pipeline is None:
        from . import audio_pipeline
        _audio_pipeline = audio_pipeline
        _elevenlabs_key = os.environ.get(config.ELEVENLABS_ENV_VAR)
    return _audio_pipeline


def generate_audio_async(audio_text: str, turn_id: str, result_holder: dict):
    """Generate audio in a background thread. Stores result in result_holder.

    result_holder is a dict that will get keys:
      'audio_path' -> str or None
      'error' -> str (on failure)
      'done' -> True
    """
    try:
        pipeline = _init_audio()
        cast = pipeline.load_cast()
        audio_path = pipeline.render_narration(
            audio_text=audio_text,
            turn_id=turn_id,
            elevenlabs_key=_elevenlabs_key,
            cast=cast,
        )
        result_holder["audio_path"] = audio_path
    except Exception as e:
        import traceback
        traceback.print_exc()
        result_holder["error"] = str(e)
    finally:
        result_holder["done"] = True


# ---------------------------------------------------------------------------
# HTML page — extends serve_dm_web.py's GUI with audio playback
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Narrator v0 — D&D with Voice</title>
<style>
  :root {
    --bg: #1a1a2e; --surface: #16213e; --border: #0f3460;
    --text: #e0e0e0; --muted: #8892b0; --accent: #e94560;
    --narrative: #c4b99a; --mechanics: #64ffda; --suggestions: #bd93f9;
    --chronicle: #ffb86c; --hp-good: #50fa7b; --hp-bad: #ff5555;
    --audio: #8be9fd;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--text); font-family: 'Georgia', serif; height: 100vh; display: flex; flex-direction: column; }
  header { background: var(--surface); padding: 12px 20px; border-bottom: 2px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
  header h1 { font-size: 18px; color: var(--accent); }
  header .model-name { color: var(--muted); font-size: 13px; font-family: monospace; }
  .main { display: flex; flex: 1; overflow: hidden; }
  .sidebar { width: 280px; background: var(--surface); border-right: 1px solid var(--border); padding: 16px; overflow-y: auto; flex-shrink: 0; }
  .sidebar h2 { font-size: 14px; color: var(--muted); text-transform: uppercase; margin-bottom: 8px; letter-spacing: 1px; }
  .stat-block { background: var(--bg); border-radius: 8px; padding: 12px; margin-bottom: 16px; }
  .stat-row { display: flex; justify-content: space-between; padding: 3px 0; font-size: 13px; }
  .stat-label { color: var(--muted); }
  .hp-bar { width: 100%; height: 8px; background: var(--border); border-radius: 4px; margin-top: 4px; overflow: hidden; }
  .hp-fill { height: 100%; background: var(--hp-good); transition: width 0.3s, background 0.3s; }
  .enemy { font-size: 12px; padding: 6px 8px; margin: 4px 0; background: var(--bg); border-radius: 4px; border-left: 3px solid var(--hp-bad); }
  .enemy.dead { opacity: 0.4; text-decoration: line-through; border-left-color: var(--muted); }
  .inv-item { font-size: 12px; color: var(--text); padding: 2px 0; }
  .chat-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  .messages { flex: 1; overflow-y: auto; padding: 20px; }
  .msg { margin-bottom: 20px; max-width: 800px; }
  .msg.player { margin-left: 40px; }
  .msg.dm { margin-right: 40px; }
  .msg .role { font-size: 11px; color: var(--muted); text-transform: uppercase; margin-bottom: 4px; letter-spacing: 1px; }
  .msg.player .role { color: var(--accent); }
  .msg.dm .role { color: var(--mechanics); }
  .msg .content { font-size: 15px; line-height: 1.6; }
  .narrative { color: var(--narrative); font-style: italic; }
  .mechanics { color: var(--mechanics); font-family: monospace; font-size: 13px; background: rgba(100,255,218,0.05); padding: 8px 12px; border-radius: 4px; margin-top: 8px; }
  .suggestions { margin-top: 10px; }
  .suggestion-btn { display: block; width: 100%; text-align: left; background: var(--surface); border: 1px solid var(--border); color: var(--suggestions); padding: 8px 12px; margin: 4px 0; border-radius: 6px; cursor: pointer; font-size: 14px; font-family: inherit; transition: all 0.2s; }
  .suggestion-btn:hover { background: var(--border); border-color: var(--suggestions); }
  .suggestion-btn .roll-tag { font-size: 11px; color: var(--accent); margin-left: 8px; }
  .chronicle { color: var(--chronicle); font-size: 12px; font-style: italic; margin-top: 8px; border-top: 1px solid var(--border); padding-top: 6px; }
  .state-changes { font-size: 12px; color: var(--mechanics); margin-top: 6px; }
  .audio-bar { margin-top: 10px; background: var(--surface); border-radius: 8px; padding: 10px 14px; display: flex; align-items: center; gap: 10px; }
  .audio-bar audio { height: 32px; flex: 1; }
  .audio-bar .audio-label { color: var(--audio); font-size: 12px; font-family: monospace; white-space: nowrap; }
  .audio-bar .audio-status { color: var(--muted); font-size: 12px; font-style: italic; }
  .input-area { background: var(--surface); border-top: 1px solid var(--border); padding: 16px 20px; display: flex; gap: 12px; }
  .input-area input { flex: 1; background: var(--bg); border: 1px solid var(--border); color: var(--text); padding: 12px 16px; border-radius: 8px; font-size: 15px; font-family: inherit; outline: none; }
  .input-area input:focus { border-color: var(--accent); }
  .input-area button { background: var(--accent); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 15px; font-family: inherit; }
  .input-area button:hover { opacity: 0.85; }
  .input-area button:disabled { opacity: 0.4; cursor: not-allowed; }
  .typing { color: var(--muted); font-style: italic; padding: 8px 0; }
  .controls { display: flex; gap: 8px; }
  .controls button { background: var(--border); color: var(--text); border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px; }
  .controls button:hover { background: var(--accent); }
  .dice-roller { display: flex; gap: 4px; margin-bottom: 8px; flex-wrap: wrap; }
  .dice-btn { background: var(--border); color: var(--text); border: none; padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; font-family: monospace; }
  .dice-btn:hover { background: var(--accent); }
  .dice-result { color: var(--chronicle); font-size: 13px; font-family: monospace; margin-left: 8px; }
  .autoplay-toggle { display: flex; align-items: center; gap: 6px; margin-top: 8px; font-size: 12px; color: var(--muted); }
  .autoplay-toggle input { accent-color: var(--accent); }
</style>
</head>
<body>
<header>
  <h1>Narrator v0</h1>
  <span class="model-name" id="modelLabel">Loading...</span>
  <div class="controls">
    <button onclick="newGame()">New Game</button>
    <button onclick="toggleSidebar()">Toggle Stats</button>
  </div>
</header>
<div class="main">
  <aside class="sidebar" id="sidebar">
    <h2>Character</h2>
    <div class="stat-block" id="charBlock"></div>
    <h2>Enemies</h2>
    <div id="enemyList"></div>
    <h2>Inventory</h2>
    <div id="invList"></div>
    <h2>Dice Roller</h2>
    <div class="dice-roller">
      <button class="dice-btn" onclick="rollDice(20)">d20</button>
      <button class="dice-btn" onclick="rollDice(12)">d12</button>
      <button class="dice-btn" onclick="rollDice(10)">d10</button>
      <button class="dice-btn" onclick="rollDice(8)">d8</button>
      <button class="dice-btn" onclick="rollDice(6)">d6</button>
      <button class="dice-btn" onclick="rollDice(4)">d4</button>
      <button class="dice-btn" onclick="rollDice(100)">d100</button>
    </div>
    <span class="dice-result" id="diceResult"></span>
    <div class="autoplay-toggle">
      <input type="checkbox" id="autoplayAudio" checked>
      <label for="autoplayAudio">Auto-play audio when ready</label>
    </div>
  </aside>
  <div class="chat-area">
    <div class="messages" id="messages"></div>
    <div class="input-area">
      <input type="text" id="playerInput" placeholder="What do you do?" onkeypress="if(event.key==='Enter')sendAction()" autofocus>
      <button id="sendBtn" onclick="sendAction()">Send</button>
    </div>
  </div>
</div>
<script>
let history = [];
let sidebarVisible = true;
let turnCounter = 0;

async function newGame() {
  history = [];
  turnCounter = 0;
  document.getElementById('messages').innerHTML = '';
  try {
    const resp = await fetch('/api/newgame', {method: 'POST'});
    const data = await resp.json();
    if (data.error) {
      addMessage('dm', 'Error starting game: ' + data.error);
      return;
    }
    document.getElementById('modelLabel').textContent = data.model + (data.audio_enabled ? ' + audio' : ' (text only)');
    updateState(data.state);
    addMessage('dm', data.response, null, data.audio_turn_id, data.audio_enabled);
  } catch(e) {
    addMessage('dm', 'Error connecting to server: ' + e.message);
  }
}

async function sendAction() {
  const input = document.getElementById('playerInput');
  const btn = document.getElementById('sendBtn');
  const action = input.value.trim();
  if (!action) return;
  input.value = '';
  btn.disabled = true;
  addMessage('player', action);
  const typing = document.createElement('div');
  typing.className = 'msg dm typing'; typing.id = 'typing'; typing.textContent = 'DM is thinking...';
  document.getElementById('messages').appendChild(typing);
  document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
  try {
    const resp = await fetch('/api/turn', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action})
    });
    const data = await resp.json();
    document.getElementById('typing')?.remove();
    if (data.error) {
      addMessage('dm', 'Error: ' + data.error);
    } else {
      addMessage('dm', data.response, data.changes, data.audio_turn_id, data.audio_enabled);
      updateState(data.state);
    }
  } catch(e) {
    document.getElementById('typing')?.remove();
    addMessage('dm', 'Error connecting to server: ' + e.message);
  }
  btn.disabled = false;
  input.focus();
}

function addMessage(role, content, changes, audioTurnId, audioEnabled) {
  const messages = document.getElementById('messages');
  const msg = document.createElement('div');
  msg.className = 'msg ' + role;
  let html = `<div class="role">${role === 'player' ? 'You' : 'DM'}</div>`;
  if (role === 'player') {
    html += `<div class="content">${escapeHtml(content)}</div>`;
  } else {
    const sections = parseSections(content);
    if (sections.NARRATIVE) html += `<div class="content narrative">${escapeHtml(sections.NARRATIVE)}</div>`;
    if (sections.MECHANICS && sections.MECHANICS !== 'NO_MECHANICS')
      html += `<div class="mechanics">${escapeHtml(sections.MECHANICS)}</div>`;
    if (sections.SUGGESTIONS) {
      html += '<div class="suggestions">';
      sections.SUGGESTIONS.split('\n').filter(s=>s.trim()).forEach(s => {
        const rollMatch = s.match(/\[roll:(true|false)\]/);
        const rollTag = rollMatch ? `<span class="roll-tag">${rollMatch[1]==='true' ? '🎲' : '💬'}</span>` : '';
        const text = s.replace(/\[roll:(true|false)\]/,'').replace(/^[-•]\s*/,'').trim();
        if (text) html += `<button class="suggestion-btn" onclick="useSuggestion('${escapeAttr(text)}')">${escapeHtml(text)}${rollTag}</button>`;
      });
      html += '</div>';
    }
    if (sections.CHRONICLE && sections.CHRONICLE !== 'NO_ENTRY')
      html += `<div class="chronicle">📜 ${escapeHtml(sections.CHRONICLE)}</div>`;
    if (changes && changes.length)
      html += `<div class="state-changes">⚡ ${changes.map(escapeHtml).join(' · ')}</div>`;
    // Audio playback bar
    if (audioEnabled && audioTurnId) {
      html += `<div class="audio-bar" id="audio_${audioTurnId}">
        <span class="audio-label">🔊 Audio</span>
        <span class="audio-status" id="audio_status_${audioTurnId}">generating...</span>
      </div>`;
      pollAudio(audioTurnId);
    }
  }
  msg.innerHTML = html;
  messages.appendChild(msg);
  messages.scrollTop = messages.scrollHeight;
}

async function pollAudio(turnId) {
  const maxPolls = 120; // 2 minutes max (60s * 2)
  for (let i = 0; i < maxPolls; i++) {
    try {
      const resp = await fetch(`/api/audio_status?turn_id=${turnId}`);
      const data = await resp.json();
      if (data.status === 'ready') {
        const bar = document.getElementById(`audio_${turnId}`);
        if (bar) {
          bar.innerHTML = `<span class="audio-label">🔊 Audio</span>
            <audio controls src="/audio/${turnId}.wav" ${document.getElementById('autoplayAudio').checked ? 'autoplay' : ''}></audio>
            <span class="audio-status">${data.duration}s</span>`;
        }
        return;
      } else if (data.status === 'error') {
        const status = document.getElementById(`audio_status_${turnId}`);
        if (status) status.textContent = 'error: ' + (data.error || 'unknown');
        return;
      } else if (data.status === 'no_audio') {
        const status = document.getElementById(`audio_status_${turnId}`);
        if (status) status.textContent = 'no audio for this turn';
        return;
      }
    } catch(e) { /* keep polling */ }
    await new Promise(r => setTimeout(r, 1000));
  }
  const status = document.getElementById(`audio_status_${turnId}`);
  if (status) status.textContent = 'timeout';
}

function useSuggestion(text) {
  document.getElementById('playerInput').value = text;
  document.getElementById('playerInput').focus();
}

function parseSections(text) {
  const sections = {NARRATIVE:'', MECHANICS:'', SUGGESTIONS:'', CHRONICLE:'', AUDIO:''};
  text = text.replace(/<think>.*?<\/think>/gs, '');
  for (const tag of Object.keys(sections)) {
    const re = new RegExp(`\\*{0,2}\\[${tag}\\]\\*{0,2}\\s*(.*?)(?=\\*{0,2}\\[(?:NARRATIVE|MECHANICS|SUGGESTIONS|CHRONICLE|AUDIO)\\]|$)`, 's');
    const m = text.match(re);
    if (m) sections[tag] = m[1].trim();
  }
  return sections;
}

function updateState(state) {
  if (!state) return;
  const hpPct = (state.pc_hp / state.pc_max_hp) * 100;
  const hpColor = hpPct > 60 ? 'var(--hp-good)' : hpPct > 30 ? 'var(--chronicle)' : 'var(--hp-bad)';
  document.getElementById('charBlock').innerHTML = `
    <div class="stat-row"><span class="stat-label">Name</span><span>${state.pc_name}</span></div>
    <div class="stat-row"><span class="stat-label">Class</span><span>Level ${state.pc_level} Fighter</span></div>
    <div class="stat-row"><span class="stat-label">AC</span><span>${state.pc_ac}</span></div>
    <div class="stat-row"><span class="stat-label">HP</span><span>${state.pc_hp}/${state.pc_max_hp}</span></div>
    <div class="hp-bar"><div class="hp-fill" style="width:${hpPct}%;background:${hpColor}"></div></div>`;
  document.getElementById('enemyList').innerHTML = state.enemies.map(e =>
    `<div class="enemy ${e.alive ? '' : 'dead'}">${e.name} — ${e.hp}/${e.max_hp} HP, AC ${e.ac}</div>`).join('');
  document.getElementById('invList').innerHTML = state.inventory.map(i =>
    `<div class="inv-item">• ${i}</div>`).join('');
}

function rollDice(sides) {
  const result = Math.floor(Math.random() * sides) + 1;
  document.getElementById('diceResult').textContent = `d${sides} = ${result}`;
  document.getElementById('playerInput').value += ` I rolled a ${result} on d${sides}.`;
  document.getElementById('playerInput').focus();
}

function toggleSidebar() {
  sidebarVisible = !sidebarVisible;
  document.getElementById('sidebar').style.display = sidebarVisible ? '' : 'none';
}

function escapeHtml(s) { const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function escapeAttr(s) { return s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, '\\n').replace(/\r/g, '\\r'); }

newGame();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Web server
# ---------------------------------------------------------------------------

class NarratorHandler(BaseHTTPRequestHandler):
    # Class-level state (shared across requests in a single server)
    state = None
    history = []
    client = None
    model = None
    provider = None
    audio_enabled = True
    turn_counter = 0
    audio_results = {}  # turn_id -> {done, audio_path, error, duration}

    def log_message(self, format, *args):
        pass  # suppress default logging

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())

        elif parsed.path.startswith("/audio/"):
            # Serve a generated audio file
            turn_id = parsed.path.replace("/audio/", "").replace(".wav", "")
            # Sanitize: only allow alphanumeric + underscore
            if not turn_id.replace("_", "").isalnum():
                self.send_response(400)
                self.end_headers()
                return
            audio_path = config.OUTPUT_DIR / f"{turn_id}.wav"
            if audio_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(audio_path.stat().st_size))
                self.end_headers()
                with open(audio_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

        elif parsed.path == "/api/audio_status":
            # Poll audio generation status
            from urllib.parse import parse_qs
            params = parse_qs(parsed.query)
            turn_id = params.get("turn_id", [""])[0]
            result = self.audio_results.get(turn_id)
            if result is None:
                self._json_response({"status": "unknown"})
            elif not result.get("done"):
                self._json_response({"status": "generating"})
            elif result.get("error"):
                self._json_response({"status": "error", "error": result["error"]})
            elif result.get("audio_path"):
                import numpy as np
                import soundfile as sf
                try:
                    info = sf.info(result["audio_path"])
                    duration = round(info.frames / info.samplerate, 1)
                    self._json_response({"status": "ready", "duration": f"{duration}s"})
                except Exception:
                    self._json_response({"status": "ready", "duration": "?"})
            else:
                self._json_response({"status": "no_audio"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode()

        if self.path == "/api/newgame":
            try:
                NarratorHandler.state = make_initial_state()
                NarratorHandler.history = []
                NarratorHandler.turn_counter = 0
                NarratorHandler.audio_results = {}

                opening = "I enter the tavern and look around, hand on my sword hilt."
                resp_text, elapsed, usage = self._call_dm(opening)
                sections = parse_response_v0(resp_text)
                NarratorHandler.state.apply_mechanics(sections["MECHANICS"])
                NarratorHandler.history.append({"role": "user", "content": opening})
                NarratorHandler.history.append({"role": "assistant", "content": resp_text})

                # Start audio generation in background
                audio_turn_id = self._start_audio(sections.get("AUDIO", ""))

                self._json_response({
                    "response": resp_text,
                    "state": NarratorHandler.state.to_dict(),
                    "model": NarratorHandler.model,
                    "audio_enabled": NarratorHandler.audio_enabled,
                    "audio_turn_id": audio_turn_id,
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._json_response({"error": str(e)})

        elif self.path == "/api/turn":
            try:
                data = json.loads(body)
                action = data.get("action", "")
                if not action.strip():
                    self._json_response({"error": "Empty action"})
                    return
                resp_text, elapsed, usage = self._call_dm(action)
                sections = parse_response_v0(resp_text)
                changes = NarratorHandler.state.apply_mechanics(sections["MECHANICS"])
                NarratorHandler.history.append({"role": "user", "content": action})
                NarratorHandler.history.append({"role": "assistant", "content": resp_text})

                # Start audio generation in background
                audio_turn_id = self._start_audio(sections.get("AUDIO", ""))

                self._json_response({
                    "response": resp_text,
                    "state": NarratorHandler.state.to_dict(),
                    "changes": changes,
                    "audio_enabled": NarratorHandler.audio_enabled,
                    "audio_turn_id": audio_turn_id,
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._json_response({"error": str(e)})
        else:
            self.send_response(404)
            self.end_headers()

    def _call_dm(self, player_input):
        """Call the DM brain for one turn."""
        state_block = NarratorHandler.state.to_prompt_block()
        text, elapsed, usage = dm_turn_v0(
            client=NarratorHandler.client,
            model=NarratorHandler.model,
            state=NarratorHandler.state,
            history=NarratorHandler.history,
            player_input=player_input,
        )
        return text, elapsed, usage

    def _start_audio(self, audio_text: str) -> str:
        """Start audio generation in a background thread. Returns turn_id."""
        NarratorHandler.turn_counter += 1
        turn_id = f"turn_{NarratorHandler.turn_counter:04d}"

        # Clean up old audio results (keep last 20 to avoid unbounded growth)
        if len(NarratorHandler.audio_results) > 20:
            old_keys = sorted(NarratorHandler.audio_results.keys())[:-20]
            for k in old_keys:
                del NarratorHandler.audio_results[k]

        if not NarratorHandler.audio_enabled or not audio_text.strip():
            NarratorHandler.audio_results[turn_id] = {
                "done": True, "audio_path": None, "error": None
            }
            return turn_id

        result_holder = {"done": False, "audio_path": None, "error": None}
        NarratorHandler.audio_results[turn_id] = result_holder

        thread = threading.Thread(
            target=generate_audio_async,
            args=(audio_text, turn_id, result_holder),
            daemon=True,
        )
        thread.start()
        return turn_id

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Narrator v0 — D&D with voice narration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python -m narrator_v0.app --model gemini-3.5-flash-lite
  python -m narrator_v0.app --model openai/gpt-oss-120b --provider groq
  python -m narrator_v0.app --no-audio  # text-only mode
  python -m narrator_v0.app --port 8080
""",
    )
    parser.add_argument("--model", default=config.DEFAULT_MODEL,
                        help=f"Model name (default: {config.DEFAULT_MODEL})")
    parser.add_argument("--provider", default=None,
                        help="API provider (auto-detected from model name if omitted)")
    parser.add_argument("--port", type=int, default=5102,
                        help="Port to serve on (default: 5102, avoids macOS AirPlay on 5000)")
    parser.add_argument("--no-audio", action="store_true",
                        help="Disable audio generation (text-only mode for testing)")
    args = parser.parse_args()

    # Load .env
    load_dotenv(config.ENV_FILE)

    # Determine provider
    provider = args.provider or config.detect_provider(args.model)
    print(f"Provider: {provider} ({config.PROVIDERS[provider]['label']})")

    # Create API client
    try:
        client = make_client_v0(provider=provider, model=args.model)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    NarratorHandler.client = client
    NarratorHandler.model = args.model
    NarratorHandler.provider = provider
    NarratorHandler.audio_enabled = not args.no_audio

    if NarratorHandler.audio_enabled:
        print(f"Audio: ENABLED (Qwen3 TTS + SFX + music)")
        el_key = os.environ.get(config.ELEVENLABS_ENV_VAR)
        if el_key and not el_key.startswith("your_"):
            print(f"  ElevenLabs SFX: available (API key set)")
        else:
            print(f"  ElevenLabs SFX: cached + procedural fallback only (no API key)")
    else:
        print(f"Audio: DISABLED (text-only mode)")

    server = ThreadingHTTPServer(("localhost", args.port), NarratorHandler)
    print(f"\n  Narrator v0 running at http://localhost:{args.port}")
    print(f"  Model: {args.model}")
    print(f"  Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
