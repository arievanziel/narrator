#!/usr/bin/env python3
"""Narrator v0.1 — The full D&D narration app.

Features:
- Multi-provider DM brain (Gemini, Groq, Anthropic) with live switching
- v9-inspired book-like GUI with collapsible panels, circle buttons
- Word-for-word text matching: screen text = TTS audio text
- Parallel audio generation with Qwen3 TTS
- Continuous background music with mood-based switching
- Settings panel: model, TTS engine, volumes, auto-roll, budget
- Intro screen for story style input
- Budget tracking with automatic fallback for paid APIs
- Visual dice roller with animation
- 3+ choices per turn

Usage:
  cd glm-work && source .venv/bin/activate
  python -m narrator_v01.app --port 5102
  python -m narrator_v01.app --no-audio  # text-only mode
"""
import argparse
import json
import os
import sys
import time
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure glm-work/ is on the path
GLM_WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GLM_WORK))

from dotenv import load_dotenv

from . import config
from .dm_engine import (
    GameState, Enemy, SYSTEM_PROMPT, parse_response, parse_story,
    parse_suggestions, make_client, detect_provider, dm_turn,
    make_initial_state,
)

# Load .env
load_dotenv(GLM_WORK / ".env")


# ---------------------------------------------------------------------------
# Budget tracker
# ---------------------------------------------------------------------------

class BudgetTracker:
    def __init__(self, budget_usd: float = 5.0):
        self.budget = budget_usd
        self.spent = 0.0
        self.lock = threading.Lock()

    def add_cost(self, provider: str, model: str, input_tok: int, output_tok: int) -> float:
        pricing = config.PRICING.get(provider, {}).get(model)
        if not pricing:
            return 0.0
        cost = (input_tok * pricing[0] + output_tok * pricing[1]) / 1_000_000
        with self.lock:
            self.spent += cost
        return cost

    def can_spend(self, estimated_cost: float = 0.01) -> bool:
        return (self.spent + estimated_cost) < self.budget

    def should_fallback(self, provider: str, model: str) -> bool:
        """Check if a paid provider should fall back to a free one."""
        if provider not in config.PRICING:
            return False
        return not self.can_spend()

    def remaining(self) -> float:
        return max(0, self.budget - self.spent)

    def to_dict(self) -> dict:
        return {"budget": self.budget, "spent": round(self.spent, 4),
                "remaining": round(self.remaining(), 4)}


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

class Session:
    def __init__(self):
        self.state: GameState = None
        self.history: list = []
        self.client = None
        self.model = config.DEFAULT_MODEL
        self.provider = config.DEFAULT_PROVIDER
        self.audio_enabled = True
        self.tts_engine = "qwen3"
        self.tts_speed = 1.0
        self.music_enabled = True
        self.music_volume = 0.12
        self.music_source = "library"
        self.turn_counter = 0
        self.audio_results: dict = {}  # turn_id -> {done, audio_path, duration, error}
        self.budget = BudgetTracker(config.DEFAULT_BUDGET)
        self.started = False
        self.cast = None

    def init_client(self):
        if self.client is None or self.model != getattr(self, '_last_model', None):
            self.provider = detect_provider(self.model)
            self.client = make_client(self.provider)
            self._last_model = self.model

    def load_cast(self):
        if self.cast is None:
            try:
                with open(config.CAST_FILE) as f:
                    self.cast = json.load(f)
            except:
                self.cast = {}
        return self.cast


session = Session()


# ---------------------------------------------------------------------------
# Audio generation (background thread)
# ---------------------------------------------------------------------------

