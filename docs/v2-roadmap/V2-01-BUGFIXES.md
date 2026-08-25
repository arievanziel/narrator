# V2-01 — Bug Fixes from V1 Playtest

**Status:** Planning — no implementation yet
**Priority:** Highest — fix before any new features
**Estimated effort:** Small (mostly frontend gating + terminology)
**Feedback:** Add `>` inline notes anywhere.

## Summary

Fix all issues identified in the v1 playtest feedback. These are mostly correctness and gating bugs — things that should already work but don't.

## Issues to fix

### 1. Storyteller mode leaks mechanics in book mode

**Problem:** When storyteller mode is OFF, the reader still sees:
- "Roll requested: 1d20 for Perception DC 12"
- "[Guard: response regenerated due to a consistency violation]"
- Dice roll results on the main page

**Root cause:** The `reader_notes` and `changes` arrays are not being fully gated by `storytellerMode` in the frontend. The guard note (now in `changes`) still shows because the `reader_notes` path renders regardless of mode in some cases.

**Fix:**
- In `addStoryTurn()`, the `reader_notes` block (line ~469 in app.js) renders when `!storytellerMode && data.reader_notes && data.reader_notes.length`. But `reader_notes` is generated from `changes` by `reader_notes()` in `game_loop.py` — if it contains guard notes or roll requests, those leak through.
- The backend `reader_notes()` function should filter out anything that contains engine-internal language (roll requests, guard notes, DC references, dice notation).
- The frontend should also double-check: if `storytellerMode` is false, never render anything containing "roll", "DC", "d20", "Guard", "REJECTED", etc.

**Files:** `game_loop.py` (reader_notes filter), `app.js` (frontend gating)

### 2. Dice roller always visible

**Problem:** The dice roller in the left panel is always visible, even in book mode.

**Fix:** The dice roller section already has class `storyteller-only` but the CSS may not be hiding it. Check that `.storyteller-only { display: none; }` is applied when `storytellerMode` is false, and `body.storyteller .storyteller-only { display: block; }` when true.

**Files:** `style.css`, `app.js` (toggleStorytellerMode)

### 3. "Turn" appears instead of "passage" in some places

**Problem:** The bottom bar / audio bar still says "turn" in some places.

**Fix:** Search all frontend strings for "turn" and replace with "passage" where it refers to the user's interaction. Keep "turn" only where it refers to the engine's internal turn counter (which the reader never sees).

**Files:** `app.js`, `index.html`

### 4. Left panel opens automatically at chapter start

**Problem:** The left panel opens automatically when chapter 1 begins. The GUI should stay minimal.

**Fix:** In `szFinish()` and `startGame()`, remove the lines that add `show-left` class. The user should open panels themselves.

**Files:** `app.js`

### 5. Quick start is not fully procedural

**Problem:** "Open the book with defaults" uses hardcoded defaults instead of generating a random story.

**Fix:** `startGame({skip:true})` calls `newGame({})` with no params. The backend `handle_new_game()` should generate random style, setting, persona, atmosphere, and name when no params are provided. Use the procedural character generator that already exists.

**Files:** `game_loop.py` (handle_new_game)

### 6. Model dropdown locks after first Session Zero exchange

**Problem:** The model selector is disabled after the first foreword exchange. The user wants to change models freely, with the change taking effect after their next input.

**Fix:**
- Remove the `szModel.disabled = true` line from `szStart()`.
- In the backend, `handle_session_zero_turn()` should re-initialize the client if the model has changed. Check `data.get("model")` against `session.model` and call `session.init_client()` if different.
- The frontend should send the current model selection with each turn.

**Files:** `app.js` (remove lock), `game_loop.py` (re-init on model change)

### 7. Free-text audio plays too early

**Problem:** Free-text TTS generates and plays as soon as the user types, not when they send.

**Fix:**
- Remove the `oninput` listener that triggers free-text generation on every keystroke.
- Instead, generate free-text TTS only when the user sends their action (clicks Send or presses Enter).
- The "voicing..." indicator should appear only after send, while the TTS is being generated.
- The audio should play after the narrator's response audio finishes (or immediately if no narrator audio is playing).

**Files:** `app.js` (onFreeTextInput, sendAction)

### 8. "Resume reading" not available after refresh

**Problem:** After a page refresh, the intro screen shows but there's no way to resume a saved game — the side panels with save/load buttons aren't visible.

**Fix:**
- On page load, check if a save exists (call `/api/state` or a new `/api/has_save` endpoint).
- If a save exists, show a "Resume reading" button on the intro screen alongside "Read the foreword" and "Open the book".
- Clicking it calls `loadGame()` which restores the session and shows the main app.

**Files:** `app.js` (page load logic), `index.html` (intro screen), `game_loop.py` (has_save endpoint)

### 9. "New book" should be "New story"

**Problem:** The button says "New book" but Arie prefers "New story".

**Fix:** Change the button label in `index.html`.

**Files:** `index.html`

### 10. Save/load terminology and clarity

**Problem:** "Place bookmark" and "Resume reading" are unclear. Where is it saved? How to load a previous book?

**Fix:**
- In the settings panel, use clear labels: "Save story", "Load story", "New story".
- Show save metadata: story title, chapter number, last saved time.
- This connects to v1.4 (multi-book library) but for now, at least make the current save/load clear.

**Files:** `index.html`, `app.js`

## Testing

After all fixes:
- Run full test suite (should still be 93+)
- Run Playwright smoke test
- Manual playtest: toggle storyteller mode on/off and verify nothing leaks
- Manual playtest: refresh page and verify "Resume reading" appears
- Manual playtest: type in the input and verify no audio plays until Send
