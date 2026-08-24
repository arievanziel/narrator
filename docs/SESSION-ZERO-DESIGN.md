# Session Zero — Onboarding Wizard Design (Sonnet, execution-ready)

**Confidence level:** high — this reuses the exact same DM-turn-loop infrastructure as
the main game (same LLM, same turn format, same audio pipeline), just pointed at a
different goal for the first few turns. No new architecture, no Opus needed.

## What Arie asked for (verbatim, `QUESTIONS-FOR-ARIE-V01.md` #10)

> imagine it like a session 0, a written out conversation from the DM with the player.
> The DM asks questions, the player answers, and the DM writes it all down. The goal of
> the DM is to create a world/campaign/story that is the best experience and the most
> fun for the player as possible... all should be live generated and lively asking for
> user input, like a real person would do.

This replaces the current single static intro form entirely. Not a form — a
conversation, narrated like the rest of the game.

## Design: Session Zero is just the DM engine's turn loop, retargeted

Reuse everything already built (LLM call → parse response → TTS → audio queue from
`AUDIO-STREAMING-DESIGN.md`) with a **different system prompt and a different output
target**:

```
Normal play turn:  LLM narrates story, proposes state changes → World Store
Session Zero turn: LLM asks a setup question in character (as "the DM"), player
                    answers in free text or picks a suggested option → answer gets
                    written into `campaign_meta` (see World Store's campaign_meta field)
```

**Turn format for Session Zero** (a variant of the existing 5-section format):
```
[NARRATIVE]   — the DM's spoken question/commentary, in a warm, foreword-like voice
[TOPIC]       — which setup topic this addresses (setting, tone, character, style...)
[SUGGESTIONS] — 2-4 example answers the player could pick, OR free text
[DONE]        — true/false — has Session Zero gathered enough to start the real game?
```

The `[SUGGESTIONS]` here work exactly like in-game choices (already built, already
wired into the audio-streaming pre-generation design) — no new UI pattern needed, reuse
the choice-button component.

## What topics Session Zero should cover

Based on the existing intro form fields (style, setting, character name, persona,
atmosphere, inspiration, dice mode) plus what the World Engine needs to seed a
procedurally generated world:
- Tone/style (already exists)
- Setting/world flavor (already exists, but now feeds `propose_entity()` seed content
  instead of a hardcoded scenario)
- Player character (name, persona — already exists; consider whether stats should be
  chosen here too, given Arie wants full character-sheet management in v1)
- Dice/rules preference (already exists — auto vs manual, and now also which rules
  system flavor if not strict D&D 5e, per the World Engine doc's "rules system doesn't
  have to be D&D 5e" note)
- **New**: pacing/content preferences (combat-heavy vs. roleplay-heavy, content
  boundaries) — this was already drafted months ago in
  `sonnet-work/CAMPAIGN-CONFIG-DRAFT.md`, worth reusing rather than re-deriving.

The LLM decides how many turns Session Zero takes (via `[DONE]`) rather than a fixed
number of steps — matches "live generated" and "like a real person would."

## How this ends and feeds the real game

When `[DONE]=true`, the code:
1. Compiles all Session Zero answers into `campaign_meta` (World Store).
2. Triggers the **opening scene generation** — the DM LLM's first real turn, seeded by
   `campaign_meta`, using the World Engine's `propose_entity()` flow (no hardcoded
   goblins) to create the actual opening scene.
3. Optionally narrates a longer "chapter one" introduction first (Arie mentioned this:
   "the start of the game... could have a longer introduction narrated, to set the
   scene") — this is just a system-prompt instruction for the first real turn to be
   longer/more scene-setting than usual, not new infrastructure.

## Dependency note

This depends on the World Engine's `campaign_meta` field and `propose_entity()` existing
(see `docs/WORLD-ENGINE-DESIGN.md`) to be fully real — but the conversational wizard UI
and turn-loop reuse can be built and tested with a stub/flat dict for `campaign_meta`
in the meantime, then wired to the real World Store once that lands. Don't block one on
the other.
