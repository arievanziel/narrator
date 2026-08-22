# Narrator v0.3 — GLM Handoff to Sonnet

**Date:** 2026-08-21
**Author:** GLM (Instance A — Rules Lawyer + Core App)
**Status:** v0.3 functional, extensively tested, committed

## Version history

- **v0.1**: Core app — DM engine, GUI, TTS, music, intro screen, settings
- **v0.2**: Pre-loaded TTS model, dark/sepia themes, budget fallback, continuous
  background music with mood-based switching, save/load game state, Kokoro TTS,
  auto TTS mode, real progress indicator, chronicle panel
- **v0.3**: UX polish + TTS fidelity fix — keyboard shortcuts, auto-send choices,
  smooth scroll, model label sync, mood in topbar, loading states, procedural
  music crash fix, Qwen3 paraphrasing fix (auto-fallback to Kokoro)

## Testing summary

70 audio recordings, 7 screenshots, 6 rounds of playtests (30+ playtests total).

### TTS fidelity finding

Qwen3 VoiceDesign paraphrases heavily, especially for longer passages:
- 286 chars of text → 160s of audio (8.4x longer than expected)
- Qwen3 adds words, skips words, or goes on tangents

Kokoro is consistently faithful (ratio ~1.0-1.2):
- Same 286 chars → 20.2s of audio (1.06x — nearly perfect)

**Fix**: Default TTS changed to Kokoro. Qwen3 still available but with:
- temperature=0.0 (reduces paraphrasing)
- max_tokens limited to text length * 4 + 200
- Auto-fallback: if Qwen3 audio is >2x expected duration, regenerate with Kokoro

### Test results

- **Kokoro default**: All turns GOOD fidelity (ratio 1.0-1.2)
- **Qwen3 with auto-fallback**: Paraphrasing detected and fallback to Kokoro works
- **Groq provider**: 6-turn playthrough, perfect fidelity (0.99-1.03)
- **10-turn playthrough**: All turns generated audio correctly, rules lawyer working
- **Edge cases**: Empty input, long input, special characters, unicode — all handled
- **Settings switching**: All models, TTS engines, music sources, speeds — all work
- **Save/Load**: Working correctly
- **Music**: Library and procedural both return HTTP 200
- **HTML features**: 17/17 present

### Bugs fixed during testing

1. Qwen3 text mismatch (paraphrasing) — fixed with Kokoro default + auto-fallback
2. Qwen3 file-finding logic missing after generate_audio call
3. mix_narration UnboundLocalError when procedural music fails
4. Silence fallback for failed segments was only 0.5s (now proportional to text)
5. Audio file overwrites between games — fixed with unique game IDs
6. Kokoro am_george voice doesn't exist — replaced with bm_george
7. Narrator and player character had same voice — now differentiated

### Voice mapping (Kokoro)

- Narrator: am_michael (mature male)
- Player character: am_puck or am_adam (distinct from narrator)
- Female NPCs: af_bella or af_heart
- Old characters: bm_george
- Goblin/rough: am_adam
- British/formal: bm_fable

## What was built

A complete v0.2 D&D narration app at `glm-work/narrator_v01/`. This is a fresh package
(separate from the old `narrator_v0/`) that implements the full story loop:

```
Player action → DM brain (LLM) → rules lawyer → parsed story → TTS → music mix → browser
```

### Files

| File | Purpose |
|---|---|
| `narrator_v01/__init__.py` | Package init |
| `narrator_v01/config.py` | Configuration: providers, models, music, TTS, paths |
| `narrator_v01/dm_engine.py` | DM brain: system prompt, game state, parser, API client |
| `narrator_v01/audio_engine.py` | TTS generation (Qwen3), music mixing, procedural ambient |
| `narrator_v01/app.py` | HTTP server + full v9-inspired GUI (HTML/CSS/JS embedded) |

### Features implemented

**A: Story generation (multi-provider)**
- Gemini 3.5 Flash-Lite (default, free) and Groq GPT-OSS 120B (free, fast)
- Live model switching via settings panel dropdown
- Auto-roll mode (app rolls dice) and manual mode (player rolls)
- Rules-lawyer safeguards: waste-potion guard, control-NPC guard
- 5-section response format: [SCENE], [STORY], [MECHANICS], [SUGGESTIONS], [CHRONICLE]
- Handles legacy [NARRATIVE]/[AUDIO] format from models that don't follow the prompt exactly
- Budget fallback: auto-switch to free provider when paid budget exhausted
- Fallback warning shown on screen when model is switched

