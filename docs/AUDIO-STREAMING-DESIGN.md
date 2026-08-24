# Live Audio Streaming — Design (Sonnet, execution-ready for GLM)

**Confidence level:** high — this is a producer/consumer streaming-media pipeline, a
well-understood pattern. No Opus needed here; this is ready for GLM to implement
directly. Grounded in Arie's exact requirements from `QUESTIONS-FOR-ARIE-V01.md` #1, #3,
#5 and `V1-PLAN.md`'s definition-of-v1 notes.

## Requirements, restated precisely

1. Narration must play **live, generated faster than playback** — not generate-then-wait.
2. **Player's own action/choice gets voiced too** — as soon as they pick a preset choice
   (pre-generate all choice options' audio *before* they choose) or as soon as they start
   typing free text (a few words in, regenerating if they keep editing).
3. While the player's choice-audio plays, **generate the next narration segments in the
   background** — use that time productively.
4. **Audio must always exactly match displayed text** (already a stated principle in the
   current app — keep it).
5. **Quality/speed tradeoff**: prefer best quality (Qwen3), fall back to faster/lower
   quality (Kokoro) if generation is falling behind playback.
6. Short segments first, longer ones after — "buy time" to generate the rest.

## Architecture: a segment queue with three producers, one consumer

```
                    ┌─────────────────────────────────┐
                    │         Playback Queue            │  <- ordered list of
                    │  [seg0: READY] [seg1: GENERATING] │     audio segments,
                    │  [seg2: PENDING] ...               │     each with a state
                    └─────────────────────────────────┘
                              ▲              ▲
                    ┌─────────┘              └──────────┐
          ┌──────────────────┐          ┌──────────────────────┐
          │  Player-input     │          │  DM-response          │
          │  producer         │          │  producer             │
          │  (choice audio,   │          │  (narration segments,  │
          │  pre-generated    │          │  generated as soon as  │
          │  per choice, or   │          │  the [STORY] section   │
          │  free-text as     │          │  streams in from the   │
          │  typed)           │          │  LLM)                  │
          └──────────────────┘          └──────────────────────┘
```

- **Playback queue** is the single source of truth the browser polls/streams from —
  already exists in `narrator_v01/app.py` as the audio-status polling mechanism, just
  needs to become a proper ordered queue instead of one-shot generation.
- **Segment state machine:** `PENDING → GENERATING → READY → PLAYING → DONE`, plus
  `FAILED → FALLBACK_GENERATING` (see quality/speed fallback below).
- **Player-input producer** fires in two modes:
  - *Preset choices*: as soon as `[SUGGESTIONS]` arrives from the LLM, immediately
    kick off TTS generation for all 3-4 choice strings in parallel (they're short,
    cheap, and only one will actually be used — acceptable waste for the latency win).
  - *Free text*: debounce ~2-3 words / ~1 second of no typing, generate, and if the
    player keeps typing, cancel the in-flight generation and restart. This needs a
    cancellable generation call, not just "start another one."
- **DM-response producer** starts generating the first narration segment the moment the
  `[STORY]` section (or the equivalent parsed segment) is available — don't wait for the
  whole LLM response to finish streaming if the API supports token streaming; if not
  (current providers may not stream), at minimum start segment 1's TTS while segment 2+
  are still being parsed from the response.

## Quality/speed fallback — concrete rule, not vague "if slow"

Define it in terms of a real number so it's implementable, not a judgment call at
runtime:

```python
# Budget: how much lead time do we need before this segment is due to play?
lead_time_available = (queue_position_seconds_until_due) 
estimated_gen_time = estimate_tts_time(segment_text, engine="qwen3")  # from RTF data already measured (~0.5-0.6 RTF)

if estimated_gen_time > lead_time_available * 0.7:  # 70% safety margin
    engine = "kokoro"  # faster, RTF ~0.17-0.2, accept lower expressiveness this once
else:
    engine = "qwen3"
```

This reuses RTF numbers GLM already measured (`tts_fidelity_test.py`,
`outputs/tts_comparison/`) — no new research needed, just wiring the existing numbers
into a real-time scheduling decision instead of a fixed engine choice.

## "Short segment first" — a prompt-format nudge, not new infrastructure

Ask the DM LLM's system prompt to structure `[STORY]` so the first segment is short
(one sentence, sets the scene) and later segments can be longer — this is a prompt
engineering change, not a code architecture change. The queue above handles the rest
automatically (segment 1 is quick to generate and starts playing while segments 2+ are
still being generated).

## What GLM needs to build (concrete task list)

1. Refactor `audio_engine.py`'s generation into a queue-based model with the state
   machine above, instead of "generate the whole turn's audio, then serve it."
2. Add the player-input producer (choice pre-generation + debounced free-text TTS).
3. Add the lead-time/fallback scheduling rule above, using existing RTF measurements.
4. Update the browser polling/playback JS to consume an ordered queue instead of one
   audio blob per turn.
5. Verify audio-to-text exact match is preserved through all of this (should be — the
   underlying TTS calls don't change, only when/in what order they're kicked off).

This is a substantial refactor of `audio_engine.py` and `app.py`'s JS, but it's an
engineering task with a clear spec, not an open design question — good candidate for a
single focused GLM instance to own end-to-end rather than splitting further.
