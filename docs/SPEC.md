# Project Spec — Narrator

## Background / why this exists

Arie DMs D&D for himself via Claude (text-based story narration + lettered A/B/C/D
choice points). He wants the narration read aloud in a good-quality voice while he
types his responses — critically, **without any microphone input ever being used**
(Claude's native voice mode was ruled out both because it doesn't support silent typed
input alongside voice output, and because he wants a hard guarantee of no mic usage).

Browser-based TTS (phone's built-in accessibility reader, Web Speech API) was tested and
rejected — quality was too poor/robotic to be immersive.

Paid TTS APIs (ElevenLabs) were priced out and ruled out for the target usage volume:
Arie wants up to ~3 hours/day of narration, which at per-character API pricing would cost
far more than his ~€10/month budget. This pushes the project toward **self-hosted,
open-source TTS models** running locally (free, no per-character cost) instead.

Note: the Claude API itself has no audio/TTS generation capability (text and image input,
text output only) — so there's no path where Claude directly produces the narration audio.
Any voice layer has to be a separate TTS component.

## Current status

We are in **Phase 1** (see `docs/PHASE_1_TESTING.md`): setting up local testing of
several candidate TTS models on Arie's M1 Max, before any commitment to building an
actual app. No app should be built until Arie reviews Phase 1 results and picks a
direction.

## Long-term vision (context, not a current-phase task)

The eventual ambition is a **fully online app with multiple commercial users** —
i.e. this could grow into a real product, not just a personal tool. That is NOT
in scope now. For now the target is strictly a local, personal tool for Arie until
he's happy with narration quality and workflow. Keep this vision in mind for
architecture decisions (e.g. avoid choices that would be painful to ever move to a
hosted multi-user setup later) but do not build multi-user, auth, hosting, or
commercial features now — that would be premature.

## Constraints established so far

- **No microphone input, ever**, unless Arie explicitly types written agreement to use it
  in a given moment. This is a hard requirement carried over from how this project started
  — treat it as non-negotiable unless Arie says otherwise directly to you.
- **Budget:** ideally free or near-free (self-hosted). Paid cloud GPU rental for heavier
  models is a possible fallback but should be treated as a real ongoing cost to flag, not
  a default.
- **Hardware:** primary dev/runtime target is Arie's MacBook M1 Max (Apple Silicon, no
  CUDA). Assume no Nvidia GPU is available locally. Devin has full access to this machine.
- **Volume:** target usage is potentially heavy — up to ~3 hours/day of narration. Model
  choice and architecture should keep this realistic, not just work for short demo clips.
- **Input source:** narration text comes from a Claude conversation, pasted in manually by
  Arie (copy from chat, paste into the tool). No live API integration with Claude is in
  scope right now — assume manual paste as the input method unless Arie asks for more.
- **Multi-voice is required, not optional.** Arie wants distinct voices per NPC, not just
  a single narrator voice. Weight this into model evaluation in Phase 1 — note explicitly
  for each model whether/how well it supports multiple distinct, consistent voices in one
  session (e.g. Dia2's [S1]/[S2] tags, Qwen3-TTS's voice design/cloning, vs. Kokoro which
  may need one generation call per voice/character stitched together).

## Candidate TTS models under consideration

See `docs/PHASE_1_TESTING.md` for the current test list and priority order. Leading
candidates from informal testing so far (via Hugging Face Spaces demos, not yet
self-hosted): **Kokoro** (very lightweight, surprisingly good quality) and **Qwen3-TTS**
(heavier but versatile — multi-voice, natural-language voice design, good scripting
support). Dia2 and Higgs Audio V2 are also of interest but have heavier hardware
requirements that may not suit Apple Silicon well.

**No model has been chosen yet.** Do not treat any model mentioned here as a final
decision — Phase 1 exists specifically to get real comparative data before deciding.

## Decided / answered questions

- **Devin should ask Arie clarifying questions as it goes**, throughout Phase 1 and
  beyond — do not silently assume and do not stockpile questions until the end of a
  phase. Ask when something is genuinely ambiguous or consequential.
- **Long-term shape:** see "Long-term vision" above — eventually hosted/multi-user,
  but strictly local-only for now.
- **Multi-voice:** required — see constraints above.

## Open questions (ask Arie before assuming)

- Should there be any direct integration with Claude (e.g. a way to pull narration text
  in automatically) or does manual copy-paste stay the workflow long-term?
- Any preference on interaction model for the eventual local tool — desktop app, local
  web page (like the earlier Web Speech API prototype), CLI, something else?
- For multi-voice: does Arie want to explicitly tag which lines are which speaker (like
  Dia2's [S1]/[S2] format), or would he rather the tool/Claude infer speaker changes from
  the narration text automatically?
- Given the long-term commercial ambition — is there an existing product (open-source
  self-hostable, or a commercial service) that already does something close to this and
  could be adopted/adapted instead of building from scratch? See the new market-research
  task added to `docs/PHASE_1_TESTING.md`.

If any of these matter for how you structure Phase 1 code (e.g. keeping TTS generation
logic decoupled from any future UI/input layer), lean toward decoupled/modular now so
the answers don't require a rewrite later — but don't build speculative features for
questions that haven't been answered yet.

## Explicitly not decided yet

- Final model choice
- Whether this becomes a proper packaged app at all, vs. a personal script/tool
- Any cloud/VPS component
- Voice cloning / custom voice setup
- Anything related to the eventual multi-user/commercial version — not a current-phase
  concern
