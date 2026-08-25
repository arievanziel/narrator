# Instance B — GUI: Book Experience Frontend

**Created by:** Instance A (main programmer), 2026-08-24
**Source:** `docs/GLM-V1-FINISH-INSTRUCTIONS.md` TASK 1
**Design rationale:** `docs/V1-BOOK-EXPERIENCE-PLAN.md` (read §"Design decisions" once before starting)

## Your files (ONLY touch these)

- `glm-work/narrator_v01/templates/index.html`
- `glm-work/narrator_v01/static/app.js`
- `glm-work/narrator_v01/static/style.css`

**Do NOT touch:** `game_loop.py`, `world_store.py`, `dm_engine.py`, `audio_engine.py`, `audio_queue.py`, `app.py` — Instance A is working on those.

## Context

The backend book layer is DONE (commit `1474895`, 74/74 tests pass). The app currently renders a **game UI** over a **book engine**. Your job is to make the GUI look like a book. This is the single biggest gap to v1.

The backend already returns these fields in `/api/newgame` and `/api/turn` responses — **use them**:

```jsonc
{
  "chapter": { "number": 1, "title": "Silted Sanctum", "scene_setting": "...",
               "start_turn": 0, "location_name": "", "mood": "mystery",
               "is_new": true },        // null only if no world store
  "scene_setting": "...",               // non-empty ONLY when chapter.is_new
  "reader_notes": ["Vocation: Disgraced Cartographer", ...],  // safe to print
  "changes": [...],                     // RAW engine log — storyteller mode only
  "state": { "pc_vocation": "Disgraced Cartographer",
             "narrative_voice": "third_past", "character_generated": true, ... }
}
```

Existing endpoints you'll use (already working, no backend changes needed):
- `GET /api/chapters` — returns `{"chapters": [{number, title, scene_setting, start_turn, location_name, mood}, ...]}`
- `GET /api/state` — returns current game state (currently dead code — your work makes it live)

## TASK 1a — Lexicon layer

Add to `app.js` a single `LEXICON` object and a `storytellerMode` boolean (default `false`, persisted in `localStorage`). Every player-visible string goes through it. Add one toggle in settings: **"Show storyteller's notes"**.

| internal | reader sees by default |
|---|---|
| DM / Dungeon Master | the Narrator |
| Session Zero | Foreword |
| turn | passage |
| roll / dice / d20 / DC | **hidden entirely** |
| HP | Condition |
| AC | **hidden** |
| Enemies | Present in this scene |
| Mechanics | Storyteller's notes |
| Inventory | Belongings |
| Chronicle | The story so far |
| class | vocation (use `state.pc_vocation`) |
| Save / Load | Place bookmark / Resume reading |
| New game | New book |

When `storytellerMode` is off: hide the roll-result block, hide the `🎲` on choices, render `reader_notes` instead of `changes`, and hide AC/stats. When on: show everything exactly as today. **Do not delete the existing roll UI — gate it.**

## TASK 1b — Replace the stat topbar

Today's `HP | AC | Turn | Location | Mood` bar is the most game-like thing on screen. Replace with a book header: book/campaign title left, **"Chapter One · Silted Sanctum"** centre, controls right. Stats move into the left panel and only appear in storyteller mode. Chapter numbers spelled out in words, not digits or roman numerals.

## TASK 1c — Render the story as a book

In `addStoryTurn()` (`app.js:308`):
- **Remove** the roman-numeral turn mark (`app.js:316-319`) — it is a turn counter wearing a costume.
- When `data.chapter && data.chapter.is_new`: insert a chapter heading — small-caps `CHAPTER TWO`, then the title in a larger serif, then a thin rule. Give headings `id="chapter-N"` for TOC anchoring.
- Then render `data.scene_setting` as one justified paragraph **with a drop cap** on the first letter (`.scene-setting::first-letter`). This is the mood-setting paragraph. It is also narration — see Instance A's audio work.
- Narration: justified prose, generous leading, no speaker label.
- Dialogue: indented, speaker name in small caps italic.
- The existing three themes already work and are visually distinct — keep.

## TASK 1d — Panels

- Left panel becomes **"Your character"**: name, vocation, Condition bar, Belongings, Carried. Stats only in storyteller mode. Refresh it from `GET /api/state` (that endpoint is currently dead code — this makes it live).
- Add **"The story so far"**: a table of contents from `GET /api/chapters`, each entry clickable to scroll to that chapter's heading (give headings `id="chapter-N"`).
- Chronicle entries stay, retitled to "The story so far".

## TASK 1e — Foreword

Restyle the intro overlay as a book cover / foreword page. Rename "Begin Session Zero" → **"Read the foreword"**, "Quick Start" → **"Open the book"**. Same handlers, same endpoints — presentation only.

## Ground rules

- Run `node -c static/app.js` after every JS edit.
- Run `python3 -c "import py_compile;[py_compile.compile(f,doraise=True) for f in ['app.py','game_loop.py','audio_engine.py','config.py','dm_engine.py']]"` from `narrator_v01/` — should still pass (you're not touching Python, but verify nothing broke).
- Never write lines starting with `>` in any doc — those are Arie's.
- Do not touch `sonnet-work/`.
- If a design question comes up that this file doesn't answer, **pick the option that looks more like a book and less like a game**, note the choice, and move on.
- **Coordinate with Instance C**: Instance C owns TASK 2 (GUI audit fixes) which also touches `app.js`. You go first. When you're done, tell Arie so C can start.
- **Coordinate with Instance D**: D will run tests after you finish. Leave the codebase in a working state.

## Verification

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v01.app --port 5102
# Then open http://localhost:5102/ in a browser and verify:
# - Intro screen says "Read the foreword" / "Open the book"
# - Starting a game shows chapter heading, drop cap on scene setting
# - No roman numeral turn marks
# - Left panel shows "Your character" with vocation, not "Class"
# - "The story so far" panel lists chapters, clicking scrolls to them
# - Storyteller's notes toggle shows/hides mechanics, dice, AC
node -c narrator_v01/static/app.js
```
