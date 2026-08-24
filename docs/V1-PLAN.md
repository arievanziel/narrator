# Narrator — Path to v1

**Status check performed by Sonnet, 2026-08-21**, by actually opening the Playwright
screenshots/videos and reading `GLM-V01-HANDOFF.md` against them — not just trusting the
doc. Verdict: **this is a real, working app**, not a demo. Full loop confirmed visually:
intro → story generation → rules-lawyer enforcement (visibly shown to the player,
exactly per Arie's "automatic but visible" philosophy) → TTS + music → choices → repeat.
70 audio recordings, 13 Playwright screenshots, 2 video recordings, 30+ playtests.

## What I verified directly (not just read about)

- **Intro screen**: clean, on-brand, all fields working (name, style, setting, persona,
  atmosphere, inspiration, dice mode).
- **Game loop**: HP/AC/turn/location/mood topbar, character/enemies/inventory/dice-roller/
  chronicle side panel, numbered choices with keyboard shortcuts, free-text input.
- **Rules lawyer working live, visibly**: a screenshot shows
  `[REJECTED — no roll evidence]` displayed inline in the story feed when the DM model
  tried to apply enemy state changes without valid roll evidence. This is the "control
  NPC" guard from Phase 1, confirmed working in the actual running app, not just a unit
  test — and it's shown to the player per Arie's transparency requirement. This is
  exactly right.
- **Settings panel**: model picker with live free/paid indicators (green=free: Gemini
  Flash-Lite, Groq GPT-OSS 120B/20B; yellow=paid: Claude Haiku 4.5, Claude Sonnet 5),
  auto-roll toggle, TTS engine + speed, music source + volume, budget tracker
  ($0.00/$5.00 cap shown), save/load/new-story buttons, theme selector.
- **Claude/Anthropic integration**: code is in place and wired correctly (confirmed via
  `outputs/dm_test_anthropic_claude-haiku-4-5.json`) — it just hasn't been tested yet
  because the Anthropic account has insufficient credits (a real API error, not a bug).

## Bug found (worth fixing before calling this v1)

**Sepia theme doesn't look distinct from dark theme.** I compared
`outputs/playwright/09_theme_sepia.png` and `10_theme_dark.png` pixel-by-pixel — they're
nearly identical (same near-black background, same accent color). Sepia should be a warm
parchment/tan palette, not another dark variant. Either the theme CSS isn't hooked up
correctly or the test didn't wait for the theme switch to apply before capturing.

> in the live app, the sepia theme looks fine, it's just the test that didn't wait for the theme to apply or made a mistake with creating the screenshots. Worth to double check why this happened, but the app is fine for now.

## Repo hygiene (fixed directly, no need for GLM)

`node_modules/` (18MB, Playwright) and the `outputs/playwright/*.webm` + `outputs/
screenshots/*.png` test artifacts weren't gitignored — I added them to `.gitignore` just
now so they don't bloat the repo on the next commit. Nothing else needed here.

> very good, we need to keep any uploads and downloads to a minimum as long as i'm still in Laz mountain hut with a very limmited 5g connection.

## Is it time for Opus/Fable?

**Almost, not quite.** The trigger condition I set earlier was "rules-lawyer fixes +
expanded trickster scenarios." The fixes are done and confirmed working live. The
*expanded* scenarios (long-context attacks after 10+ turns, gradual HP inflation,
fabricated items after many turns) were proposed but not yet added — the original
10-scenario suite is still what's running. **Recommend: have GLM add those expanded
scenarios first (cheap, well-specified), then trigger an Opus review** of the full
rules-lawyer + state schema. Close, but not there yet.

## Definition of "fully working v1"

Proposing this as the bar — confirm or adjust:
1. A full extended session (~30+ turns) runs without crashing or requiring a server restart.
2. Opening wizard (foreword-style guided setup) replaces the current single-form intro.
3. Sepia theme bug fixed; all three themes visually distinct.
4. At least 2 story models and 2 TTS engines reliably selectable and working mid-session (already mostly true — needs the extended-session stress test to confirm "reliably").
5. Save/load works across a real session, not just unit-tested.
6. GUI polish pass applied (side-panel tab anchoring, single unified bottom audio bar, per my earlier `GUI-V9-POLISH-INSTRUCTIONS.md` — now targeting the live `narrator_v01/app.py` templates, not the static mockups).
7. Arie has personally played a real session end-to-end and is satisfied.

> Direct playing audio for all narration, live generated faster than playback. Including the sfx and music.

> The story should feel alive and responsive, with dynamic music and sound effects that enhance the atmosphere and immerse the player in the world.

> The npc's should not be scripted, now it always starts with the same two goblin npc's. flavoured differently yes, but still hard-coded and not live generated. Any world aspect, npc, location, should be generated on the fly and nothing should be hardcoded.

> The world should be procedurally generated, with no hardcoded locations or items.

> The 'DM engine' need not strictly be D&D 5e, it can be any rules system or even a custom one. But the core mechanics should be well-defined and consistent. The 'World engine' or whatever we call it, should keep detailled track of anything that is generated, never trust the llm's or ai running the narration to 'remember' correctly what happened before. Any detail should be stored and retrieved reliably. 

> The manual dice-rolling UI should be working in v1.

> deep character management and full character sheet management including progress tracking and full inventory management should be working in v1.

Not required for v1 (per Arie's "keep it simple" scope note): multi-session support, mobile/responsive layout, network deployment. These are real "later phase" items GLM correctly did not build yet.

## Scope update, 2026-08-21 (after Arie's detailed answers) — this is bigger than v0.4

Arie's answers materially expand the target. Three new architecture documents exist to
prepare this for GLM execution — **honesty note**: I designed all three myself, and I'm
confident in two of them (audio streaming, Session Zero — well-understood patterns). The
third (World Engine — persistent, procedurally-generated, LLM-can't-be-trusted-to-
-remember state) is a genuine "get it right once" architecture decision where I'm
recommending a second opinion before GLM builds heavily on it. See
`sonnet-work/OPUS-BRIEF-WORLD-ENGINE.md` — ready to launch, Arie's call on timing/cost.

- **`docs/WORLD-ENGINE-DESIGN.md`** — replaces today's flat `GameState` with a proper
  entity store (NPCs/locations/items/factions/quests), procedural generation (no
  hardcoded goblins), and deterministic DC-then-roll rules enforcement (the LLM sets a
  difficulty, the roll — not the LLM — decides the outcome).
- **`docs/AUDIO-STREAMING-DESIGN.md`** — live, faster-than-playback narration, including
  pre-generating choice audio before the player picks, and voicing free-text input as
  the player types.
- **`docs/SESSION-ZERO-DESIGN.md`** — replaces the static intro form with a live,
  narrated DM-conversation onboarding (reuses the same turn-loop infrastructure).

## Status update, 2026-08-24 (Opus) — the book layer

Arie's later v1 bullets (book structure with foreword/chapters, per-chapter scene-setting
paragraphs, literary terminology by default, audiobook-first, no hardcoding, "every
element works or is removed") are a real reframe, not polish. **The backend half of that
reframe is now built, tested and committed** (`1474895`): chapters with code-owned
numbering, `[SCENE_SETTING]` prose, procedurally generated character sheets (the last
hardcoded island — no more default longsword and chain mail), a deterministic guard
stopping the narrator speaking for the player, and a reader-safe mechanics log.
74/74 tests pass; verified live against Groq GPT-OSS 120B.

**The GUI half is not built** — the app still renders a game UI over a book engine.
That is now the single biggest gap to v1.

- Plan and rationale: `docs/V1-BOOK-EXPERIENCE-PLAN.md`
- **Execution instructions for GLM: `docs/GLM-V1-FINISH-INSTRUCTIONS.md`** ← start here
- World Engine review (answers the three open questions): `docs/WORLD-ENGINE-REVIEW-OPUS.md`

Three findings that change assumptions elsewhere in this plan:
1. **`enter_scene()` is never called from the live turn flow**, so three already-built
   features are dormant: location tracking, the "since you were last here" digest, and
   the presence-and-liveness guard. Cheapest high-value backend fix remaining.
2. **A GUI audit found 16 of 21 controls work end to end.** The four that don't are all
   small fixes, and one of them *is* the "manual dice-rolling UI" v1 requirement — it's
   90% built and simply never sends `manual_roll` to the server.
3. The DM broke "never act for the player" on turn 1 despite the prompt forbidding it.
   Prompt rules are not enforcement; that guard is now code.

## Versioning plan — corrected 2026-08-22 after Opus's review

**Opus found a real dependency the original plan missed: audio streaming and DC-then-roll
are NOT independent.** DC-then-roll makes contested actions two sequential LLM calls,
which roughly doubles worst-case latency — acceptable *only* if the segment-queue audio
pipeline already exists to hide it behind playing audio. Building DC-then-roll first
would make the app feel twice as slow until audio streaming catches up. See
`docs/WORLD-ENGINE-REVIEW-OPUS.md` §2 and §9 for the full reasoning — the sequence below
reflects it.

The app is currently at **v0.3** (per `GLM-V01-HANDOFF.md`'s title — authoritative over
the ambiguous mix of v0.1/v0.2 commit messages before it).

| Stage | Focus | Depends on | Owner |
|---|---|---|---|
| **v0.3.5** | **File restructuring** (`app.py` split — see below). Do this before more parallel work lands on the current monolith. | Nothing | one instance, blocks nothing else once started |
| **v0.4a** | Audio segment queue (`AUDIO-STREAMING-DESIGN.md`) — **prerequisite**, not parallel, to v0.4b | v0.3.5 | Instance B |
| **v0.4b** | DC-then-roll two-call flow + seeded RNG + resolution ledger + manual dice UI | v0.4a (latency-hiding) | Instance A (+C for UI) |
| **v0.4c** | `world_store.py` standalone (Entity/Scene/links/validation/atomic persistence/`resolve_or_create`) — no `app.py` changes yet, unit-tested in isolation | v0.3.5 | Instance A |
| **v0.4d** | `GameState` becomes a thin facade over `WorldStore` — behavior-neutral refactor, provable via transcript replay | v0.4c | Instance A |
| **v0.5a** | Context assembler (stable/volatile split, directory, scored working set, token budgets); fix the `history[-10:]` cache-breaking bug | v0.4d | Instance A |
| **v0.5b** | Consistency guard pass + `[RECALL]` loop + `[ENTITY_UPDATE]`/revisions | v0.5a | Instance A |
| **v0.5c** | Procedural opening — kill the hardcoded goblins, seed from `campaign_meta` via `propose_entity()` | v0.4c (can pull forward on a stub store if it doesn't destabilize) | Instance A |
| **v0.6** | Session Zero conversational wizard + voice assignment screen | v0.5c for full integration, UI can be stubbed earlier | Instance C |
| **v0.7** | Full character sheet + inventory + progression management UI | v0.4c (entity model must exist) | Instance C |
| **v0.8** | Audio polish: crossfade, loudness normalization, adaptive ducking, fix non-working volume sliders | v0.4a | Instance B |
| **v0.9** | Long-session stability pass, expanded/fake-LLM trickster tests, golden-transcript regression harness, Anthropic testing | Everything above | Instance D |
| **v1.0** | Arie has played multiple full sessions across all the above and is satisfied | — | — |

This is a dependency graph more than a strict queue — v0.4c/d (World Engine store) and
v0.4a/b (audio+rules) can run in parallel on different files once v0.3.5 is done, since
they don't touch each other until v0.4d's facade work.

## v0.3.5 — file restructuring (do this first, blocks nothing else)

**The problem, with numbers:** `narrator_v01/app.py` is 1,673 lines. Roughly 1,000 of
those lines (177–1240) are a single Python string literal (`HTML_PAGE`) containing all
the HTML/CSS/JS inline, plus the HTTP handler logic in the same file. Every planned
instance (A: rules/world engine, B: audio, C: Session Zero/character sheet UI) needs to
touch this file. That's a merge-conflict machine, and it's the same "extract shared
code before building more on top" lesson from the GUI mockup phase, just now in
production code.

**Target module layout** (standard separation: HTTP layer / domain logic / presentation
— no new frameworks, no new dependencies, consistent with the bandwidth constraint):

```
narrator_v01/
  app.py              # HTTP server + routing ONLY — thin, delegates everything else
  templates/
    index.html         # the actual page structure
  static/
    style.css           # extracted from the HTML_PAGE string
    app.js               # extracted from the HTML_PAGE string
  game_loop.py         # turn orchestration: the two-call DC-then-roll flow, calls into
                        # dm_engine.py + world_store.py + audio_engine.py, returns a
                        # response the HTTP layer just serializes
  dm_engine.py         # system prompts + LLM API calls + response parsing (unchanged
                        # role, just no longer also holding turn orchestration)
  world_store.py        # NEW — Entity/Scene/WorldStore, per GLM-WORLD-ENGINE-SPEC.md
  audio_engine.py       # TTS + music generation (existing, gets the segment-queue
                        # rewrite from AUDIO-STREAMING-DESIGN.md)
  audio_queue.py         # NEW — the segment queue / state machine, separated from
                        # generation so game_loop.py can reason about playback state
                        # without needing to know how TTS actually works
  config.py             # unchanged
```

**Why `game_loop.py` is worth adding, not just splitting the HTML out:** the DC-then-roll
two-call flow (v0.4b) and the World Engine's context assembly (v0.5a) both need to sit
*between* the HTTP handler and the DM engine — right now that orchestration logic is
mixed into `app.py`'s request handlers. Pulling it into its own module now means v0.4b
and v0.5a land as changes to `game_loop.py`, not as more surgery on `app.py`.

**How to do this without breaking anything:** move the HTML/CSS/JS out first (purely
mechanical, zero behavior risk), serve it via Python's stdlib static-file handling or a
simple template read — no new dependency needed. Then extract `game_loop.py` by moving
functions, not rewriting them; run the existing Playwright test suite after each
extraction step to confirm nothing broke. This is exactly the kind of safe, mechanical
refactor GLM does well — no design judgment needed, just careful moving.

## Task division for parallel GLM instances

### Instance "A GLM - Rules & World Engine" — v0.4c/d, v0.5a/b/c
**Build from `sonnet-work/GLM-WORLD-ENGINE-SPEC.md` now (supersedes `WORLD-ENGINE-DESIGN.md`
— that doc is historical only).** In order: `world_store.py` standalone (v0.4c) →
`GameState` facade over it, behavior-neutral (v0.4d) → context assembler (v0.5a) →
consistency guard + RECALL (v0.5b) → procedural opening, no more hardcoded goblins
(v0.5c). DC-then-roll (v0.4b) **waits for Instance B's audio queue to land first** —
see the dependency note above, don't start it early even though it touches the same
files you'll already be in.

Also, still pending from before: expanded trickster scenarios, mechanics-log display
formatting fix, and re-running the Claude test once Anthropic credits are added (try it
regardless per Arie's answer — "try it anyway and keep the api included").

### Instance "B GLM - Audio Streaming" — v0.4a first (priority), then v0.8
**This is now the critical path — Instance A's DC-then-roll work is blocked on it
(see dependency note above).** Start here first if only one instance runs initially.
1. Implement the segment-queue architecture in `docs/AUDIO-STREAMING-DESIGN.md` —
   ready to build directly, no open design questions.
2. Fix all non-working volume sliders in the settings panel (Arie flagged this
   specifically — double-check every audio type: narration, music, SFX).
3. Implement crossfade for music transitions + loudness normalization + adaptive
   ducking scaled to speech volume (whisper = quieter background, not a fixed duck %).
4. Double-check why the sepia-theme screenshots looked wrong (Arie confirmed the live
   app is fine — likely a test-timing issue in `playwright_test.js`, not an app bug).

### Instance "C GLM - GUI/UX" — v0.6 UI + v0.7
1. Build the Session Zero conversational wizard UI per `docs/SESSION-ZERO-DESIGN.md`
   (can start now with a stubbed `campaign_meta`, wire to the real World Store once
   Instance A's work lands).
2. Build the voice assignment screen (pick/customize voice per character, with a
   sensible auto-pre-pick default per Arie's answer).
3. Build the manual dice-roll UI (the dice buttons already exist in the side panel per
   the screenshots — verify they're wired to actually roll and feed the DC-then-roll
   flow from Instance A).
4. Build the full character sheet + inventory + progression management UI (v0.7) —
   sequence this after Instance A's World Engine entity model exists for character
   state, to avoid building UI against a data model that's about to change.

### Instance "D GLM - Stability" (optional 4th instance)
1. Long-session (30+ turn) stress test once the above stabilizes — don't run this too
   early, the app is about to change substantially.
2. General regression sweep before each version checkpoint.

## What's needed from Arie

Most of the 10 original questions are now answered in detail. Two open items:
- **Opus review timing/cost approval** for the World Engine doc — your call, see
  `sonnet-work/OPUS-BRIEF-WORLD-ENGINE.md`.
- Everything else in Arie's answers reads as clear direction, not open questions — GLM
  should proceed against the design docs above rather than asking further for now.
