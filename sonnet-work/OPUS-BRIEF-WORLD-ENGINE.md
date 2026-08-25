# Ready-to-launch Opus review task — World Engine design

**Status: not launched yet.** Trigger this once GLM has the expanded trickster
scenarios in (per `V1-PLAN.md`'s Opus trigger condition) — or launch it now in parallel
if Arie wants to unblock World Engine implementation faster; the two aren't dependent on
each other. Arie's call given it costs quota.

## Task to hand to Opus (paste as the prompt)

> Read `docs/WORLD-ENGINE-DESIGN.md` in the Narrator project
> (/Users/arie/CascadeProjects/narrator). This is a draft architecture for a persistent,
> procedurally-generated game-state store for an AI-narrated D&D-style app, written by
> Claude Sonnet. Also read `narrator_v01/dm_engine.py` for the current (much simpler)
> GameState implementation this is meant to replace, and `docs/SESSION-ZERO-DESIGN.md`
> which depends on it.
>
> Focus specifically on the three open questions flagged in the doc's final section:
> 1. Context budget/retrieval strategy at scale (what does the LLM see each turn, from
>    a world that may have 50+ NPCs/locations, without either blowing the context
>    window or losing consistency).
> 2. Duplicate/near-duplicate entity detection strategy.
> 3. Consistency edge cases at longer horizons (player leaves and returns to a
>    location/NPC after many turns).
>
> Also sanity-check the entity model itself (Entity/WorldStore/apply_turn_mechanics)
> for anything a production implementation would regret later — this is a "get it right
> once" architecture decision, we'd rather find problems now than after GLM has built
> significant code on top of it.
>
> Hard constraint: the user is on a very limited connection right now, so don't propose
> anything requiring new heavy dependencies/downloads (e.g. a vector database, a local
> embedding model) unless you're confident it's necessary — prefer solutions that work
> with what's already in the stack (Python, JSON/SQLite, the existing LLM API calls)
> until proven insufficient.
>
> Output: a revised/annotated version of the design doc, or a clear list of concrete
> changes, that GLM (a capable but less experienced engineer) can implement directly
> without further architecture decisions of its own.

## Why this is worth the cost (per my own stated heuristic)

This is exactly the "design it right once, expensively" case: the World Engine is the
component every other new feature (Session Zero, procedural encounters, character
persistence) depends on, and Arie's explicit, repeated concern ("never trust the LLM to
remember correctly") means getting the retrieval/consistency strategy wrong is the
single most expensive mistake to make right now — worse than a UI bug, worse than an
audio glitch, because everything else gets built assuming it works.

## Why NOT to send everything to Opus

The audio streaming design and Session Zero design (also in `docs/`) are, in my honest
assessment, within normal senior-engineer competency — well-understood patterns
(producer/consumer queues, reusing an existing turn loop for a new purpose). Spending
Opus quota reviewing those would mostly be re-confirming things I'm already confident
about. Reserve the spend for the one place where the stakes and my uncertainty are both
genuinely higher.
