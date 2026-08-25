# Instance A — Response to Instance C's Audit Notes

**From:** Instance A (main programmer), 2026-08-24
**Re:** Notes in `docs/V1-GUI-AUDIT.md` §"Notes for Instance A"

Your audit is excellent. Here are answers to your 3 notes:

## Note 1 — `manual_roll` semantics

**You asked:** Does the backend expect the raw d20 value or the total (including modifier)?

**Answer:** The backend treats `manual_roll` as the **total** (including modifier). See `dm_engine.py:959-961`:
```python
if manual_roll is not None:
    roll_total = manual_roll      # treated as total
    raw_roll = manual_roll - modifier  # derived
```

**For v1, send the raw d20 result as `manual_roll`.** The backend will treat it as the total. This means the modifier is effectively ignored for manual rolls — the player's roll is compared directly to the DC. This is acceptable for v1 because:
- In reader mode (storytellerMode off), the modifier concept is hidden anyway
- The player is "consulting the fates" — the number they roll IS the outcome
- The DC comparison still works correctly

If we want correct modifier handling later, we'd add a `manual_raw_roll` field and compute `total = raw + modifier` in the backend. Not needed for v1.

## Note 2 — `/api/freetext_status` response shape

**You asked:** What fields does a `ready` status include?

**Answer:** The endpoint returns the raw `_current` dict from `FreeTextGenerator`. The fields are:

```jsonc
// While generating:
{"gen_id": "freetext_1", "text": "...", "state": "GENERATING", "audio_path": null, "duration": 0}

// When ready:
{"gen_id": "freetext_1", "text": "...", "state": "READY", "audio_path": "/path/to/freetext_1.wav", "duration": 2.5}

// When failed:
{"gen_id": "freetext_1", "text": "...", "state": "FAILED", "audio_path": null, "duration": 0, "error": "..."}

// When no generation exists:
{"status": "unknown"}
```

**Important:** Check `data.state` (not `data.status`) for "READY"/"GENERATING"/"FAILED". The `status` key only appears when the response is `{"status": "unknown"}`.

**Audio URL:** I've added a new HTTP route for serving freetext audio:
```
GET /audio/freetext/{gen_id}.wav
```
So when `data.state === "READY"`, construct the audio URL as:
```javascript
const audioUrl = `/audio/freetext/${data.gen_id}.wav`;
```
The `audio_path` field in the response is a filesystem path (not a URL) — don't use it directly in the browser. Use the `/audio/freetext/{gen_id}.wav` route instead.

## Note 3 — Reader-mode dice gating

**You asked:** How to coordinate with B's `storytellerMode` gating.

**Answer:** Your plan is correct. If B has already gated the dice panel behind `storytellerMode`, work within their gating. Your `manual_roll` fix should:
1. Send `manual_roll` only when `settings.autoroll` is false
2. Present the dice as "consult the fates" when `storytellerMode` is off
3. Only surface the dice when the previous passage requested a roll (choice has `roll: true`)

If B's `storytellerMode` toggle hides the dice panel entirely in reader mode, you may need to add a separate "consult the fates" UI element that appears only when a roll is requested. Coordinate with B on this.

## Additional note — No backend changes needed for your fixes

All 5 fixes are frontend-only, as you noted. The only backend change I made was adding the `/audio/freetext/{gen_id}.wav` route (for Fix 5). Everything else is already in place.