**B: GUI (v9-inspired)**
- Book-like aesthetic: paper background, serif font, circle buttons
- Collapsible panels: left (character/enemies/inventory/dice), right (settings)
- Collapsible top bar with live stats (HP, AC, turn, location)
- Audio bar with play/pause, progress, seek, generating indicator
- Intro screen: story style, setting, character name, persona, atmosphere, inspiration, dice mode
- 3+ choices per turn as clickable buttons
- Free text input with Enter to send
- Visual dice roller (d4-d100) with shake animation
- Turn marks (Roman numerals)
- Speaker labels for dialogue
- State changes shown inline (HP changes, item used/gained)
- Dark, sepia, and light theme options
- Save/Load buttons in settings panel

**C: Audio narration**
- Qwen3-TTS VoiceDesign via mlx_audio (local, Apple Silicon)
- Word-for-word matching: screen text = TTS text (exact same segments)
- Character voices: narrator voice + gender-based character voices
- Background generation: audio starts generating immediately when LLM responds
- Audio status polling: browser polls until audio is ready, then auto-plays
- Pre-loaded model: 4s → 0.7s per TTS call (model stays in memory)
- RTF ~0.47 (2x faster than real-time for longer text)
- Music ducking: music volume reduces during speech

**D: Background music (continuous)**
- Separate continuous music stream via /api/music endpoint
- Two music sources:
  1. Library: curated CC0/CC-BY tracks mapped by scene mood
  2. Procedural: synthesized ambient (drone + noise + bells, mood-based)
- Mood-based selection from [SCENE] tag: combat, tense, horror, mystery, exploration, tavern, etc.
- Music changes automatically when scene mood changes
- Music ducking during speech segments (in narration audio)
- Settings: enable/disable, source selection, volume control
- Background music loops continuously between turns

**Save/Load**
- /api/save: saves game state + history to JSON file
- /api/load: restores game state from save file
- /api/chronicle: returns campaign log entries

**Budget tracking**
- BudgetTracker class with USD cap
- Per-call cost tracking for paid providers (Anthropic)
- Budget bar in settings panel
- Auto-fallback: free providers (Gemini, Groq) have no budget limit
- Visual warning when fallback is triggered

### v0.3 UX improvements

- **Keyboard shortcuts**: 1-9 to select choices, Esc to close panels, Enter to send
- **Auto-send choices**: Clicking a choice immediately sends it (no need to press Send)
- **Choice numbers**: Shown as 1/2/3 (matches keyboard shortcuts)
- **Smooth scroll**: Story area scrolls smoothly instead of jumping
- **Model label sync**: Topbar model label updates when model is switched or fallback occurs
- **Mood in topbar**: Current scene mood shown alongside location
- **Loading states**: Send button shows "..." while waiting, intro button shows "Starting..."
- **Procedural music fix**: Pre-generated and cached at startup to avoid MLX threading crash
- **Bg music at newgame**: Background music starts immediately when game starts

## How to run

```bash
cd /Users/arie/CascadeProjects/narrator/glm-work
source .venv/bin/activate
python -m narrator_v01.app --port 5102
# Text-only mode:
python -m narrator_v01.app --port 5102 --no-audio
# With budget cap:
python -m narrator_v01.app --port 5102 --budget 3.0
```

Then open http://localhost:5102 in your browser.

## Test results

### Verified working
- Multi-turn story generation with Gemini 3.5 Flash-Lite (4 turns tested)
- Model switching: Gemini → Groq mid-game (works)
- Rules-lawyer: waste-potion guard, control-NPC guard (unit tested)
- Audio generation: Qwen3 TTS produces 29-36s audio per turn
- Music mixing: library tracks + ducking
- Procedural ambient: instant generation (0.06s for 10s audio)
- Word-for-word matching: display segments = TTS segments
- Intro screen: story style settings passed to DM
- Settings panel: model, TTS, music, budget controls

