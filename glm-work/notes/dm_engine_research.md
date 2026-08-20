# AI-DM Engine Architecture Research

**Author:** GLM-5.2 High, 2026-08-18
**Task:** INSTRUCTIONS-FOR-GLM.md task 1 — how do existing AI-DM products
architect state tracking, dice, tool-calling, and DM system prompts?
**Lens:** `sonnet-work/CAMPAIGN-CONFIG-DRAFT.md` — the 6 config categories
(campaign style, tracking granularity, dice, NPC management, world persistence,
player input style) are used as the concrete target.

This is a deeper, architecture-focused second pass over the products in
`MARKET_RESEARCH.md`, plus several open-source projects and engineering
write-ups found during research. The first pass asked "does this replace our
TTS need?" — this pass asks "how is it built, and what should we steal?"

---

## TL;DR — the consensus architecture

Across commercial and open-source AI-DM systems, **one pattern dominates: separate
the LLM (narration) from a deterministic rules/state engine (mechanics).** No
serious product asks the LLM to be the whole DM. Specifically:

1. **LLM narrates; code adjudicates.** TableForge states this most explicitly:
   "LLMs are genuinely good at collaborative fiction. What they cannot reliably
   do is track spell slots, adjudicate grapple checks, apply the correct damage
   type, and remember that the rogue spent their Bardic Inspiration die three
   turns ago — all at the same time, correctly, every time." Familiar, Project
   Infinity, and SoloQuest all implement the same split.
2. **Structured world state is the source of truth, not conversation history.**
   State lives in JSON/SQLite/Postgres, is injected into the prompt every turn,
   and is updated via tool calls or parsed machine-readable tags — never by
   trusting the LLM to "remember."
3. **Dice are rolled by code, not the LLM.** Project Infinity: "All rolls
   performed by a dedicated server. The AI sees results, it doesn't generate
   them." SoloQuest makes "rolls mandatory before outcomes" a bolded system-
   prompt rule with explicit wrong/correct pattern examples.
4. **Memory is tiered.** Event log (ground truth) + vector DB (semantic search
   over past scenes) + summaries/knowledge graph (relationships). No one relies
   on the context window alone for a multi-session campaign.
5. **Response format is enforced.** SoloQuest requires 4 sections
   ([NARRATIVE]/[MECHANICS]/[SUGGESTIONS]/[CHRONICLE]); the parser maps
   [MECHANICS] tags to deterministic state transitions. Free-form LLM output
   is the enemy of reliable state tracking.

**For Arie's app:** this consensus is the single most important input to the
later Opus architecture session. The DM engine should be designed around this
split from day one — it is not optional refinement, it is the load-bearing
architectural decision.

---

## 1. Product-by-product architecture breakdown

### 1.1 TableForge (commercial, AI DM web app)
**URL:** tableforge.gg · **Model:** cloud LLM (unspecified) + programmatic rules engine

The clearest articulation of the separation pattern. From their "About" page,
written by a solo developer who works in AI systems:

> "TableForge separates these concerns. The LLM handles storytelling, NPC
> dialogue, world-building, and narrative continuity. A programmatic engine —
> code, not a model — handles every mechanical ruling. Dice rolls, HP tracking,
> combat resolution, condition application, spell slot management: all
> deterministic, all correct. The engine feeds results to the narrator, which
> describes what happened."

**State tracking:** "Full cross-session persistence. NPCs, locations, decisions,
quest state, and narrative threads all carry forward indefinitely." Campaign
memory is comprehensive and crosses every session. Stored in a database (not
public which one).

**Dice:** handled by the deterministic rules engine, not the LLM. 5e SRD 2024
(CC license) adjudication — "consistent, correct rulings every time."

**Tool-calling:** not detailed publicly, but the architecture implies the LLM
calls into the rules engine for mechanical actions rather than adjudicating
them itself.

**System prompt:** not public. The split itself is the architecture — the LLM's
prompt likely scopes it to narration only, with mechanics results fed back in.

**Other features:** auto-generated tactical maps with live token positioning,
AI-generated scene illustrations, scene-matched background audio that shifts
with encounter tone (combat/exploration/mystery/rest). Solo, duo, and up to
6-player support; real-time and async play.

**Relevance to Arie:** this is the architectural template. The "two different
jobs, two different tools" framing is the clearest justification for the
pattern and should be quoted in the Opus architecture doc.

---

### 1.2 Familiar (Foundry VTT module, BYOK)
**URL:** familiarvtt.com · **Model:** bring-your-own-key (Claude/ChatGPT/Gemini
via MCP, or 23 direct providers, or local via LM Studio)

