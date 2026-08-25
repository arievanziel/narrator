# World Engine — GLM Implementation Spec

**Author:** Sonnet, 2026-08-22, written per `docs/WORLD-ENGINE-REVIEW-OPUS.md` §10's
instructions. Treats that review's §§3-6 as **decided architecture** — this doc does not
re-litigate them, only translates them into buildable specifics. If you (GLM) disagree
with something here, flag it to Arie/Sonnet rather than silently building something
different — a spec everyone read and diverged from quietly is worse than a spec with a
flagged disagreement in it.

**Read first:** `docs/WORLD-ENGINE-REVIEW-OPUS.md` (the "why"), `docs/V1-PLAN.md` (the
build sequence and dependency ordering — audio queue before DC-then-roll, restructuring
before all of it). This doc is the "what, exactly."

**Prerequisite: v0.3.5 file restructuring must land first** (see `V1-PLAN.md`). Sections
below assume `world_store.py`, `game_loop.py`, and `audio_queue.py` exist as separate
modules, not embedded in `app.py`.

---

## 0. Do-not-build list (copied from Opus review §8 — read this before starting)

Do not build any of these for v1, even if it seems like the "proper" solution:
- Vector DB / embeddings / semantic search
- Knowledge-graph database (Neo4j etc.)
- SQLite (JSON + JSONL is fine to ~10k turns — revisit only when actually measured to be
  a problem)
