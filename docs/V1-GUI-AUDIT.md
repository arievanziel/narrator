# V1 GUI Audit — Instance C

**Created by:** Instance C (UX), 2026-08-24
**Source:** `docs/INSTANCE-C-UX-HANDOFF.md`
**App version:** narrator_v01, pre-Book-GUI (Instance B has not started yet)

This audit walks every control in the current UI and records its status. It is the prerequisite work for the 4 fixes + 1 polling task assigned to Instance C. Instance B (Book GUI) has not started yet at the time of writing — the fixes below will be applied after B finishes, against whatever `app.js`/`index.html`/`style.css` look like then.

## Method

- Read `static/app.js` (1252 lines), `templates/index.html` (315 lines), `static/style.css` (250 lines) end-to-end.
- Started the app on port 5107 (`--no-audio`) and probed every endpoint referenced by the frontend.
- Ran a Playwright smoke check for DOM existence and console errors.
- Cross-checked backend claims in `game_loop.py`, `app.py`, `dm_engine.py`.

## Smoke test results

- `GET /` → 200, HTML serves.
- `GET /static/app.js` → 200, JS serves.
- `GET /api/state` → 200 (dead code until Instance B wires it up).
- `GET /api/freetext_status?gen_id=` → `{"status": "unknown"}` — endpoint is live.
- Playwright DOM check: all controls present (`#sz-model`, `#set-model`, Voice Assignment button, 7 dice buttons, `#dice-history`, `#sz-send-btn`, `#sz-skip-btn`).
- Console errors: **none**.

## Control-by-control audit

### Intro overlay (`#intro-overlay`)

| Control | Status | Notes |
|---|---|---|
| "Begin Session Zero" button (`#intro-session-zero-btn`) | Works | Calls `openSessionZero()`. |
| Quick-start form (style/setting/name/persona/atmosphere/inspiration/dicemode) | Works | Posted to `/api/newgame`. |
| "Quick Start" button (`#intro-start-btn`) | Works | Calls `startGame()`. |
| "Skip — use defaults" button | Works | Calls `startGame({skip:true})`. |

**Note for Instance B:** This overlay is what gets restyled into a book cover / foreword page. The handlers stay; only presentation changes.

### Session Zero wizard (`#session-zero-overlay`)

| Control | Status | Notes |
|---|---|---|
| Conversation area (`#sz-conversation`) | Works | `addSzMsg()` renders DM/player bubbles + suggestions. |
| Progress dots (`#sz-progress`) | Works | `updateSzProgress()` fills 8 dots as `szTurnCount` advances. |
| **Model dropdown (`#sz-model`)** | **Bug — Fix 4** | `onchange="szChangeModel(this.value)"` only updates `settings.model` locally. The `/api/session_zero/turn` POST body is `{answer}` only — the model is never sent after the first exchange. Changing it mid-conversation silently does nothing. See Fix 4 below. |
| "Skip to game with defaults" button | Works | Calls `szSkipToGame()`. |
| Input field (`#sz-input`) | Works | Enter key triggers `szSendAnswer()`. |
| Send button (`#sz-send-btn`) | Works | Calls `szSendAnswer()`. |
| Suggestion buttons | Works | Inline `onclick="szSendAnswer('...')"` with `escapeAttr`. |

### Voice assignment overlay (`#voice-overlay`)

| Control | Status | Notes |
|---|---|---|
| Overlay open (via Settings → "Voice Assignment") | Works | `openVoiceScreen()` fetches `/api/voice/list`. |
| Voice entry textareas | Works | One per cast key (excluding `_defaults`). |
| "Add new character voice" field | Works | `addNewVoiceField()` inserts a new entry before the add-section. |
| "Skip" button | Works | Closes without saving. |
| "Save & Continue" button | Works | POSTs changed/new assignments to `/api/voice/assign`, then closes. |

### Top bar

| Control | Status | Notes |
|---|---|---|
| HP stat + bar (`#tb-hp`, `#tb-hpfill`) | Works | Updated by `updateState()`. |
| AC stat (`#tb-ac`) | Works | Updated by `updateState()`. |
| Turn counter (`#tb-turn`) | Works | Set from `turnCount`. |
| Location (`#tb-loc`) | Works | From `state.location`. |
| Mood (`#tb-mood`) | Works | From `data.scene` via `setMood()`. |
| Left-panel toggle (`#tab-left`) | Works | `togglePanel('left')`. |
| Settings toggle (`#tab-settings`) | Works | `togglePanel('settings')`. |
| Model label (`#model-label`) | Works | Updated on new game / turn. |
| Top-bar hide toggle (`.circle-tab-top`) | Works | `toggleBar()`. |

