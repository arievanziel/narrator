# v1 "Book Experience" — plan of record

**Author:** Opus, 2026-08-23 07:52
**Goal:** turn Narrator from a D&D web app with book-ish fonts into an *audiobook you
can steer*. Driven entirely by Arie's v1 bullet list (see `docs/V1-PLAN.md`).

**Resumability:** this file is written so a cheaper model can pick up any unfinished
task. Each task has: file(s), what to change, and how to verify. Tasks are ordered by
value. Check off with `[x]` as they land.

---

## Baseline verified at 07:45 (live API call, not assumed)

Ran a real `POST /api/newgame` against `openai/gpt-oss-120b`. Backend is in good shape —
procedural generation works, entities get created, chronicle is written. Confirmed
working: World Store, entity creation, DC-then-roll plumbing, audio segment queue,
guards, save/load, Session Zero backend.

**Five concrete defects found in that single response:**

1. **The DM spoke as the player character.** Output contained
   `[Vess] "I'm Vess, cartographer. I need a way through the ruins..."` — Vess is Arie.
   The system prompt forbids this (rule 3) and the model did it anyway on turn 1.
   Prompt rules are not enough; this needs a deterministic guard.
2. **Character sheet is still hardcoded.** A "disgraced cartographer" spawned with
   `Fighter`, `longsword/shield/chain mail`, `Health Potion, Torch, Waterskin, 50ft rope`,
   and fixed STR 16/DEX 12/... Arie: *"nothing should be hardcoded"*. This is the last
   big hardcoded island.
3. **`state.location` is empty** even though the store created `Sunken Spire` — the
   topbar shows `—`. Store→facade sync gap.
4. **Engine internals leak to the player:**
   `"Created: Mirel (created new: no match within policy window)"` is shown in the story
   feed. Unacceptable in a book.
5. **No chapter structure at all.** Output is one flat blob per turn, labelled with a
   roman-numeral *turn* mark. Arie explicitly wants foreword / introduction / chapter 1 /
   chapter 2, each with a scene-setting opening paragraph.

---

## Design decisions (decided — do not re-litigate)

### D1. Chapters are driven by the World Engine, not the LLM's whim
A new chapter begins when **the location changes** or the LLM explicitly requests one via
`[CHAPTER: title]`. Code owns the chapter counter and the chapter list; the LLM only
proposes a title and the opening paragraph. Same trust model as everything else.

### D2. Scene-setting is a distinct, longer prose block
New response section `[SCENE_SETTING]` — 3-6 sentences of place/mood/sensory description,
emitted **only** on a chapter opening. It is narration (goes to TTS as the narrator) and
renders with a drop cap. Normal turns omit it.

### D3. The lexicon is a presentation layer, one source of truth
All player-visible game jargon passes through a single map. Default = literary. A
**"Storyteller's notes"** toggle (default OFF) reveals mechanics. The World Engine keeps
using D&D-ish terms internally — we only translate at the edges.

| internal | player sees (default) |
|---|---|
| DM / Dungeon Master | the Narrator |
| Session Zero | Foreword |
| turn | passage |
| roll / dice / d20 | *hidden*; outcome shown as "as fortune had it…" |
| DC | *hidden* |
| HP | Condition |
| AC | *hidden* |
| Enemies | Present in this scene |
| Mechanics | Storyteller's notes |
| Inventory | Belongings |
| Chronicle | The story so far |
| Character sheet | Dramatis personae / Your character |
| Save/Load | Place bookmark / Resume reading |
| New game | New book |

### D4. Nothing about the character is hardcoded
Class, stats, equipment, and starting belongings are generated at book start from the
persona/setting, via a `[CHARACTER]` block on the opening turn. Code validates and
clamps; the LLM proposes.

### D5. Everything visible works, or it goes
Audit every control. Anything not wired gets removed rather than left as decoration.

---

## Task list

### P1 — Book structure (backend)  `dm_engine.py`, `world_store.py`, `game_loop.py`
- [ ] **P1.1** Add `[CHAPTER]` and `[SCENE_SETTING]` to the response format + system
      prompt. `[CHAPTER]` is `NONE` or a title string. Bump `PROMPT_VERSION`.
