#!/usr/bin/env python3
"""Simple local web server for interactive D&D play via Groq API.

Serves the HTML GUI and proxies API calls to Groq (keeps the API key server-side).

Usage:
  python serve_dm_web.py --model openai/gpt-oss-120b
  python serve_dm_web.py --model openai/gpt-oss-20b --port 8080

Then open http://localhost:5000 in your browser.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent / ".env")

# ---------------------------------------------------------------------------
# DM system prompt and state (shared with test_api_dm.py logic)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert D&D 5e Dungeon Master running a solo campaign for one player.

## RULES CONTRACT (follow strictly)

1. ROLLS BEFORE OUTCOMES. Never narrate a combat result before the dice are rolled.
   WRONG: "Your sword strikes true, dealing 8 damage!"
   CORRECT: Ask the player to roll, wait for the number, THEN narrate the outcome.
   If the player has not provided a roll for an action that needs one, ask for it.

2. STATE IS AUTHORITATIVE. The game state provided in each turn is the source of
   truth. Do not contradict it. Do not invent items, HP, conditions, or NPCs not
   listed in the state.

3. RESPONSE FORMAT. Every response MUST contain exactly 4 sections:

   [NARRATIVE]
   The story beat — 2 to 4 paragraphs. Vivid but not purple prose.

   [MECHANICS]
   Machine-readable tags only, one per line:
     HP_CHANGE:<signed_int>
     ENEMY_HP:<name>,<current>/<max>
     ENEMY_DEAD:<name>
     ROLL_REQUEST:<dice> for <skill>
     ITEM_USED:<name>
     ITEM_GAINED:<name>
     SPELL_SLOT_USED:<level>
     CONDITION:<target>,<condition>
     NO_MECHANICS

   [SUGGESTIONS]
   2-3 player options, each tagged:
     - <option text> [roll:true]
     - <option text> [roll:false]

   [CHRONICLE]
   One-line campaign log entry. Use "NO_ENTRY" for uneventful turns.

4. ENCOUNTER BALANCE. Solo play — no party backup. Level 1 enemies: max 7 HP.

5. BE THE DM, NOT A PLAYER. You control NPCs, monsters, and the world.

6. WARLOCK SPELL SLOTS recharge on a short rest, not a long rest.
"""

import re
import time
from dataclasses import dataclass, field


@dataclass
class Enemy:
    name: str
    hp: int
    max_hp: int
    ac: int
    @property
    def alive(self): return self.hp > 0
    def __repr__(self):
        s = f"{self.hp}/{self.max_hp} HP, AC {self.ac}"
        if not self.alive: s += " [DEAD]"
        return f"{self.name} ({s})"