The most tool-rich implementation found. 194-195 tools across 24 domains of
D&D 5e. The AI reads the Foundry world and runs Foundry actions; it does not
author the plot.

**State tracking — the key insight:** "Familiar treats the imported adventure
and your campaign's accumulated record as the source of truth, not the
conversation history. Consistency lives in your prep, not the model's
short-term memory." Two stores:
- The imported adventure (journals, NPCs, statblocks, maps) — the authored
  spine, fixed before the session.
- A persistent record of what the table actually did — carries forward as you
  play, kept current with a ~2-minute end-of-session wrap-up.

Three capabilities do the carrying: (a) full-text search across every journal,
character, scene, item, and recorded transcript; (b) a persistent memory bank
for campaign facts that survive between sessions; (c) a continuously-rewritten
plot summary (the standing "where are we").

**Dice:** Foundry's own dice roll every result. A rules engine sits between the
AI and the game: "Every attack, spell, and move is checked against the D&D 5e
(2024) rules before it lands. Out of range, out of turn, no slot left, action
already spent: the move comes back refused with the reason, the AI adapts."
The referee is optional (one setting turns rule enforcement off).

**Tool-calling:** this is the entire substrate. MCP (Model Context Protocol) is
the wire format — Familiar exposes the Foundry table as an MCP tool server, and
any MCP-speaking client (Claude, Codex, Antigravity, LM Studio local) connects.
"Your AI reads the scene and picks which of the 194 tools to call." Tool calls
reach the world over an authenticated WebSocket. Full audit log of every tool
call. Thread-based: pin/archive/switch between named campaign threads, each
persisting as a Foundry journal entry.

**System prompt:** not public (BYOK — the user's own model + their own system
prompt, or Familiar provides one). The 194-tool surface is the real "prompt" —
the model's behavior is shaped by which tools are loaded ("loads only the
handful of tools your AI needs for what you asked").

**Auto-Pilot:** "Run NPC Turn" — Familiar takes each turn from a battlefield
snapshot, scores moves, reads cover, runs monsters and friendly NPCs (never
player characters). Safety caps and optional turn-by-turn confirmation.

**Relevance to Arie:** the MCP-as-tool-server pattern is directly relevant if
Arie wants the DM brain to be swappable (local Ollama vs. Claude vs. GPT). The
"consistency lives in prep, not model memory" principle is the same as
TableForge's. The 194-tool count is a useful data point on how granular tool
surfaces get for full 5e — Arie's v1 can be much smaller.

---

### 1.3 Scrollbook / Cipher (Discord bot + web app, Claude Sonnet 4.5)
**URL:** scrollbook.app · **Model:** Claude Sonnet 4.5 via Anthropic API

The most detailed public architecture write-up found — a three-part blog series
by the solo engineer who built it (serving 867 Discord servers at peak).

**State tracking — 5-layer cached context architecture:**
1. **System Prompt (cached for days):** DM role, campaign name/era/tone, house
   rules, responsibilities (narrate, voice NPCs, apply 5e rules, track combat,
   adapt, use tools for mechanical tasks). Changes rarely.
2. **World State (cached, updated between sessions):** serialized locations,
   NPCs, factions, active quests.
3. **Session History (cached):** the running conversation.
4. **Current Turn (not cached):** current situation (combat state or world
   state) + player action.
5. (Implied) Character sheets, party, encounters — pulled from Postgres per
   request, scoped to Discord guild ID.

**Dice & mechanics — tool use (function calling):** Claude invokes functions to
roll dice + calculate modifiers, look up spells/monster stat blocks, update
character sheet values, track initiative/combat state, query the campaign
database. "RNG must be provably fair" — dice are a tool, not LLM output.

**Tool-calling — hybrid AI + deterministic functions:** tools handle dice
rolling, stat calculations, database queries. Parallel processing: for
multi-part responses (narration + dice rolls + state updates), the system
parallelizes via `asyncio.gather` — narration, dice, and state updates run
concurrently.

**Cost optimization — prompt caching (90% savings):** the single most important
cost finding in this research. "The system prompt and campaign context were
structurally identical on every request for a given server... it was being sent
and fully reprocessed every single time." Anthropic's `cache_control` field
(2 lines of code) cut API costs 90%. **This is directly relevant to Arie's
budget question — see local_llm_dm_research.md §5.**

**Multiplayer isolation:** every Discord channel = its own session. API
boundary enforces campaign isolation, character ownership, session scoping,
allowed-tools scoping. Players could privately DM the bot without leaking
hidden campaign info or mutating others' characters.

