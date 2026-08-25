# Instance C — UX Handoff (Audit Phase Complete)

**Created by:** Instance C (UX), 2026-08-24
**Status:** Audit complete. Code fixes blocked on Instance B (Book GUI).
**Audit doc:** `docs/V1-GUI-AUDIT.md` (read this for full control-by-control findings)

## What I've done

1. **Wrote `docs/V1-GUI-AUDIT.md`** — a complete walk of every UI control in the current app, with status (works / bug) and notes for each. This was the prerequisite task assigned to me while waiting for Instance B.

2. **Read the entire frontend codebase** — `app.js` (1252 lines), `index.html` (315 lines), `style.css` (250 lines).

3. **Verified all 5 bugs at the source level** — each fix in the handoff doc was confirmed against the actual code:
   - Fix 1 (volume slider): code path looks correct on static reading; needs live audio test to confirm the bug reproduces.
   - Fix 2 (dice roller): confirmed — `sendAction()` never sends `manual_roll`; backend reads it at `game_loop.py:639`.
   - Fix 3 (seek bar): confirmed — `seekAudio()` seeks within current segment only; `onclick` and `cursor: pointer` both present.
   - Fix 4 (SZ model dropdown): confirmed — `szChangeModel()` only updates local state; turn POST body is `{answer}` only.
   - Fix 5 (freetext_status): confirmed — `grep -c freetext_status app.js` → 0; endpoint exists but is never called.

4. **Smoke-tested the app** via HTTP + Playwright — no console errors, all controls present in the DOM.

5. **Discovered a backend dependency for Fix 5** — the freetext status response has no `audio_url` field, and there is no HTTP route to serve freetext audio files. See below.

## What's blocking me

**Instance B has not started.** All 5 fixes touch `app.js`, which B is rewriting for the Book GUI. Per the coordination doc, I must not edit `app.js` until B finishes — we'd get merge conflicts.

`grep -c "LEXICON\|storytellerMode\|chapter.*is_new" static/app.js` → 0 (no Book GUI changes present).

## What happens when B finishes

I will:
1. Re-read the new `app.js`/`index.html`/`style.css` (B may have moved or rewritten `playSegment()`, `rollDice()`, `seekAudio()`, `szStart()`, `onFreeTextInput()`).
2. Apply the 5 fixes against the new code.
3. Run `node -c static/app.js` after every edit.
4. Update `docs/V1-GUI-AUDIT.md` with final verdicts.

## The 5 fixes — one-line summary

| Fix | Bug | Fix | Backend needed? |
|---|---|---|---|
| 1 | Narration volume slider may reset mid-passage | Re-apply `settings.narrationVol` in `playSegment()` (may already be correct — needs live test) | No |
| 2 | Dice roller is cosmetic — never sends `manual_roll` | Store last d20 result, send as `manual_roll` in `sendAction()` POST body | No — backend already reads it |
| 3 | Seek bar jumps unpredictably in multi-segment passages | Remove `onclick` from HTML, `cursor: pointer` from CSS, neuter `seekAudio()` | No |
| 4 | Session Zero model dropdown silently does nothing after first exchange | Disable `#sz-model` after `szStart()` completes | No |
| 5 | `/api/freetext_status` is never called | Poll it after free-text generation, show "voicing..." indicator | **Yes — see below** |

## Backend request for Instance A (blocking Fix 5)

The freetext TTS flow is broken at the backend level, not just the frontend:

1. **`/api/freetext_status` response has no `audio_url`:** The endpoint returns `freetext_generator.get_status(gen_id)` which returns the raw `_current` dict (`audio_queue.py:527-534`). It has `audio_path` (a filesystem path) but no `audio_url`. The response also uses `state` (not `status`) with values `"GENERATING"`/`"READY"`/`"FAILED"`.

2. **No route serves freetext audio files:** The output path is `SEGMENTS_DIR/freetext/{gen_id}.wav` (`audio_queue.py:562-564`), but `app.py` only has routes for `/audio/segments/{turn_id}/seg_{index}.wav` and `/audio/{turn_id}.wav`. There is no `/audio/freetext/{gen_id}.wav` route.

**I need one of:**
- **(a)** You add `audio_url` to the freetext status response + a route in `app.py` for `/audio/freetext/{gen_id}.wav`. Then I can poll status, get the URL, and play the audio.
- **(b)** You confirm freetext playback is out of v1 scope. Then I'll only show a "voicing..." → "voiced" indicator without playback (the audio will play after the turn is sent via the normal segment queue).

Either is fine — just let me know which.

## Notes for Sonnet / Opus review

1. **Fix 1 may be a false alarm.** The handoff doc claims the volume slider "resets mid-passage," but static code reading shows `playSegment()` re-applies `settings.narrationVol` on every segment (lines 750, 770, 776). The bug may only manifest in a race condition between `player.play()` promise resolution and the fade-in. I'll verify with a live audio test before applying any fix — if it doesn't reproduce, I'll note it as a no-op.

2. **Fix 2 coordinates with Instance B's `storytellerMode`.** In reader mode (storytellerMode off), the dice should be presented as "consult the fates" and only surfaced when the previous passage requested a roll. I'll implement this within B's gating framework.

3. **Fix 3 is a v1 scope decision, not a bug fix.** The seek bar is broken for multi-segment passages, and proper cross-segment seeking is a real refactor. The decision (per Arie's "work fully or be removed") is to make it a non-interactive progress indicator for v1. This is documented in the handoff and the audit.

4. **Fix 4 is the simplest** — just `disabled = true` on the dropdown after the first exchange. No backend change, no UX complexity.

5. **Fix 5 has the backend dependency described above.** If Instance A chooses option (b), the fix is frontend-only and simple. If option (a), I need the `audio_url` field and route before I can wire up playback.

## Files I will touch (after B finishes)

- `glm-work/narrator_v01/static/app.js` — all 5 fixes
- `glm-work/narrator_v01/templates/index.html` — one line (remove `onclick` from `#audio-progress`, Fix 3)
- `glm-work/narrator_v01/static/style.css` — one line (change `cursor: pointer` to `cursor: default` on `.audio-progress`, Fix 3)

**Files I will NOT touch:** `game_loop.py`, `world_store.py`, `dm_engine.py`, `audio_engine.py`, `audio_queue.py`, `app.py` — these are Instance A's.

## Verification (after fixes are applied)

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v01.app --port 5102
# Then verify:
# - Narration volume slider persists across segments within a passage
# - Dice roller sends manual_roll and the roll result appears in the story
# - Seek bar is non-interactive (no pointer cursor, no jump on click)
# - Session Zero model dropdown is disabled after first exchange
# - Free-text TTS shows a "voicing..." indicator (and plays back if Instance A added the route)
node -c narrator_v01/static/app.js
```