def generate_audio_async(segments: list, scene_mood: str, turn_id: str):
    """Generate audio in background thread."""
    result = {"done": False, "audio_path": None, "duration": 0, "error": None}
    session.audio_results[turn_id] = result

    def worker():
        try:
            from . import audio_engine
            cast = session.load_cast()
            audio_result = audio_engine.render_narration(
                segments=segments, scene_mood=scene_mood, turn_id=turn_id,
                cast=cast, tts_engine=session.tts_engine,
                speed=session.tts_speed, music_enabled=session.music_enabled,
                music_source=getattr(session, 'music_source', 'library'),
                music_volume=session.music_volume,
            )
            result["audio_path"] = audio_result["audio_path"]
            result["duration"] = audio_result["duration"]
            result["errors"] = audio_result.get("errors", [])
        except Exception as e:
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        finally:
            result["done"] = True

    t = threading.Thread(target=worker, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# HTML page — v9-inspired book-like GUI
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Narrator — D&D Story Engine</title>
<style>
  :root {
    --bg: #e6e4e0; --bg-soft: #dedcd8; --bg-panel: #d8d6d2;
    --ink: #1c1c1a; --ink-mid: #4a4a48; --ink-light: #8a8a86; --ink-faint: #b0b0ac;
    --rule: #c4c2be; --rule-soft: #d0ceca;
    --accent: #8b6914; --accent-soft: rgba(139,105,20,0.1);
    --hp-good: #4a7a4a; --hp-bad: #a04040; --hp-mid: #b8860b;
    --shadow: 0 2px 12px rgba(0,0,0,0.08);
    --col-left: 0px; --col-right: 0px;
    --topbar-h: 36px; --audio-h: 44px;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { height: 100%; overflow: hidden; }
  body { background: var(--bg); color: var(--ink); font-family: 'Iowan Old Style','Palatino','Book Antiqua',Georgia,serif; font-weight: 300; font-size: 17px; line-height: 1.85; -webkit-font-smoothing: antialiased; }
  .ui-font { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

  /* Layout grid */
  #app { display: grid; grid-template-columns: var(--col-left) 1fr var(--col-right); grid-template-rows: var(--topbar-h) 1fr var(--audio-h); height: 100vh; transition: grid-template-columns 0.3s ease, grid-template-rows 0.3s ease; }
  #app.show-left { --col-left: 260px; }
  #app.show-settings { --col-right: 340px; }
  #app.hide-topbar { --topbar-h: 0px; }
  #app.audio-collapsed { --audio-h: 20px; }

  /* Circle tabs on screen edges */
  .float-controls { position: fixed; top: var(--topbar-h); left: 0; right: 0; height: 0; z-index: 100; pointer-events: none; transition: top 0.3s ease; }
  .circle-tab { position: absolute; top: 8px; width: 28px; height: 28px; border-radius: 50%; background: var(--bg-soft); border: 1px solid var(--rule); color: var(--ink-light); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 12px; opacity: 0.45; transition: all 0.2s; pointer-events: auto; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
  .circle-tab:hover { opacity: 0.8; transform: scale(1.1); }
  .circle-tab.active { opacity: 0.7; border-color: var(--ink-mid); color: var(--ink-mid); }
  .circle-tab-left { left: -14px; border-radius: 0 50% 50% 0; border-left: none; padding-left: 4px; }
  .circle-tab-right { right: -14px; border-radius: 50% 0 0 50%; border-right: none; padding-right: 4px; }
  #app.show-left .circle-tab-left { left: var(--col-left); }
  #app.show-settings .circle-tab-right { right: var(--col-right); }
  .circle-tab-top { position: fixed; top: var(--topbar-h); left: 50%; transform: translateX(-50%); width: 28px; height: 14px; background: var(--bg-soft); border: 1px solid var(--rule); border-radius: 0 0 50% 50%; border-top: none; cursor: pointer; opacity: 0.4; transition: opacity 0.2s, top 0.3s; z-index: 101; pointer-events: auto; }
  .circle-tab-top:hover { opacity: 0.75; }

  /* Top bar */
  .topbar { grid-column: 1 / -1; grid-row: 1; background: var(--bg-soft); border-bottom: 1px solid var(--rule); padding: 0 1rem; display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: var(--ink-light); overflow: hidden; z-index: 50; }
  .topbar-center { display: flex; align-items: center; gap: 1rem; flex: 1; justify-content: center; }
  .topbar .stat { display: flex; align-items: center; gap: 4px; }
  .topbar .stat-label { color: var(--ink-faint); font-size: 10px; letter-spacing: 1px; text-transform: uppercase; }
  .topbar .stat-val { color: var(--ink-mid); font-weight: 500; }
  .topbar .hp-bar { width: 60px; height: 4px; background: var(--rule); border-radius: 2px; overflow: hidden; }
  .topbar .hp-fill { height: 100%; background: var(--hp-good); transition: width 0.5s, background 0.3s; }
  .topbar .sep { color: var(--rule); }
  .topbar-circle { width: 20px; height: 20px; border-radius: 50%; background: var(--bg); border: 1px solid var(--rule); color: var(--ink-light); cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 10px; opacity: 0.5; transition: all 0.2s; flex-shrink: 0; }
  .topbar-circle:hover { opacity: 0.85; }
  .topbar-circle.active { opacity: 0.7; border-color: var(--ink-mid); color: var(--ink-mid); }

  /* Left panel */
  .left-panel { grid-column: 1; grid-row: 2 / 3; background: var(--bg-soft); border-right: 1px solid var(--rule); overflow-y: auto; padding: 1rem; display: none; }
  #app.show-left .left-panel { display: block; }
  .panel-section { margin-bottom: 1.5rem; }
  .panel-h { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--ink-faint); margin-bottom: 0.6rem; padding-bottom: 0.4rem; border-bottom: 1px solid var(--rule); }
  .panel-item { font-size: 14px; color: var(--ink-mid); padding: 0.3rem 0; display: flex; justify-content: space-between; align-items: center; line-height: 1.4; }
  .panel-item .qty { color: var(--ink-light); font-size: 12px; }
  .enemy-item { display: flex; align-items: center; gap: 8px; padding: 0.4rem 0; font-size: 14px; color: var(--ink-mid); }
  .enemy-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
  .enemy-dot.alive { background: var(--hp-bad); }
  .enemy-dot.dead { background: var(--rule); }
  .enemy-item .enemy-status { font-size: 11px; color: var(--ink-faint); margin-left: auto; }
  .enemy-item.dead { text-decoration: line-through; opacity: 0.5; }

  /* Dice roller */
  .dice-roller { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
  .dice-btn { background: var(--bg); border: 1px solid var(--rule); color: var(--ink-mid); padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; font-family: monospace; transition: all 0.15s; }
  .dice-btn:hover { background: var(--accent-soft); border-color: var(--accent); }
  .dice-btn:active { transform: scale(0.95); }
  .dice-btn.rolling { animation: shake 0.3s ease-in-out; }
  @keyframes shake { 0%,100% { transform: translateX(0); } 25% { transform: translateX(-2px); } 75% { transform: translateX(2px); } }
  .dice-result { color: var(--accent); font-size: 14px; font-family: monospace; margin-top: 4px; min-height: 20px; }
  .dice-result .roll-val { font-size: 20px; font-weight: 500; }

  /* Settings panel (right) */
  .settings-panel { grid-column: 3; grid-row: 2 / 3; background: var(--bg-soft); border-left: 1px solid var(--rule); overflow-y: auto; padding: 1rem; display: none; }
  #app.show-settings .settings-panel { display: block; }
  .setting-group { margin-bottom: 1.2rem; }
  .setting-label { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--ink-faint); margin-bottom: 0.4rem; }
  .setting-row { display: flex; align-items: center; justify-content: space-between; padding: 0.3rem 0; font-size: 14px; color: var(--ink-mid); }
  .setting-row select, .setting-row input[type="range"] { font-family: sans-serif; font-size: 13px; }
  .setting-row select { background: var(--bg); border: 1px solid var(--rule); border-radius: 4px; padding: 4px 8px; color: var(--ink-mid); cursor: pointer; }
  .setting-row input[type="range"] { flex: 1; max-width: 150px; accent-color: var(--accent); }
  .setting-row .val { font-size: 12px; color: var(--ink-light); font-family: monospace; min-width: 40px; text-align: right; }
  .setting-toggle { width: 36px; height: 20px; background: var(--rule); border-radius: 10px; cursor: pointer; position: relative; transition: background 0.2s; }
  .setting-toggle.on { background: var(--accent); }
  .setting-toggle::after { content: ''; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; background: white; border-radius: 50%; transition: left 0.2s; }
  .setting-toggle.on::after { left: 18px; }
  .budget-bar { width: 100%; height: 6px; background: var(--rule); border-radius: 3px; overflow: hidden; margin-top: 4px; }
  .budget-fill { height: 100%; background: var(--hp-good); transition: width 0.3s, background 0.3s; }
  .budget-text { font-size: 11px; color: var(--ink-light); margin-top: 2px; font-family: monospace; }

  /* Main content area */
  .main-area { grid-column: 2; grid-row: 2; overflow-y: auto; padding: 2rem 3rem; scroll-behavior: smooth; }
  .story-content { max-width: 680px; margin: 0 auto; }
  .turn-mark { text-align: center; color: var(--ink-faint); font-size: 13px; letter-spacing: 4px; margin: 2rem 0 1.5rem; text-transform: uppercase; }
  .story-passage { margin-bottom: 1rem; }
  .speaker-label { font-size: 11px; color: var(--ink-faint); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px; }
  .narrator-text { color: var(--ink-mid); font-style: normal; }
  .dialogue-text { color: var(--ink); font-style: italic; }
  .player-action { color: var(--accent); font-size: 14px; margin: 1rem 0; padding: 0.5rem 1rem; background: var(--accent-soft); border-radius: 6px; border-left: 3px solid var(--accent); }
  .player-action::before { content: '→ '; }
  .state-changes { font-size: 12px; color: var(--ink-light); margin: 0.5rem 0; padding: 0.3rem 0.5rem; background: var(--bg-soft); border-radius: 4px; }
  .state-change { display: inline-block; margin-right: 8px; }
  .state-change.hp-down { color: var(--hp-bad); }
  .state-change.hp-up { color: var(--hp-good); }

  /* Choices */
  .choices-block { margin: 1.5rem 0 1rem; }
  .choices-label { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: var(--ink-faint); margin-bottom: 0.5rem; }
  .choice-item { display: flex; align-items: center; gap: 8px; padding: 0.6rem 1rem; background: var(--bg-soft); border: 1px solid var(--rule); border-radius: 6px; cursor: pointer; margin-bottom: 6px; transition: all 0.15s; font-size: 15px; color: var(--ink-mid); }
  .choice-item:hover { background: var(--accent-soft); border-color: var(--accent); color: var(--ink); }
  .choice-letter { font-size: 12px; color: var(--ink-faint); font-weight: 500; min-width: 20px; }
  .choice-roll { font-size: 11px; color: var(--accent); margin-left: auto; }

  /* Input area */
  .input-block { margin: 1.5rem 0 2rem; display: flex; gap: 8px; align-items: center; }
  .input-block input { flex: 1; background: var(--bg-soft); border: 1px solid var(--rule); color: var(--ink); padding: 12px 16px; border-radius: 8px; font-size: 16px; font-family: inherit; outline: none; transition: border-color 0.2s; }
  .input-block input:focus { border-color: var(--accent); }
  .input-block button { background: var(--accent); color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 15px; font-family: inherit; transition: opacity 0.2s; }
  .input-block button:hover { opacity: 0.85; }
  .input-block button:disabled { opacity: 0.4; cursor: not-allowed; }

  /* Typing indicator */
  .typing-indicator { text-align: center; color: var(--ink-faint); padding: 1rem; font-style: italic; }
  .typing-dots { display: inline-flex; gap: 4px; }
  .typing-dot { width: 6px; height: 6px; background: var(--ink-faint); border-radius: 50%; animation: pulse 1.4s infinite; }
  .typing-dot:nth-child(2) { animation-delay: 0.2s; }
  .typing-dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes pulse { 0%,80%,100% { opacity: 0.3; } 40% { opacity: 1; } }

  /* Audio bar */
  .audio-bar { grid-column: 1 / -1; grid-row: 3; background: var(--bg-soft); border-top: 1px solid var(--rule); display: flex; align-items: center; gap: 10px; padding: 0 1rem; font-size: 12px; color: var(--ink-light); overflow: hidden; }
  .audio-play-btn { width: 32px; height: 32px; border-radius: 50%; background: var(--accent); color: white; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; transition: opacity 0.2s; }
  .audio-play-btn:hover { opacity: 0.85; }
  .audio-play-btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .audio-progress { flex: 1; height: 4px; background: var(--rule); border-radius: 2px; overflow: hidden; cursor: pointer; position: relative; }
  .audio-progress-fill { height: 100%; background: var(--accent); width: 0%; transition: width 0.1s linear; }
  .audio-label { color: var(--ink-mid); font-size: 12px; white-space: nowrap; min-width: 120px; }
  .audio-time { color: var(--ink-faint); font-size: 11px; font-family: monospace; min-width: 80px; text-align: right; }
  .audio-status { color: var(--ink-faint); font-size: 11px; font-style: italic; }
  .audio-gen-bar { position: absolute; top: -3px; left: 0; right: 0; height: 2px; background: var(--rule-soft); overflow: hidden; }
  .audio-gen-fill { height: 100%; background: var(--accent); width: 0%; transition: width 0.3s; animation: genPulse 1.5s ease-in-out infinite; }
  @keyframes genPulse { 0%,100% { opacity: 0.4; } 50% { opacity: 1; } }
  #app.audio-collapsed .audio-bar { padding: 0 0.5rem; }
  #app.audio-collapsed .audio-label, #app.audio-collapsed .audio-time, #app.audio-collapsed .audio-status { display: none; }
  #app.audio-collapsed .audio-progress { height: 2px; }

  /* Intro screen */
  #intro-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: var(--bg); z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 2rem; }
  #intro-overlay.hidden { display: none; }
  .intro-card { max-width: 600px; background: var(--bg-soft); border: 1px solid var(--rule); border-radius: 12px; padding: 2.5rem; box-shadow: var(--shadow); }
  .intro-card h1 { font-size: 28px; color: var(--ink); margin-bottom: 0.5rem; text-align: center; font-weight: 400; }
  .intro-card .subtitle { text-align: center; color: var(--ink-light); font-size: 15px; margin-bottom: 2rem; font-style: italic; }
  .intro-field { margin-bottom: 1.2rem; }
  .intro-field label { display: block; font-size: 11px; letter-spacing: 1px; text-transform: uppercase; color: var(--ink-faint); margin-bottom: 4px; }
  .intro-field input, .intro-field select, .intro-field textarea { width: 100%; background: var(--bg); border: 1px solid var(--rule); border-radius: 6px; padding: 10px 12px; color: var(--ink); font-size: 15px; font-family: inherit; outline: none; }
  .intro-field input:focus, .intro-field select:focus, .intro-field textarea:focus { border-color: var(--accent); }
  .intro-field textarea { resize: vertical; min-height: 60px; }
  .intro-start { width: 100%; background: var(--accent); color: white; border: none; padding: 14px; border-radius: 8px; cursor: pointer; font-size: 17px; font-family: inherit; margin-top: 1rem; transition: opacity 0.2s; }
  .intro-start:hover { opacity: 0.85; }
  .intro-skip { width: 100%; background: none; border: none; color: var(--ink-faint); cursor: pointer; font-size: 13px; margin-top: 0.5rem; }
  .intro-skip:hover { color: var(--ink-mid); }

  /* Fallback indicator */
  .fallback-indicator { display: inline-flex; align-items: center; gap: 4px; font-size: 10px; color: var(--hp-mid); background: rgba(184,134,11,0.1); padding: 2px 6px; border-radius: 4px; margin-left: 8px; }
</style>
</head>
<body>

<!-- Intro screen -->
<div id="intro-overlay">
  <div class="intro-card">
    <h1>Narrator</h1>
    <div class="subtitle">A D&D story engine that reads to you</div>
    <div class="intro-field">
      <label>Story Style</label>
      <select id="intro-style">
        <option value="classic fantasy">Classic Fantasy</option>
        <option value="dark fantasy">Dark Fantasy</option>
        <option value="grimdark">Grimdark</option>
        <option value="high fantasy">High Fantasy</option>
        <option value="sword and sorcery">Sword & Sorcery</option>
        <option value="gothic horror">Gothic Horror</option>
        <option value="mystery investigation">Mystery & Investigation</option>
      </select>
    </div>
    <div class="intro-field">
      <label>Setting</label>
      <input type="text" id="intro-setting" placeholder="e.g. A remote mountain village beset by strange happenings">
    </div>
    <div class="intro-field">
      <label>Your Character's Name</label>
      <input type="text" id="intro-name" placeholder="e.g. Kael" value="Kael">
    </div>
    <div class="intro-field">
      <label>Character Persona</label>
      <input type="text" id="intro-persona" placeholder="e.g. A grizzled veteran seeking redemption">
    </div>
    <div class="intro-field">
      <label>Atmosphere</label>
      <select id="intro-atmosphere">
        <option value="adventurous">Adventurous</option>
        <option value="mysterious">Mysterious</option>
        <option value="tense">Tense</option>
        <option value="melancholic">Melancholic</option>
        <option value="whimsical">Whimsical</option>
      </select>
    </div>
    <div class="intro-field">
      <label>Inspired by (books, movies, games)</label>
      <input type="text" id="intro-inspiration" placeholder="e.g. Lord of the Rings, The Witcher, D&D">
    </div>
    <div class="intro-field">
      <label>Dice Mode</label>
      <select id="intro-dicemode">
        <option value="auto">Automatic — the app rolls for me</option>
        <option value="manual">Manual — I roll my own dice</option>
      </select>
    </div>
    <button class="intro-start" onclick="startGame()">Begin Your Story</button>
    <button class="intro-skip" onclick="startGame({skip:true})">Skip — use defaults</button>
  </div>
</div>

<!-- Main app -->
<div id="app">

  <!-- Top bar -->
  <div class="topbar ui-font">
    <div class="topbar-circle" id="tab-left" onclick="togglePanel('left')" title="Character panel">☰</div>
    <div class="topbar-center">
      <div class="stat"><span class="stat-label">HP</span><span class="stat-val" id="tb-hp">12/12</span><div class="hp-bar"><div class="hp-fill" id="tb-hpfill"></div></div></div>
      <span class="sep">|</span>
      <div class="stat"><span class="stat-label">AC</span><span class="stat-val" id="tb-ac">16</span></div>
      <span class="sep">|</span>
      <div class="stat"><span class="stat-label">Turn</span><span class="stat-val" id="tb-turn">0</span></div>
      <span class="sep">|</span>
      <div class="stat"><span class="stat-label">Location</span><span class="stat-val" id="tb-loc">—</span></div>
    </div>
    <div style="display:flex;gap:6px;align-items:center;">
      <span id="model-label" class="stat-val" style="font-size:11px;">Loading...</span>
      <div class="topbar-circle" id="tab-settings" onclick="togglePanel('settings')" title="Settings">⚙</div>
    </div>
  </div>

  <!-- Circle tabs for panels -->
  <div class="float-controls">
    <div class="circle-tab circle-tab-left" id="ctab-left" onclick="togglePanel('left')">☰</div>
    <div class="circle-tab circle-tab-right" id="ctab-settings" onclick="togglePanel('settings')">⚙</div>
  </div>
  <div class="circle-tab-top" onclick="toggleBar()" title="Toggle top bar"></div>

  <!-- Left panel: character info -->
  <div class="left-panel ui-font">
    <div class="panel-section">
      <div class="panel-h">Character</div>
      <div id="char-info"></div>
    </div>
    <div class="panel-section">
      <div class="panel-h">Enemies</div>
      <div id="enemy-list"></div>
    </div>
    <div class="panel-section">
      <div class="panel-h">Inventory</div>
      <div id="inv-list"></div>
    </div>
    <div class="panel-section">
      <div class="panel-h">Dice Roller</div>
      <div class="dice-roller">
        <button class="dice-btn" onclick="rollDice(this,20)">d20</button>
        <button class="dice-btn" onclick="rollDice(this,12)">d12</button>
        <button class="dice-btn" onclick="rollDice(this,10)">d10</button>
        <button class="dice-btn" onclick="rollDice(this,8)">d8</button>
        <button class="dice-btn" onclick="rollDice(this,6)">d6</button>
        <button class="dice-btn" onclick="rollDice(this,4)">d4</button>
        <button class="dice-btn" onclick="rollDice(this,100)">d100</button>
      </div>
      <div class="dice-result" id="dice-result"></div>
    </div>
  </div>

  <!-- Main story area -->
  <div class="main-area" id="main-area">
    <div class="story-content" id="story-content">
      <!-- Story content appears here -->
    </div>
  </div>

  <!-- Settings panel (right) -->
  <div class="settings-panel ui-font">
    <div class="setting-group">
      <div class="panel-h">Story AI</div>
      <div class="setting-row">
        <span>Model</span>
        <select id="set-model" onchange="changeModel(this.value)">
          <optgroup label="Google Gemini (free)">
            <option value="gemini-3.5-flash-lite">Gemini Flash-Lite</option>
            <option value="gemini-3.5-flash">Gemini Flash</option>
          </optgroup>
          <optgroup label="Groq (free, fast)">
            <option value="openai/gpt-oss-120b">GPT-OSS 120B</option>
            <option value="groq/compound-mini">Compound Mini</option>
          </optgroup>
        </select>
      </div>
      <div class="setting-row">
        <span>Auto-roll dice</span>
        <div class="setting-toggle on" id="set-autoroll" onclick="toggleSetting('autoroll',this)"></div>
      </div>
    </div>

    <div class="setting-group">
      <div class="panel-h">Voice & TTS</div>
      <div class="setting-row">
        <span>TTS Engine</span>
        <select id="set-tts" onchange="changeTTS(this.value)">
          <option value="qwen3">Qwen3 VoiceDesign</option>
          <option value="silent">Silent (text only)</option>
        </select>
      </div>
      <div class="setting-row">
        <span>Speed</span>
        <input type="range" min="0.5" max="2" step="0.1" value="1" oninput="changeSpeed(this.value)">
        <span class="val" id="speed-val">1.0x</span>
      </div>
    </div>

    <div class="setting-group">
      <div class="panel-h">Music</div>
      <div class="setting-row">
        <span>Background music</span>
        <div class="setting-toggle on" id="set-music" onclick="toggleSetting('music',this)"></div>
      </div>
      <div class="setting-row">
        <span>Music source</span>
        <select id="set-musicsrc" onchange="changeMusicSrc(this.value)">
          <option value="library">Library (curated tracks)</option>
          <option value="procedural">Procedural (synthesized)</option>
        </select>
      </div>
      <div class="setting-row">
        <span>Music volume</span>
        <input type="range" min="0" max="0.3" step="0.01" value="0.12" oninput="changeMusicVol(this.value)">
        <span class="val" id="musicvol-val">12%</span>
      </div>
    </div>

    <div class="setting-group">
      <div class="panel-h">Budget (paid APIs)</div>
      <div class="setting-row">
        <span>Spent</span>
        <span class="val" id="budget-spent">$0.00</span>
      </div>
      <div class="budget-bar"><div class="budget-fill" id="budget-fill" style="width:0%"></div></div>
      <div class="budget-text" id="budget-text">$0.00 / $5.00</div>
    </div>

    <div class="setting-group">
      <div class="panel-h">Session</div>
      <div class="setting-row">
        <button onclick="newGame()" style="background:var(--bg);border:1px solid var(--rule);color:var(--ink-mid);padding:6px 12px;border-radius:4px;cursor:pointer;font-size:13px;">New Story</button>
      </div>
    </div>

    <div class="setting-group">
      <div class="panel-h">Theme</div>
      <div class="setting-row">
        <span>Appearance</span>
        <select id="set-theme" onchange="setTheme(this.value)">
          <option value="light">Light (paper)</option>
          <option value="dark">Dark (ink)</option>
          <option value="sepia">Sepia</option>
        </select>
      </div>
    </div>
  </div>

  <!-- Audio bar -->
  <div class="audio-bar ui-font">
    <button class="audio-play-btn" id="audio-play" onclick="toggleAudio()" disabled>▶</button>
    <div class="audio-progress" id="audio-progress" onclick="seekAudio(event)">
      <div class="audio-gen-bar" id="audio-gen-bar" style="display:none;"><div class="audio-gen-fill" id="audio-gen-fill"></div></div>
      <div class="audio-progress-fill" id="audio-fill"></div>
    </div>
    <span class="audio-label" id="audio-label">No audio</span>
    <span class="audio-time" id="audio-time">0:00 / 0:00</span>
    <span class="audio-status" id="audio-status"></span>
  </div>
</div>

<!-- Hidden audio elements -->
<audio id="audio-player" preload="auto"></audio>
<audio id="bg-music-player" preload="auto" loop></audio>

<script>
// State
let history = [];
let turnCount = 0;
let currentAudio = null;
let audioPollTimer = null;
let isPlaying = false;
let audioDuration = 0;
let audioPosition = 0;
let audioUpdateTimer = null;
let settings = { autoroll: true, music: true, tts: 'qwen3', speed: 1.0, musicVol: 0.12, musicSrc: 'library', model: 'gemini-3.5-flash-lite' };
let currentMood = 'exploration';
let bgMusicPlaying = false;

// Panel toggling
function togglePanel(name) {
  const app = document.getElementById('app');
  if (name === 'left') {
    app.classList.toggle('show-left');
    document.getElementById('tab-left').classList.toggle('active');
    document.getElementById('ctab-left').classList.toggle('active');
  } else if (name === 'settings') {
    app.classList.toggle('show-settings');
    document.getElementById('tab-settings').classList.toggle('active');
    document.getElementById('ctab-settings').classList.toggle('active');
  }
}
function toggleBar() {
  document.getElementById('app').classList.toggle('hide-topbar');
}

// Settings
function toggleSetting(name, el) {
  el.classList.toggle('on');
  settings[name] = el.classList.contains('on');
  if (name === 'music') { updateBgMusic(); }
}
function changeModel(val) { settings.model = val; }
function changeTTS(val) { settings.tts = val; }
function changeSpeed(val) { settings.speed = parseFloat(val); document.getElementById('speed-val').textContent = val + 'x'; }
function changeMusicVol(val) { settings.musicVol = parseFloat(val); document.getElementById('musicvol-val').textContent = Math.round(val*100) + '%'; }
function changeMusicSrc(val) { settings.musicSrc = val; updateBgMusic(); }

function updateBgMusic() {
  const player = document.getElementById('bg-music-player');
  if (!settings.music) {
    player.pause();
    bgMusicPlaying = false;
    return;
  }
  const url = `/api/music?mood=${currentMood}&source=${settings.musicSrc}`;
  if (player.src.indexOf(url) === -1) {
    player.src = url;
    player.volume = settings.musicVol * 2; // bg music is quieter than narration
    if (bgMusicPlaying) player.play().catch(()=>{});
  } else {
    player.volume = settings.musicVol * 2;
  }
}

function setMood(mood) {
  if (mood && mood !== currentMood) {
    currentMood = mood;
    updateBgMusic();
  }
}

function setTheme(theme) {
  const root = document.documentElement;
  if (theme === 'dark') {
    root.style.setProperty('--bg', '#1a1a1e');
    root.style.setProperty('--bg-soft', '#22222a');
    root.style.setProperty('--bg-panel', '#26262e');
    root.style.setProperty('--ink', '#d8d6d2');
    root.style.setProperty('--ink-mid', '#a8a6a2');
    root.style.setProperty('--ink-light', '#78767a');
    root.style.setProperty('--ink-faint', '#504e52');
    root.style.setProperty('--rule', '#38383e');
    root.style.setProperty('--rule-soft', '#2e2e34');
    root.style.setProperty('--accent', '#c8a040');
    root.style.setProperty('--accent-soft', 'rgba(200,160,64,0.15)');
    root.style.setProperty('--hp-good', '#5a9a5a');
    root.style.setProperty('--hp-bad', '#c05050');
    root.style.setProperty('--hp-mid', '#d8a830');
  } else if (theme === 'sepia') {
    root.style.setProperty('--bg', '#f0e6d2');
    root.style.setProperty('--bg-soft', '#e8dcc4');
    root.style.setProperty('--bg-panel', '#e2d6be');
    root.style.setProperty('--ink', '#3a2e1e');
    root.style.setProperty('--ink-mid', '#5a4e3e');
    root.style.setProperty('--ink-light', '#8a7e6e');
    root.style.setProperty('--ink-faint', '#b0a490');
    root.style.setProperty('--rule', '#d0c4a8');
    root.style.setProperty('--rule-soft', '#d8ccb0');
    root.style.setProperty('--accent', '#8b6914');
    root.style.setProperty('--accent-soft', 'rgba(139,105,20,0.12)');
    root.style.setProperty('--hp-good', '#4a7a4a');
    root.style.setProperty('--hp-bad', '#a04040');
    root.style.setProperty('--hp-mid', '#b8860b');
  } else {
    // Light (default)
    root.style.setProperty('--bg', '#e6e4e0');
    root.style.setProperty('--bg-soft', '#dedcd8');
    root.style.setProperty('--bg-panel', '#d8d6d2');
    root.style.setProperty('--ink', '#1c1c1a');
    root.style.setProperty('--ink-mid', '#4a4a48');
    root.style.setProperty('--ink-light', '#8a8a86');
    root.style.setProperty('--ink-faint', '#b0b0ac');
    root.style.setProperty('--rule', '#c4c2be');
    root.style.setProperty('--rule-soft', '#d0ceca');
    root.style.setProperty('--accent', '#8b6914');
    root.style.setProperty('--accent-soft', 'rgba(139,105,20,0.1)');
    root.style.setProperty('--hp-good', '#4a7a4a');
    root.style.setProperty('--hp-bad', '#a04040');
    root.style.setProperty('--hp-mid', '#b8860b');
  }
}

// Dice roller
function rollDice(btn, sides) {
  btn.classList.add('rolling');
  setTimeout(() => btn.classList.remove('rolling'), 300);
  const result = Math.floor(Math.random() * sides) + 1;
  const el = document.getElementById('dice-result');
  el.innerHTML = `<span class="roll-val">${result}</span> <span style="color:var(--ink-faint)">on d${sides}</span>`;
  // Add to input
  const input = document.querySelector('.input-block input');
  if (input) input.value += ` I rolled a ${result} on d${sides}.`;
}

// Start game from intro
async function startGame(opts = {}) {
  const overlay = document.getElementById('intro-overlay');
  const params = opts.skip ? {} : {
    style: document.getElementById('intro-style').value,
    setting: document.getElementById('intro-setting').value,
    name: document.getElementById('intro-name').value || 'Kael',
    persona: document.getElementById('intro-persona').value,
    atmosphere: document.getElementById('intro-atmosphere').value,
    inspiration: document.getElementById('intro-inspiration').value,
    dicemode: document.getElementById('intro-dicemode').value,
  };
  overlay.classList.add('hidden');
  // Show left panel by default
  document.getElementById('app').classList.add('show-left');
  document.getElementById('tab-left').classList.add('active');
  document.getElementById('ctab-left').classList.add('active');
  await newGame(params);
  // Start background music after game starts
  if (settings.music) {
    bgMusicPlaying = true;
    updateBgMusic();
    document.getElementById('bg-music-player').play().catch(()=>{});
  }
}

// New game
async function newGame(params = {}) {
  history = [];
  turnCount = 0;
  document.getElementById('story-content').innerHTML = '';
  const typing = showTyping();
  try {
    const resp = await fetch('/api/newgame', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(params),
    });
    const data = await resp.json();
    typing.remove();
    if (data.error) { addError(data.error); return; }
    document.getElementById('model-label').textContent = data.model;
    settings.autoroll = data.auto_roll;
    updateSettingsUI();
    updateState(data.state);
    if (data.story) addStoryTurn(data, true);
    if (data.audio_enabled) pollAudio(data.audio_turn_id);
    updateBudget(data.budget);
  } catch(e) { typing.remove(); addError('Connection error: ' + e.message); }
}

// Send action
async function sendAction() {
  const input = document.querySelector('.input-block input');
  if (!input) return;
  const action = input.value.trim();
  if (!action) return;
  input.value = '';
  const btn = document.querySelector('.input-block button');
  if (btn) btn.disabled = true;

  addPlayerAction(action);
  const typing = showTyping();

  try {
    const resp = await fetch('/api/turn', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ action, settings: { autoroll: settings.autoroll, music: settings.music, tts: settings.tts, speed: settings.speed, musicVol: settings.musicVol, musicSrc: settings.musicSrc, model: settings.model } }),
    });
    const data = await resp.json();
    typing.remove();
    if (data.error) { addError(data.error); }
    else {
      updateState(data.state);
      addStoryTurn(data);
      if (data.audio_enabled && data.audio_turn_id) pollAudio(data.audio_turn_id);
      updateBudget(data.budget);
      if (data.fallback_used) {
        showFallbackWarning(data.original_model, data.model);
      }
    }
  } catch(e) { typing.remove(); addError('Connection error: ' + e.message); }
  if (btn) btn.disabled = false;
  if (input) input.focus();
}