- Multi-model Director/Actor/Narrator split
- MCP tool server
- Function/tool calling for mechanics (tags stay, for cross-provider portability —
  Arie's model picker includes free models with inconsistent tool-calling support)
- TTA's full 6-tier context stack (the layered assembler in §6 below is the cheap
  version of this idea — don't build the expensive version)

---

## 1. Dataclasses

```python
@dataclass
class Entity:
    id: str                          # stable, opaque-ish: "npc_0007_gorak" — generated
                                      # once at creation, NEVER re-derived from name
    type: str                        # "pc" | "npc" | "location" | "item" | "faction" | "quest"
    name: str                        # current display name
    norm_name: str                   # normalized for matching (see §4)
    summary: str                     # 1-2 sentences, always shown when entity is in context
    attributes: dict                 # type-specific, see §1.1 for required-key tables
    links: list["Link"]              # generic relationships (see below)
    tags: list[str]                  # retrieval hints: ["goblin", "hostile", "tavern"]
    alive: bool = True                # for npc/pc; irrelevant but present for others
    first_seen_turn: int = 0
    last_seen_turn: int = 0
    revisions: list["Revision"] = field(default_factory=list)  # append-only, see §4.2
    known_facts: list["Fact"] = field(default_factory=list)     # append-only, see §4.2
    schema_version: int = 1

@dataclass
class Link:
    rel: str            # "connected_to" | "member_of" | "owns" | "hostile_to" | etc. — freeform
    target_id: str

@dataclass
class Revision:
    turn: int
    field: str
    old: Any
    new: Any
    source: str          # "llm_update" | "guard_correction" | "player_action"

@dataclass
class Fact:
    turn: int
    text: str             # e.g. "told the player about the cave in the northern hills"

@dataclass
class Scene:
    location_id: str
    present_entity_ids: list[str]
    started_turn: int
    encounter: Optional["Encounter"] = None
    light: str = "normal"      # or whatever campaign_meta's rules_profile defines
    time_of_day: str = "day"

@dataclass
class Encounter:
    round: int = 1
    turn_order: list[str] = field(default_factory=list)   # entity ids, initiative order
    active_entity_id: Optional[str] = None

@dataclass
class RollRecord:
    turn: int
    action: str            # free text description of what was attempted
    skill: str
    dc: int
    seed: int               # per-campaign seeded RNG value used
    roll: int                # raw die result
    modifier: int
    total: int
    result: str              # "success" | "failure" | "critical_success" | "critical_failure"

@dataclass
class TurnRecord:
    turn: int
    player_input: str
    narrative: str            # what was actually shown/spoken
    mechanics_applied: list[str]   # human-readable log lines, same as today's apply_mechanics() output
    roll: Optional[RollRecord] = None
    entity_deltas: list[str] = field(default_factory=list)   # entity ids touched this turn

@dataclass
class TokenBudget:
    l0_system: int = 1200
    l1_campaign_meta: int = 300
    l2_directory: int = 1500
    l3_pinned: int = 1500
    l4_working_set: int = 2000
    l5_scene: int = 300
    l6_digest: int = 400
    l7_recent_turns: int = 1500
    l8_rules: int = 400
    l9_input: int = 200
    # Total target ~9.3k max, ~6-8k typical (per Opus §3.3) — these are starting values,
    # GLM should log actual usage and tune, not treat as sacred.

@dataclass
class ContextBundle:
    stable_prefix: str
    volatile_suffix: str
    included_entity_ids: list[str]
    dropped_entity_ids: list[str]     # needed by the guard and by [RECALL]
```

### 1.1 Required attributes per entity type (validated on write — Opus §6.6)

| type | required keys in `attributes` | clamp/validation rule |
|---|---|---|
| `npc` | `hp: int`, `max_hp: int`, `disposition: str`, `voice_description: str` | `0 <= hp <= max_hp`; reject non-int hp (this is the exact "LLM writes hp: 'badly wounded'" failure Opus flagged — validate at the store boundary, reject and log if it fails, don't crash) |
| `pc` | same as npc, plus `inventory: list[item_id]`, `stats: dict` (shape from `rules_profile`, see §1.2) | same hp clamp |
| `location` | `description: str`, `discovered: bool` | none |
| `item` | `description: str`, `owner_entity_id: str \| "world"` | `owner_entity_id` must resolve to an existing entity or be `"world"` |
| `faction` | `description: str`, `disposition_to_player: int` (-100..100) | clamp to range |
| `quest` | `description: str`, `status: "active"\|"completed"\|"failed"`, `objectives: list[str]` | status must be one of the three |

### 1.2 `rules_profile` (Opus §6.10 — data, not code)

Lives in `campaign_meta`, a plain dict, e.g.:
```json
{
  "name": "dnd5e_lite",
  "dc_ladder": {"trivial": 5, "easy": 10, "medium": 15, "hard": 20, "very_hard": 25},
  "ability_list": ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
  "hp_model": "flat",
  "crit_rule": "nat20_success_nat1_failure"
}
```
Session Zero can override this per-campaign (Arie: "the DM engine need not strictly be
D&D 5e"). The deterministic roll resolver (§3) reads DCs and crit rules from here, never
hardcodes them.

---

## 2. `world_store.py` — method signatures

```python
class WorldStore:
    def __init__(self, campaign_id: str, rules_profile: dict): ...

    def resolve_or_create(self, name: str, type: str, proposed_attrs: dict,
                           current_turn: int, current_location_id: str) -> tuple[Entity, bool, str]:
        """Returns (entity, created, reason). `created=False` means it matched an
        existing entity (exact/alias/fuzzy — see §4). `reason` is a short human-readable
        string always logged visibly to the mechanics log, e.g. "matched alias 'the
        innkeeper' -> npc_0003_marla" or "created new: no match within policy window"."""

    def propose_entity(self, name: str, type: str, attrs: dict,
                        current_turn: int, current_location_id: str) -> tuple[Entity, bool, str]:
        """LLM-facing wrapper around resolve_or_create — this is what ENTITY_NEW tags call."""

    def apply_turn_mechanics(self, mechanics_tags: list[str], current_turn: int) -> list[str]:
        """Generalizes today's apply_mechanics(). Returns the human-readable change log
        (same role as today). Every tag in §3 is handled here. Unknown/malformed tags are
        rejected and logged, never silently dropped (Arie's transparency requirement)."""

    def get_context_for_turn(self, player_input: str, budget: TokenBudget,
                              current_scene: Scene) -> ContextBundle:
        """The retrieval function. Implements the layered assembly + scoring from §6."""

    def enter_scene(self, location_id: str, current_turn: int) -> Optional[str]:
        """Updates current Scene. Returns the 'since you were last here' digest text
        (§7) if location_id was last visited >0 turns ago, else None."""

    def exit_scene(self) -> None: ...

    def record_roll(self, roll: RollRecord) -> None:
        """Persists to the turn log BEFORE the outcome is narrated — this is what makes
        rolls traceable/replayable. Called by game_loop.py between the two DC-then-roll
        calls, never by the LLM."""

    def compact_chronicle(self, current_turn: int) -> None:
        """Every K turns (config, default 20): compact turns [1..current-10] into a
        chronicle summary entry via a cheap model call. Raw TurnRecord JSONL is never
        deleted — it's the replay corpus."""

    def save(self, path: Path) -> None:
        """Atomic write: write to path.tmp, then os.replace(). Never leave world.json
        partially written (Opus §6.8 — this is the worst possible bug class for a 30+
        turn session)."""

    def load(self, path: Path) -> "WorldStore": ...

    def migrate(self, data: dict) -> dict:
        """If data['schema_version'] < current, apply migrations in order. Start this
        now even though there's only one version — the alternative is discovering you
        need it after Arie already has real save files."""
```

**Persistence layout (Opus §6.8):** two files per campaign, not one —
`world_<campaign_id>.json` (entity snapshot, overwritten atomically each save) and
`turns_<campaign_id>.jsonl` (append-only, one `TurnRecord` per line, never rewritten).

---

## 3. Full tag vocabulary

| Tag | Emitted by | Grammar | Validation | On failure |
|---|---|---|---|---|
| `HP_CHANGE` | LLM | `HP_CHANGE:<signed int>` | target must be alive & present in scene | reject, log, HP unchanged |
| `ENEMY_HP` | LLM | `ENEMY_HP:<name>,<current>/<max>` | resolves via `resolve_or_create`; `0<=current<=max` | reject, log |
| `ENEMY_DEAD` | LLM | `ENEMY_DEAD:<name>` | **requires roll evidence this turn** (existing guard, keep) | reject, log |
| `ITEM_USED` | LLM | `ITEM_USED:<name>` | must exist in pc inventory; existing waste-potion guard: if ANY named item this turn doesn't resolve, block ALL item use this turn | reject, log |
| `ITEM_GAINED` | LLM | `ITEM_GAINED:<name>` | via `resolve_or_create(type="item")` | — |
| `CONDITION` | LLM | `CONDITION:<target>,<condition>` | target must resolve | reject, log |
| `ROLL_REQUEST` | LLM | `ROLL_REQUEST:<dice> for <skill> DC <n>` | `n` must be in `rules_profile.dc_ladder` range | reject, treat as non-contested turn |
| `ENTITY_NEW` | LLM | `ENTITY_NEW:<type>,<name>,<one-line summary>` | goes through `propose_entity` | dedup per §4, always succeeds (creates or matches) |
| `ENTITY_UPDATE` | LLM | `ENTITY_UPDATE:<name>,<field>,<value>` | field must be in that type's allowed-mutable set; writes a `Revision`, never overwrites in place | reject if entity unresolvable; contradictions applied but logged visibly (§4.2) |
| `ALIAS` | LLM | `ALIAS:<alt name> -> <canonical name>` | canonical must resolve | reject, log |
| `RECALL` | LLM | `RECALL:<name or topic>` | resolved against directory + alias table | if nothing found, tell the LLM so in the re-run, don't silently loop |
| `ENTER_SCENE` / `EXIT_SCENE` | code (not LLM) | — | — | — |
| `ROLL_RESULT` | code (not LLM) | — | fed to phase-2 call, never emitted by LLM | — |
| `QUEST_UPDATE` | LLM | `QUEST_UPDATE:<name>,<status>` | status in `{active,completed,failed}` | reject, log |

**Rejection messages are always visible to the player**, same convention as today's
`[REJECTED — no roll evidence]` — this is load-bearing for Arie's "automatic but
transparent" requirement, don't quietly swallow any rejection.

---

## 4. Duplicate resolution — `resolve_or_create` pipeline

Implement exactly the 8-step pipeline from Opus review §4.1:
1. Code owns IDs; LLM refers by name only.
2. Normalize: lowercase, strip punctuation, strip leading articles/honorifics
   (`the`, `old`, `ser`, `captain`, `mister`, ...— keep this list in `config.py`, easy to
   extend), collapse whitespace.
3. Exact match on `(norm_name, type)`.
4. Alias table lookup (`WorldStore.aliases: dict[str, str]`, populated on every
   successful resolution).
5. Fuzzy: `difflib.SequenceMatcher(None, a, b).ratio() >= 0.85`, same type.
6. Token overlap: shared first token, same type.
7. Candidate policy: same location OR seen within last ~20 turns → treat as existing,
   record alias. Otherwise → create new with `_2` suffix, log visibly.
8. Return `(entity, created, reason)` — every caller must handle the tuple, not assume
   a bare `Entity`.

### 4.2 Contradictory re-description (Opus §4.2 — don't skip this, it's the harder half)

- `summary`/`attributes` changes go through `ENTITY_UPDATE` only, never direct overwrite.
- `known_facts` and `revisions` are append-only lists — never truncated, never rewritten.
- A contradiction (e.g. overwriting a previously-set `species` or fixed physical
  description) is **applied** (don't block the story) but **logged visibly** exactly
  like a rejected mechanic — same UI treatment as `[REJECTED — no roll evidence]`.

---

## 5. Consistency guards (Opus §5 — implement all five)

1. **"Since you were last here" digest** — `enter_scene()` generates this from
   `TurnRecord`s tagged to that location since `last_visited_turn`. Code-generated
   string, no LLM call. Injected as context layer L6.
2. **`[KNOWN]`/`[NEW]` markers** on every entity in the assembled context, plus one
   system-prompt clause telling the LLM not to re-introduce KNOWN entities.
3. **Presence-and-liveness guard** — post-generation, pre-display/TTS: every speaker
   name in `[STORY]` must resolve to an entity that is alive AND in
   `scene.present_entity_ids` (or is narrator/PC). On violation: regenerate once with an
   explicit correction message, then **fail open** with a visible warning — never block
   the turn entirely. This is the single highest-value guard per Opus — implement it
   first among the five.
4. **Hierarchical chronicle compaction** — verbatim last N turns; every K turns, a cheap
   model call compacts older turns into a chronicle entry; chronicle entries later
   compact into chapter summaries. Raw JSONL is the permanent record, never deleted.
5. **Scene as first-class** — already covered by the `Scene` dataclass in §1.

---

## 6. Context assembler — layered assembly with token budgets

```
STABLE PREFIX (cacheable — must be byte-identical across turns whenever content allows)
  L0  system prompt (versioned, see §8)                          budget: 1200 tok
  L1  campaign_meta (session-zero answers, tone, rules_profile)  budget:  300 tok
  L2  world directory: "id | name | type | one-line summary"     budget: 1500 tok
      per entity (~12 tok each -> ~120 entities before truncation)
      Degrade order when over budget: pinned -> seen last 50 turns -> quest-linked -> drop rest
  L3  pinned entities, full records (PC, active quests, current location)  budget: 1500 tok

VOLATILE SUFFIX (never cached)
  L4  working set: full records for scored-in entities (see scoring below)  budget: 2000 tok
  L5  scene block: who's present, encounter/initiative, light/time          budget:  300 tok
  L6  "since you were last here" digest, if applicable                      budget:  400 tok
  L7  last N turns verbatim + rolling chronicle                             budget: 1500 tok
  L8  just-in-time rules: top-3 keyword-scored from rules.json               budget:  400 tok
  L9  player action + resolved roll facts (if phase 2 of DC-then-roll)      budget:  200 tok
```

**Working-set scoring** (integer weights, exactly as specified, tune later from logged data):
```python
SCORE_WEIGHTS = {
    "pinned": 100,            # PC, active-quest entities, current location
    "present_in_scene": 50,
    "named_in_player_input": 40,
    "named_in_last_narration": 30,
    "one_graph_hop": 20,       # via Link
    "linked_to_active_quest": 15,
    "recency_max": 10,          # decays with (current_turn - last_seen_turn)
}
```
Take everything scoring >=100 unconditionally; fill remaining L4 budget by score
descending. Log `included_entity_ids`/`dropped_entity_ids` on every call — needed by the
guard (§5.3) and by `[RECALL]`.

**Cache-breaking bug to fix while building this (Opus §3.3):** `dm_turn()` currently
does `messages.extend(history[-10:])` — a sliding window that changes every turn and
defeats prompt caching entirely once past turn 10. Replace with: keep a growing prefix
of compacted history (via `compact_chronicle`), only the *volatile* L7 layer changes
turn-to-turn.

**`[RECALL]` handling:** if the LLM emits `RECALL:<name>`, resolve against directory +
aliases, append the full record to L4, re-run the turn **once** (hard cap — if still
missing after one recall, proceed without it rather than looping).

---

## 7. Two-call DC-then-roll turn flow (numbered, don't infer ordering)

**Precondition: this waits for Instance B's audio segment queue (v0.4a) to exist — see
`V1-PLAN.md`'s dependency note. Do not build this before the audio queue lands.**

1. Player submits action → `game_loop.py` assembles context via `get_context_for_turn()`.
2. **Call 1** to the DM LLM: system prompt + context. LLM returns `[STORY]` (setup
   narration only) + `[ROLL_REQUEST:<dice> for <skill> DC <n>]` — explicitly forbidden
   from narrating an outcome (system prompt enforces this, see §8).
3. If no `ROLL_REQUEST` in the response → this was a non-contested turn, skip to step 8
   with the single response.
4. **The moment `[STORY]` is available, feed it to the audio queue** (per
   `AUDIO-STREAMING-DESIGN.md`) — playback starts while the rest of this flow continues.
   This is what hides call 2's latency.
5. Code resolves the roll: seeded RNG (`seed` derived from `campaign_id + turn_number`,
   so a session is exactly replayable), apply modifiers from `rules_profile`, compare to
   DC, determine result.
6. `world_store.record_roll(RollRecord(...))` — **persisted before step 7's LLM call**,
   so the roll is traceable even if call 2 fails.
7. **Call 2** to the DM LLM: same context plus `[ROLL_RESULT: roll=14 dc=12 result=success]`
   as a stated fact. LLM narrates only the consequence — cannot alter the outcome. This
   response feeds the audio queue as the next segment, already queued behind call 1's
   audio.
8. `apply_turn_mechanics()` runs on the combined mechanics from whichever call(s)
   happened. Guards from §5 run post-generation, before display/TTS.
9. `TurnRecord` written to the append-only log (§2).

---

## 8. System prompt — required contract, versioned

Keep the existing prompt's overall structure and tone (it's tested and working — don't
rewrite from scratch), but it **must** gain these clauses, and you should budget it
growing toward ~300-350 lines as more `rules_profile`-driven content and the
KNOWN/NEW + RECALL affordances get added (per Opus's research citation that this is
realistic at maturity — don't be alarmed if it's much longer than today's):

- **DC-before-outcome contract**: explicit instruction that `ROLL_REQUEST` must come
  before any outcome narration, and the model must stop and wait — this exists in
  today's prompt already (`dm_turn_dc_roll`), verify it survives the rewrite intact.
- **KNOWN/NEW clause**: "Entities marked KNOWN in your context have already been met.
  Do not re-introduce them as if new."
- **Refer by name, never invent IDs**: the LLM must never emit an `id`-looking string —
  names only, code resolves.
- **RECALL affordance**: how and when to use `[RECALL: ...]`, and that it costs one
  re-run so use it only when genuinely needed.
- **No hardcoded content**: instruct the model to generate NPCs/locations/encounters
  fitting `campaign_meta`, never reuse a fixed scenario.

**Version-stamp it**: `PROMPT_VERSION = "v10"` (or whatever the next number is) as a
module-level constant in `dm_engine.py`. Bump it on every prompt edit — this is cheap
and makes prompt changes an explicit, loggable decision rather than an invisible diff.

---

## 9. Strangler-fig facade contract (v0.4d — must be behavior-neutral)

`GameState` must keep exposing exactly these attributes/methods so every existing
`app.py`/`game_loop.py` call site keeps working unmodified during the transition —
**audit the current codebase for every read of these before starting, list them here as
you find them, and confirm each still works post-facade**:
- `pc_hp`, `pc_max_hp` — become properties reading/writing the PC entity's `attributes`
- `inventory` — property reading PC's linked item entities
- `enemies` — property reading scene's present hostile NPCs
- `chronicle` — property reading the compacted chronicle entries
- `apply_mechanics(text)` — becomes a thin wrapper calling
  `world_store.apply_turn_mechanics()`, same return shape as today

**Definition of done for v0.4d**: replay the existing Playwright test transcripts and
confirm identical (or intentionally-improved, documented) behavior — this refactor
should be provable, not just "looks right."

---

## 10. Test plan

1. **Golden-transcript replay** (`tests/test_replay.py`, new): record real LLM outputs
   to `tests/fixtures/*.jsonl` once, replay against `WorldStore` offline, assert
   resulting state. Zero API cost — primary regression harness given Arie's bandwidth/
   budget constraints.
2. **Fake-LLM trickster harness** (extend `test_trickster.py`): a stub emitting
   adversarial tag sequences directly, no API needed. At least these 12 scenarios:
   - fabricated item claim (existing)
   - dead NPC speaks
   - HP inflation gradually over 30 turns
   - duplicate NPC introduced with a slightly different name
   - contradictory re-description (hair color changes)
   - control-NPC without roll evidence (existing)
   - waste-potion trick (existing)
   - `RECALL` for a nonexistent entity
   - `ENTITY_UPDATE` on an immutable-ish field (species)
   - roll result tampering (LLM tries to restate a different roll in call 2)
   - entity re-introduced after 40+ turns away (tests the digest, §5.1)
   - malformed/unknown tag (must reject and log, not crash)
3. **Property/invariant tests** (`tests/test_invariants.py`, new): apply N random valid
   tag sequences; assert `0<=hp<=max_hp` always, no negative inventory counts, no dead
   entity ever in `present_entity_ids`, every `ENTITY_UPDATE` has a matching `Revision`.
4. **Long-horizon soak** (offline, part of `test_replay.py`): replay a synthetic 200-turn
   transcript, assert the context assembler stays under budget every turn and never
   drops a `score>=100` (pinned) entity.

---

## Build order recap (matches `V1-PLAN.md`, repeated here for convenience)

v0.3.5 (restructure) → v0.4a (audio queue, Instance B) → v0.4c/d (world_store.py +
facade, Instance A, parallel to v0.4a) → v0.4b (DC-then-roll, Instance A, *after* v0.4a)
→ v0.5a (context assembler) → v0.5b (guards) → v0.5c (procedural opening).