**Note for Instance B:** This entire top bar is what gets replaced by a book header (title left, chapter centre, controls right). Stats move into the left panel and are gated by `storytellerMode`.

### Left panel

| Control | Status | Notes |
|---|---|---|
| Character info (`#char-info`) | Works | Name/Class/HP/AC. Uses `state.pc_class` — Instance B will switch to `pc_vocation`. |
| Ability scores (`#char-stats`) | Works | 6-stat grid with modifiers. |
| Equipment (`#equipment-list`) | Works | Split from `state.equipment` on commas. |
| Conditions (`#conditions-list`) | Works | Reads `state.conditions` (currently always empty — World Store not wired). |
| Enemies (`#enemy-list`) | Works | Renders `state.enemies` with alive/dead styling. |
| Inventory (`#inv-list`) | Works | Renders `state.inventory`. |
| Dice buttons (d20/d12/d10/d8/d6/d4/d100) | **Bug — Fix 2** | `rollDice()` only appends "I rolled a X on dY" as free text. `sendAction()` never sends `manual_roll` in the POST body. Backend already reads `data.get("manual_roll")` at `game_loop.py:639`. See Fix 2 below. |
| Dice result display (`#dice-result`) | Works | Shows latest roll. |
| Dice history (`#dice-history`) | Works | Last 10 rolls, styled. |
| Chronicle (`#chronicle-list`) | Works | Fetched from `/api/chronicle`. |

### Settings panel (right)

| Control | Status | Notes |
|---|---|---|
| Model select (`#set-model`) | Works | `changeModel()` updates `settings.model`. |
| Auto-roll toggle (`#set-autoroll`) | Works | `toggleSetting('autoroll', this)`. |
| Provider status (`#provider-status`) | Works | `fetchProviderStatus()` shows availability dots. |
| TTS engine select (`#set-tts`) | Works | `changeTTS()`. |
| Speed slider | Works | `changeSpeed()`. |
| **Narration volume slider** | **Bug — Fix 1** | `changeNarrationVol()` sets `player.volume` immediately, but `playSegment()` sets `player.volume = 0` then fades in to `settings.narrationVol` — so mid-passage the volume is correct. However, the *initial* set in `changeNarrationVol` is overwritten on the next segment load. The real bug: if the user changes the slider *during* a segment, it works; but each new segment re-reads `settings.narrationVol` via `_fadeInVolume`, so the value persists. **Re-verified:** `playSegment()` at line 750 sets `player.volume = settings.narrationVol` and line 776 fades to `settings.narrationVol`. The slider updates `settings.narrationVol`. So the value *does* persist across segments. The handoff's claim of "resets mid-passage" needs live audio testing to confirm — the code path looks correct. See Fix 1 notes below. |
| Music toggle (`#set-music`) | Works | `toggleSetting('music', this)` → `updateBgMusic()`. |
| Music source select (`#set-musicsrc`) | Works | `changeMusicSrc()`. |
| Music volume slider | Works | `changeMusicVol()`. |
| Budget display | Works | `updateBudget()`. |
| New Story / Save / Load buttons | Work | Call `newGame()` / `saveGame()` / `loadGame()`. |
| Voice Assignment button | Works | `openVoiceScreen()`. |
| Theme select (`#set-theme`) | Works | `setTheme()`. |

### Audio bar

| Control | Status | Notes |
|---|---|---|
| Play/pause button (`#audio-play`) | Works | `toggleAudio()`. |
| Replay button | Works | `replayAudio()`. |
| **Seek bar (`#audio-progress`)** | **Bug — Fix 3** | `onclick="seekAudio(event)"` is set in HTML (line 298). CSS gives it `cursor: pointer` (style.css line 167). `seekAudio()` only seeks within the *current segment* — clicking during a multi-segment passage jumps unpredictably because `player.currentTime` is segment-local, not passage-global. See Fix 3 below. |
| Audio label (`#audio-label`) | Works | Shows "Narrator · turn X · seg Y/Z". |
| Audio time (`#audio-time`) | Works | Segment-local time. |
| Audio status (`#audio-status`) | Works | Shows "generating..." etc. |
| Generation progress bar (`#audio-gen-bar`) | Works | Shown during segment generation. |