// Add story turn to display
function addStoryTurn(data, isFirst = false) {
  turnCount = data.turn || turnCount + 1;
  const container = document.getElementById('story-content');

  // Update background music mood
  if (data.scene) setMood(data.scene);

  // Turn mark
  const mark = document.createElement('div');
  mark.className = 'turn-mark';
  mark.textContent = toRoman(turnCount);
  container.appendChild(mark);

  // Story segments (word-for-word = what's spoken)
  if (data.segments && data.segments.length) {
    for (const seg of data.segments) {
      const passage = document.createElement('div');
      passage.className = 'story-passage';
      if (seg.kind === 'narrator') {
        passage.innerHTML = `<div class="narrator-text">${escapeHtml(seg.text)}</div>`;
      } else {
        passage.innerHTML = `<div class="speaker-label">${escapeHtml(seg.speaker)}</div><div class="dialogue-text">"${escapeHtml(seg.text)}"</div>`;
      }
      container.appendChild(passage);
    }
  } else if (data.response) {
    // Fallback: show raw response
    const passage = document.createElement('div');
    passage.className = 'story-passage';
    passage.innerHTML = `<div class="narrator-text">${escapeHtml(data.response)}</div>`;
    container.appendChild(passage);
  }

  // State changes
  if (data.changes && data.changes.length) {
    const changes = document.createElement('div');
    changes.className = 'state-changes';
    changes.innerHTML = data.changes.map(c => {
      const cls = c.includes('→') && c.includes('-') ? 'hp-down' : c.includes('→') && c.includes('+') ? 'hp-up' : '';
      return `<span class="state-change ${cls}">${escapeHtml(c)}</span>`;
    }).join('');
    container.appendChild(changes);
  }

  // Choices
  if (data.suggestions && data.suggestions.length) {
    const choices = document.createElement('div');
    choices.className = 'choices-block';
    choices.innerHTML = '<div class="choices-label">What do you do?</div>';
    data.suggestions.forEach((s, i) => {
      const letter = String.fromCharCode(65 + i);
      const item = document.createElement('div');
      item.className = 'choice-item';
      item.innerHTML = `<span class="choice-letter">${letter}.</span><span>${escapeHtml(s.text)}</span>${s.roll ? '<span class="choice-roll">🎲 roll</span>' : ''}`;
      item.onclick = () => useChoice(s.text);
      choices.appendChild(item);
    });
    container.appendChild(choices);
  }

  // Input area
  if (!isFirst) {
    // Remove old input areas
    document.querySelectorAll('.input-block').forEach(el => el.remove());
  }
  const inputArea = document.createElement('div');
  inputArea.className = 'input-block';
  inputArea.innerHTML = `<input type="text" placeholder="What do you do?" onkeypress="if(event.key==='Enter')sendAction()" autofocus><button onclick="sendAction()">Send</button>`;
  container.appendChild(inputArea);

  // Scroll to bottom
  document.getElementById('main-area').scrollTop = document.getElementById('main-area').scrollHeight;
  if (inputArea.querySelector('input')) inputArea.querySelector('input').focus();
}

