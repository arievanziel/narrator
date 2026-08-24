# GLM — finish v1. Handover from Opus, 2026-08-24

Opus ran out of quota part-way. **The backend book layer is done, committed and
tested (74/74). The GUI is not.** Everything below is specified tightly enough to
build without further architecture decisions. If something here contradicts an older
doc, this file wins.

Design rationale lives in `docs/V1-BOOK-EXPERIENCE-PLAN.md` (read §"Design decisions"
once before starting). Commit `1474895` is the backend work.

---

## What is DONE (do not redo)

| Thing | Where |
|---|---|
| `[CHAPTER]` + `[SCENE_SETTING]` response sections, prompt v11 | `dm_engine.py` SYSTEM_PROMPT, `parse_response()` |
| `Chapter` model, code-owned numbering, schema v2 + migration | `world_store.py` `Chapter`, `maybe_start_chapter()` |
| `GET /api/chapters` | `app.py` |
| `[CHARACTER]` block → procedural character sheet (no more hardcoded longsword/chain mail/potion) | `dm_engine.py` `apply_character_block()`, `make_initial_state(procedural=True)` |
| `player_voice_guard()` — strips dialogue written for the listener's own character | `world_store.py` |
| `reader_notes()` — keeps engine strings out of the story feed | `game_loop.py` |
| Narrative voice directive (third-person past default) | `dm_engine.py` `voice_block()`, `state.narrative_voice` |
| All three wired into every turn path | `game_loop.py` `finalize_passage()` |

**New fields now in `/api/newgame` and `/api/turn` responses — the GUI must use these:**

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

Verified live: a "disgraced cartographer" now gets STR 8 / INT 14 and a sketchbook,
quill, lens and broken sextant. Chapter One came back titled "Silted Sanctum" with a
five-sentence scene-setting paragraph.

---

## TASK 1 — Book GUI (the big one, highest value)

Files: `templates/index.html`, `static/app.js`, `static/style.css`. Backend needs no
changes. **This is the single thing standing between the current state and Arie's v1.**

Arie's words: *"i would like to see the app work like a book, all from within the same
book style gui with a foreword, introduction, chapter 1, chapter 2.."* and *"for the
user all terms related to D&D, like 'DM' or 'turn' or 'roll', should only be visible if
specifically turned on... If in doubt always default to terminology from literature,
books, libraries, etc.. not roleplaying games."*

### 1a. Lexicon layer
Add to `app.js` a single `LEXICON` object and a `storytellerMode` boolean (default
`false`, persisted in `localStorage`). Every player-visible string goes through it.
Add one toggle in settings: **"Show storyteller's notes"**.

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

When `storytellerMode` is off: hide the roll-result block, hide the `🎲` on choices,
render `reader_notes` instead of `changes`, and hide AC/stats. When on: show everything
exactly as today. **Do not delete the existing roll UI — gate it.**

### 1b. Replace the stat topbar
Today's `HP | AC | Turn | Location | Mood` bar is the most game-like thing on screen.
Replace with a book header: book/campaign title left, **"Chapter One · Silted Sanctum"**
centre, controls right. Stats move into the left panel and only appear in storyteller
mode. Chapter numbers spelled out in words, not digits or roman numerals.

### 1c. Render the story as a book
In `addStoryTurn()` (`app.js:308`):
- **Remove** the roman-numeral turn mark (`app.js:316-319`) — it is a turn counter
  wearing a costume.
- When `data.chapter && data.chapter.is_new`: insert a chapter heading —
  small-caps `CHAPTER TWO`, then the title in a larger serif, then a thin rule.
- Then render `data.scene_setting` as one justified paragraph **with a drop cap** on the
  first letter (`.scene-setting::first-letter`). This is the mood-setting paragraph Arie
  asked for. It is also narration — see Task 3.
- Narration: justified prose, generous leading, no speaker label.
- Dialogue: indented, speaker name in small caps italic.
- The existing three themes already work and are visually distinct (verified) — keep.

### 1d. Panels
- Left panel becomes **"Your character"**: name, vocation, Condition bar, Belongings,
  Carried. Stats only in storyteller mode. Refresh it from `GET /api/state` (that
  endpoint is currently dead code — this makes it live).