**Infrastructure:** 6 services — Discord bot, REST API, cipher_service.py (owns
all Anthropic calls), ai_usage_tracker.py (token budgeting), ai_extraction_service.py
(PDF/Bedrock), AWS CDK (ECS Fargate, RDS, ALB). Postgres + pgvector for state
and semantic retrieval. Redis for streaming/events.

**Relevance to Arie:** the 5-layer context architecture is a concrete template
for the prompt-assembly design Opus should produce. The prompt-caching 90%
savings is the key number for the API-vs-local cost decision. The multiplayer
isolation boundary design is relevant if Arie's app ever goes multi-user.

---

### 1.4 Eternal DM (commercial web app)
**URL:** eternaldm.com · **Model:** cloud (unspecified)

The least architecturally transparent of the surveyed products. Public info:
dedicated web app (no install), "Garvic" is the AI DM character, character
sheets and in-game resources in-browser. "Uses advanced machine learning
algorithms to understand and adapt to your group's playstyle... learns from
your input, refining its storytelling and decision-making."

**State tracking:** not detailed. Implied persistent (character sheets,
resources in-browser) but no public info on world-state architecture.
**Dice:** not detailed.
**Tool-calling:** not detailed.
**System prompt:** not public.

**Relevance to Arie:** low — no public architecture to learn from. The
"adapts to playstyle" claim is interesting but unverifiable. Skip for
architecture purposes; keep on the competitive-context list only.

---

### 1.5 Visionarium (TTRPG multimedia control hub)
**URL:** visionarium.space · **Model:** cloud AI tools

Different scope from the others — it is a *control hub* for maps, tokens,
music, lighting, VFX across outputs (screens, speakers, lights, props,
streams), with AI-native creation layered on. "Local-first Scene Runner —
prompt → package → play": speak/type a scene idea, it assembles a playable
pack (battlemap, tokens, NPC notes, ambience).

**State tracking:** scene bundles exported/reloaded; opt-in cloud sync. Not a
campaign-state engine in the TableForge sense — more of a scene-composition tool.
**Dice:** not a focus.
**Tool-calling:** AI generates scene assets (maps, tokens, music) on demand.
**System prompt:** not public.

**Relevance to Arie:** relevant to **workstream 3 (ambient audio/music)** more
than to the DM engine. The "prompt → package → play" scene-assembly pattern and
the multimedia-sync architecture are worth referencing when researching
ambient audio. Not directly useful for DM-brain architecture.

---

### 1.6 Project Infinity (open source, electronistu)
**URL:** github.com/electronistu/project_infinity · **Model:** any (Claude,
local, etc. — has `play.py` and `play_with_claude.py`)

A text-based 5e-compatible RPG with an AI DM that "rolls real dice, tracks real
stats, and plays by the rules." The open-source exemplar of the
separation-of-concerns pattern.

**State tracking — persistent character + world:**
- Stats, inventory, gold, spell slots, reputation live in a real database
  (`.player` files, SQLite-style). "No forgetting."
- Reputation system: faction standing persists between sessions; heroic deeds
  and crimes tracked, visible via `/stats`.
- Session timeline: every 5 rounds, the GM auto-summarizes key events, NPCs
  met, mechanical changes, and active hooks into a structured `timeline.md`.
  Persists between sessions, injected on next load. "Cache-friendly: old
  entries reused by the LLM without re-processing."

**Dice — fair dice, server-side:** "All rolls performed by a dedicated server.
The AI sees results, it doesn't generate them." Combat registry: GM registers
all combatants once per battle, initiative auto-rolled for everyone.

**Mechanics — code-owned:** rest & recovery auto-applies hit dice, slot
recovery, Arcane Recovery, effect clearing per SRD 5.1. Leveling: XP
thresholds auto-trigger HP, proficiency, hit dice, and spell slot progression.

**Tool-calling / protocol:** in-game commands (`/stats`, `/save`, `/sync`,
`/quit`) from within the game. The AI reads state but cannot invent it.

**Relevance to Arie:** high — this is a working open-source implementation of
exactly the pattern Arie's app needs, small enough to read in full. The
`timeline.md` auto-summarization every 5 rounds is a concrete, copyable memory
design. The "AI reads but cannot invent" framing is the cleanest statement of
the state-authority principle.

---

### 1.7 AURA (open source, hbbtsk)
**URL:** github.com/hbbtsk/AURA · **Model:** configurable Director LLM
(DeepSeek by default), Actor/Narrator sub-models

A different architectural pattern worth flagging: **layered multi-model.**
Instead of one LLM doing everything, AURA splits the DM job across model roles:

| Layer | Model | Role |
|---|---|---|
| Director | Configurable LLM (cloud Sonnet/DeepSeek/GPT, or local fine-tuned 7B — deferred goal) | Global narrative decisions: conflict advancement, character scheduling, pacing, state mutations |
| Actor | LLM | Character performance: dialogue, action, inner monologue |
| Narrator | LLM | Environment description, scene transitions, narrative breathing room |

**Protocol — frozen 8-field JSON:** the Director Model interacts with the state
machine via a frozen 8-field JSON snapshot and returns 8 sections. "Protocol-
frozen, data-driven." The key design rationale: validating the protocol against
a strong general model first, before committing to a smaller fine-tuned one,
"avoids conflating 'is the protocol viable' with 'is the small model capable
enough.'"

**Relevance to Arie:** the layered-model pattern is more complex than Arie's
v1 needs (one model is enough for solo play), but the **frozen-JSON-protocol
idea is valuable** — defining a stable state-snapshot schema that any model
(local or cloud) must produce/consume decouples the architecture from the model
choice. Worth raising in the Opus session as a design option.

---

### 1.8 SoloQuest prompt architecture (engineering write-up)
**URL:** dev.to/austin_amento_860aebb9f55 · **Model:** cloud LLM (Sonnet-class)

Not a product, but the most detailed public write-up of *how to structure the
DM prompt itself.* Four layers:

**Layer 1 — System prompt as a "rules contract" (v9, ~350 lines):**
- Inventory/resource tracking: "the AI is told explicitly what it can and cannot
  offer based on current character state. Confiscated items are off-limits. When
  a consumable gets used, the model emits a machine-readable tag
  (`ITEM_USED: Item Name`) that the game parser watches for."
- Spell management by caster type: three different systems (prepared/known/
  spellbook casters) with different rules. Warlocks get a dedicated callout
  because "Warlock slots recharge on short rest, not long rest" is a common AI
  failure mode.
- **Rolls mandatory before outcomes:** bolded in the prompt. Shows the wrong
  pattern ("Your sword strikes true, dealing 8 damage!") and the correct one
  (request roll, wait, narrate after). "Without this, the AI just collapses
  into a choose-your-own-adventure book where the dice are decoration."
- Encounter balance guardrails: at levels 1-3, solo encounters have hard HP
  caps baked into the prompt (level 1 enemies: max 7 HP, no multiattack).

**Layer 2 — Inject rules right when needed:** every turn, a keyword extractor
scores the player's input (active enemies? low HP? class? verb used?) and pulls
the top 3 relevant rules from a structured SRD database into the user prompt.
"The model doesn't have to recall Sneak Attack from training data. The rule is
just sitting right there."

**Layer 3 — Game state as source of truth:** the entire engine state is
serialized into every prompt turn — combat state (initiative, turn, distances,
cover), exploration state (pace, light, time, passive perception), death save
tracker, active effects with round durations. "The state in context is the
source of truth, not whatever the model thinks it remembers." The previous
turn's machine-readable combat trace is also passed in to prevent re-narrating
a hit that was a miss.

**Layer 4 — Enforced response structure:** every turn returns 4 sections:
- `[NARRATIVE]` — the story beat, free-form
- `[MECHANICS]` — machine-readable tags only (`HP_CHANGE:-8`,
  `ENEMY_HP: Goblin Scout, 4`, `ROLL:1d20+DEX for Stealth`)
- `[SUGGESTIONS]` — player options, each tagged `roll:true/false`
- `[CHRONICLE]` — one-line campaign log entry, only on significant beats

The parser maps [MECHANICS] tags to deterministic state transitions. The
`roll:true/false` flag on suggestions is checked by the client — if a roll is
required and the player hasn't provided one, the UI stops and prompts for it.
"The AI can't skip the dice."