function useChoice(text) {
  const input = document.querySelector('.input-block input');
  if (input) { input.value = text; input.focus(); }
}

function addPlayerAction(text) {
  const container = document.getElementById('story-content');
  const el = document.createElement('div');
  el.className = 'player-action';
  el.textContent = text;
  container.appendChild(el);
  document.getElementById('main-area').scrollTop = document.getElementById('main-area').scrollHeight;
}

function showTyping() {
  const container = document.getElementById('story-content');
  const el = document.createElement('div');
  el.className = 'typing-indicator';
  el.innerHTML = 'The DM is weaving the story <span class="typing-dots"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></span>';
  container.appendChild(el);
  document.getElementById('main-area').scrollTop = document.getElementById('main-area').scrollHeight;
  return el;
}

function addError(msg) {
  const container = document.getElementById('story-content');
  const el = document.createElement('div');
  el.className = 'story-passage';
  el.style.color = 'var(--hp-bad)';
  el.textContent = '⚠ ' + msg;
  container.appendChild(el);
}

function showFallbackWarning(originalModel, fallbackModel) {
  const container = document.getElementById('story-content');
  const el = document.createElement('div');
  el.className = 'story-passage';
  el.style.color = 'var(--hp-mid)';
  el.style.fontSize = '13px';
  el.style.padding = '0.5rem 1rem';
  el.style.background = 'rgba(184,134,11,0.1)';
  el.style.borderRadius = '6px';
  el.innerHTML = `⚠ Budget limit reached — switched from <b>${escapeHtml(originalModel)}</b> to free model <b>${escapeHtml(fallbackModel)}</b>`;
  container.appendChild(el);
  document.getElementById('main-area').scrollTop = document.getElementById('main-area').scrollHeight;
}

