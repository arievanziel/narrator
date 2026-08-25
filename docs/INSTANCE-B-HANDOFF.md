# Instance B — Handoff: Book Experience GUI Complete

**Author:** Instance B (GLM), 2026-08-24
**Task:** `docs/INSTANCE-B-GUI-HANDOFF.md` TASKS 1a–1e
**Status:** All 5 tasks complete, 28/28 browser smoke tests pass

## What was done

All five sub-tasks from `INSTANCE-B-GUI-HANDOFF.md` are implemented. The GUI now looks like a book, not a D&D character sheet. No backend files were touched — only `templates/index.html`, `static/app.js`, and `static/style.css`.

### TASK 1a — Lexicon layer
- Added a single `LEXICON` object at the top of `app.js` mapping all D&D jargon to literary phrasing (DM→Narrator, HP→Condition, AC→hidden, Inventory→Belongings, etc.).
- Added `storytellerMode` boolean (default `false`), persisted in `localStorage` under `narrator_storytellerMode`.
- Added "Show storyteller's notes" toggle in the settings panel (Story AI group).
- When storyteller mode is OFF: roll-result block is hidden, 🎲 on choices is hidden, `reader_notes` is rendered instead of raw `changes`, AC/ability scores are hidden, dice roller is hidden, enemies section is hidden.
- When storyteller mode is ON: everything shows exactly as before — the existing roll UI is gated, not deleted.
- CSS uses `html.storyteller-mode .storyteller-only { display: block; }` to gate visibility.

### TASK 1b — Book header
- Replaced the `HP | AC | Turn | Location | Mood` stat topbar with a book header:
  - **Left:** book/campaign title (e.g. "Kael's Tale"), derived from `state.pc_name`.
  - **Centre:** "Chapter One · Silted Sanctum" — chapter number spelled out in words (not digits or roman numerals), title from `currentChapter.title`.
  - **Right:** model label + settings gear.
- Stats moved to the left panel and only appear in storyteller mode.
- Added `numberToWord()` function with words for 0–25.

### TASK 1c — Book rendering
- **Removed** the roman-numeral turn mark (`toRoman(turnCount)` div).
- When `data.chapter && data.chapter.is_new`: inserts a chapter heading with:
  - Small-caps "Chapter One" (`.chapter-number`)
  - Title in larger serif (`.chapter-title`)
  - Thin rule (`.chapter-rule`)
  - `id="chapter-N"` for TOC anchoring
- Renders `data.scene_setting` as one justified paragraph with a drop cap on the first letter (`.scene-setting::first-letter`).
- Narration: justified prose, generous leading (1.9), no speaker label.
- Dialogue: indented (`margin-left: 2rem`), speaker name in small-caps italic.
- All three themes (light/sepia/dark) verified working.

### TASK 1d — Panels
- Left panel restructured:
  - **"Your character"** — name, vocation (from `state.pc_vocation`, falls back to `state.pc_class`), Condition bar, HP bar. AC/ability scores only in storyteller mode.
  - **"Carried"** — equipment (was "Equipment").
  - **"Conditions"** — unchanged.
  - **"Present in this scene"** — enemies (was "Enemies"), only in storyteller mode.
  - **"Belongings"** — inventory (was "Inventory").
  - **Dice Roller** — only in storyteller mode (`.storyteller-only`).
  - **"The story so far"** — NEW: table of contents from `GET /api/chapters`, each entry clickable to scroll to the chapter heading (`scrollToChapter(N)`).
  - **"Chronicle"** — retitled label, entries use "passage" instead of "Turn".
- `fetchChapters()` calls `/api/chapters` after every turn and after new game.
- `GET /api/state` is now live — `updateState()` is called on every turn and on storyteller toggle.

### TASK 1e — Foreword
- Intro overlay restyled as a book cover:
  - Added `.book-cover-frame` with centered title and subtitle, separated by a rule.
  - "Begin Session Zero" → **"Read the foreword"**
  - "Quick Start" → **"Open the book"**
  - "A D&D story engine that reads to you" → "An audiobook you can steer"
  - "DM:" label → "Narrator:"
- Session Zero wizard retitled "Foreword".
- Typing indicator: "The DM is weaving" → "The Narrator is weaving", "DM is thinking" → "The Narrator is thinking".
- Save/Load messages: "Game saved" → "Bookmark placed at passage N", "Game loaded" → "Resumed reading at passage N".
- Session buttons: "New Story" → "New book", "Save" → "Place bookmark", "Load" → "Resume reading".

## Files changed

| File | Lines before | Lines after | Change |
|------|-------------|-------------|--------|
| `templates/index.html` | 314 | 322 | +8 (book header, TOC section, storyteller toggle, foreword labels) |
| `static/app.js` | 1252 | 1380 | +128 (LEXICON, storyteller gating, chapter headings, TOC, book lexicon) |
| `static/style.css` | 250 | 287 | +37 (book header, chapter heading, drop cap, reader notes, TOC, storyteller gating) |

## Verification