- [ ] **P1.2** `Chapter` dataclass + `chapters: list[Chapter]` on WorldStore
      (`number`, `title`, `scene_setting`, `start_turn`, `location_id`).
      `maybe_start_chapter()` — opens one on location change or explicit `[CHAPTER]`.
- [ ] **P1.3** Parse both sections; return `chapter` (`{number,title,scene_setting,is_new}`)
      in the `/api/turn` and `/api/newgame` payloads.
- [ ] **P1.4** `GET /api/chapters` for the table of contents.
      Verify: `curl /api/chapters` after 2 turns lists ≥1 chapter.

### P2 — Kill the last hardcoding  `dm_engine.py`, `game_loop.py`
- [ ] **P2.1** `[CHARACTER]` block on the opening turn: class/vocation, 6 stats,
      equipment, 3-5 belongings, max HP — all derived from persona + setting.
      Validate + clamp in code (stats 3..18, HP 6..20).
- [ ] **P2.2** `make_initial_state(procedural=True)` must produce an *empty* sheet;
      no default longsword/potion/rope. Applied from `[CHARACTER]`.
- [ ] **P2.3** Sync `location` (and light/time) from the store into the facade so the
      header is never empty.
      Verify: `grep -c "Health Potion" dm_engine.py` == 0; new game shows a persona-
      appropriate kit.

### P3 — Guards  `world_store.py`, `game_loop.py`
- [ ] **P3.1** `player_voice_guard()` — any `[<pc_name>]` dialogue segment in `[STORY]`
      is a violation. Strip the segment and log it; do not spend an LLM call re-rolling
      (cheap + deterministic beats a regeneration).
- [ ] **P3.2** Player-facing change log: translate engine strings
      (`"created new: no match within policy window"`) into either literary phrasing or
      nothing. Raw strings stay in the storyteller's-notes view only.

### P4 — Book GUI  `templates/index.html`, `static/app.js`, `static/style.css`
- [ ] **P4.1** `LEXICON` object in `app.js` + `applyLexicon()` on load; `storytellerMode`
      setting (default false) persisted to `localStorage`.
- [ ] **P4.2** Replace the stat topbar with a book header: book title (left),
      current chapter (centre), controls (right). Stats only in storyteller mode.
- [ ] **P4.3** Story feed rendered as book pages: chapter headings (`Chapter One` +
      title, small caps, rule), scene-setting paragraph with drop cap, narration as
      justified prose, dialogue indented. Remove the roman-numeral turn marks.
- [ ] **P4.4** Left panel → "Your character" (Condition, Belongings, Bearing) +
      "The story so far" (table of contents, click to scroll to chapter).
- [ ] **P4.5** Choices restyled as a reader's prompt, not a quiz. Hide the 🎲 unless
      storyteller mode.
- [ ] **P4.6** Intro screen → **Foreword**: book-cover styling, literary labels.

### P5 — GUI audit (everything works or is removed)
- [ ] **P5.1** Walk every control; list verdict in `docs/V1-GUI-AUDIT.md`.
- [ ] **P5.2** Fix or remove. Known suspects: narration volume slider, seek bar,
      replay, music source, voice assignment, dice roller wiring, theme sepia.

### P6 — Audio (only if time)
- [ ] **P6.1** Confirm segment streaming genuinely outruns playback; measure.
- [ ] **P6.2** SFX: currently ~absent from `narrator_v01`. Cheapest real win is a
      per-chapter ambience bed keyed off `[SCENE]`, not per-line SFX.

---

## Verification commands

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v01.app --port 5150          # run
python -m pytest narrator_v01/ -q 2>/dev/null || \
  for t in narrator_v01/test_*.py; do python -m "${t%.py}" ; done
node -c narrator_v01/static/app.js               # JS syntax
python3 -c "import py_compile;[py_compile.compile(f,doraise=True) for f in ['narrator_v01/dm_engine.py','narrator_v01/game_loop.py','narrator_v01/world_store.py','narrator_v01/app.py']]"
```

Playwright screenshots: `glm-work/shots/` (see `glm-work/shoot.cjs`).

---

## Progress log

- 07:52 — plan written, baseline defects confirmed by live API call.