// Update state display
function updateState(state) {
  if (!state) return;
  const hpPct = (state.pc_hp / state.pc_max_hp) * 100;
  const hpColor = hpPct > 60 ? 'var(--hp-good)' : hpPct > 30 ? 'var(--hp-mid)' : 'var(--hp-bad)';

  // Top bar
  document.getElementById('tb-hp').textContent = `${state.pc_hp}/${state.pc_max_hp}`;
  document.getElementById('tb-hpfill').style.width = hpPct + '%';
  document.getElementById('tb-hpfill').style.background = hpColor;
  document.getElementById('tb-ac').textContent = state.pc_ac;
  document.getElementById('tb-turn').textContent = turnCount;
  document.getElementById('tb-loc').textContent = state.location || '—';

  // Left panel
  document.getElementById('char-info').innerHTML = `
    <div class="panel-item"><span>Name</span><span>${escapeHtml(state.pc_name)}</span></div>
    <div class="panel-item"><span>Class</span><span>Level ${state.pc_level} ${escapeHtml(state.pc_class)}</span></div>
    <div class="panel-item"><span>HP</span><span>${state.pc_hp}/${state.pc_max_hp}</span></div>
    <div class="panel-item"><span>AC</span><span>${state.pc_ac}</span></div>
    <div class="panel-item"><span>STR</span><span>${state.pc_str}</span></div>
    <div class="panel-item"><span>DEX</span><span>${state.pc_dex}</span></div>
    <div class="panel-item"><span>CON</span><span>${state.pc_con}</span></div>`;

  document.getElementById('enemy-list').innerHTML = state.enemies.map(e =>
    `<div class="enemy-item ${e.alive ? '' : 'dead'}"><div class="enemy-dot ${e.alive ? 'alive' : 'dead'}"></div><span>${escapeHtml(e.name)}</span><span class="enemy-status">${e.hp}/${e.max_hp} HP, AC ${e.ac}</span></div>`
  ).join('') || '<div class="panel-item" style="color:var(--ink-faint)">None</div>';

  document.getElementById('inv-list').innerHTML = state.inventory.map(i =>
    `<div class="panel-item"><span>${escapeHtml(i)}</span></div>`
  ).join('') || '<div class="panel-item" style="color:var(--ink-faint)">Empty</div>';
}

