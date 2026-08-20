# Narrator — Project Roadmap (living document)

**Maintained by:** Sonnet, kept current as the canonical source of truth for overall
project goals and Arie's decisions across all sessions/agents. Other agents (GLM, Opus,
Fable) should read this alongside `docs/SPEC.md` and `docs/PHASE_1_TESTING.md`.

**Last major update:** 2026-08-17 — realignment from "TTS testing only" to full scope.

---

## What changed today

The project started as: *"narrate text Arie pastes in from a separate Claude chat, with
good multi-voice TTS."* `docs/SPEC.md` explicitly scoped out live LLM integration
("Input source: narration text comes from a Claude conversation, pasted in manually...
No live API integration with Claude is in scope right now").

**Arie has now expanded the actual target**, verbatim intent:
> a D&D app that narrates the story, while the user provides text input for each next
> step... Mainly building the world, storyline and character tracking needs more work
> and preparation... basic user input about the campaign style, level of tracking
> details like inventory, fighting, skill use, dice rolls hidden or explicitly, npc
> management, and probably lots more background work that normally a DM would do.

This means the app itself now needs to **run the DM** — not just read aloud text
generated elsewhere. This is a materially bigger scope than Phase 1 assumed. `docs/SPEC.md`
needs a follow-up update to reflect this (flagged below, not yet made — Arie should
confirm before it's treated as settled).

## Three workstreams, going forward

### 1. TTS (voices) — Phase 1, nearly done
Kokoro and Qwen3-TTS VoiceDesign tested and working via `mlx-audio` on Apple Silicon.
Dia-1.6B and Higgs Audio V2 still pending (need Arie's download approval, ~8GB combined).
UTMOSv2 objective scoring needs a re-run. See `RESULTS.md` and `glm-work/` for detail.
**Status: wrap up, don't abandon — GLM continues this as background/lower-priority work.**

### 2. DM Engine (NEW — the actual bottleneck now)
The "brain" that plays Dungeon Master: generates narration, tracks world/character/
inventory state, adjudicates dice/combat, manages NPCs, and takes the player's typed
input each turn. This is the hard, high-value unknown — bigger scope than picking a TTS
model, because it requires:
- **Model choice:** capable-enough LLM for creative long-form narrative + reliable
  structured state tracking (see "Model choice for the DM brain" below — this has real
  budget implications, unlike self-hosted TTS).
- **Campaign configuration:** a basic setup flow so Arie (and later, other users) can
  set campaign style, tracking granularity (inventory? fine-grained skill checks?),
  dice visibility (rolled openly vs. hidden by the DM), NPC memory/consistency, etc.
  Draft in `sonnet-work/CAMPAIGN-CONFIG-DRAFT.md` — a first pass, not final.
- **Prior art:** `MARKET_RESEARCH.md` already surveyed AI-DM products (Familiar,
  TableForge, Eternal DM, Scrollbook, Visionarium) from a "does this replace our TTS
  need" angle. They're now directly relevant from a *different* angle: how do they
  architect state tracking, tool-calling for dice/inventory, and DM system prompts?
  Worth a second, deeper pass — see GLM instructions below.

### 3. Ambient audio (NEW — music + environmental sound)
Background music and environmental soundscapes (tavern ambience, combat stings, forest
sounds) to layer under the narration. Not yet researched at all. Two very different
approaches exist and need comparing: **generative** (e.g. MusicGen, Stable Audio Open —
generate fresh audio per scene) vs. **library-based** (curated royalty-free ambience/loop
libraries triggered by scene-type keywords — much cheaper/simpler, more practical for
real-time use than generating music per turn). See GLM instructions below.

---

## Model choice for the DM brain — the key open decision

This is fundamentally different from the TTS decision: TTS models run locally for free
after a one-time download. An LLM capable of DMing a multi-hour campaign with consistent
state is a much heavier reasoning task, and the realistic options have different cost
shapes:

| Option | Quality for DMing | Cost shape | Notes |
|---|---|---|---|
| Claude Sonnet/Opus via API | High — this is what Arie already uses manually | **Per-token, ongoing** — needs real estimation before committing. ~3hrs/day of narration could add up fast depending on context size per turn (state tracking means growing context). | Directly comparable to what Arie already does by hand in a Claude chat |
| GPT-5 / other frontier API | High | Same shape as above | Worth comparing pricing/quality once we scope token volume |
| Local open-weight model (Llama, Qwen, DeepSeek, Mixtral, etc. via Ollama/llama.cpp on the M1 Max) | Unknown — likely noticeably weaker at long-context consistency and creative DMing than frontier models, but free/private and no per-use cost | Free after setup | Needs real hands-on testing, not just spec-reading, to know if "good enough" |

**Nothing is decided.** Given the original budget framing (~€10/month, which is why TTS
went self-hosted), an API-based DM brain needs a real cost estimate before Arie commits —
this could plausibly blow that budget if usage is as heavy as planned (~3hrs/day). This
is the single most important number to get before architecture decisions are locked in.

---

## Task split (as of 2026-08-17)

**GLM (free, does the bulk of research + implementation legwork):**
1. Finish Phase 1 TTS wrap-up (UTMOSv2 re-run, Dia/Higgs after Arie approves download size, `RESULTS.md`) — lower priority now, don't block on it.
2. Deepen the AI-DM competitor research — HOW do Familiar/TableForge/Scrollbook/Eternal DM/others track world state, handle dice/combat, structure their DM system prompts? (Not just "what do they charge" — this time it's "how is it built.")
3. Research local/offline LLM options for DM-brain duty: which open-weight models are realistic on an M1 Max (32GB) for creative long-context narration, and how would Arie actually test one hands-on (e.g. Ollama + a specific model + a short trial campaign)?
4. Research music/ambient-sound generation: survey both generative models (MusicGen, Stable Audio Open, AudioLDM2 — self-hostable feasibility on M1 Max) and library/loop-based approaches (royalty-free ambience libraries, licensing, how they'd integrate).

**Sonnet (me):**
- Maintain this roadmap as the project's source of truth.
- Drafted `sonnet-work/CAMPAIGN-CONFIG-DRAFT.md` — a first-pass questionnaire/config schema for campaign style, tracking detail, dice visibility, NPC management (answers your "basic user input about campaign style" ask directly — needs your review, not final).
- Audit GLM's research for accuracy/gaps, same as I've been doing for TTS.
- Once research (GLM, above) is back, estimate real API token-cost for the DM-brain option before any commitment.

**Opus/Fable (paid, use narrowly, only when it's clearly worth it):**
- **Recommended trigger point:** once GLM's DM-engine research and my cost estimate are
  both back, a **short, focused Opus session** to actually design the DM-engine
  architecture (state schema, system prompt structure, tool-calling design for
  dice/inventory) is worth the cost. This is a "design it right once" problem, not a
  "grind through many mechanical steps" problem — exactly the kind of task where paying
  for a stronger model's first pass beats iterating cheaply. I'll flag explicitly when
  we hit that point rather than deciding it for you now.
- Not recommended yet: it's premature to spend Opus/Fable budget before the research
  above narrows the actual options.

---

## Status as of 2026-08-20 (major update — v0 app built and tested)

GLM has built and tested the complete v0 app. Summary by workstream — full detail
in `glm-work/SONNET-HANDOFF.md` (the canonical handoff doc for Sonnet):

- **TTS:** Kokoro + Qwen3-TTS VoiceDesign both tested, UTMOSv2-scored (Kokoro 3.65,
  Qwen3 3.57 avg MOS). Arie chose Qwen3 for ALL voices. Dia/Higgs deferred.
- **DM engine:** SoloQuest pattern implemented and tested across 9 models. GPT-OSS
  120B (best rule enforcement, 10/10 trickster) and Gemini 3.5 Flash-Lite (best
  value, Arie's default) are the top picks. 27B+ models required; smaller models
  fail the structured format.
- **Rules lawyer:** 10-scenario trickster test validates cheat resistance. Two
  known vulnerabilities: "waste potion" trick and "control NPC" trick. Fixing
  these is the highest-priority next step.
- **Audio pipeline:** 4 iterations of demo pipeline (v2→v3→v4) based on Arie's
  feedback. SFX in gaps (no voice overlap), music ducking, volume spike fixes,
  SFX fade in/out, MusicGen integration. 15 demo audio files reviewed by Arie.
- **v0 app:** `narrator_v0/` package — web server + DM brain + rules lawyer +
  Qwen3 TTS + SFX + music. Tested end-to-end: 208s narration generated in ~70s.
  Model comparison test run against 4 models with 9 audio files.
- **GUI:** 6 HTML mockups in `gui_v2/`. Arie prefers `ink-extended.html`. Live
  app GUI is simpler — needs to be brought up to mockup quality.
- **Feedback forms:** 3 forms prepared for Arie (GUI, audio, playtesting). Not
  yet filled in.
- **Claude baseline:** Not yet run (needs Arie to do manually).

**Important cost/scope note:** the ElevenLabs SFX API was used for demos (~$0.50
total). Arie decided "B + C" — cached ElevenLabs + new API + free library support.
The app works without ElevenLabs (procedural fallback). This decision is settled.

**Git state:** All code, docs, notes, and test results committed and pushed to
`glm-phase1` branch. Audio WAV files are gitignored (regenerable).

## Decisions log (append here as things get settled)

- 2026-08-17: Arie expanded scope from "TTS narration of externally-authored text" to
  "app runs the DM." `docs/SPEC.md` updated same day to reflect this — "Input source"
  constraint marked superseded, "Current status" points here.
- 2026-08-17: **Budget for the DM brain confirmed — stay near the original ~€10/month
  total.** This pushes hard toward a local/offline LLM for the DM engine rather than a
  paid API (Claude/GPT-5), unless GLM's local-model research finds them clearly not good
  enough for DMing quality, in which case come back to Arie with real numbers before
  defaulting to an API. This materially changes the DM-brain research priority: local
  feasibility (task 2 in GLM's instructions) is now the load-bearing question, not a
  secondary option.
- 2026-08-18: **Arie chose Qwen3-TTS VoiceDesign for ALL voices** (narrator +
  characters). Reassess if too slow or voice drifting cannot be controlled. Kokoro
  is the fallback for characters.
- 2026-08-18: **Arie chose "B + C" for SFX** — cached ElevenLabs + new API generation
  + free/local library support. Paid API use is optional, not mandatory.
- 2026-08-19: **v0 app built and tested end-to-end.** `narrator_v0/` package is the
  merged app. All work committed to `glm-phase1` branch and pushed.
- 2026-08-19: **Arie's default DM model: Gemini 3.5 Flash-Lite** (best value, most
  token-efficient, free with no card). GPT-OSS 120B remains the best rule-enforcement
  option but Groq's 200K token/day quota is tighter.
- 2026-08-19: **Model comparison test run** — 4 models tested with trickster (10
  tricks) + scripted scenario (3 turns) + audio generation. GPT-OSS 120B: 10/10
  trickster. Gemini Flash-Lite: 9/10. Groq/compound and Gemini Flash hit quotas.