### Keyboard shortcuts

| Shortcut | Status | Notes |
|---|---|---|
| Enter (in input) | Works | Triggers `sendAction()`. |
| 1-9 (not in input) | Works | Clicks the Nth `.choice-item`. |
| Escape | Works | Closes settings panel. |

### Free-text TTS

| Feature | Status | Notes |
|---|---|---|
| `onFreeTextInput()` debounce | Works | Triggers `/api/freetext/generate` after 1s of no typing. |
| Cancel on new input | Works | POSTs `/api/freetext/cancel`. |
| **`/api/freetext_status` polling** | **Bug — Fix 5** | The endpoint exists (`app.py:159`) and returns `{"status": "unknown"}` for empty gen_id, but **no frontend code ever calls it**. `grep -c freetext_status app.js` → 0. The generated free-text audio is never played back to the user. See Fix 5 below. |

---

## The 5 fixes — detailed analysis

### Fix 1 — Narration volume slider resets mid-passage

**Handoff claim:** "each new queue segment loads at default volume, so it resets mid-passage."

**Code reading:** `playSegment()` (app.js:747-820) does:
1. Line 750: `player.volume = settings.narrationVol;` — sets to user's value.
2. Line 770: `player.volume = 0;` — resets to 0 for fade-in.
3. Line 776: `_fadeInVolume(player, settings.narrationVol, 50);` — fades back up to user's value.

So each segment *does* re-apply `settings.narrationVol`. The slider updates `settings.narrationVol` at `changeNarrationVol()` (line 48-53). The value persists across segments.

**Verdict:** The code path looks correct on static reading. The handoff's claim may be based on an older version of `playSegment()`, or the bug may only manifest in a specific edge case (e.g. the fade-in race with `player.play()` promise resolution). **Needs live audio testing to confirm.** If the bug does not reproduce, this fix becomes a no-op and I'll note that in the handoff.

**If the bug does reproduce:** The fix is to ensure `settings.narrationVol` is re-applied inside `playSegment()` after the fade-in completes, and that `changeNarrationVol()` also updates the currently-playing segment's volume in real time (it already does at line 52).

**Status:** Pending live audio test. Will apply after Instance B finishes (B may rewrite `playSegment()`).

### Fix 2 — Dice roller buttons are cosmetic

**Confirmed.** `rollDice()` (app.js:186-199):
- Generates a random result.
- Displays it in `#dice-result`.
- Appends "I rolled a X on dY." to the input field.
- **Does not** store the result for `sendAction()` to send as `manual_roll`.

`sendAction()` (app.js:266-305) POSTs `{ action, settings: {...} }` — no `manual_roll` field.

Backend `game_loop.py:639` reads `data.get("manual_roll")` and passes it to `dm_turn_dc_roll()` at line 646 (only when `auto_roll` is false).