function updateSettingsUI() {
  const ar = document.getElementById('set-autoroll');
  if (settings.autoroll) ar.classList.add('on'); else ar.classList.remove('on');
  document.getElementById('set-model').value = settings.model;
  document.getElementById('set-tts').value = settings.tts;
}

function updateBudget(budget) {
  if (!budget) return;
  const pct = (budget.spent / budget.budget) * 100;
  document.getElementById('budget-spent').textContent = '$' + budget.spent.toFixed(2);
  document.getElementById('budget-fill').style.width = Math.min(pct, 100) + '%';
  document.getElementById('budget-fill').style.background = pct > 80 ? 'var(--hp-bad)' : pct > 50 ? 'var(--hp-mid)' : 'var(--hp-good)';
  document.getElementById('budget-text').textContent = `$${budget.spent.toFixed(2)} / $${budget.budget.toFixed(2)}`;
}

// Audio playback
function pollAudio(turnId) {
  if (!turnId) return;
  // Show generating indicator
  document.getElementById('audio-gen-bar').style.display = 'block';
  document.getElementById('audio-gen-fill').style.width = '30%';
  document.getElementById('audio-status').textContent = 'generating...';
  document.getElementById('audio-label').textContent = 'Generating audio';

  if (audioPollTimer) clearInterval(audioPollTimer);
  let pollCount = 0;
  audioPollTimer = setInterval(async () => {
    pollCount++;
    if (pollCount > 180) { // 3 min timeout
      clearInterval(audioPollTimer);
      document.getElementById('audio-status').textContent = 'timeout';
      document.getElementById('audio-gen-bar').style.display = 'none';
      return;
    }
    try {
      const resp = await fetch(`/api/audio_status?turn_id=${turnId}`);
      const data = await resp.json();
      if (data.status === 'ready') {
        clearInterval(audioPollTimer);
        document.getElementById('audio-gen-bar').style.display = 'none';
        loadAudio(data.audio_url, data.duration);
      } else if (data.status === 'error') {
        clearInterval(audioPollTimer);
        document.getElementById('audio-gen-bar').style.display = 'none';
        document.getElementById('audio-status').textContent = 'error: ' + (data.error || 'unknown');
      } else if (data.status === 'generating') {
        // Update progress bar (fake progress)
        const pct = Math.min(30 + pollCount * 2, 90);
        document.getElementById('audio-gen-fill').style.width = pct + '%';
      }
    } catch(e) {}
  }, 1000);
}

