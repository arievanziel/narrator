# Sonnet's Audit of GLM's Phase 1 Work — 2026-08-17

Read-only audit. I have not modified `glm-work/`, `docs/`, or any GLM file. This
supersedes anything I said earlier in the same chat session, since GLM's work moved
forward mid-conversation (weights finished downloading, tests ran, you gave feedback).

## Verified current state (from git log + filesystem, not just GLM's self-report)

**Done and solid:**
- `docs/SPEC.md` / `docs/PHASE_1_TESTING.md` updated with your answered questions +
  market-research task + multi-voice requirements (commits `daa7952`, `d2815dc`)
- Kokoro-82M: fully installed, weights downloaded (312MB), all 3 test scripts run,
  5 `.wav` files in `glm-work/outputs/kokoro/`, detailed notes in
  `glm-work/notes/kokoro_notes.md`, generation speed 4.3–6.8x real-time on CPU (no MPS
  needed — model's small enough CPU is already fast)
- You already gave feedback on Kokoro: *"sounds ok, but not good enough, especially the
  pauses and narrator voice vs character voices changes... I kind of like the fixed
  voices... 54 is quite enough."* GLM logged this and correctly flagged it as likely an
  **input-engineering/pipeline problem, not a model problem** — worth remembering when
  comparing against Qwen3-TTS later.
- `glm-work/notes/download_budget_all_models.md`: exact (not estimated) HF file sizes
  for Qwen3-TTS, Dia2, Higgs Audio V2, Chatterbox, with Apple Silicon compatibility
  notes for each, gated on your per-model approval per the spec's slow-4G rule.

**Still outstanding:**
- **Task 0 (market research) was never done** — spec says do this *first*, before
  installing anything. GLM added the task to the spec doc but never produced
  `docs/MARKET_RESEARCH.md`. This is a process gap worth deciding on (see below).
- Qwen3-TTS not yet downloaded/tested (GLM's recommended next step: 1.7B-VoiceDesign,
  ~4.7GB, confirmed MPS-compatible)
- Dia2, Higgs Audio V2, Chatterbox: nothing done yet (P2/P3, lower urgency)
- `RESULTS.md` comparison writeup not started (needs ≥2 models tested first)
- Open question GLM asked you but hasn't gotten an answer to yet: *"would you like me
  to prototype an improved Kokoro pipeline (pause control, voice-transition smoothing)
  as a follow-up, or is current quality floor too low to bother?"*

## Decision points for you

1. **Market research (Task 0):** skip it permanently, do it now out of order, or do it
   after all models are tested (so it's informed by what you've learned hands-on)?
2. **Qwen3-TTS 4.7GB download** — biggest single ask so far on your 4G connection. Worth
   confirming size/timing tolerance before GLM (or anyone) pulls the trigger.
3. **Kokoro pipeline improvement** — worth doing now, or wait until Qwen3-TTS is tested
   so you're comparing "best possible Kokoro" vs "best possible Qwen3-TTS" rather than
   "default Kokoro" vs something else?

## Model routing recommendations for what's left

| Remaining task | Recommended model | Why |
|---|---|---|
| Market research (Task 0) | GLM or me (Sonnet) | Broad web research + judgment call on competitive landscape — no deep ML/systems skill needed. Cheap either way. |
| Download Qwen3-TTS + run standard test scripts | GLM | Mechanical, same pattern as Kokoro which GLM executed cleanly (including catching and fixing the spacy 429 issue on its own). |
| Qwen3-TTS VoiceDesign API specifics (natural-language voice prompts, consistency across calls) | GLM first; escalate to me only if GLM gets stuck | Documented in GLM's own handoff as the one part of Qwen3-TTS it's least confident about. |
| Kokoro pause/voice-transition pipeline engineering (your explicit feedback) | Me (Sonnet) or Opus, once you decide to pursue it | This is software/audio-pipeline design work (text segmentation, pause insertion, crossfade stitching) — a stronger model likely produces a noticeably better result on the first pass than iterating with GLM. Doesn't need Opus-level reasoning, but is worth a capable model rather than trial-and-error. |
| Dia2 on Apple Silicon (CUDA-first, no official MPS port) | Opus, if/when you decide it's worth pursuing | GLM's own handoff already flags this as the one place it expects to get stuck — genuine CUDA→Apple Silicon porting/debugging, the kind of task where a stronger model's depth pays off. Low priority per spec unless Kokoro/Qwen3-TTS both disappoint. |
| Higgs Audio V2 / Chatterbox | GLM (or skip) | Spec already says these are stretch/low-priority; GLM's sizing research suggests likely skip or quick attempt only. Not worth a smarter model's time. |
| Final `RESULTS.md` comparison writeup | GLM | Mechanical once data exists; explicitly must NOT recommend a final model per spec, which is an easy instruction to follow correctly regardless of model. |

**Bottom line:** GLM has been executing well — it self-corrected a real bug (spacy 429),
produced accurate download-size research, and is appropriately deferring judgment calls
(audio quality, model choice) to you. Nothing so far has needed escalation. The two
places I'd actually expect a stronger model to add value are (a) the Kokoro
pause/voice-transition pipeline redesign, since that's closer to a legit engineering task
than a mechanical install-and-test loop, and (b) Dia2's CUDA→Apple-Silicon porting, if you
choose to pursue it at all.

I have not started any of this work — awaiting your direction per your instruction.
