# World Engine — Opus review + implementation strategy

**Author:** Opus, 2026-08-22
**Inputs read:** `sonnet-work/OPUS-BRIEF-WORLD-ENGINE.md`, `docs/WORLD-ENGINE-DESIGN.md`,
`glm-work/notes/dm_engine_research.md`, `docs/SESSION-ZERO-DESIGN.md`,
`docs/AUDIO-STREAMING-DESIGN.md`, `docs/V1-PLAN.md`, and the live code
(`glm-work/narrator_v01/dm_engine.py`, `app.py`).

**Status:** this file *is* the Opus review the brief asked for — it does not need to be
launched separately. It answers the three open questions, sanity-checks the entity model,
and reconciles the design doc with the research. It is deliberately **architecture-level**:
Sonnet writes the line-level spec for GLM from §7.

This file is Opus's. Sonnet should write its detailed GLM spec in its own file (§7),
not by editing this one.

---

## 1. Headline finding: the two docs were written in isolation

`dm_engine_research.md` (GLM, 08-18) is a genuinely good survey — 13 products, concrete
architectural patterns, 10 recommendations. `WORLD-ENGINE-DESIGN.md` (Sonnet, 08-21)
does not cite it once, and re-derives from first principles.

The good news: **they agree on the load-bearing decision** (LLM narrates, code
adjudicates, structured state is the source of truth). Sonnet's independent conclusion
matches the industry consensus, so there's no architectural conflict to resolve.

The bad news: three things the research already established are missing from the design,
and one of them is a *hard constraint* on the retrieval design that Sonnet flagged as an
open question. Merging them resolves most of the uncertainty without needing new ideas.

**Missing from the design, present in the research:**

| Research finding | Why it changes the World Engine design |
|---|---|
| **Prompt caching = 90% cost saving** (Scrollbook, §1.3) | This is a *structural constraint on `get_context_for_turn()`*, not an optimization. If retrieval emits one freshly-assembled blob each turn, cache reuse is destroyed. The assembler must emit **stable prefix + volatile suffix**, separately. See §3. |
| **Just-in-time rule injection** (SoloQuest, §1.8 layer 2) | Keeps the prompt small enough for the free Groq/Gemini models in Arie's model picker. Not in the design at all. |
| **Deterministic consistency guard as a separate pass** (Pr0degie, §1.11) | Today's guards live *inside* `apply_mechanics()`. They need to be a distinct post-generation validation layer with regenerate-once/fail-open, because the World Engine adds guard cases (`dead NPC speaks`, `entity re-introduced`) that aren't mechanics tags. |
| **3-pass state-diff** (Gemma4 DM, §1.9) | The natural hook point for duplicate detection (Q2) — you diff which entities came into existence this turn, and dedup at that boundary rather than ad hoc. |

**Also worth stating explicitly, because it's an unstated assumption in both docs:**
the research's "don't build TTA's 6-tier stack / no vector DB for v1" (§4.5, §4.10)
agrees with the brief's bandwidth constraint. Good — everything below uses Python
stdlib, JSON/JSONL, and the existing LLM calls. No new dependencies.

---

## 2. The one real conflict nobody has flagged: DC-then-roll vs. "faster than playback"

`WORLD-ENGINE-DESIGN.md` makes contested actions **two sequential LLM calls**.
`V1-PLAN.md` records Arie's hard requirement: *"Direct playing audio for all narration,
live generated faster than playback."* Two serial calls roughly doubles the worst case.

**This is resolvable, and the resolution is good news, but it constrains the build order.**

The setup narration from call 1 is itself playable audio. The correct pipeline is:

```
call 1 → [STORY] setup narration + [ROLL_REQUEST: skill, DC]
       → TTS starts immediately, audio begins playing
       → code rolls (instant) while audio plays
       → call 2 fires while call-1 audio is still playing
       → outcome narration is queued behind it
```

Latency is hidden **only if the segment-queue streaming from
`AUDIO-STREAMING-DESIGN.md` already exists.** Without it, DC-then-roll makes the app feel
twice as slow and Arie will (correctly) hate it.

**Recommendation: audio streaming lands before, or at minimum alongside, DC-then-roll.**
This confirms V1-PLAN's v0.4 pairing, but the two halves are *not* independent as the
plan currently claims — Instance B's queue is a prerequisite for Instance A's rules work
feeling acceptable. Say so explicitly in the instructions.

