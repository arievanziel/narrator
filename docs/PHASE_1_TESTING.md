# Phase 1 — Local TTS Model Testing Harness

**Goal of this phase:** before any app gets built, set up a local test rig that lets Arie
generate and compare narration audio from several open-source TTS models, on his own
machine (MacBook M1 Max), with no per-generation limits (unlike the public Hugging Face
Spaces demos, which rate-limit and cap generation length).

This phase produces **no app** — just scripts, sample outputs, a market-research writeup,
and a model comparison writeup. Do not start on the actual narration app until Arie has
reviewed results from this phase and explicitly signs off on a model choice.

**Ask Arie clarifying questions as you go** whenever something is genuinely ambiguous or
consequential — don't stockpile questions until the end, and don't silently assume.

## Task 0 — Market research (do this first, before installing anything)

Given the long-term ambition (see docs/SPEC.md "Long-term vision" — eventually a hosted
app with multiple commercial users), check whether something like this already exists
before building more than necessary:

- Search for existing **open-source, self-hostable** tools that do text-to-speech
  narration specifically for interactive fiction / TTRPGs / audiobook-style long-form
  narration with multi-voice/character support (not just generic TTS wrappers).
- Search for existing **commercial/hosted services** aimed at a similar niche (AI
  audiobook narration, D&D/TTRPG narration tools, interactive fiction narration apps) —
  even if they don't fit Arie's current no-mic/budget constraints, they're useful
  competitive context for the long-term vision.
- For anything promising, note: what it does, whether it's actively maintained, license,
  rough cost if hosted, and whether it could plausibly be adopted/forked/adapted instead
  of building from scratch, or is just useful as a reference.
- Produce `docs/MARKET_RESEARCH.md` summarizing findings. This should inform but not
  block Task 1-3 below — proceed with local model testing regardless of what turns up,
  unless something so obviously fits that it's worth flagging to Arie before continuing.

## Hardware context

- Target machine: MacBook Pro M1 Max (Apple Silicon, unified memory, no CUDA/Nvidia GPU)
- Models must run via CPU or Apple's MPS backend — do NOT assume CUDA is available
- Some candidate models (e.g. Higgs Audio V2, Dia2) are CUDA-first and may run poorly or
  not at all on Apple Silicon — note this clearly per-model rather than forcing it to work
- Devin has full local access to this machine — no need to ask before installing
  dependencies, just record what was installed

## Models to install and test

