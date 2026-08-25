# Instance C — UX: GUI Audit Fixes

**Created by:** Instance A (main programmer), 2026-08-24
**Source:** `docs/GLM-V1-FINISH-INSTRUCTIONS.md` TASK 2
**Prerequisite:** Wait for Instance B (GUI) to finish TASK 1 first — you both need `app.js`.

## Your files (ONLY touch these)

- `glm-work/narrator_v01/static/app.js`
- `glm-work/narrator_v01/templates/index.html` (minimal — one `onclick` removal)
- `glm-work/narrator_v01/static/style.css` (minimal — cursor change)

**Do NOT touch:** `game_loop.py`, `world_store.py`, `dm_engine.py`, `audio_engine.py`, `audio_queue.py`, `app.py` — Instance A is working on those.

## Timing

**You are blocked on Instance B.** B is rewriting `app.js` for the Book GUI (TASK 1). Do not start editing `app.js` until B is done — you'll get merge conflicts.

### While waiting (do this now):

1. **Write `docs/V1-GUI-AUDIT.md`** — walk every control in the current UI and document its status. Use the audit results from Opus below as your starting point, then verify each one yourself by running the app.

2. **Read the codebase** to understand each fix before you start coding.

## The 4 fixes (after B finishes)

### Fix 1 — Narration volume slider resets mid-passage

**Problem:** `changeNarrationVol()` sets `player.volume`, but each new queue segment loads at default volume, so it resets mid-passage.

**Fix:** Re-apply `settings.narrationVol` inside `playSegment()` every time a segment `src` is set. Client-side only; no backend change needed.

**Note:** Instance B may have already moved/rewritten `playSegment()`. Find it in the current `app.js` and apply the fix there.

### Fix 2 — Dice roller buttons are cosmetic

**Problem:** `rollDice()` appends *"I rolled a 14 on d20"* as free text and nothing more. `game_loop.handle_turn()` already accepts a `manual_roll` field that the frontend never sends.

**Fix:** Store the last d20 result and send it as `manual_roll` in the `sendAction()` POST body. This is the "manual dice-rolling UI should be working in v1" requirement — it is 90% built and just not connected.

In reader mode (storytellerMode off), present it as *"consult the fates"* rather than a d20, and only surface it when the previous passage requested a roll.

**Backend status:** `handle_turn()` already reads `data.get("manual_roll")` and passes it to `dm_turn_dc_roll()`. No backend change needed — just send the field.

### Fix 3 — Audio seek bar jumps unpredictably

**Problem:** `seekAudio()` only seeks within the *current segment*, so clicking it during a multi-segment passage jumps unpredictably. Proper cross-segment seeking is a real refactor.

**Fix (v1 scope):** Make the bar a **non-interactive progress indicator** — remove the `onclick` from the HTML (`index.html` line ~298), drop the pointer cursor in CSS, remove or neuter `seekAudio()`. Keep play/pause and replay, which do work.

Per Arie's "work fully or be removed": don't leave broken seek functionality.

### Fix 4 — Session Zero model dropdown silently does nothing

**Problem:** Changing the model dropdown mid-Session-Zero conversation silently does nothing.

**Fix:** Either disable it after the first exchange, or send the change to the server. Disabling is simpler and safer — add `disabled` attribute after `szStart()` completes, re-enable if user starts a new Session Zero.

### Also — `/api/freetext_status` is never called

**Problem:** The endpoint exists in `app.py` but no frontend code polls it.

**Fix:** Either poll it in `onFreeTextInput()` to show generation progress, or delete the endpoint from `app.py` and the freetext_status polling stub. Polling is better UX — show a subtle "voicing..." indicator near the input while free-text TTS is generating.

**Note:** If you delete the endpoint, coordinate with Instance A — `app.py` is A's file. Prefer polling over deletion.

## Ground rules

- Run `node -c static/app.js` after every JS edit.
- Write your findings/verdicts into `docs/V1-GUI-AUDIT.md` as you go.
- Never write lines starting with `>` in any doc — those are Arie's.
- Do not touch `sonnet-work/`.
- If a design question comes up, pick the option that looks more like a book and less like a game, note the choice, and move on.

## Verification

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v01.app --port 5102
# Then verify:
# - Narration volume slider persists across segments within a passage
# - Dice roller sends manual_roll and the roll result appears in the story
# - Seek bar is non-interactive (no pointer cursor, no jump on click)
# - Session Zero model dropdown is disabled after first exchange
node -c narrator_v01/static/app.js
```