function loadAudio(url, duration) {
  const player = document.getElementById('audio-player');
  player.src = url;
  audioDuration = duration;
  document.getElementById('audio-play').disabled = false;
  document.getElementById('audio-label').textContent = `Narrator · turn ${toRoman(turnCount)}`;
  document.getElementById('audio-time').textContent = `0:00 / ${formatTime(duration)}`;
  document.getElementById('audio-status').textContent = '';
  // Auto-play
  player.play().then(() => { isPlaying = true; document.getElementById('audio-play').textContent = '⏸'; startAudioUpdate(); }).catch(() => {});
}

function toggleAudio() {
  const player = document.getElementById('audio-player');
  if (player.paused) {
    player.play().then(() => { isPlaying = true; document.getElementById('audio-play').textContent = '⏸'; startAudioUpdate(); }).catch(()=>{});
  } else {
    player.pause(); isPlaying = false; document.getElementById('audio-play').textContent = '▶'; stopAudioUpdate();
  }
}

function startAudioUpdate() {
  if (audioUpdateTimer) clearInterval(audioUpdateTimer);
  audioUpdateTimer = setInterval(() => {
    const player = document.getElementById('audio-player');
    if (player.duration) {
      const pct = (player.currentTime / player.duration) * 100;
      document.getElementById('audio-fill').style.width = pct + '%';
      document.getElementById('audio-time').textContent = `${formatTime(player.currentTime)} / ${formatTime(player.duration)}`;
    }
    if (player.ended) { isPlaying = false; document.getElementById('audio-play').textContent = '▶'; stopAudioUpdate(); }
  }, 200);
}
function stopAudioUpdate() { if (audioUpdateTimer) { clearInterval(audioUpdateTimer); audioUpdateTimer = null; } }

function seekAudio(e) {
  const player = document.getElementById('audio-player');
  if (!player.duration) return;
  const bar = e.currentTarget;
  const pct = (e.clientX - bar.getBoundingClientRect().left) / bar.offsetWidth;
  player.currentTime = pct * player.duration;
}