**Multi-voice support is a hard requirement for the eventual tool** (Arie wants distinct
voices per NPC, not just one narrator voice) — weight this explicitly in evaluation, not
just raw single-voice audio quality. For each model, note clearly whether/how it supports
multiple distinct, consistent voices in one session:
- Native multi-speaker scripting (e.g. Dia2's `[S1]`/`[S2]` tags)
- Voice design/cloning that could be used to assign a different voice per character
  (e.g. Qwen3-TTS)
- Or only single-voice generation, requiring one generation call per character/voice
  stitched together externally (e.g. likely Kokoro) — note how practical that stitching
  approach seems for a live-session workflow

Install and test each of these independently. For each, produce:
1. Install steps that actually worked (record exact commands, flag anything that needed
   a workaround)
2. Generation speed for the test scripts below (wall-clock time, and whether it beat
   real-time — i.e. can it generate audio faster than the audio's own playback duration)
3. Output audio files (save all, don't just describe them) — one per model per test script,
   named clearly e.g. `outputs/kokoro/test1_single_speaker.wav`
4. Any install/runtime issues encountered, and whether Apple Silicon (MPS/CPU) worked or
   needed CPU fallback
5. Multi-voice capability notes as described above

| Model | Notes |
|---|---|
| **Kokoro-82M** | Priority 1. Very lightweight (82M params, ~2-3GB), should run comfortably on CPU/MPS. `pip install kokoro`. Likely single-voice-per-call — test how well stitching multiple voice generations together works for multi-character scenes. |
| **Qwen3-TTS** | Priority 1. Multilingual, supports base voice cloning, preset-timbre style control, and natural-language voice design. Test both the smaller (~0.6B) and larger (~1.7B) variants if feasible; note the speed difference. Test its multi-voice/voice-design features specifically against the multi-speaker script. |
| **Dia2 (1B and/or 2B)** | Priority 2. Dialogue-focused, needs `[S1]`/`[S2]` speaker tags in script input — native multi-voice support, worth weighing this in its favor even if raw quality is close to others. Capped at ~2 min generation per run — test how well chunking longer text works. CUDA-first — test on Mac and clearly report if it fails, degrades, or needs CPU fallback. |
| **Higgs Audio V2** | Priority 3 / stretch. Heavier model (~5B backbone), built around CUDA/vLLM. Likely impractical on M1 Max — attempt install, but if it clearly won't run reasonably, document why and stop rather than fighting it. |
| **Chatterbox** | Priority 3 / stretch, for completeness — already informally tested via HF Space and sounded weak, so low priority, but include for a fair side-by-side if time allows. |

If any model listed here turns out to be unmaintained, broken, or has moved to a
significantly different setup process than expected, note that and move on rather than
sinking excess time into it — flag it in the writeup for Arie to see.

## Test scripts to run through every model

Use the exact same text for every model so comparisons are fair. Save these as files in
`test_scripts/` and reuse them programmatically rather than retyping.

### `test_scripts/1_single_speaker.txt`
(Tests: invented fantasy names, homographs, numbers, punctuation-driven pacing, whispered/emotional delivery)

```
Mireth Pollenwake counted the wounds by lamplight — eleven of them, three deep enough to
worry about. "Hold still," she whispered, "this will sting." The old man's breath caught; a
low growl rattled from somewhere in the reeds outside, and for a moment neither of them
moved.

"You're not from Quill's Hollow," he said — not a question.

"No," she said. "I read the signs wrong once, in a place like this. I won't again."

Thunder rolled. 1,200 years the marsh had stood untouched; tonight, that changed. She
didn't lead him toward the door. She led him away from it.
```

### `test_scripts/2_multi_speaker.txt`
(Tests: multi-speaker dialogue consistency, non-verbal/paced beats, whispered mid-dialogue delivery, a dialect/folklore term — this is also the primary multi-voice capability test)

```
[S1] "Something's wrong with the water," Mireth said, kneeling at the bank.
[S2] "Wrong how?"
[S1] "It's not moving. Not even the reeds." She dipped a finger in — cold, unnervingly
cold — and pulled back sharp.
[S2] "Gods." A pause.
[S1] "Don't. Not yet."
Somewhere behind them, branches cracked — once, twice, then silence.
[S2] "We need to go. Now."
[S1] "Wait —" Her voice dropped to barely a breath. "It's a vodnik. It won't chase if we
don't run."
[S2] (whispering) "That's not exactly comforting."
[S1] "No. It isn't."
```

For single-speaker-only models (Kokoro, Qwen3-TTS base mode), strip the `[S1]`/`[S2]` tags,
run it as one continuous narrated passage, AND additionally try generating S1 and S2 lines
as separate calls with two different voice settings, then note in the writeup how viable
that stitching approach seems (quality, effort, whether timing/pacing feels natural once
combined).

### `test_scripts/3_long_form.txt`

A ~3-4 minute continuous narration passage (roughly 500-600 words) to test consistency
over a longer duration and, for Dia2 specifically, how chunking across the ~2-minute cap
affects flow. Devin: generate a suitable atmospheric fantasy narration passage of this
length in the same tone/style as the two scripts above (marsh/wilderness fantasy setting,
first-person-adjacent close narration) — this doesn't need sign-off, just keep tone
consistent with the other two.

## Output: comparison writeup

Produce `RESULTS.md` at the repo root with:
- A table: model x test script x generation time x real-time-or-not x multi-voice
  capability x subjective notes
- All output `.wav` files committed to `outputs/<model>/` (or linked if too large for git —
  flag this if file sizes become a problem, don't just silently skip committing them)
- A short "what worked / what didn't" per model
- Explicitly do NOT recommend a final model choice — that decision is Arie's, this phase
  is purely to give him enough real audio samples to judge for himself

## Explicitly out of scope for this phase

- No app, UI, or integration with Claude's narration output
- No voice cloning setup beyond what's needed to test multi-voice capability above (skip
  deeper prompt-audio-based voice conditioning/cloning workflows for now)
- No cloud/VPS deployment — local Mac only
- No ElevenLabs or other paid API testing (already ruled out on cost grounds for the
  target usage volume — see docs/SPEC.md background)
- No multi-user/hosted/commercial work of any kind — see docs/SPEC.md "Long-term vision"