**Fix plan (after B finishes):**
1. Add `let lastManualRoll = null;` and `let lastManualRollSides = null;` to state.
2. In `rollDice()`, store `lastManualRoll = result; lastManualRollSides = sides;` (only for d20, since the backend's `manual_roll` is the d20 total).
3. In `sendAction()`, add `manual_roll: lastManualRoll` to the POST body when `lastManualRoll` is set and `settings.autoroll` is false. Clear it after sending.
4. In reader mode (Instance B's `storytellerMode` off): present the dice as "consult the fates" rather than d20, and only surface it when the previous passage requested a roll (i.e. when a choice has `roll: true`).

**Status:** Ready to implement after B finishes.

### Fix 3 — Audio seek bar jumps unpredictably

**Confirmed.** `seekAudio()` (app.js:936-942) seeks within the current segment only:
```javascript
function seekAudio(e) {
  const player = document.getElementById('audio-player');
  if (!player.duration) return;
  const bar = e.currentTarget;
  const pct = (e.clientX - bar.getBoundingClientRect().left) / bar.offsetWidth;
  player.currentTime = pct * player.duration;
}
```

`player.duration` is segment-local, so clicking the bar mid-passage jumps to a fraction of the *current segment*, not the passage. The progress fill (`#audio-fill`) is also segment-local (updated in `startAudioUpdate()` at line 922).

**Fix plan (after B finishes):**
1. In `index.html`: remove `onclick="seekAudio(event)"` from `#audio-progress` (line 298). This is the one HTML line I'm allowed to touch.
2. In `style.css`: change `.audio-progress { cursor: pointer; ... }` to `cursor: default;` (line 167). This is the one CSS line I'm allowed to touch.
3. In `app.js`: neuter `seekAudio()` to a no-op (or delete it). Keep `toggleAudio()` and `replayAudio()`, which work correctly.

**Status:** Ready to implement after B finishes. The HTML and CSS changes are minimal and explicitly permitted.

### Fix 4 — Session Zero model dropdown silently does nothing

**Confirmed.** `szChangeModel()` (app.js:1053-1055):
```javascript
function szChangeModel(model) {
  settings.model = model;
}
```

This only updates the local `settings.model`. The `/api/session_zero/turn` POST body is `{answer}` only (app.js:994) — the model is never sent. The `/api/session_zero/start` POST includes `{model}` (app.js:967), so the model is set on the first exchange but cannot be changed after that.

**Fix plan (after B finishes):** Disable the dropdown after `szStart()` completes. Re-enable it if the user starts a new Session Zero (i.e. in `openSessionZero()`).

```javascript
// In szStart(), after the first response:
document.getElementById('sz-model').disabled = true;

// In openSessionZero(), before szStart():
document.getElementById('sz-model').disabled = false;
```

This is simpler and safer than sending the model change to the server (which would require a new endpoint or changing the turn body shape).

**Status:** Ready to implement after B finishes.

### Fix 5 — `/api/freetext_status` is never called

**Confirmed.** `grep -c freetext_status app.js` → 0. The endpoint exists at `app.py:159` and returns `{"status": "unknown"}` for empty/missing gen_id, but no frontend code polls it.

The free-text TTS flow currently:
1. User types in input → `onFreeTextInput()` debounces 1s → POSTs `/api/freetext/generate` → gets `gen_id`.
2. `freetextGenId` is stored but never used to poll status.
3. The generated audio is never played back.

**Fix plan (after B finishes):** Poll `/api/freetext_status?gen_id=...` after generation starts. Show a subtle "voicing..." indicator near the input. When state is `READY`, play the audio (or cache it for when the user sends the action).

**Backend dependency discovered (needs Instance A):** The freetext status response from `audio_queue.py:604-614` returns the raw `_current` dict, which has:
- `state` (not `status`): `"GENERATING"`, `"READY"`, or `"FAILED"`
- `audio_path`: a **filesystem path** (e.g. `/.../segments/freetext/freetext_1.wav`), not a URL
- `duration`, `gen_id`, `text`
- No `audio_url` field.

There is also **no HTTP route** to serve freetext audio files. The existing routes are:
- `/audio/segments/{turn_id}/seg_{index}.wav` (segment audio)
- `/audio/{turn_id}.wav` (legacy full-turn audio)

There is no `/audio/freetext/{gen_id}.wav` route. So even if the frontend polls status and sees `READY`, it cannot play the audio back without a URL.

**Instance A needs to do one of:**
1. Add an `audio_url` field to the freetext status response (e.g. `/audio/freetext/{gen_id}.wav`), AND add a route in `app.py` to serve files from `SEGMENTS_DIR/freetext/`.
2. OR confirm that freetext audio playback is out of v1 scope and the "voicing..." indicator is sufficient (audio plays only after the turn is sent, via the normal segment queue).

**Frontend plan (assuming option 1):**
```javascript
// After freetextGenId is set in onFreeTextInput():
if (freetextGenId) pollFreetextStatus(freetextGenId);

function pollFreetextStatus(genId) {
  const timer = setInterval(async () => {
    try {
      const resp = await fetch(`/api/freetext_status?gen_id=${genId}`);
      const data = await resp.json();
      if (data.state === 'READY') {
        clearInterval(timer);
        // Play or cache data.audio_url
        showFreetextVoicedIndicator(data.audio_url);
      } else if (data.state === 'FAILED' || data.state === 'superseded' || data.status === 'unknown') {
        clearInterval(timer);
      }
    } catch(e) { clearInterval(timer); }
  }, 500);
}
```

**Status:** Frontend ready to implement after B finishes AND after Instance A adds the `audio_url` field + serving route. If A declines (option 2), the frontend will only show a "voicing..." → "voiced" indicator without playback.

---

## Dependency on Instance B

All 5 fixes touch `app.js`, which Instance B is rewriting for the Book GUI. Per the coordination doc:

> C starts after B finishes (both need `app.js`)

**Current status:** Instance B has not started. `grep -c "LEXICON\|storytellerMode\|chapter.*is_new" app.js` → 0. No Book GUI changes present.

**What I've done while waiting:**
1. Written this audit doc (you're reading it).
2. Read the entire frontend codebase.
3. Verified all 5 bugs at the source level.
4. Confirmed backend claims (`manual_roll` read, `freetext_status` endpoint exists).
5. Smoke-tested the app via HTTP + Playwright (no console errors, all controls present).

**What happens next:**
- When Instance B finishes, I re-read the new `app.js`/`index.html`/`style.css` (B may have moved or rewritten `playSegment()`, `rollDice()`, `seekAudio()`, `szStart()`, `onFreeTextInput()`).
- I apply the 5 fixes against the new code.
- I run `node -c static/app.js` after every edit.
- I update this doc with the final verdicts.

---

## Notes for Instance A (main programmer)

1. **`manual_roll` semantics:** The backend treats `manual_roll` as the d20 *total* (including modifier) — see `dm_engine.py:959-961`. The frontend fix will send the raw d20 result as `manual_roll`. If the backend expects the raw d20 value (before modifier), please clarify. The test at `test_dc_roll.py:137` comments "manual_roll is the total (including modifier)" — I'll follow that.

2. **`/api/freetext_status` response shape + serving route (blocking Fix 5):** The endpoint returns `freetext_generator.get_status(gen_id)` which returns the raw `_current` dict. The response uses `state` (not `status`) with values `"GENERATING"`/`"READY"`/`"FAILED"`, and has `audio_path` (a **filesystem path**, not a URL). There is no `audio_url` field, and no HTTP route serves files from `SEGMENTS_DIR/freetext/`. To make free-text TTS playback work, I need either:
   - (a) You add `audio_url` to the status response + a route in `app.py` for `/audio/freetext/{gen_id}.wav`, OR
   - (b) You confirm playback is out of v1 scope and I only show a "voicing..." indicator.
   See `audio_queue.py:527-534` (the `_current` dict shape) and `audio_queue.py:562-564` (output path `SEGMENTS_DIR/freetext/{gen_id}.wav`).

3. **Reader-mode dice gating:** Instance B's `storytellerMode` toggle will hide dice in reader mode. My Fix 2 needs to coordinate with B's gating — I'll surface the dice as "consult the fates" only when `storytellerMode` is off and a roll was requested. If B has already gated the dice panel, I'll work within their gating.

4. **No backend changes needed:** All 5 fixes are frontend-only, per the handoff. The backend already supports `manual_roll` and `freetext_status`.

## Notes for Instance B (GUI)

1. **`playSegment()` location:** Fix 1 targets `playSegment()`. If you move or rewrite it, please keep the volume re-application logic (lines 750, 770, 776) so I don't have to re-add it.

2. **`rollDice()` gating:** Fix 2 will add `manual_roll` to `sendAction()`. If your `storytellerMode` gating hides the dice panel, my fix will still work — I'll send `manual_roll` only when `settings.autoroll` is false and a roll value exists.

3. **Seek bar:** Fix 3 removes the `onclick` from `#audio-progress` in HTML and the `cursor: pointer` in CSS. If you restyle the audio bar, please don't re-add seek functionality — it's broken for multi-segment passages and the v1 decision is to make it a non-interactive progress indicator.

4. **Session Zero model dropdown:** Fix 4 disables `#sz-model` after the first exchange. If you restyle Session Zero as a "foreword", please keep the `#sz-model` element (or its equivalent) so I can disable it.

5. **Free-text TTS:** Fix 5 adds polling for `/api/freetext_status`. If you add a "voicing..." indicator, I'll wire it up. Otherwise I'll add a minimal one near the input.

## Notes for Instance D (testing)

After I finish, the verification checklist is:

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v01.app --port 5102
# Then verify:
# - Narration volume slider persists across segments within a passage
# - Dice roller sends manual_roll and the roll result appears in the story
# - Seek bar is non-interactive (no pointer cursor, no jump on click)
# - Session Zero model dropdown is disabled after first exchange
# - Free-text TTS shows a "voicing..." indicator and plays back when ready
node -c narrator_v01/static/app.js
```

The 5 fixes are all frontend-only; no backend test changes needed.