@dataclass
class GameState:
    pc_name: str = "Kael"
    pc_class: str = "Fighter"
    pc_level: int = 1
    pc_hp: int = 12
    pc_max_hp: int = 12
    pc_ac: int = 16
    pc_str: int = 16
    pc_dex: int = 12
    pc_con: int = 14
    inventory: list = field(default_factory=lambda: ["Health Potion", "Torch", "Waterskin", "50 feet of rope"])
    equipment: str = "longsword (1d8+3 slashing), shield, chain mail"
    enemies: list = field(default_factory=list)
    location: str = "The Rusty Anchor tavern"
    light: str = "dim (candlelit)"
    time: str = "evening"
    last_mechanics: str = "(start of encounter)"
    chronicle: list = field(default_factory=list)
    @property
    def str_mod(self): return (self.pc_str - 10) // 2
    @property
    def dex_mod(self): return (self.pc_dex - 10) // 2

    def to_prompt_block(self):
        enemies_str = "\n  ".join(str(e) for e in self.enemies) if self.enemies else "None"
        inv = ", ".join(self.inventory) if self.inventory else "Empty"
        return f"""CURRENT GAME STATE (authoritative):
  PC: {self.pc_name}, Level {self.pc_level} {self.pc_class} | HP: {self.pc_hp}/{self.pc_max_hp} | AC: {self.pc_ac}
  STR {self.pc_str} ({'+' if self.str_mod >= 0 else ''}{self.str_mod}) | DEX {self.pc_dex} ({'+' if self.dex_mod >= 0 else ''}{self.dex_mod})
  Inventory: {inv}
  Equipment: {self.equipment}
  Enemies:
  {enemies_str}
  Scene: {self.location} | Light: {self.light} | Time: {self.time}
  Previous turn mechanics: {self.last_mechanics}"""

    def apply_mechanics(self, text):
        changes = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or line == "NO_MECHANICS": continue
            if ":" not in line: continue
            tag, val = line.split(":", 1)
            tag = tag.strip().upper(); val = val.strip()
            if tag == "HP_CHANGE":
                try:
                    amt = int(val); old = self.pc_hp
                    self.pc_hp = max(0, min(self.pc_max_hp, self.pc_hp + amt))
                    changes.append(f"PC HP: {old} → {self.pc_hp}")
                except ValueError: pass
            elif tag == "ENEMY_HP":
                parts = val.split(",")
                if len(parts) == 2:
                    name = parts[0].strip(); hp_p = parts[1].strip().split("/")
                    if len(hp_p) == 2:
                        for e in self.enemies:
                            if e.name.lower() == name.lower():
                                e.hp = max(0, int(hp_p[0]))
                                changes.append(f"{e.name} HP → {e.hp}/{e.max_hp}")
                                break
            elif tag == "ENEMY_DEAD":
                for e in self.enemies:
                    if e.name.lower() == val.lower() and e.alive:
                        e.hp = 0; changes.append(f"{e.name} DEAD"); break
            elif tag == "ITEM_USED":
                if val in self.inventory: self.inventory.remove(val); changes.append(f"Used: {val}")
            elif tag == "ITEM_GAINED":
                self.inventory.append(val); changes.append(f"Gained: {val}")
            elif tag == "CONDITION":
                changes.append(f"Condition: {val}")
            elif tag == "ROLL_REQUEST":
                changes.append(f"Roll: {val}")
        self.last_mechanics = text.strip()[:200] if text.strip() else "NO_MECHANICS"
        return changes

    def to_dict(self):
        return {
            "pc_name": self.pc_name, "pc_hp": self.pc_hp, "pc_max_hp": self.pc_max_hp,
            "pc_ac": self.pc_ac, "inventory": list(self.inventory),
            "enemies": [{"name": e.name, "hp": e.hp, "max_hp": e.max_hp, "ac": e.ac, "alive": e.alive} for e in self.enemies],
            "location": self.location, "time": self.time,
        }


def parse_response(text):
    sections = {"NARRATIVE": "", "MECHANICS": "", "SUGGESTIONS": "", "CHRONICLE": ""}
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    for tag in sections:
        pattern = rf"\*{{0,2}}\[{tag}\]\*{{0,2}}\s*(.*?)(?=\*{{0,2}}\[(?:NARRATIVE|MECHANICS|SUGGESTIONS|CHRONICLE)\]|$)"
        m = re.search(pattern, text, re.DOTALL)
        if m: sections[tag] = m.group(1).strip()
    return sections


def make_initial_state():
    return GameState(enemies=[Enemy("Goblin Scout", 7, 7, 15), Enemy("Goblin Raider", 7, 7, 15)])


# ---------------------------------------------------------------------------
# Web server
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>D&D DM Brain — Interactive Play</title>
<style>
  :root {
    --bg: #1a1a2e; --surface: #16213e; --border: #0f3460;
    --text: #e0e0e0; --muted: #8892b0; --accent: #e94560;
    --narrative: #c4b99a; --mechanics: #64ffda; --suggestions: #bd93f9;
    --chronicle: #ffb86c; --hp-good: #50fa7b; --hp-bad: #ff5555;
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
</style>
</head>
<body>
<header>
  <h1>🎲 D&D DM Brain</h1>
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

async function newGame() {
  history = [];
  document.getElementById('messages').innerHTML = '';
  const resp = await fetch('/api/newgame', {method: 'POST'});
  const data = await resp.json();
  document.getElementById('modelLabel').textContent = data.model;
  updateState(data.state);
  addMessage('dm', data.response);
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
    addMessage('dm', data.response, data.changes);
    updateState(data.state);
  } catch(e) {
    document.getElementById('typing')?.remove();
    addMessage('dm', 'Error: ' + e.message);
  }
  btn.disabled = false;
  input.focus();
}