- Add **"The story so far"**: a table of contents from `GET /api/chapters`, each entry
  clickable to scroll to that chapter's heading (give headings `id="chapter-N"`).
- Chronicle entries stay, retitled.

### 1e. Foreword
Restyle the intro overlay as a book cover / foreword page. Rename "Begin Session Zero"
→ **"Read the foreword"**, "Quick Start" → **"Open the book"**. Same handlers, same
endpoints — presentation only.

---

## TASK 2 — GUI audit fixes ("work fully or be removed")

A full control-by-control audit was done. **16 of 21 controls work end to end.** Four
need fixing, and they are all small:

1. **Narration volume slider** — `changeNarrationVol()` sets `player.volume`, but each
   new queue segment loads at default volume, so it resets mid-passage. Fix: re-apply
   `settings.narrationVol` inside `playSegment()` (`app.js:747`) every time a segment
   `src` is set. Client-side only; no backend change needed.
2. **Dice roller buttons** — currently cosmetic. `rollDice()` (`app.js:186`) appends
   *"I rolled a 14 on d20"* as free text and nothing more. `game_loop.handle_turn()`
   already accepts a `manual_roll` field that the frontend never sends. Fix: store the
   last d20 result and send it as `manual_roll` in the `sendAction()` POST body. This is
   the "manual dice-rolling UI should be working in v1" requirement — it is 90% built
   and just not connected. In reader mode, present it as *"consult the fates"* rather
   than a d20, and only surface it when the previous passage requested a roll.
3. **Audio seek bar** — `seekAudio()` only seeks within the *current segment*, so
   clicking it during a multi-segment passage jumps unpredictably. Proper cross-segment
   seeking is a real refactor. Per Arie's "work fully or be removed": for v1 make the
   bar a **non-interactive progress indicator** (remove the `onclick`, drop the pointer
   cursor). Keep play/pause and replay, which do work.
4. **Session Zero model dropdown** — changing it mid-conversation silently does nothing.
   Either disable it after the first exchange or send the change to the server.

Also: `/api/freetext_status` is never called by anything. Either poll it or delete it.

Write your findings/verdicts into `docs/V1-GUI-AUDIT.md` as you go.

---

## TASK 3 — Audio for the new book structure

1. `scene_setting` **must be spoken**. It is currently returned but not sent to TTS —
   prepend it to the segment list as a `narrator` segment before the `[STORY]` segments,
   in `game_loop.finalize_passage()` or where `generate_audio_queue()` is called. Without
   this, the chapter opening is silent, which defeats the point.
2. Verify generation genuinely outruns playback and **measure it** (Arie: *"live
   generated faster than playback"*). Log per-segment generate-time vs audio duration
   for a 10-passage session and put the numbers in the handoff. If generation loses,
   say so plainly rather than claiming success.
3. SFX are essentially absent from `narrator_v01`. Do **not** build per-line SFX. The
   cheap real win is a **per-chapter ambience bed** keyed off `chapter.mood`, crossfaded
   at chapter boundaries — which the new chapter events now make easy.

---

## TASK 4 — Known gaps worth closing

- **`enter_scene()` is never called from the live turn flow.** Consequence:
  `chapter.location_id` / `location_name` come back empty, `state.location` stays `""`,
  and the presence-and-liveness guard can't fire because `current_scene` is `None`. Fix:
  call `world_store.enter_scene()` when the DM's `ENTITY_NEW:location` or a location
  change is detected, and put the returned "since you were last here" digest into the
  next prompt. **This unlocks three features that are already built but dormant** —
  highest-value backend task remaining.
- Chapter `start_turn` is 0 for the opening passage (turn counter increments after
  `finalize_passage`). Cosmetic; fix if convenient.
- Long-session soak (30+ passages) still not done.

---

## Ground rules

- Run `for t in test_*.py; do python -m narrator_v01.${t%.py}; done` before every
  commit. All 74 must pass. Add tests for the lexicon and chapter rendering.
- `node -c static/app.js` after every JS edit.
- Never write lines starting with `>` in any doc — those are Arie's.
- Do not touch `sonnet-work/`.
- If a design question comes up that this file doesn't answer, **pick the option that
  looks more like a book and less like a game**, note the choice, and move on.