```
node -c narrator_v01/static/app.js          → JS OK
python3 -c "import py_compile;..."           → PY OK (all 5 Python files)
Browser smoke test (28 checks)              → 28/28 PASS
```

All 28 browser smoke test checks passed:
- TASK 1e: "Read the foreword", "Open the book", book-cover-frame
- TASK 1b: book title, chapter label, HP/AC removed from topbar
- TASK 1c: roman turn mark removed, chapter heading present, chapter heading id=chapter-1, chapter number spelled out, scene-setting paragraph, narration justified
- TASK 1d: "Your character"/"Carried"/"Belongings"/"The story so far" headers, vocation shown, "Class" hidden, TOC entries
- TASK 1a: AC hidden by default, dice roller hidden by default, storyteller-mode class on toggle, AC visible in storyteller mode, dice roller visible in storyteller mode, storyteller-mode removed on toggle off
- Theme regression: dark, sepia
- Console errors: none

Screenshots saved to `glm-work/screenshots/book_*.png` (foreword, story light/sepia/dark, storyteller mode).

## Design decisions made (per ground rules)

Where the handoff doc didn't specify, I chose the option that looks more like a book:

1. **Book title**: Used `state.pc_name + "'s Tale"` (e.g. "Kael's Tale") since there's no campaign/book title field from the backend. If the backend adds a `book_title` or `campaign_title` field later, swap it in at `updateState()`.
2. **Chapter label separator**: Used a middle dot (·) with ornamental fleurons (❦) on either side: `❦ Chapter One · Silted Sanctum ❦`.
3. **Vocation fallback**: `state.pc_vocation` is empty when `character_generated` is false (the backend's P2 task isn't done yet). Falls back to `state.pc_class` so the panel isn't blank.
4. **Chronicle vs TOC**: Kept both — the TOC is chapter-level (from `/api/chapters`), the Chronicle is passage-level (from `/api/chronicle`). Both are retitled to "The story so far" variants. If Arie wants only one, the Chronicle section can be removed.
5. **Reader notes**: When `storytellerMode` is off and `data.reader_notes` is empty (which it currently is — the backend doesn't populate it yet), nothing is shown. This is correct — the raw `changes` are hidden and there's nothing literary to show yet. When the backend starts populating `reader_notes`, they'll appear automatically.

## What Instance A (main programmer) should know

1. **`reader_notes` is wired but empty**: The frontend reads `data.reader_notes` from `/api/newgame` and `/api/turn` responses. It currently returns `[]`. When P3.2 (translating engine strings to literary phrasing) is done, the notes will automatically appear in the story feed.
2. **`state.pc_vocation` is wired but empty**: The frontend uses `state.pc_vocation` for the "Vocation" field. It currently returns `""`. When P2.1 (`[CHARACTER]` block) is done, the vocation will automatically appear.
3. **`currentChapter` tracking**: The frontend tracks `currentChapter` from `data.chapter` in every `/api/turn` response. The book header centre shows "Chapter One · Title". This updates live as chapters change.
4. **No backend changes were made**: All work was in the three frontend files only. The Python compile check passes for all 5 files.
5. **`GET /api/state` is now live**: It's called on every turn and on storyteller-mode toggle to refresh the left panel.

## What Instance C (GUI audit) should know

Instance B went first per the coordination note. The codebase is in a working state. Instance C can now start TASK 2 (GUI audit fixes). Notes for C:

- The `toRoman()` function is still in `app.js` (used by audio labels like "turn I"). If C removes it, check for remaining references in `playSegment()` and `loadAudioLegacy()`.
- The `.turn-mark` CSS class is still in `style.css` but no longer used by any DOM element. Safe to remove if desired.
- The `.topbar .stat`, `.topbar .stat-label`, `.topbar .hp-bar`, `.topbar .hp-fill`, `.topbar .sep` CSS classes are still in `style.css` but no longer used (the stat topbar was replaced). Safe to remove.
- The `#tb-hp`, `#tb-ac`, `#tb-turn`, `#tb-loc`, `#tb-mood` element IDs no longer exist in the HTML. Any JS referencing them will fail silently — grep for these IDs before removing the fallback.

## What Instance D (tests) should know

The codebase is in a working state. All Python files compile, JS syntax is valid, and the browser smoke test passes. The app runs with:
```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v01.app --port 5102
```

## What Sonnet/OPUS should know

This is the single biggest gap to v1, now closed. The GUI is a book, not a game. The remaining v1 gaps are backend-side:
- **P2**: Kill the last hardcoding (`[CHARACTER]` block, empty initial state, location sync). The frontend is ready for `pc_vocation` and will display it automatically.
- **P3**: Guards (player voice guard, literary change log). The frontend is ready for `reader_notes` and will display them automatically.
- **P5**: GUI audit (Instance C's task) — walk every control, fix or remove non-working ones.
- **P6**: Audio (only if time) — confirm segment streaming outruns playback.

The frontend lexicon is a single `LEXICON` object at the top of `app.js`. To add or change a translation, edit one line. The `storytellerMode` toggle is the single switch between literary and mechanical views.
