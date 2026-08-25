# v9-circle-buttons — Polish Instructions (Sonnet, visual review)

I reviewed actual screenshots (`glm-work/notes/gui_v2/screenshots/v9-circle-buttons_*.png`)
pixel-by-pixel, not just the HTML/CSS source. v9 is a strong baseline — clean book-like
typography, restrained color, good information hierarchy. Here's what's actually wrong,
grounded in what I saw, plus a code-quality ask.

## Issue 1: Side-panel toggle circles aren't anchored to the panel (confirms Arie's report)

In `v9-circle-buttons_left-panel.png`: the circular ☰ toggle sits at the top-left,
vertically straddling the boundary between the top status bar and the panel below,
rather than sitting flush with the panel's own top edge. It reads as "floating near the
corner" rather than "the tab that opens this specific panel."

**Fix:** anchor the toggle's vertical position to `top: var(--topbar-h)` exactly (the
same Y as the panel's own top edge), not to a fixed pixel offset independent of the
topbar. When the topbar is hidden, the toggle should move up to `top: 0` in lockstep —
check this state transition specifically, it's the likely source of the misalignment
Arie noticed (works in one topbar state, drifts in the other).

## Issue 2: Bottom double-bar — audio bar + footer bar compete for the same space

In `v9-circle-buttons_everything.png`: there are two stacked bottom rows — the audio bar
(play/pause, progress, "NARRATOR · TURN IV", time, skip, then a cluster of circle
toggle icons on its far right) directly above a second thin footer row (location/time,
"auto-saved", TTS engine name). Both rows have their own right-aligned metadata, which
reads as visually redundant and is exactly what Arie flagged as "doesn't work well."

**Fix — pick one, don't keep both:**
- **Option A (recommended):** merge the footer info into the audio bar itself as a
  third text cluster (e.g., far-left: play controls; center: now-playing label; far
  right: split into two small text groups — "turn info" and "session status" — instead
  of a whole separate row). One row, not two.
- **Option B:** keep the footer bar but make it purely session metadata (no controls,
  no icons) and drop it entirely when the audio bar is expanded, so there's never two
  bottom rows visible at once.

Also: the panel/bar toggle circles currently live in the audio bar's expanded state
(bottom-right) AND separately in the top bar (top-right) — that's the same controls
in two different places. Pick one home for the panel/bar toggles (I'd recommend the
side-anchored tabs per Issue 1, not duplicated into the audio bar) and remove them from
the audio bar entirely — it should only contain playback controls.

## Issue 3: Code quality — 14 nearly-identical 47-51KB HTML files

Every `vN-*.html` file duplicates the same ~1200 lines of CSS/JS with only the control
UI (ribbons/dog-ears/circles/etc.) actually differing. Fine for rapid exploration, not
fine to carry into the real app.

**Before wiring the chosen design into `narrator_v0/app.py`:**
- Extract the shared CSS (typography, layout grid, panel/topbar/audio-bar base styles —
  everything that's identical across all 14 files) into one stylesheet.
- Extract the shared JS (state toggling, audio simulation) into one module.
- The control-UI-specific bits (circle buttons vs. ribbons vs. dog-ears) become a small,
  isolated CSS/JS layer on top of the shared base — this is the only part that should
  differ between "variants," and it's the only part relevant once one is chosen.
- Once wired into `narrator_v0/app.py`, this becomes real Jinja/template + static CSS/JS
  files, not one inline HTML blob — this is the "modern, professionally coded" ask.

## What to keep as-is (don't touch)

- The reading-area typography and layout (serif font, line spacing, chapter/turn
  dividers) — this is the best part of the design and matches Arie's stated preference
  for "a modern book" feel.
- The topbar's HP/AC/turn/location/time stat display — clean, unobtrusive, correct
  information for a game that's mostly narration (see Arie's scope note: DM mechanics
  should be visible but not interactive-by-default).
- The settings panel layout (theme/contrast/typography/Story AI/voice sections) —
  good grouping, no changes needed there.

## Priority order

1. Fix Issue 1 (toggle anchoring) — small, well-defined CSS fix.
2. Fix Issue 2 (bottom bar consolidation) — needs a real layout decision (Option A vs B
   above), pick one and implement.
3. Do the code-quality extraction (Issue 3) **only once Arie confirms v9 (or whichever
   variant) is the final pick** — no point refactoring something that might still change.
4. Wire the polished, extracted version into `narrator_v0/app.py` as the real GUI.

Per Arie: "for a v0.1 app we can already start using the current gui" — meaning it's
fine to wire the *current* (imperfect) GUI into the live app now and polish in place,
rather than blocking the whole app on this being perfect first.