// Utilities
function escapeHtml(s) { if(!s) return ''; const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function formatTime(s) { if(!s) return '0:00'; const m=Math.floor(s/60); const sec=Math.floor(s%60); return `${m}:${sec.toString().padStart(2,'0')}`; }
function toRoman(n) { const r=['','I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV','XV','XVI','XVII','XVIII','XIX','XX']; return r[n] || n.toString(); }

// Keyboard shortcut: Enter to send
document.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && document.activeElement.tagName === 'INPUT' && document.activeElement.closest('.input-block')) {
    sendAction();
  }
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class NarratorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logging

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())

        elif parsed.path.startswith("/audio/"):
            turn_id = parsed.path.replace("/audio/", "").replace(".wav", "")
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
            params = parse_qs(parsed.query)
            turn_id = params.get("turn_id", [""])[0]
            result = session.audio_results.get(turn_id)
            if result is None:
                self._json({"status": "unknown"})
            elif not result.get("done"):
                self._json({"status": "generating"})
            elif result.get("error"):
                self._json({"status": "error", "error": result["error"]})
            elif result.get("audio_path"):
                self._json({
                    "status": "ready",
                    "audio_url": f"/audio/{turn_id}.wav",
                    "duration": result.get("duration", 0),
                })
            else:
                self._json({"status": "no_audio"})

        elif parsed.path == "/api/state":
            if session.state:
                self._json({"state": session.state.to_dict()})
            else:
                self._json({"error": "no game"})

        elif parsed.path == "/api/music":
            # Serve continuous background music
            self._serve_music(parsed)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len).decode() if content_len else "{}"
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        if parsed.path == "/api/newgame":
            self._handle_newgame(data)
        elif parsed.path == "/api/turn":
            self._handle_turn(data)
        else:
            self.send_response(404)
            self.end_headers()

    def _handle_newgame(self, data):
        try:
            # Apply settings from intro
            story_style = data.get("style", "")
            setting = data.get("setting", "")
            name = data.get("name", "Kael")
            persona = data.get("persona", "")
            atmosphere = data.get("atmosphere", "")
            inspiration = data.get("inspiration", "")
            auto_roll = data.get("dicemode", "auto") == "auto"

            session.state = make_initial_state(
                story_style=story_style, setting=setting, persona=persona,
                atmosphere=atmosphere, inspiration=inspiration, auto_roll=auto_roll,
            )
            if name:
                session.state.pc_name = name
            session.history = []
            session.turn_counter = 0
            session.model = data.get("model", session.model)
            session.init_client()

            # Generate opening narration
            state_block = session.state.to_prompt_block()
            opening = f"Start the story. The player character ({session.state.pc_name}) enters the scene for the first time. Set the scene, introduce the atmosphere, and present the initial situation."

            text, elapsed, usage = dm_turn(
                session.client, session.model, SYSTEM_PROMPT,
                state_block, [], opening,
            )
            print(f"[server] DM response: {len(text)} chars in {elapsed:.1f}s")

            # Track cost
            cost = session.budget.add_cost(session.provider, session.model,
                                           usage["prompt_tokens"], usage["completion_tokens"])

            sections = parse_response(text)
            print(f"[server] Parsed sections: {[(k, bool(v)) for k,v in sections.items()]}")
            changes = session.state.apply_mechanics(sections["MECHANICS"])
            segments = parse_story(sections["STORY"], sections.get("AUDIO", ""))
            suggestions = parse_suggestions(sections["SUGGESTIONS"])
            print(f"[server] Segments: {len(segments)}, Suggestions: {len(suggestions)}")

            if sections["CHRONICLE"] and sections["CHRONICLE"] != "NO_ENTRY":
                session.state.chronicle.append(sections["CHRONICLE"])

            session.history.append({"role": "user", "content": opening})
            session.history.append({"role": "assistant", "content": text})
            session.turn_counter = 1

            # Start audio generation
            audio_turn_id = f"turn_{session.turn_counter:03d}"
            if session.audio_enabled and segments:
                generate_audio_async(segments, sections.get("SCENE", "exploration"), audio_turn_id)

            self._json({
                "model": session.model,
                "story": sections["STORY"],
                "segments": segments,
                "suggestions": suggestions,
                "changes": changes,
                "state": session.state.to_dict(),
                "turn": session.turn_counter,
                "scene": sections.get("SCENE", "exploration"),
                "audio_enabled": session.audio_enabled,
                "audio_turn_id": audio_turn_id if segments else None,
                "auto_roll": session.state.auto_roll,
                "budget": session.budget.to_dict(),
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._json({"error": str(e)})

    def _handle_turn(self, data):
        try:
            if not session.state:
                self._json({"error": "No game in progress. Start a new game first."})
                return

            action = data.get("action", "").strip()
            if not action:
                self._json({"error": "No action provided"})
                return

            # Apply settings from client
            client_settings = data.get("settings", {})
            if "model" in client_settings and client_settings["model"] != session.model:
                session.model = client_settings["model"]
                session.init_client()
            if "autoroll" in client_settings:
                session.state.auto_roll = client_settings["autoroll"]
            if "music" in client_settings:
                session.music_enabled = client_settings["music"]
            if "tts" in client_settings:
                session.tts_engine = client_settings["tts"]
            if "speed" in client_settings:
                session.tts_speed = client_settings["speed"]
            if "musicVol" in client_settings:
                session.music_volume = client_settings["musicVol"]
            if "musicSrc" in client_settings:
                session.music_source = client_settings["musicSrc"]

            session.init_client()

            # Check if we need to fall back to a free provider
            fallback_used = False
            original_model = session.model
            if session.budget.should_fallback(session.provider, session.model):
                print(f"[server] Budget exhausted — falling back to free provider")
                session.model = config.DEFAULT_MODEL
                session.provider = detect_provider(session.model)
                session.init_client()
                fallback_used = True

            state_block = session.state.to_prompt_block()

            text, elapsed, usage = dm_turn(
                session.client, session.model, SYSTEM_PROMPT,
                state_block, session.history, action,
            )

            cost = session.budget.add_cost(session.provider, session.model,
                                           usage["prompt_tokens"], usage["completion_tokens"])

            sections = parse_response(text)
            changes = session.state.apply_mechanics(sections["MECHANICS"])
            segments = parse_story(sections["STORY"], sections.get("AUDIO", ""))
            suggestions = parse_suggestions(sections["SUGGESTIONS"])

            if sections["CHRONICLE"] and sections["CHRONICLE"] != "NO_ENTRY":
                session.state.chronicle.append(sections["CHRONICLE"])

            session.history.append({"role": "user", "content": action})
            session.history.append({"role": "assistant", "content": text})
            session.turn_counter += 1

            audio_turn_id = f"turn_{session.turn_counter:03d}"
            if session.audio_enabled and segments:
                generate_audio_async(segments, sections.get("SCENE", "exploration"), audio_turn_id)

            self._json({
                "story": sections["STORY"],
                "segments": segments,
                "suggestions": suggestions,
                "changes": changes,
                "state": session.state.to_dict(),
                "turn": session.turn_counter,
                "scene": sections.get("SCENE", "exploration"),
                "audio_enabled": session.audio_enabled,
                "audio_turn_id": audio_turn_id if segments else None,
                "budget": session.budget.to_dict(),
                "elapsed": round(elapsed, 1),
                "fallback_used": fallback_used,
                "original_model": original_model if fallback_used else None,
                "model": session.model,
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._json({"error": str(e)})

    def _json(self, data):
        body = json.dumps(data, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_music(self, parsed):
        """Serve a continuous music stream based on current scene mood."""
        params = parse_qs(parsed.query)
        mood = params.get("mood", ["exploration"])[0]
        source = params.get("source", ["library"])[0]

        if source == "procedural":
            # Generate procedural ambient on the fly
            from . import audio_engine
            data, sr = audio_engine.generate_procedural_ambient(30.0, mood)
            import io
            buf = io.BytesIO()
            import soundfile as sf
            sf.write(buf, data, sr, format='WAV')
            buf.seek(0)
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(buf.getbuffer().nbytes))
            self.end_headers()
            self.wfile.write(buf.read())
        else:
            # Serve from library
            from . import audio_engine
            track_path = audio_engine.select_music_track(mood)
            if track_path and Path(track_path).exists():
                data_size = Path(track_path).stat().st_size
                self.send_response(200)
                ext = Path(track_path).suffix.lower()
                ct = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg"}.get(ext, "audio/mpeg")
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(data_size))
                self.end_headers()
                with open(track_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Narrator v0.1 — D&D story engine")
    parser.add_argument("--port", type=int, default=5102, help="Port (default 5102)")
    parser.add_argument("--model", default=config.DEFAULT_MODEL, help="DM model")
    parser.add_argument("--no-audio", action="store_true", help="Text-only mode")
    parser.add_argument("--budget", type=float, default=config.DEFAULT_BUDGET, help="USD budget cap")
    args = parser.parse_args()

    session.model = args.model
    session.provider = detect_provider(args.model)
    session.audio_enabled = not args.no_audio
    session.budget = BudgetTracker(args.budget)

    print(f"\n{'='*60}")
    print(f"  Narrator v0.1 — D&D Story Engine")
    print(f"  Model: {args.model} ({session.provider})")
    print(f"  Audio: {'enabled' if session.audio_enabled else 'disabled'}")
    print(f"  Budget: ${args.budget:.2f}")
    print(f"  URL: http://localhost:{args.port}")
    print(f"{'='*60}\n")

    server = ThreadingHTTPServer(("0.0.0.0", args.port), NarratorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