Two further requirements that fall out of this:
- **In manual-dice mode** the player's roll is a natural pause; call-1 audio fills it. Fine.
- **The DC must be persisted before the roll is resolved.** Write
  `{turn, action, skill, dc, seed, roll, modifier, total, result}` to the turn log
  *before* narrating the outcome. That's what makes Arie's "deterministic and traceable"
  literally true, and it's what makes replay testing (§6) possible. Use a per-campaign
  seeded RNG so a session can be re-run exactly.

---

## 3. Open question 1 — context budget / retrieval at scale

**Answer: no embeddings, no vector DB. A deterministic, token-budgeted, cache-ordered
assembler plus a directory of everything plus an LLM escape hatch.**

### 3.1 Reframe the problem

Sonnet's worry is "50+ NPCs won't fit." That's the wrong failure mode. **A scene is local
— it never needs more than ~10-15 full entity records.** The real failure mode is *the
right entity wasn't retrieved*, and the DM narrates around a gap it doesn't know it has.

So the design goal is not compression; it is **making it impossible for the DM to not
know an entity exists.**

### 3.2 The cheap trick that defers this problem past v1

Include a **world directory** in every prompt: one line per entity, `id | name | type |
one-line summary`, ~12 tokens each. 200 entities ≈ 2,400 tokens. That is affordable, and
it eliminates "the DM forgot a character existed" entirely. Full records are loaded only
for the working set.

Budget rule: if the directory exceeds ~1,500 tokens, degrade to *pinned + seen in the
last 50 turns + all quest-linked entities*, and only then start dropping.

### 3.3 Layered assembly, ordered for prompt caching

`get_context_for_turn()` must return **two strings**, not one:

```
STABLE PREFIX  (cacheable, byte-identical across turns wherever possible)
  L0  system prompt / rules contract
  L1  campaign_meta (session-zero answers, tone, rules_profile)
  L2  world directory (see 3.2) — changes only when an entity is created
  L3  pinned entities, full records (PC, active quests, current location)

VOLATILE SUFFIX (never cached)
  L4  working set — full records for retrieved entities (see 3.4)
  L5  scene block — who is present, encounter/initiative state, light/time
  L6  "since you were last here" digest, if applicable (see §5)
  L7  last N turns verbatim + rolling chronicle
  L8  just-in-time rules (top 3, see 3.6)
  L9  player action + resolved roll facts
```

Target ~6-8k prompt tokens total. Each layer gets an explicit token budget and is
truncated independently, so one runaway layer can't starve the others.

**Cache-breaking bug already in the code:** `dm_turn()` sends `history[-10:]` — a sliding
window. Once you pass 10 turns, the prefix changes every single turn and prompt caching
never hits. Replace with a **growing prefix + periodic compaction** (compact turns
1..N-10 into a summary block that only changes every K turns).

### 3.4 Working-set selection — integer scoring, no ML

For each entity, score:

```
+100  pinned (PC, active-quest entities, current location)
+ 50  present in the current scene
+ 40  name or alias appears in the player's input
+ 30  name or alias appears in the last turn's narration
+ 20  one graph hop from a present entity (links/connected_to/members)
+ 15  linked to an active quest
+  0..10  recency, decaying on (current_turn - last_seen_turn)
```

Take entities above a threshold, sorted, until the L4 token budget is spent. Always
include everything scoring ≥100. This is TTA's graph-hop retrieval implemented with a
dict and integers.

### 3.5 The escape hatch — `[RECALL: ...]`

Give the DM a way to say "I need something I wasn't given." It emits
`[RECALL: <name or topic>]`; code resolves it against the directory/alias table, appends
the full record to L4, and **re-runs the turn once** (hard cap: one recall round-trip per
turn, then proceed without it). This is SEP's `query_memory` "Memory Packet" implemented
as a tag rather than a function call.

**Why a tag and not tool/function calling:** Arie's model picker includes free Groq and
Gemini models with inconsistent tool-calling support. A tag protocol works identically
across every provider and keeps the model genuinely swappable. Tool-calling can come
later for the paid Claude path if it ever proves worthwhile. Note the tradeoff so it's a
decision, not an accident.

### 3.6 Just-in-time rules (adopt from research §1.8)

Keep rules in a JSON file, not the system prompt. Each turn, keyword-score the player's
input + scene state and inject the top 3 relevant rules into L8. Keeps L0 small enough
for the free models, and is where a non-D&D `rules_profile` plugs in.

---

## 4. Open question 2 — duplicate / near-duplicate entities

**Answer: deterministic, stdlib-only, at the 3-pass diff boundary. And the design is
missing the harder half of this problem.**

### 4.1 Resolution pipeline (`resolve_or_create`)

