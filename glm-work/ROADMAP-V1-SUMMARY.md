# Narrator — Full Roadmap to v1.0

**Created:** 2026-08-22
**For:** Arie
**Current version:** v0.5c (Instance A) + v0.4a (Instance B)
**Source:** `docs/V1-PLAN.md` (Sonnet's canonical plan)

This is a plain-language summary of where the project is and what's left
before v1.0. Lines starting with `>` are reserved for your input.

---

## Where we are now

```
v0.1   Core app — DM engine, GUI, TTS, music, intro screen
v0.2   Pre-loaded TTS, themes, budget fallback, continuous music, save/load
v0.3   UX polish — keyboard shortcuts, auto-send, scroll, Qwen3 fallback fix
v0.3.5 File restructuring — app.py split into 6 modules ✓ DONE
v0.4a  Audio segment queue — live streaming ✓ DONE (Instance B)
v0.4c  World Store — entity store, validation, persistence ✓ DONE
v0.4d  GameState facade — behavior-neutral ✓ DONE
v0.5a  Context assembler — layered memory with token budgets ✓ DONE
v0.5b  Consistency guards + RECALL ✓ DONE
v0.5c  Procedural opening — no more hardcoded goblins ✓ DONE
```

**You are here →** v0.5c is built and tested. The next step is wiring the
World Engine into the live turn flow, then building the remaining UI.

---

## What's left (v0.4b → v1.0)

### v0.4b — DC-then-roll two-call flow (Instance A)

**What it is:** When you attempt a contested action (attack, pick lock,
persuade), the app makes two LLM calls instead of one:
1. Call 1: DM narrates the setup and sets a difficulty class (DC), then stops
2. Python rolls the dice deterministically (seeded by campaign + turn)
3. Call 2: DM narrates only the consequence of the already-decided result

**Why it matters:** Right now the LLM decides whether you succeed or fail.
With DC-then-roll, the dice decide — the LLM can't cheat or fudge outcomes.

**Why it waited:** Two LLM calls doubles latency. This was blocked until
Instance B's audio queue (v0.4a) landed, so the first call's narration
starts playing while the second call is in flight. Audio hides the wait.

**Status:** The dice helpers exist in `dm_engine.py`. The audio queue is
ready. This can now be wired in.

**What you'll notice:** Dice rolls feel more real — the DM sets up the
tension, you see the roll, then the DM narrates the result. Slightly longer
pause before the result, but audio fills the gap.

---

### v0.6 — Session Zero wizard + voice assignment (Instance C)

**What it is:** Replaces the current single-form intro with a conversational
DM-guided onboarding. The DM talks with you to collaboratively design your
character and campaign — like a real Session Zero at the table.

**Why it matters:** The current intro form is functional but flat. Arie
specifically wanted "an opening wizard guiding setup like an introduction
or foreword to a book."

**Also includes:**
- Voice assignment screen — pick or customize a voice per character, with
  a sensible auto-pre-pick default
- Manual dice-roll UI — the dice buttons in the side panel wired to
  actually roll and feed into the DC-then-roll flow

**Status:** The Session Zero backend exists in `game_loop.py` (the
conversational prompts and parsing are built). The UI hasn't been built yet.
Instance C hasn't started.

**What you'll notice:** Starting a new game feels like talking to a DM who's
helping you set up, not filling out a form.

---

### v0.7 — Full character sheet + inventory + progression (Instance C)

**What it is:** A real character sheet UI — stats, skills, inventory grid,
equipment slots, level progression, conditions tracker.

**Why it matters:** Arie specifically requested "deep character management
and full character sheet management including progress tracking and full
inventory management" for v1.

**Status:** The data model exists in the World Store (entities with
attributes, links, revisions). The UI hasn't been built. Instance C.

**What you'll notice:** You can see and manage your character's full state
visually, not just in the side panel summary.

---

### v0.8 — Audio polish (Instance B)

**What it is:**
- Crossfade for music transitions (no abrupt cuts)
- Loudness normalization (consistent volume across TTS engines)
- Adaptive ducking (background music ducks more when narration is quiet,
  less when it's loud — not a fixed percentage)
- Fix non-working volume sliders (Arie flagged this specifically)

**Why it matters:** Audio quality is the difference between "feels like an
audiobook" and "feels like a game." Arie wanted "direct playing audio for
all narration, live generated faster than playback, including SFX and music."

**Status:** Instance B built the segment queue (v0.4a). Polish is the next
pass. Some of this (loudness normalization) is already partially done.

**What you'll notice:** Smoother audio, no jarring transitions, volume
sliders that actually work.

---

### v0.9 — Long-session stability (Instance D)

**What it is:**
- 30+ turn stress test — run a full session without crashes or restarts
- Expanded trickster tests — more adversarial scenarios (long-context
  cheating after 40+ turns, entity reintroduction, roll-result tampering)
- Golden-transcript regression harness — replay old playthroughs against
  new code to catch behavior changes
- Anthropic/Claude testing — once credits are available

**Why it matters:** The app hasn't been stress-tested for long sessions yet.
Memory leaks, context window overflow, entity store bloat — these only show
up after 30+ turns.

**Status:** Deferred until the app stabilizes. Instance D hasn't started.

**What you'll notice:** The app stays fast and reliable even in long sessions.

---

### v1.0 — Arie is satisfied

**The bar (from V1-PLAN.md):**
1. A full extended session (~30+ turns) runs without crashing
2. Opening wizard replaces the single-form intro
3. All three themes visually distinct
4. At least 2 story models and 2 TTS engines reliably working mid-session
5. Save/load works across a real session
6. GUI polish pass applied
7. Manual dice-rolling UI working
8. Deep character management + full character sheet + inventory + progression
9. Direct playing audio for all narration, live generated faster than playback
10. Procedurally generated world — no hardcoded NPCs, locations, or items
11. Arie has personally played a real session end-to-end and is satisfied

**Not required for v1:** multi-session support, mobile/responsive layout,
network deployment.

---

## Integration gaps (built but not yet wired in)

These components exist, are tested, and pass all tests — but aren't connected
to the live turn flow yet. This is the next phase of work:

1. **WorldStore attachment** — `GameState.attach_world_store()` exists but
   `game_loop.py` never calls it. The app runs in legacy mode (flat state).

2. **Context assembler** — `world_store.get_context_for_turn()` exists but
   the app still uses `history[-10:]` sliding window. Wiring this in fixes
   the prompt-caching bug (the prefix changes every turn after turn 10).

3. **Presence-and-liveness guard** — `world_store.presence_liveness_guard()`
   exists but isn't called after the LLM responds. Wiring this in catches
   dead NPCs speaking.

4. **RECALL loop** — `world_store.handle_recall()` exists but the turn flow
   doesn't check for RECALL tags or trigger re-runs.

5. **TurnRecord logging** — `world_store.append_turn_record()` exists but
   isn't called. The JSONL replay corpus isn't being built yet.

6. **Chronicle compaction** — `world_store.compact_chronicle()` exists but
   isn't triggered automatically.

7. **DC-then-roll** — `dm_turn_dc_roll()` exists but isn't called. Blocked
   on audio queue (now ready).

---

## Dependency graph

```
v0.3.5 (restructuring) ✓
  ├── v0.4a (audio queue) ✓          ← Instance B
  │     └── v0.4b (DC-then-roll)     ← Instance A, NEXT
  ├── v0.4c (world store) ✓          ← Instance A
  │     └── v0.4d (facade) ✓         ← Instance A
  │           └── v0.5a (context) ✓  ← Instance A
  │                 └── v0.5b (guards) ✓  ← Instance A
  │                       └── v0.5c (procedural) ✓  ← Instance A
  ├── v0.6 (Session Zero UI)         ← Instance C, NOT STARTED
  │     └── v0.7 (character sheet)   ← Instance C
  ├── v0.8 (audio polish)            ← Instance B, NEXT after v0.4b
  └── v0.9 (stability testing)       ← Instance D, NOT STARTED
        └── v1.0 (Arie satisfied)    ← Everyone
```

---

## Instance ownership

| Instance | Role | Status | Current work |
|---|---|---|---|
| A | Rules & World Engine | Active | v0.5c done, ready for integration |
| B | Audio Streaming | Active | v0.4a done, ready for v0.8 polish |
| C | GUI/UX | Not started | v0.6 Session Zero, v0.7 character sheet |
| D | Stability Testing | Not started | v0.9 long-session stress test |
| Sonnet | Architecture lead | Oversees | Reviews handoffs, plans next steps |
| Opus | Second opinion | On call | World Engine review (3 open questions) |

---

## Test coverage today

67 tests across 6 suites, all passing:

| Suite | Tests | What it covers |
|---|---|---|
| Trickster | 16 | Rules-lawyer adversarial scenarios |
| World Store | 15 | Entity CRUD, persistence, validation |
| Facade | 11 | Behavior-neutral GameState ↔ WorldStore |
| Context Assembler | 9 | Layered assembly, scoring, budgets |
| Guards | 9 | Presence/liveness, RECALL, contradictions |
| Procedural | 7 | No hardcoded goblins, prompt version |
| Playwright | 1 flow | Full browser E2E (13 screenshots) |

**Still needed (v0.9):**
- Golden transcript replay tests
- 200-turn offline soak test
- Expanded trickster scenarios (40+ turns, entity reintroduction)
- Invariant/property tests (HP range, no negative inventory, no dead in scene)

---

## Your questions / direction

> (Write any questions or direction changes here. Lines starting with > are yours.)

> Should Instance C (GUI/UX) start now, or wait for the World Engine integration?

> Is the DC-then-roll two-call flow the right priority, or should I focus on
> something else first?

> Any feedback on the procedural opening — does it feel different each time?

> Anything else:
