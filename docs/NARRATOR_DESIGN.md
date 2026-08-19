# Phase 2 (design, not yet approved to build) — LLM Story/Narrator Generation

**Status:** Draft design for Arie to review. This is NOT an approved work order yet —
do not start implementation from this doc until Arie explicitly says go. This phase also
depends on Phase 1 (local TTS) being far enough along that we know the audio pipeline's
input format requirements (e.g. whether speaker tags need a specific format for the
multi-voice router).

## Background

Audio generation (TTS) is being handled entirely locally — see Phase 1 — and reportedly
already works well. This doc covers the other half: generating the actual story text
(narration, dialogue, world reactions to player choices) via an LLM, rather than Arie
manually running the story through a separate Claude.ai chat and copy-pasting.

## Cost reality check (do this math again if pricing has changed by the time you read this)

Checked August 2026 Anthropic API pricing, per million tokens:

| Model | Input | Output |
|---|---|---|
| Haiku 4.5 | $1 | $5 |
| Sonnet 5 | $2 (intro, ends Aug 31 2026) → $3 after | $10 → $15 after |
| Opus 4.8 | $5 | $25 |

A 3-hour narration session is roughly 27,000 words of narration output (~36,000 tokens).
At Sonnet's standard post-intro rate that's roughly $0.50/session; Opus roughly $0.85/session.
Even daily heavy play lands around $15-25/month on Sonnet. **Unlike TTS, LLM story
generation cost is not the tight constraint here** — the €10/month ceiling that ruled out
paid TTS APIs does not similarly rule out paid LLM APIs for this project. Re-verify current
pricing before finalizing any budget assumptions, since rates change.

## Proposed architecture

1. **Model routing, not one model for everything:**
   - **Sonnet** (currently Sonnet 5) as the default narrator for routine scenes.
   - **Opus** reserved for flagged high-stakes scenes (climaxes, major character deaths,
     pivotal decisions) — either manually toggled by Arie per scene, or auto-flagged by
     the app based on session/plot structure. Needs a concrete trigger rule — TBD, ask
     Arie for his preference here rather than guessing.
   - **Haiku** for cheap mechanical subtasks: parsing which choice (A/B/C/D/custom) was
     picked, tagging speaker segments for the TTS voice router, extracting world-state
     deltas after a scene so the narrator doesn't have to re-derive "what changed" from
     scratch every turn.

2. **Persistent world/story bible, cached.** Character sheets, established lore, tone
   guide (Critical Role campaign 2/3 style — see docs/SPEC.md), and running plot state
   live in a structured doc fed into the system prompt every turn. Use prompt caching
   (1-hour TTL given multi-hour sessions) so this context is cheap to reuse across a
   whole session rather than paying full input price every turn.

3. **Rolling summarization instead of full history.** Don't resend the entire campaign
   transcript every turn — periodically compress older scenes into a short summary (cheap
   Haiku call) and keep only recent scenes verbatim in context. Keeps cost and latency
   flat over a long campaign instead of creeping up as the campaign grows.

4. **Structured output for the choice menu.** Have the model return narration text +
   the A/B/C/D options as one structured response (e.g. a small JSON block alongside the
   prose) in a single call, rather than a second call just to format the menu.

5. **Inline speaker tagging for TTS handoff.** Have the model output tags like
   `[NARRATOR]` / `[NPC:Innkeeper]` inline as part of the story text, generated as part
   of the same call, so it feeds directly into the multi-voice TTS pipeline from Phase 1
   without a separate tagging pass. Coordinate the exact tag format with whatever the
   Phase 1 multi-voice approach ends up needing (Dia2-style `[S1]`/`[S2]`, or something
   else) — check docs/PHASE_1_TESTING.md and RESULTS.md (once it exists) before finalizing
   the tag format here.

## Open questions for Arie

- What should trigger "use Opus for this scene" — manual toggle, or auto-detection by
  the app? If auto, what signals (Arie flagging key plot beats in advance, session
  length/pacing heuristics, something else)?
- Does the world bible / character sheet get authored by Arie up front, generated
  collaboratively with the LLM at campaign start, or some mix?
- Should there be a hard per-session or per-month budget cap/alert built into the app,
  given this is real per-token spend now (unlike the free local TTS)?

## Explicitly out of scope for this doc / phase

- No implementation yet — this is a design doc pending Arie's review and go-ahead
- No decision yet on how this integrates with the Phase 1 TTS pipeline beyond the
  speaker-tag coordination noted above
- No multi-user/hosted concerns — see docs/SPEC.md "Long-term vision"