1. **Code owns IDs. The LLM never emits one.** The LLM refers to entities by *name*;
   code resolves name → id. Requiring exact ID echo from an LLM is a known failure source.
2. **Normalize**: lowercase, strip punctuation, strip leading articles and honorifics
   (`the`, `old`, `ser`, `captain`, `mister`), collapse whitespace → `norm_name`.
3. **Exact match** on `(norm_name, type)` → return existing. This catches ~90%.
4. **Alias table lookup** — a store-level `aliases: dict[str, entity_id]`, populated on
   every successful resolution. Handles "the innkeeper" → `npc_marla`. The DM can also
   assert one explicitly: `[ALIAS: the innkeeper -> Marla]`.
5. **Fuzzy**: `difflib.SequenceMatcher` ratio ≥ 0.85 on `norm_name`, same type → candidate.
   Stdlib, zero dependencies.
6. **Token overlap**: shared first token, same type ("Gorak" vs "Gorak Ironhand") → candidate.
7. **Candidate policy** — don't silently merge, don't silently fork:
   - same location, or seen within the last ~20 turns → **treat as existing**, record the
     new string as an alias.
   - otherwise → **create new**, ID suffixed `_2`, and write a visible line to the
     mechanics log. Arie's stated preference is automatic-but-visible; a wrong merge that
     nobody can see is far worse than a visible near-miss.
8. `propose_entity()` must return `(entity, created: bool, reason: str)` — the current
   signature returning bare `Entity` hides the merge case from every caller.

### 4.2 The half the design misses: contradictory *re-description*

Duplicate *names* are the easy case. The common failure is the same entity described
differently — Marla had brown hair on turn 8, red hair on turn 40.

- `summary` and `attributes` are **not** free to overwrite. Changes go through
  `[ENTITY_UPDATE: <name>, <field>, <value>]`.
- Every entity carries an append-only `revisions: [{turn, field, old, new, source}]`.
- `known_facts` is **append-only, turn-stamped, never rewritten.**
- A contradiction (overwriting a previously-asserted immutable-ish field like appearance
  or species) is applied but logged visibly, same as a rejected mechanic tag.

This is cheap, it's just list appends, and it's the difference between "the world is
consistent" and "the world is whatever the last turn said."

---

## 5. Open question 3 — consistency at long horizons

Five mechanisms, all deterministic:

1. **"Since you were last here" digest.** When `current_location_id` changes to a place
   with a stale `last_visited_turn`, code injects L6:
   *"You last visited The Rusty Anchor on turn 12, 28 turns ago. Since then: <chronicle
   lines tagged to this location>. Present then: Marla (alive, friendly), Gorak (dead)."*
   Code-generated, no LLM involved. This kills the re-narration failure directly.

2. **`[KNOWN]` / `[NEW]` markers** on every entity in context, plus one prompt clause:
   *"Entities marked KNOWN have already been met. Do not re-introduce them."*

