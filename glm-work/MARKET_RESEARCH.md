# Market Research — TTS for D&D Narration (Task 0)

**Author:** GLM-5.2 High, 2026-08-17
**Source:** Compiled from Sonnet's research in `sonnet-work/TTS-LANDSCAPE-RESEARCH-2026.md`
section 4, with hands-on context from Kokoro Phase 1 testing.

**Note on ordering:** The spec (`docs/PHASE_1_TESTING.md`) requested this market
research as a task. It was done out of order — after Kokoro testing — because the
research was conducted by Sonnet in parallel with GLM's hands-on model work. Doing
it now, informed by actual Kokoro testing, gives a more grounded assessment than
doing it cold would have. See `sonnet-work/INSTRUCTIONS-FOR-GLM.md` for context.

## What we're looking for

Per `docs/SPEC.md`: a self-hosted, local-only tool that narrates Claude-authored
D&D text pasted in manually, with **no microphone input**, **no cloud TTS APIs**,
and **multi-voice support** (distinct voices per NPC). The long-term vision is a
hosted multi-user product, so license matters.

## Open-source, self-hostable tools — directly relevant

### 1. Xerophayze/TTS-Story
- **URL:** https://github.com/xerophayze/tts-story
- **What it does:** Web-based multi-voice TTS *studio* app. Supports Kokoro,
  Chatterbox, Qwen3-TTS, and others as swappable backends. Has speaker tagging
  (`[narrator]...[/narrator]`, `[alice-female]...[/alice-female]`), per-speaker
  pitch/speed, pause markers, silence controls.
- **Maintained?** Active (verify commit recency before relying on this).
- **License:** Check repo — likely MIT or Apache.
- **Cost if hosted:** Self-hosted only; no hosted offering.
- **Adopt/fork/reference-only:** **Reference first, potentially fork.** The
  speaker-tagging + pause-marker + per-speaker-pitch system directly addresses
  Arie's Kokoro feedback about pause timing and narrator/character voice
  transitions. Worth reading the tagging/pause-handling code before building
  anything custom. Could be adopted as a frontend if its workflow fits
  paste-from-Claude, but it assumes you're writing/importing story text into its
  own app, not pasting from a separate Claude chat — so it's not a drop-in
  replacement for the target workflow.

### 2. wcharliebrown/multivoice
- **URL:** https://github.com/wcharliebrown/multivoice
- **What it does:** Novel-to-audiobook pipeline built on Qwen3-TTS with
  `[beat]`/`[long beat]` pause tags, automatic sentence-pause insertion,
  emotion/delivery cue parsing (e.g. `(whispering)`), and quality-scored
  regeneration.
- **Maintained?** Active (verify).
- **License:** Check repo.
- **Cost if hosted:** Self-hosted only.
- **Adopt/fork/reference-only:** **Reference implementation.** This is close to
  a reference implementation of exactly the "input engineering" fix Arie's
  Kokoro feedback was asking for — pause tags, emotion cue parsing, automatic
  pacing — just built for Qwen3-TTS instead of Kokoro. The `(whispering)` cue
  parsing is directly relevant to the test scripts in Phase 1 (test script 2
  contains `(whispering)` as a delivery cue).

### 3. vorojar/VibeVoice (fork)
- **URL:** https://github.com/vorojar/VibeVoice
- **What it does:** Local audiobook studio on Qwen3-TTS with LLM-based automatic
  character/emotion detection (no manual speaker tagging needed) and
  per-sentence voice/emotion control.
- **Maintained?** Verify.
- **License:** Check repo.
- **Cost if hosted:** Self-hosted only.
- **Adopt/fork/reference-only:** **Reference for future.** The automatic
  character detection is relevant long-term — Arie pastes narration from a
  Claude chat that already has implicit narrator/dialogue structure, so
  automatic character detection could remove a manual-tagging step. Not needed
  for Phase 1 but worth noting for the app-building phase.

### 4. ekale007/RPAudiobook
- **URL:** https://github.com/ekale007/RPAudiobook
- **What it does:** Browser-based interactive fiction/RPG narrator using local
  Kokoro.
- **Maintained?** Smaller/less mature than the above.
- **License:** Check repo.
- **Cost if hosted:** Self-hosted only.
- **Adopt/fork/reference-only:** **Reference only.** Shows the space is active
  and that Kokoro is being used for exactly this use case (RPG narration) by
  others. Smaller project, less to learn from than TTS-Story or multivoice.

## Commercial products — competitive context only, none fit

All of these are **AI Dungeon Master products** (they run the game, not just
narrate your own Claude-driven session), and all use **paid cloud TTS APIs**
(ElevenLabs, Cartesia, OpenAI TTS) — exactly what the budget/self-hosting
constraints rule out.

| Product | What it is | TTS | Fit |
|---|---|---|---|
| Familiar (Foundry VTT module) | AI co-DM plugin, bring-your-own-LLM | ElevenLabs/Cartesia/OpenAI, per-NPC voices | No — needs Foundry VTT, cloud TTS |
| TableForge | Full AI DM web app | Not detailed, likely cloud | No — full AI DM, not a narration layer |
| Eternal DM | Fully-voiced AI DM web app | Cloud (unspecified) | No — full AI DM |
| Scrollbook | AI co-DM via Discord | Cloud | No — different use case |
| Visionarium | TTRPG multimedia control hub (maps/lighting/music + narration) | Cloud AI tools | No — much broader scope |

## Conclusion

**Nothing existing fits** "self-hosted, local-only, narrates Claude-authored text
I paste in, no AI-DM logic of its own, no mic." The commercial market has
converged on full AI-DM products with cloud TTS, which is the opposite of this
project's constraints. This validates that the project fills a real gap rather
than duplicating an existing tool.

The open-source finds (especially TTS-Story's and multivoice's pause/tagging
approach) are useful building blocks but none should block or replace Phase 1.
Recommend proceeding with local model testing as planned, per spec, and
referencing these projects' tagging/pause-handling code when building the
narration pipeline in a later phase.

## 2026 TTS landscape context

Community leaderboards (Elo-style blind rankings) as of mid-2026 rank
open-weight TTS roughly: Step Audio EditX, Fish Audio S2 Pro (non-commercial),
Voxtral TTS (non-commercial), **Kokoro** (Apache 2.0, still highly competitive
despite being tiny), Maya1, NVIDIA Magpie, **Chatterbox** (MIT), Zonos,
OpenVoice v2. Kokoro punches way above its weight class (82M params vs
multi-billion competitors). Several "better" models are non-commercial-licensed,
which matters given the long-term commercial ambition.

**Qwen3-TTS and Higgs Audio v3 remain the strongest Apache-2.0-licensed options
with real multi-voice/voice-design capability** — this lines up with the spec's
Priority 1 choice of Qwen3-TTS.
