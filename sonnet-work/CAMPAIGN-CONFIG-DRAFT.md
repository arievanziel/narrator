# Campaign Configuration — first draft (Sonnet, 2026-08-17)

**Status:** DRAFT for Arie's review, not a spec. Answers the "basic user input about
campaign style, tracking detail, dice visibility, NPC management" need from the
realignment discussion. Meant as a starting point for GLM's research and Opus's later
architecture design, not a final schema — expect this to change.

## Why this exists

A DM engine needs to know, before a campaign starts, how much of the "normal DM
background work" it should do explicitly/visibly vs. quietly in the background. Getting
this wrong either overwhelms the player with bookkeeping or hides so much that the game
feels arbitrary. This draft is a first pass at the questions the app should ask once,
up front (and let the player revisit in settings).

## Draft config categories

### 1. Campaign style / tone
- Setting: high fantasy / grim & gritty / homebrew / published module (which one?)
- Tone: heroic, dark, comedic, mixed
- Pacing: combat-heavy, roleplay-heavy, exploration-heavy, balanced
- Content boundaries: anything off-limits (violence level, mature themes)

### 2. Rules/tracking granularity
- **Inventory:** full item-by-item tracking vs. abstracted ("you have adventuring
  supplies") vs. none
- **Combat:** full turn-by-turn tactical (positions, action economy) vs. narrative/
  abstracted combat (a few rolls, described cinematically)
- **Skill checks:** explicit ("roll Perception") vs. invisible (DM decides outcome,
  narrates it, never surfaces the mechanic)
- **Character sheet depth:** full 5e-style stats vs. simplified/narrative stats

### 3. Dice
- Visible (player sees/rolls dice, numbers shown) vs. hidden (DM rolls internally,
  only narrates outcome) vs. mixed (player rolls for their own actions, DM hides
  monster/secret rolls)
- If visible: does the player actually roll (type a number / use a virtual die) or does
  the DM engine roll and just show the result?

### 4. NPC management
- How many recurring NPCs should the engine actively track for consistency (name,
  personality, relationship to player, known facts)?
- Should NPCs "remember" across sessions (persistent world) or reset per session?
- Voice assignment: does each tracked NPC get a distinct TTS voice automatically, or
  does the player assign voices manually? (Ties directly into the TTS multi-voice work.)

### 5. World/state persistence
- Session-based (state resets each session) vs. persistent campaign (world state,
  quest log, relationships carry across sessions)
- What counts as "world state" the engine must remember: locations visited, quests
  active/completed, faction reputation, time/calendar tracking?

### 6. Player input style
- Free text ("what do you do?") vs. multiple choice (A/B/C/D, matching how Arie
  currently plays via Claude) vs. both available
- If multiple choice: does the engine always offer choices, or only at decision points?

## Open questions this raises for the DM-engine research (for GLM/Opus)

- How do existing AI-DM products (Familiar, TableForge, Scrollbook, Eternal DM) expose
  these settings to their users? Worth checking their onboarding flows specifically.
- Is a JSON/structured "world state" object the right mental model (locations, NPCs,
  inventory, quest flags as fields), with the LLM required to read/update it via tool
  calls each turn? This is the architecture question Opus should weigh in on once
  research is back — don't build this yet.

## What Arie should do with this

Not asking you to fill this out formally right now — just flagging that these are the
categories of setup questions the eventual app will need answers to, so the DM-engine
research (GLM) and the architecture design (later, Opus) have a concrete target instead
of designing in the abstract. If any of these categories feel wrong or missing, say so
and I'll revise.