function addMessage(role, content, changes) {
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
  }
  msg.innerHTML = html;
  messages.appendChild(msg);
  messages.scrollTop = messages.scrollHeight;
}

function useSuggestion(text) {
  document.getElementById('playerInput').value = text;
  document.getElementById('playerInput').focus();
}

function parseSections(text) {
  const sections = {NARRATIVE:'', MECHANICS:'', SUGGESTIONS:'', CHRONICLE:''};
  text = text.replace(/<think>.*?<\/think>/gs, '');
  for (const tag of Object.keys(sections)) {
    const re = new RegExp(`\\*{0,2}\\[${tag}\\]\\*{0,2}\\s*(.*?)(?=\\*{0,2}\\[(?:NARRATIVE|MECHANICS|SUGGESTIONS|CHRONICLE)\\]|$)`, 's');
    const m = text.match(re);
    if (m) sections[tag] = m[1].trim();
  }
  return sections;
}

function updateState(state) {
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
function escapeAttr(s) { return s.replace(/'/g, "\\'").replace(/"/g, '&quot;'); }

newGame();
</script>
</body>
</html>"""


class DMHandler(BaseHTTPRequestHandler):
    state = None
    history = []
    client = None
    model = None

    def log_message(self, format, *args):
        pass  # suppress default logging

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode()

        if self.path == "/api/newgame":
            DMHandler.state = make_initial_state()
            DMHandler.history = []
            opening = "I enter the tavern and look around, hand on my sword hilt."
            resp_text, elapsed, _ = self._call_dm(opening)
            sections = parse_response(resp_text)
            DMHandler.state.apply_mechanics(sections["MECHANICS"])
            DMHandler.history.append({"role": "user", "content": opening})
            DMHandler.history.append({"role": "assistant", "content": resp_text})
            self._json_response({
                "response": resp_text,
                "state": DMHandler.state.to_dict(),
                "model": DMHandler.model,
            })

        elif self.path == "/api/turn":
            data = json.loads(body)
            action = data.get("action", "")
            resp_text, elapsed, _ = self._call_dm(action)
            sections = parse_response(resp_text)
            changes = DMHandler.state.apply_mechanics(sections["MECHANICS"])
            DMHandler.history.append({"role": "user", "content": action})
            DMHandler.history.append({"role": "assistant", "content": resp_text})
            self._json_response({
                "response": resp_text,
                "state": DMHandler.state.to_dict(),
                "changes": changes,
            })
        else:
            self.send_response(404)
            self.end_headers()

    def _call_dm(self, player_input):
        state_block = DMHandler.state.to_prompt_block()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(DMHandler.history)
        messages.append({"role": "user", "content": f"{state_block}\n\nPLAYER ACTION:\n{player_input}"})
        t0 = time.time()
        resp = DMHandler.client.chat.completions.create(
            model=DMHandler.model, messages=messages,
            temperature=0.7, max_tokens=2000,
        )
        elapsed = time.time() - t0
        return resp.choices[0].message.content, elapsed, resp.usage

    def _json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def main():
    parser = argparse.ArgumentParser(description="Serve the D&D DM web GUI")
    parser.add_argument("--model", default="gemini-3.5-flash-lite",
                        help="Model name (default: gemini-3.5-flash-lite. Groq: openai/gpt-oss-120b)")
    parser.add_argument("--port", type=int, default=5000, help="Port to serve on")
    args = parser.parse_args()

    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("ERROR: No API key set. Set GROQ_API_KEY or GOOGLE_API_KEY in .env", file=sys.stderr)
        sys.exit(1)

    # Auto-detect provider based on model name
    if args.model.startswith("gemini"):
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    else:
        base_url = "https://api.groq.com/openai/v1"

    DMHandler.client = OpenAI(api_key=api_key, base_url=base_url)
    DMHandler.model = args.model

    server = HTTPServer(("localhost", args.port), DMHandler)
    print(f"\n🎲 D&D DM Brain server running at http://localhost:{args.port}")
    print(f"   Model: {args.model}")
    print(f"   Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