### Known issues
1. **Gemini model names changed**: 2.5 → 3.5. Config updated but old models in v0 still reference 2.5.
2. **Audio generation is sequential**: Segments are generated one at a time. Parallel generation would require multiple model instances (memory tradeoff).
3. **Anthropic provider not tested**: API key has insufficient credits. Code is in place but untested.
4. **Single session**: One game at a time (class-level state). Multi-session would need session management.
5. **Bg music restarts on mood change**: The /api/music endpoint serves a fresh file each time, causing a brief gap when mood changes. A proper streaming solution would be smoother.
6. **Procedural music is pre-generated**: Tracks are cached at startup to avoid MLX/numpy threading crashes. Regenerating requires server restart.
7. **Kokoro warmup**: First 1-2 Kokoro calls are slow (~6s) due to pipeline warmup. After that, RTF drops to 0.17.

## What Sonnet should focus on next

1. **GUI polish**: The v9 GUI is functional but could use more refinement — animations, transitions, better mobile support.
2. **Continuous music**: Implement a separate `/music` endpoint that streams continuous background music, independent of narration audio.
3. **Model persistence**: Keep the Qwen3 model loaded between calls to avoid 4s reload overhead.
4. **Save/load**: Add game state persistence (JSON file or SQLite).
5. **Multi-session**: Support multiple concurrent games with session IDs.
6. **Kokoro TTS**: Add Kokoro as a second TTS engine option (faster, different voice character).
7. **Streaming TTS**: Generate and play audio in chunks for faster perceived response time.

## Architecture notes

- The DM engine uses a 5-section response format. The [STORY] section contains
  line-by-line content with `[narrator]` and `[CharName]` tags. This is the EXACT
  text shown on screen and spoken by TTS — word for word.
- The parser handles both the new format ([STORY]) and legacy format ([NARRATIVE]/[AUDIO]).
  If [STORY] is prose (no tags), it falls back to [AUDIO] which has the tagged format.
- The rules lawyer in `apply_mechanics()` includes anti-cheat safeguards:
  - Waste-potion guard: invalid item claims block all item use that turn
  - Control-NPC guard: ENEMY_DEAD requires roll evidence (ENEMY_HP or ROLL_REQUEST)

---

## Instance D — v0.3 stability / regression sweep

**Date:** 2026-08-22  
**Scope:** General regression sweep of the v0.3 checkpoint before v0.4 work starts. Per `docs/V1-PLAN.md`, the long-session (30+ turn) stress test is intentionally deferred until the v0.4 changes settle.

### Tests run