**Testing approach:** no unit tests for DM behavior ("a spec can't tell you
whether the goblin acted like a goblin"). Instead: debug logging at parse time,
version bumping as change control (each prompt edit = a version, forces cache
miss), and failure-pattern cataloguing — "when the AI broke a rule, I wrote it
down, not as a bug ticket, but as a new clause in the system prompt."

**Relevance to Arie:** **this is the single most useful source for the Opus
architecture session.** The 4-layer prompt design, the [MECHANICS] tag protocol,
the roll-before-outcome enforcement, and the "every failure becomes a prompt
clause" methodology are all directly transferable. The ~350-line system prompt
at v9 is a realistic size budget for Arie's v1.

---

### 1.9 Gemma4 Dungeon Master Companion (open source, nickc672)
**URL:** github.com/nickc672/gemma4-dungeon-master · **Model:** Gemma 4 31B
dense via Ollama, local

A local-first orchestrator that turns a small open-weight LLM into a competent
DM via **three tool-calling passes per turn.** The key structural insight:

> "Most LLM-driven interactive fiction has the same failure mode. You ask one
> model pass to narrate the scene and also record what changed in the world,
> and the text looks fine while the underlying state desynchronizes. The player
> picks up the dagger, the dagger never lands in their inventory. The DM warmly
> remembers an NPC it has structurally never met. **The fix is not a bigger
> model or a fancier prompt — it's structural.**"

**3-pass architecture:**
1. Snapshot the world state (before)
2. Generate the turn (narration + proposed actions)
3. Snapshot the world state (after), derive which entities/items came into
   existence this turn, commit the turn to history

**Why this matters for local LLMs:** this is direct evidence that the
state-desync problem is solved by orchestration, not model size — which is the
core enabler for running a local 30B model as the DM brain (see
local_llm_dm_research.md §3). Gemma 4's native function-calling, long context
(128K-256K), and configurable `<|think|>` are the substrate.

**Relevance to Arie:** high — this is a working local-DM implementation Arie
could test directly (proposed in local_llm_dm_research.md §4 Option A). The
3-pass state-diff pattern should be a candidate for Arie's v1 architecture
regardless of which model runs it.

---

### 1.10 dnd-llm-game (open source, tegridydev)
**URL:** github.com/tegridydev/dnd-llm-game · **Model:** Ollama, model-agnostic
(default llama3.2:1b — too weak, but swappable)

A local-first D&D web app with a **two-model split:** a main DM narrator model
plus a separate smaller utility model for rules/state/action extraction.

- `OLLAMA_CHAT_MODEL` — the main DM narrator (default llama3.2:1b; swap to
  qwen3:32b for Arie's test)
- `OLLAMA_UTILITY_MODEL` — smaller/faster model for dice decisions, world-state
  extraction, and dynamic player choices (default granite4:350m; falls back to
  chat model if blank)

**Architecture:** FastAPI backend with streamed SSE, Vite React frontend,
SQLite via SQLModel, LanceDB local vector store for uploaded PDF lore/RAG,
hero manager with reusable player characters, campaign intro generation,
click-to-roll dice checks "when the rules referee requires uncertainty."

**DM response caps:** max 1000 chars / 200 words (tunable). The utility model
generates player-choice buttons after each DM response, "so the main DM can
focus on narration."

**Relevance to Arie:** high as a **low-effort test harness** — model-agnostic,
already solves orchestration, swap in Qwen3-32B and run the proposed hands-on
test (local_llm_dm_research.md §4 Option A). The two-model split (narrator +
utility) is a simpler alternative to AURA's three-model Director/Actor/Narrator
and may be enough for solo play.

---

### 1.11 Other open-source references (briefer)

- **Pr0degie/dungeonmaster** — structured world state (JSON/SQLite) with a
  **consistency guard** (`DM_CONSISTENCY_GUARD=1`): deterministic code
  (`llm/consistency.py`, no LLM judge) checks that dead or scene-absent
  registered NPCs don't get speech attributed. On violation, the turn is
  regenerated once with a concrete correction; fail-open (a still-violating
  retry is delivered + warn log, never blocks). Time tracking is code-owned
  (minutes counter), rendered to prose for the prompt. Per-system profiles
  (e.g. Imperium Maledictum, not just 5e).

- **SEP blog ("Building an AI Dungeon Master With Real Memory")** — 3-tier
  memory: Tier 1 NoSQL event log (ground-truth of every roll/dialogue/attack),
  Tier 2 vector DB (Qdrant, semantic search over past scene text), Tier 3
  knowledge graph (nodes/edges for characters/factions/locations
  relationships). Proactive retrieval pulls context before the AI needs it via
  a `query_memory` tool that returns a structured "Memory Packet."

- **TTA issue #266 (WorldContextBuilder v2)** — 6-tier token-budgeted context
  assembly designed for 8B local models at 8k context (~7,500 tokens total):
  Tier 1 world rules + narrator voice (~1K), Tier 2 player arc summary (~500),
  Tier 3 current scene via Neo4j 2-3 hops (~2K), Tier 4 key past decision via
  Dolt AS OF (~500), Tier 5 recent N turns verbatim from Redis (~3K), Tier 6
  current input (~500). History compression: older turns → async LLM
  summarization, pre-computed and stored. **This is the reference design for
  running a local model on a tight context budget.**

- **Arcanum RPGs blog ("Why Your AI Campaign Falls Apart at Turn 50")** — the
  accessible explanation of context-window failure: "the model isn't choosing
  to forget your gold; that information has literally scrolled out of its
  view." Fix: an external state log rewritten every turn — "a small block of
  text holding the facts that matter: your money, your inventory, your
  relationships, active quests, what has happened."

- **biscuitWizard/SillyTavern fork** — a TTRPG-reshaped SillyTavern fork with
  a Campaign Manager, AI Director, AI World Narrator, AI character actors,
  skill checks against installable rulesets. JSON/JSONL game state in per-user
  data directory, Qdrant for vector memories. Shows the "scene as first-class
  object" schema pattern.

---

## 2. Synthesis: the architectural patterns

| Pattern | Who does it | Why it matters |
|---|---|---|
| **LLM narrates, code adjudicates** | TableForge, Familiar, Project Infinity, SoloQuest | The consensus. LLMs hallucinate numbers and misrule edge cases; code doesn't. |
| **Structured world state = source of truth** | All serious products | Conversation history is unreliable; a state object injected every turn is authoritative. |
| **Dice rolled by code** | Project Infinity, SoloQuest, Scrollbook, Familiar | "AI sees results, it doesn't generate them." Provably fair, no fudging. |
| **Tiered memory** | SEP (3-tier), TTA (6-tier), Scrollbook (5-layer), Familiar (search + memory bank + summary) | No context window holds a campaign. Event log + vector search + summaries. |
| **Enforced response format** | SoloQuest ([NARRATIVE]/[MECHANICS]/[SUGGESTIONS]/[CHRONICLE]), Gemma4 DM (3-pass) | Free-form output breaks state tracking. Structured sections let a parser extract mechanics. |
| **Tool-calling for mechanics** | Familiar (194 tools, MCP), Scrollbook (function calling), SoloQuest (tags), Gemma4 DM (3-pass) | The LLM requests actions; code executes and returns results. |
| **Consistency guards** | Pr0degie (deterministic NPC-liveness check), SoloQuest (state-authority check) | Deterministic code validates LLM output before delivery; regenerate on violation. |
| **Prompt caching** | Scrollbook (90% Anthropic cost savings) | The single biggest cost lever for API-based DMing. Critical for Arie's budget. |
| **Rules injected just-in-time** | SoloQuest (keyword extractor → top 3 SRD rules/turn) | Don't put all rules in the system prompt; inject the relevant ones per turn. |
| **Failure → prompt clause** | SoloQuest (v9, every clause traces to a real failure) | The system prompt grows from observed failures, not from theory. |
| **Layered/multi-model** | AURA (Director/Actor/Narrator), dnd-llm-game (narrator + utility) | Splits the DM job across models; overkill for v1 solo but a design option. |

---

## 3. Mapping to CAMPAIGN-CONFIG-DRAFT.md categories

Sonnet's draft asked how existing products handle each config category. Here is
the concrete answer per category, to feed the Opus architecture session.

### 3.1 Campaign style / tone (setting, tone, pacing, content boundaries)
- **Scrollbook:** baked into the cached system prompt layer
  (`CAMPAIGN: {name}`, `ERA`, `TONE`, `HOUSE RULES`). Changes rarely → stays
  cached for days.
- **TableForge:** "every campaign starts with a unique opening scene written
  for your specific party composition and backstories" — tone is an input to
  generation, not just a prompt field.
- **Familiar:** lives in the imported adventure (the authored spine) — the AI
  reads tone from the adventure content, not a config flag.
- **For Arie's app:** a campaign-style config block in the system prompt
  (Scrollbook pattern) is the right v1. Keep it cached/stable.

### 3.2 Rules/tracking granularity (inventory, combat, skill checks, sheet depth)
- **SoloQuest:** granularity is encoded in (a) the system prompt's rules
  contract (what to track, what tags to emit) and (b) which state fields are
  serialized each turn. Full 5e is the default; narrative/abstracted would mean
  removing fields and tags.
- **TableForge:** full 5e SRD by default — "spells, conditions, creature stat
  blocks, action economy, concentration, saving throws." No public option for
  abstracted combat.
- **dnd-llm-game:** the utility model handles "dice decisions, scene state, and
  player choices" — granularity is partly a model-prompt concern, partly a
  utility-model-prompt concern.
- **For Arie's app:** granularity should be a **config object that controls
  (a) which state fields are tracked and (b) which [MECHANICS] tags the parser
  recognizes.** Abstracted combat = fewer fields/tags. This is a schema
  decision, not just a prompt decision.

### 3.3 Dice (visible vs. hidden vs. mixed; who rolls)
- **SoloQuest:** the `roll:true/false` flag on each [SUGGESTION] is checked by
  the client before sending — "if a suggestion requires a roll and the player
  hasn't provided one, the UI stops and prompts for it. The AI can't skip the
  dice." This implements visible/mixed dice. Hidden dice (DM rolls internally)
  would mean the engine rolls without surfacing the number.
- **Project Infinity:** "All rolls performed by a dedicated server. The AI sees
  results, it doesn't generate them." `/save` command persists state. Rolls are
  server-side; visibility is a UI choice on top.
- **Familiar:** Foundry's own dice roll every result; visibility is Foundry's
  standard roll-mode setting (public/blind/gm).
- **For Arie's app:** dice visibility is a **UI/engine config**, not an LLM
  concern. The engine always rolls (code); a config flag decides whether the
  number is shown to the player. SoloQuest's `roll:true` suggestion flag is the
  pattern for "player must roll before this action resolves."

### 3.4 NPC management (how many tracked, cross-session memory, voice assignment)
- **Familiar:** semantic search across all journals/characters/scenes/items +
  persistent memory bank for campaign facts + continuously-rewritten plot
  summary. NPCs are Foundry actors — the AI searches for them by name when
  referenced.
- **Scrollbook:** `serialize_npcs(campaign.npcs)` in the world-state layer —
  NPCs are a structured list, cached between sessions, updated as they change.
- **SEP:** knowledge graph nodes for characters/factions/locations with
  relationship edges — supports "how did the player treat this NPC?" queries.
- **Project Infinity:** reputation system tracks faction standing; NPCs met are
  logged in the session timeline.
- **Voice assignment (TTS tie-in):** none of the surveyed products document
  automatic per-NPC voice assignment from a TTS model. Familiar supports
  per-NPC voices via cloud TTS (ElevenLabs/Cartesia/OpenAI) but assignment is
  manual. **This is a gap Arie's app can fill** — mapping tracked NPCs to
  Qwen3-TTS VoiceDesign descriptions automatically is a novel feature, not a
  copied one.
- **For Arie's app:** a tracked-NPC registry (name, personality, relationship,
  known facts, voice description) as part of the world state, with a cap
  configurable in campaign setup. Cross-session persistence via the state
  store. Voice assignment = map NPC personality fields → Qwen3 VoiceDesign
  natural-language description (new work, not prior art).

### 3.5 World/state persistence (session-based vs. persistent; what's remembered)
- **TableForge:** "full cross-session persistence. NPCs, locations, decisions,
  quest state, and narrative threads all carry forward indefinitely."
- **Scrollbook:** Postgres + pgvector, scoped to Discord guild ID; sessions
  auto-expire and rotate to prevent runaway context.
- **Project Infinity:** `.player` files + `timeline.md` (auto-summarized every
  5 rounds, injected on next load).
- **Familiar:** Foundry journals as the persistence layer; threads persist as
  journal entries with full audit logs.
- **TTA:** Redis for recent turns, Dolt (time-travel SQL) for key past
  decisions, Neo4j for scene graph, async summarization for older history.
- **For Arie's app (solo, v1):** Project Infinity's pattern is the right size —
  SQLite/JSON state file + rolling session summary injected on load. Don't
  build the full TTA 6-tier stack for v1; it's designed for 40+ hour / 1000-turn
  campaigns and multi-user scale Arie doesn't need yet.

### 3.6 Player input style (free text vs. multiple choice vs. both)
- **TableForge:** free text — "you just play."
- **SoloQuest:** [SUGGESTIONS] section offers player options, each tagged
  `roll:true/false`. This is multiple-choice *alongside* free text — the
  suggestions are affordances, not constraints.
- **dnd-llm-game:** the utility model generates player-choice buttons after
  each DM response — explicit multiple-choice, generated separately so the main
  DM focuses on narration.
- **For Arie's app:** **both, per Sonnet's draft.** SoloQuest's pattern
  (suggestions as affordances + free text always accepted) is the right v1.
  The `roll:true/false` flag on suggestions is the mechanism for "the engine
  knows this choice needs a dice roll before it can resolve."

---

## 4. What this means for Arie's app — recommendations to Opus

1. **Adopt the separation-of-concerns pattern as the foundational architecture.**
   LLM narrates; a deterministic engine handles dice, HP, combat, spell slots,
   conditions, rules adjudication. This is unanimous across serious products.
   Quote TableForge's "two different jobs, two different tools" in the architecture doc.

2. **Design the world-state schema first.** It is the contract between the
   engine and the LLM. Reference Project Infinity's `.player` + `timeline.md`,
   Pr0degie's JSON state shape, and SoloQuest's serialized engine state. The
   schema must support the granularity config (§3.2) — abstracted vs. full 5e
   is a schema-field-set decision.

3. **Use SoloQuest's 4-section response format as the v1 protocol.**
   [NARRATIVE]/[MECHANICS]/[SUGGESTIONS]/[CHRONICLE] with `roll:true/false`
   flags. It is the most battle-tested public design. The [MECHANICS] tag
   vocabulary (HP_CHANGE, ENEMY_SPAWN, ITEM_GAINED, SPELL_SLOT_USED,
   CONCENTRATION, ITEM_USED) is a starting set.

4. **Add a deterministic consistency guard (Pr0degie pattern).** Before LLM
   output reaches the player/TTS, code checks: dead/absent NPCs don't speak,
   state changes are valid, no referencing items not in inventory. Regenerate
   once on violation; fail-open after that.

5. **Tiered memory, but start small.** v1: SQLite state + rolling session
   summary (Project Infinity's 5-round timeline pattern). v2: add vector search
   over past scenes (Qdrant/pgvector) when sessions get long enough to need it.
   Don't build TTA's 6-tier stack upfront.

6. **Just-in-time rule injection (SoloQuest Layer 2).** Don't put all of 5e in
  the system prompt. Keep a structured SRD rule database; inject the top 3
  relevant rules per turn based on a keyword scorer. This keeps the prompt
  small enough for local models with limited context budgets.

7. **Prompt caching from day one if using an API.** Scrollbook's 90% cost
   savings is the difference between €120/month and ~€20/month at Arie's
   planned usage. The cacheable prefix must be byte-for-byte identical across
   requests — centralize prompt assembly in one code path (Scrollbook's hard-
   won lesson).

8. **TTS voice assignment is a novel feature, not prior art.** No surveyed
   product auto-assigns TTS voices from NPC personality. Mapping tracked-NPC
   personality fields → Qwen3-TTS VoiceDesign natural-language descriptions is
   new work that ties workstream 1 (TTS) to workstream 2 (DM engine).

9. **Consider the frozen-JSON-protocol idea (AURA).** Defining a stable
   state-snapshot schema that any model (local or cloud) must produce/consume
   decouples architecture from model choice — useful given the local-vs-API
   decision is still open (pending local_llm_dm_research.md hands-on test).

10. **Don't build a multi-model Director/Actor/Narrator split for v1.** AURA's
    layered architecture is elegant but overkill for solo play. dnd-llm-game's
    narrator + utility split is the most Arie should consider, and only if the
    main model struggles with state extraction (the 3-pass state-diff pattern
    from Gemma4 DM may obviate the need for a separate utility model).

---

## 5. Sources

- tableforge.gg — how-it-works, about, faq, blog (rules engine separation)
- familiarvtt.com — main, capabilities (194 tools), memory guide, MCP guide
- foundryvtt.com/packages/familiar — module listing (rules engine, auto-pilot)
- eternaldm.com — main (limited architectural detail)
- visionarium.space — main (multimedia hub scope)
- scrollbook.app/blog — behind-the-scenes Claude integration (5-layer context,
  tool use, prompt caching), introducing Cipher, Discord setup
- dev.to/dusttoo — Scrollbook scaling post (6 services, multiplayer isolation),
  prompt caching 90% cost savings post
- github.com/electronistu/project_infinity — fair dice, persistent state,
  timeline.md auto-summarization
- github.com/hbbtsk/AURA — Director/Actor/Narrator layered architecture,
  frozen 8-field JSON protocol
- dev.to/austin_amento — SoloQuest 4-layer prompt architecture (the rules
  contract, just-in-time rule injection, enforced response format)
- github.com/nickc672/gemma4-dungeon-master — 3-pass state-diff orchestration
  for local LLMs
- github.com/tegridydev/dnd-llm-game — two-model split (narrator + utility),
  Ollama, model-agnostic
- github.com/Pr0degie/dungeonmaster — structured world state, consistency guard
- sep.com/blog — 3-tier memory (NoSQL + vector + knowledge graph)
- github.com/theinterneti/TTA issue #266 — WorldContextBuilder v2, 6-tier
  token-budgeted context for 8k local models
- arcanumrpgs.com/blog — "Why Your AI Campaign Falls Apart at Turn 50"
- github.com/biscuitWizard/SillyTavern — TTRPG fork, scene-as-first-class schema
- h-tu.ch/blog — "A Dungeon Master as a long-horizon agent" (error compounding,
  goal drift, context management)