3. **Presence-and-liveness guard (generalize Pr0degie + today's `ENEMY_DEAD` guard).**
   Post-generation, before display/TTS: every speaker name in `[STORY]` must resolve to
   an entity that is *alive* and *present in the current scene* (or narrator/PC).
   Violation → regenerate once with a concrete correction → **fail open** with a visible
   warning. Never block the turn. This is the single highest-value guard in the whole
   design.

4. **Hierarchical chronicle compaction** (Project Infinity's `timeline.md`). Verbatim
   last N turns; every K turns a cheap model compacts them into a chronicle entry;
   chronicle entries later compact into chapter summaries. **The raw JSONL turn log is
   never destroyed** — it's the replay corpus (§6) and it costs nothing to keep.

5. **Scene as a first-class object.** See §6.8 — half of these guards are unimplementable
   without an explicit notion of "who is here right now."

---

## 6. Entity-model sanity check — what a production build would regret

Ordered by how expensive they are to fix later.

1. **Add an explicit `Scene` / presence concept.** The design has `last_seen_turn` but no
   "who is in this scene right now." Retrieval (§3.4), the liveness guard (§5.3), and
   combat all need it. Add
   `scene: {location_id, present_entity_ids, started_turn, encounter: {...}}` to the store.
   **This is the biggest genuine gap in the design.**

2. **Combat/initiative state was dropped without replacement.** Today's flat state has
   `enemies`; the entity model has NPCs but no turn order, action economy, or round
   counter. Put `encounter` on the scene, not on entities.

3. **The PC should be an Entity** (`type="pc"`) with a `player_id` pointer, not a
   special-cased `PlayerState`. Otherwise every validation, retrieval, and persistence
   rule gets written twice, and the two copies drift.

4. **`id` as a name-derived slug is a trap.** If the name changes or normalizes
   differently, IDs collide or drift. Use a stable opaque-ish ID (`npc_0007_gorak`),
   generated once, never re-derived.

5. **Add `schema_version` to the store, and a migration path.** Save files already exist
   (`outputs/save.json`). This schema *will* change. Cheap insurance.

6. **Validate `attributes` on write.** Freeform dict is the right call for
   rules-system-agnosticism, but unvalidated is where the regret lives: the LLM will
   write `hp: "badly wounded"` and everything downstream breaks. Per-type required keys,
   type coercion, and numeric clamping (`0 <= hp <= max_hp`) at the store boundary.

7. **Add generic `links: [{rel, target_id}]`** to Entity. `connected_to` (locations) and
   `members` (factions) are special cases of this, and §3.4's graph-hop scoring and
   "how does this NPC feel about the player" both want the general form. Keeps the
   single-table simplicity.

8. **Persistence: two files, not one.** `world.json` (entity snapshot, atomic write via
   tmp + `os.replace`) and `turns.jsonl` (append-only). A crash mid-turn must not corrupt
   the world, and Arie runs 30+ turn sessions — losing one to a half-written JSON is the
   worst bug this app could have.

9. **`get_context_for_turn()` signature.** Should be
   `get_context_for_turn(player_input: str, budget: TokenBudget) -> ContextBundle`,
   returning `(stable_prefix, volatile_suffix, included_entity_ids, dropped_entity_ids)`.
   The included/dropped lists are needed by the guard, the `[RECALL]` loop, and debugging.

10. **`rules_profile` as data, not code.** Sonnet correctly keeps D&D out of the schema —
    but then *something* must own the DC ladder, ability list, and damage model. A JSON
    `rules_profile` in `campaign_meta` (AURA's "protocol-frozen, data-driven" point) keeps
    the deterministic engine generic. No 5e constants in code paths.

11. **Don't rewrite; strangle.** `app.py` is 1,643 lines and three GLM instances are
    working in parallel. A big-bang `GameState` → `WorldStore` swap breaks Instances B
    and C. Instead: build `world_store.py` standalone, then make `GameState` a **thin
    facade** over it (`pc_hp`, `inventory`, `enemies` become properties backed by the
    store). Every existing call site keeps working; migrate them incrementally. This is
    the most important *process* recommendation in this document.

---

## 7. Testing — the part the research gets wrong for this codebase

SoloQuest's "you can't unit-test DM behavior" is true for *narration*. It is false for
everything this architecture moves into code, which is the whole point of building it.

1. **Golden-transcript replay.** Record real LLM outputs to JSONL once; replay them
   against the store offline and assert the resulting world state. Zero API cost, zero
   bandwidth — which matters a lot given Arie's 5G link and the $5 budget cap in the UI.
   This should be the primary regression harness.
2. **Fake-LLM trickster harness.** Extend `test_trickster.py` with a stub that emits
   adversarial tag sequences directly (fabricated items, dead NPC speaking, HP inflation
   over 30 turns, duplicate NPC names, contradictory re-description). No API needed. This
   also finally unblocks the "expanded trickster scenarios" item that's been pending.
3. **Property/invariant tests.** Apply N random valid tags; assert `0 <= hp <= max_hp`,
   no negative inventory counts, no dead entity in `present_entity_ids`, every
   `ENTITY_UPDATE` has a matching revision record.
4. **Long-horizon soak, offline.** Replay a synthetic 200-turn transcript and assert the
   context assembler stays under budget and never drops a pinned entity.

---

## 8. Explicitly NOT building (guard against over-engineering)

Say no to these in writing, so nobody quietly adds them:

- Vector DB / embeddings / semantic search — §3.2's directory defers this well past v1.
- Knowledge-graph database (Neo4j etc.) — `links` on Entity is enough.
- SQLite — JSON + JSONL is fine to ~10k turns. Revisit only when measured.
- Multi-model Director/Actor/Narrator split (AURA) — overkill for solo play, and it
  multiplies the latency problem in §2.
- MCP tool server — interesting later for swappable brains, irrelevant to v1.
- Function/tool calling for mechanics — tags win on cross-provider portability (§3.5).
- TTA's full 6-tier context stack — §3.3 borrows the idea at a tenth of the cost.

---

## 9. Recommended build sequence

Slots into V1-PLAN's versioning rather than replacing it.

| Stage | Content | Owner |
|---|---|---|
| **v0.4a** | Audio segment queue (`AUDIO-STREAMING-DESIGN.md`) — **prerequisite for v0.4b feeling acceptable**, see §2 | Instance B |
| **v0.4b** | DC-then-roll two-call flow + seeded RNG + resolution ledger written in the *new* turn-log format (so v0.5 doesn't redo it) + manual dice UI | Instance A (+ C for UI) |
| **v0.4c** | `world_store.py` standalone: Entity, Scene, links, validation, atomic persistence, `resolve_or_create`. **No app.py changes yet.** Unit-tested in isolation | Instance A |
| **v0.4d** | `GameState` becomes a facade over `WorldStore` (§6.11). App behaviour unchanged — this is a pure refactor, and it should be provable by replaying transcripts | Instance A |
| **v0.5a** | Context assembler (§3): stable/volatile split, directory, scored working set, token budgets. Fix the `history[-10:]` cache-breaker | Instance A |
| **v0.5b** | Consistency guard pass (§5.3) + `[RECALL]` loop + `[ENTITY_UPDATE]`/revisions | Instance A |
| **v0.5c** | Procedural opening — kill the two hardcoded goblins, seed from `campaign_meta` via `propose_entity()` | Instance A |
| **v0.6+** | Session Zero, character sheet, audio polish — unchanged from V1-PLAN | Instances C / B |

**One deviation from V1-PLAN worth considering:** v0.5c (no more hardcoded goblins) is
small and is the change Arie will *notice* first, since he's raised it repeatedly. If it
can be pulled forward on a stub store without destabilising the rest, do it.

---

## 10. Instructions for Sonnet — what to write next

Sonnet owns the detailed GLM spec. Write it in your own file (suggest
`sonnet-work/GLM-WORLD-ENGINE-SPEC.md`); don't edit this review or
`WORLD-ENGINE-DESIGN.md` in place — instead add a short "superseded by" pointer at the
top of the design doc so the history stays readable.

Treat §§3-6 above as **decided**. Don't re-open them; if you disagree with something,
flag it to Arie rather than silently diverging — GLM having two conflicting specs is
worse than either spec being slightly wrong.

What the GLM spec needs to contain, in this order:

1. **Full dataclass definitions** — `Entity`, `Scene`, `Encounter`, `WorldStore`,
   `TurnRecord`, `ContextBundle`, `TokenBudget`, `RollRecord`. Field names, types,
   defaults, and the per-type `attributes` required-key table and clamp rules (§6.6).
2. **Complete method signatures with docstrings and error behaviour** for `world_store.py`:
   `resolve_or_create`, `propose_entity`, `apply_turn_mechanics`, `get_context_for_turn`,
   `enter_scene`, `record_roll`, `compact_chronicle`, `save`/`load`, `migrate`.
3. **The full tag vocabulary** as a table: existing tags (`HP_CHANGE`, `ENEMY_HP`,
   `ENEMY_DEAD`, `ITEM_USED`, `ITEM_GAINED`, `CONDITION`, `ROLL_REQUEST`) plus the new
   ones (`ENTITY_NEW`, `ENTITY_UPDATE`, `ALIAS`, `RECALL`, `ENTER_SCENE`, `EXIT_SCENE`,
   `ROLL_RESULT`, `QUEST_UPDATE`). For each: grammar, validation rule, rejection message,
   and whether it's LLM-emitted or code-emitted.
4. **The revised system prompt**, in full. Budget ~350 lines (research §1.8 says that's
   realistic at maturity). Must include the DC-before-outcome contract, the KNOWN/NEW
   clause, the "refer to entities by name, never invent IDs" clause, and the RECALL
   affordance. Version-stamp it (`PROMPT_VERSION = "v10"`) — prompt edits are change
   control and force a deliberate cache miss.
5. **The two-call turn flow as a numbered sequence**, including exactly where the audio
   queue is fed, where the roll is persisted, where the guard runs, and what happens on
   guard failure and on `[RECALL]`. A diagram or numbered list — GLM should not have to
   infer ordering.
6. **The context assembler pseudocode**, with the actual layer token budgets and the
   scoring weights from §3.4 as named constants GLM can tune.
7. **The strangler-fig facade contract** (§6.11): the exact list of `GameState`
   attributes that must keep working, and which `app.py` call sites read them. Make it
   explicit that v0.4d must be behaviour-neutral.
8. **The test plan** from §7, with concrete file names and at least a dozen named
   trickster scenarios.
9. **A "do not build" section** — copy §8 verbatim. GLM is capable and will happily build
   a vector store if nobody says not to.

Also please update `docs/V1-PLAN.md` with the §9 sequence and the §2 dependency
(audio-before-rules), since the current plan states those two are independent and they
are not.