| Test | Command | Result |
|---|---|---|
| Trickster unit tests (rules lawyer) | `python -m narrator_v01.test_trickster` | **16/16 PASS** |
| App startup (text-only, no API calls) | `python -m narrator_v01.app --no-audio --port 5199` | **HTTP 200 on root, /api/providers OK** |
| Theme CSS verification | Visual comparison of `setTheme()` values | **Sepia (#f0e6d2) distinct from dark (#1a1a1e) and light (#e6e4e0)** |

### Bug found and fixed

1. **Roll-evidence scoping bug in `narrator_v01/dm_engine.py` (`apply_mechanics`)**
   - **Problem:** A `ROLL_REQUEST` granted roll evidence to *all* enemies, not the target. A roll for "Goblin Scout" could kill a different "Goblin Raider" on the same turn.
   - **Fix:** Roll evidence is now scoped. An enemy gets evidence only if:
     - an `ENEMY_HP:<enemy>,...` for that enemy exists in the same mechanics block, OR
     - the enemy name appears in the `ROLL_REQUEST` text.
   - **New test:** Added "Roll scoped to target enemy only" to `narrator_v01/test_trickster.py`.
   - **Result:** All 16 trickster tests pass.

### Observations (not fixed, out of scope for v0.3)

1. **Hardcoded opening encounter:** `make_initial_state()` always spawns the same two goblins. Addressed by `docs/WORLD-ENGINE-DESIGN.md` v0.5.
2. **Prompt-caching issue:** `dm_turn()` uses `history[-10:]`, which changes the prompt prefix every turn after turn 10. Addressed by `docs/WORLD-ENGINE-REVIEW-OPUS.md` §3.3 (v0.5 context assembler).
3. **Long-session stress test:** Deferred per `docs/V1-PLAN.md` — app is about to change substantially in v0.4/v0.5.

---

## Update 2026-08-22 — v0.3.5 through v0.5c (Instance A)

**Author:** GLM (Instance A — Rules & World Engine)
**Commits:** `91af954` (v0.3.5+v0.4c), `3f96def` (v0.4d+v0.5a/b/c)
**Branch:** `glm-phase1`

### v0.3.5 — File restructuring (behavior-preserving)

Split `app.py` from 2,245 lines to 288 lines:
- `templates/index.html` — HTML structure
- `static/style.css` — all CSS (168 lines)
- `static/app.js` — all JavaScript (627 lines)
- `game_loop.py` — turn orchestration, Session, BudgetTracker, all handlers (523 lines)
- `app.py` — thin HTTP server + routing only (288 lines)

Fixed double-thread-start bug in audio generation. Verified with Playwright:
13 screenshots, 0 console errors, audio working.

### v0.4c — World Store (standalone, unit-tested)

`world_store.py` (793 lines) with:
- `Entity`, `Link`, `Revision`, `Fact`, `Scene`, `Encounter`, `RollRecord`,
  `TurnRecord`, `TokenBudget`, `ContextBundle` dataclasses
- `resolve_or_create()`: 8-step duplicate resolution (exact/alias/fuzzy/token/policy)
- `apply_turn_mechanics()`: generalized rules lawyer with all tag types
- Atomic persistence (write to .tmp, os.replace)
- Append-only JSONL turn log
- Entity validation per type (required attrs, HP clamping, quest status)
- 15/15 unit tests pass

### v0.4d — GameState facade (behavior-neutral)

`GameState` now supports optional `WorldStore` backend:
- `attach_world_store()` syncs flat attributes to/from entity store
- `apply_mechanics()` delegates to `world_store.apply_turn_mechanics()` when attached
- Legacy path preserved when no store attached
- 11/11 facade tests pass — verified behavior-neutral

### v0.5a — Context assembler

Full layered assembly (L0-L9) with token budgets:
- Stable prefix (cacheable): system prompt, campaign meta, world directory, pinned entities
- Volatile suffix (never cached): working set, scene, digest, recent turns, rules, player action
- Working-set scoring: pinned(100)/present(50)/named-in-input(40)/named-in-narration(30)/graph-hop(20)/quest-linked(15)/recency(0-10)
- [KNOWN]/[NEW] markers, dropped entity tracking
- 9/9 context assembler tests pass

### v0.5b — Consistency guards + RECALL

- Presence-and-liveness guard: detects dead/absent speakers in narrative
- RECALL handler: resolves entity by name/alias/fuzzy, returns full record
- Contradiction detection: flags contradictory ENTITY_UPDATEs
- "Since you were last here" digest in enter_scene()
- 9/9 guard tests pass

### v0.5c — Procedural opening (kills hardcoded goblins)

- `make_initial_state(procedural=True)` creates empty state — no hardcoded enemies
- `game_loop.py` uses procedural mode for new games and Session Zero
- System prompt updated: PROCEDURAL WORLD, KNOWN/NEW, RECALL clauses
- New tags: ENTITY_NEW, ENTITY_UPDATE, ALIAS, QUEST_UPDATE
- `PROMPT_VERSION = "v10"`
- Playwright confirms: LLM generates unique locations/NPCs (e.g. "Oakhaven", "Innkeeper Silas")
- 7/7 procedural tests pass

### Test summary

| Suite | Command | Result |
|---|---|---|
| Trickster (16 scenarios) | `python -m narrator_v01.test_trickster` | **16/16 PASS** |
| World Store (15 tests) | `python -m narrator_v01.test_world_store` | **15/15 PASS** |
| Facade (11 tests) | `python -m narrator_v01.test_facade` | **11/11 PASS** |
| Context Assembler (9 tests) | `python -m narrator_v01.test_context` | **9/9 PASS** |
| Guards (9 tests) | `python -m narrator_v01.test_guards` | **9/9 PASS** |
| Procedural (7 tests) | `python -m narrator_v01.test_procedural` | **7/7 PASS** |
| Playwright (browser) | `node playwright_test.js` | **13 screenshots, 0 errors** |
| **Total** | | **67/67 PASS** |

### What's next (Instance A)

Per `docs/V1-PLAN.md` build order:
- **v0.4b (DC-then-roll)**: waits for Instance B's audio queue (v0.4a) to land first
- **v0.5a context assembler integration**: wire `get_context_for_turn()` into the live turn flow
  (currently the context assembler exists but isn't called from `game_loop.py` yet — the
  existing `history[-10:]` sliding window is still in use)
- **v0.5b guard integration**: wire `presence_liveness_guard()` into the post-generation flow
- **Opus review**: three World Engine retrieval/consistency questions remain open per
  `sonnet-work/OPUS-BRIEF-WORLD-ENGINE.md`
