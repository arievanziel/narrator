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

## Current status

We are in **Phase 1** (see `docs/PHASE_1_TESTING.md`): setting up local testing of
several candidate TTS models on Arie's M1 Max, before any commitment to building an
actual app. No app should be built until Arie reviews Phase 1 results and picks a
direction.

## Constraints established so far

- **No microphone input, ever**, unless Arie explicitly types written agreement to use it
  in a given moment. This is a hard requirement carried over from how this project started
  — treat it as non-negotiable unless Arie says otherwise directly to you.
- **Budget:** ideally free or near-free (self-hosted). Paid cloud GPU rental for heavier
  models is a possible fallback but should be treated as a real ongoing cost to flag, not
  a default.
- **Hardware:** primary dev/runtime target is Arie's MacBook M1 Max (Apple Silicon, no
  CUDA). Assume no Nvidia GPU is available locally.
- **Volume:** target usage is potentially heavy — up to ~3 hours/day of narration. Model
  choice and architecture should keep this realistic, not just work for short demo clips.
- **Input source:** narration text comes from a Claude conversation, pasted in manually by
  Arie (copy from chat, paste into the tool). No live API integration with Claude is in
  scope right now — assume manual paste as the input method unless Arie asks for more.

## Candidate TTS models under consideration

See `docs/PHASE_1_TESTING.md` for the current test list and priority order. Leading
candidates from informal testing so far (via Hugging Face Spaces demos, not yet
self-hosted): **Kokoro** (very lightweight, surprisingly good quality) and **Qwen3-TTS**
(heavier but versatile — multi-voice, natural-language voice design, good scripting
support). Dia2 and Higgs Audio V2 are also of interest but have heavier hardware
requirements that may not suit Apple Silicon well.

**No model has been chosen yet.** Do not treat any model mentioned here as a final
decision — Phase 1 exists specifically to get real comparative data before deciding.

## Open questions (ask Arie before assuming)

- Once a model is chosen: local-only tool, or eventually a small web app/UI?
- Does the eventual app need to support multiple distinct NPC voices per session, or is
  a single narrator voice enough?
- Should there be any direct integration with Claude (e.g. a way to pull narration text
  in automatically) or does manual copy-paste stay the workflow long-term?
- Any preference on interaction model — local desktop app, local web page (like the
  earlier Web Speech API prototype), or something else?

If any of these matter for how you structure Phase 1 code (e.g. keeping TTS generation
logic decoupled from any future UI/input layer), lean toward decoupled/modular now so
the answers don't require a rewrite later — but don't build speculative features for
questions that haven't been answered yet.

## Explicitly not decided yet

- Final model choice
- Whether this becomes a proper packaged app at all, vs. a personal script/tool
- Any cloud/VPS component
- Voice cloning / custom voice setup
