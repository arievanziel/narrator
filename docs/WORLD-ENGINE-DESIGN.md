> **Superseded 2026-08-22.** Opus reviewed this doc — see `docs/WORLD-ENGINE-REVIEW-OPUS.md`
> for the answers to the three open questions below, and `sonnet-work/GLM-WORLD-ENGINE-SPEC.md`
> for the line-level implementation spec GLM should actually build from. This doc is kept
> for history/context only — don't implement directly against it.

# World Engine — Design v1 (Sonnet draft, needs Opus review before large-scale build)

**Honesty check first, since Arie asked for it directly:** I can design a solid,
well-reasoned v1 of this — the pattern (structured entity store + code-enforced state,
LLM only proposes/narrates) is a known, well-understood architecture ("agentic RAG for
game state"), not exotic research. I'm confident in the shape below. What I'm **less**
confident about without a dedicated review: the exact retrieval/context-budget strategy
at scale (what happens when a campaign has 200 NPCs and 50 locations — what gets loaded
into the LLM's context each turn, and what doesn't), and edge cases in consistency
enforcement that only show up after a lot of play. That's exactly a "get it right once,
expensively" situation — I'm recommending an Opus pass on this specific doc before GLM
builds a lot of code on top of it. See `sonnet-work/OPUS-BRIEF-WORLD-ENGINE.md` for the
ready-to-launch review task. Don't wait for that review to start basic implementation —
just don't consider the schema "final" until it's had a second pass.

## Why this exists (from Arie's direct feedback)

> The npc's should not be scripted... Any world aspect, npc, location, should be
> generated on the fly and nothing should be hardcoded... never trust the llm's or ai
> running the narration to 'remember' correctly what happened before. Any detail should
> be stored and retrieved reliably.

Today's `GameState` (in `narrator_v01/dm_engine.py`) is a flat object: `pc_hp`,
`inventory` (list of strings), `enemies` (list of strings), `chronicle` (list of
strings). It works for a fixed two-goblin encounter. It cannot represent a procedurally
generated world with persistent NPCs, locations, factions, and items that need to stay
consistent across dozens of turns. This doc replaces it.

## Core principle

**The LLM never IS the memory. The LLM only ever reads a summary the code assembled, and
proposes changes the code validates and stores.** Same trust model as the existing rules
lawyer (`apply_mechanics()`), generalized from "HP and inventory" to "the entire world."

## Entity model

A small, general set of entity types, each with a stable ID (so they can be referenced
consistently across turns instead of re-described from scratch each time):

```python
@dataclass
class Entity:
    id: str                    # e.g. "npc_thorn_ironhand", stable, LLM-friendly slug
    type: str                  # "npc" | "location" | "item" | "faction" | "quest"
    name: str
    summary: str                # 1-2 sentence description, shown to LLM every time it's relevant
    attributes: dict            # type-specific fields (see below)
    first_seen_turn: int
    last_seen_turn: int
    tags: list[str]              # for retrieval: ["goblin", "hostile", "tavern"], etc.

# Type-specific attributes (stored in `attributes`, not separate classes —
# keeps the store simple and schema-flexible for a system that isn't strictly D&D 5e):
# npc:      {hp, max_hp, ac, disposition, voice_description, known_facts: [str], alive: bool}
# location: {description, connected_to: [location_id], discovered: bool}
# item:     {description, owner_entity_id | "player" | "world", properties: dict}
# faction:  {description, disposition_to_player, members: [npc_id]}
# quest:    {description, status: "active"|"completed"|"failed", objectives: [str]}
```

**Why this shape:** a single `Entity` table with a `type` + freeform `attributes` dict
(rather than a rigid class per type) is deliberately flexible — Arie explicitly said the
rules system doesn't have to be D&D 5e, so hardcoding D&D-specific fields (STR/DEX/etc.)
into the schema itself would be the same mistake as hardcoding goblins into the encounter.
Keep D&D-specific stat blocks as *conventions* the system prompt asks for, not schema
constraints.

## The World Store

A single JSON file per campaign (SQLite if it grows unwieldy, but start simple —
consistent with "keep it simple," and Arie's bandwidth constraint means no new heavy
dependencies right now):

```python
class WorldStore:
    entities: dict[str, Entity]       # id -> Entity
    player: PlayerState               # HP, stats, inventory (item IDs), position (location_id)
    turn_log: list[TurnRecord]        # append-only history: turn N, action, outcome, entity deltas
    current_location_id: str
    campaign_meta: dict                # style, setting, tone, session-0 answers (see Session-0 doc)

    def get_context_for_turn(self, current_location_id: str, recent_turns: int = 3) -> str:
        """THE retrieval function — assembles what the LLM sees this turn.
        NOT the whole world. Only: entities at/connected to current location,
        entities mentioned in the last N turns, player state, active quests.
        This is the part most worth a second opinion on at scale."""

    def propose_entity(self, entity: Entity) -> Entity:
        """LLM wants to introduce a new NPC/location/item. Code assigns the stable ID,
        checks for near-duplicate names (avoid two 'Gorak the guard's), stores it."""

    def apply_turn_mechanics(self, mechanics: list[MechanicTag]) -> list[str]:
        """Generalizes today's apply_mechanics() — same validate-before-apply pattern,
        now operating on arbitrary entities instead of hardcoded pc_hp/inventory/enemies."""
```

## Rules engine: deterministic DC-then-roll (Arie's explicit requirement)

> The LLM DM sets a DC first and the roll determines the random result and story
> direction. Never give the llm DM freedom to decide the story direction, every choice
> should always be deterministic and traceable.

This changes the turn sequence from today's single-pass format into **two LLM calls per
contested action** (only when a roll is actually needed — most turns stay one call):

1. **DC-setting call:** LLM narrates the setup and emits `[ROLL_REQUEST: skill, DC]` —
   it does NOT know the outcome yet, cannot narrate one.
2. **Roll happens** (player rolls manually, or auto-roll draws a number) — this is
   pure code, no LLM involved, fully deterministic and loggable.
3. **Outcome call:** code tells the LLM `roll=14, DC=12, result=SUCCESS` as a fact, and
   the LLM narrates *only* the consequence of an already-decided outcome — it cannot
   change whether it succeeded.

This is the single biggest change to the DM engine's turn loop — bigger than it looks,
because it touches the response format, the audio pipeline (now two narration bursts per
contested turn instead of one), and the UI (needs to show "DC 12" and the roll clearly).
**This is well within my design competency** (it's a direct extension of the existing
apply_mechanics validation pattern, not new architecture) — no Opus needed for this part,
just careful GLM implementation.

## Procedural generation: no hardcoded encounters

Replace the fixed "2 goblins in a tavern" opening with: the DM LLM proposes the opening
scene's entities via `propose_entity()` calls, seeded by the Session-0 answers
(setting, tone, style) rather than a hardcoded scenario. The World Store validates each
proposal (reasonable stats for the stated difficulty/level, no duplicate names) before
persisting it. Same trust model, generalized: **the LLM improvises, the code is the
source of truth for what actually exists.**

## What changes in `narrator_v01/`

- `dm_engine.py`: `GameState` → `WorldStore` + `Entity`. `apply_mechanics()` generalizes
  to operate on entities. System prompt changes to request DC-first rolls and entity
  proposals instead of the current flat HP/inventory/enemies tags.
- New: `world_store.py` — the persistence + retrieval logic above.
- `app.py`: needs a two-call turn flow for contested actions, and UI for showing DC +
  roll clearly (ties into the manual dice-roller UI Arie wants for v1 anyway).

## What I'm NOT confident designing alone (Opus review target)

1. **Context budget at scale.** `get_context_for_turn()` above is a placeholder
   strategy (location + recent turns + active quests). Is that actually enough for the
   LLM to stay consistent over a 3-hour session with 50+ entities? Is there a better
   retrieval strategy (embedding search over entity summaries? explicit "important NPCs
   always included" pinning?) — this is the part where getting it wrong means "the DM
   forgets a character 40 turns later," exactly the failure mode Arie is trying to
   eliminate.
2. **Duplicate/near-duplicate entity detection.** My sketch above ("check for near-
   duplicate names") is hand-wavy — a real implementation needs a concrete strategy
   (fuzzy name matching? asking the LLM itself to check? both?).
3. **Consistency edge cases at longer horizons** — what happens if the player leaves a
   location for 20 turns and returns; does the world store correctly restore state
   without the LLM having "forgotten" and re-narrating a duplicate?

I've drafted enough that GLM isn't blocked (the entity model, store interface, and DC
enforcement design are solid enough to start building against), but I'd treat items 1-3
above as open until a stronger model has looked at them specifically.
