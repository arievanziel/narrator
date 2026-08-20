# Narrator v0 — Audio Feedback

**Date:** 2026-08-19
**App:** `narrator_v0/audio_pipeline.py` (Qwen3 TTS + SFX + music)

Please fill in your feedback using `>` prefix on the lines below each question.
Your input will be preserved and shared with all LLMs working on this project.
All LLMs must read `notes/HUMAN-FEEDBACK.md` before starting work.

---

## How to listen

Audio files are in `outputs/narrator_v0/model_comparison/{model_id}/scripted_audio/`:
- `gemini-flash-lite/scripted_audio/` — Gemini 3.5 Flash-Lite
- `gpt-oss-120b/scripted_audio/` — GPT-OSS 120B
- `groq-compound/scripted_audio/` — Groq/compound
- `gemini-flash/scripted_audio/` — Gemini 3.5 Flash

Each model has 3 turns of audio (turn_001, turn_002, turn_003).

An HTML preview page is available at `outputs/narrator_v0/model_comparison/index.html`.

---

## Per-model audio comparison

For each model, listen to all 3 turns and rate the audio quality.

### Gemini 3.5 Flash-Lite (best value DM)

**Narrator voice quality:**

> 

**Character voice quality:**

> 

**SFX placement (no voice overlap):**

> 

**Music selection and ducking:**

> 

**Overall audio experience:**

> 

### GPT-OSS 120B (best rule enforcement)

**Narrator voice quality:**

> 

**Character voice quality:**

> 

**SFX placement (no voice overlap):**

> 

**Music selection and ducking:**

> 

**Overall audio experience:**

> 

### Groq/compound (best combat tracking)

**Narrator voice quality:**

> 

**Character voice quality:**

> 

**SFX placement (no voice overlap):**

> 

**Music selection and ducking:**

> 

**Overall audio experience:**

> 

### Gemini 3.5 Flash (best prose)

**Narrator voice quality:**

> 

**Character voice quality:**

> 

**SFX placement (no voice overlap):**

> 

**Music selection and ducking:**

> 

**Overall audio experience:**

> 

---

## Cross-model comparison

### Which model produced the best [AUDIO] structure?

(Did the DM brain's [AUDIO] section produce good segment breakdowns, or were there issues like missing [SFX] cues, wrong [SCENE] mood, missing character names?)

> 

### Which model's narration felt most natural when spoken aloud?

> 

### Did you notice voice drifting across the 3 turns?

(Qwen3 voice consistency — does the narrator sound the same in turn 1 vs turn 3?)

> 

### Was the audio generation time acceptable?

(~70s for a long turn, ~15s for a short turn)

> 

### Should we switch to Kokoro for character voices (faster but less expressive)?

> 

---

## SFX feedback

### SFX volume

> 

### SFX variety (were the SFX appropriate for the scene?)

> 

### SFX timing (were they placed correctly in gaps between speech?)

> 

---

## Music feedback

### Music volume during narrator vs character dialogue

> 

### Music track selection (did the mood match the scene?)

> 

### Music transitions (were there abrupt volume changes?)

> 

---

## Previous feedback check

These are from your earlier feedback in `HUMAN-FEEDBACK.md`. Have these issues been addressed?

### SFX overlapping voice (was: "sfx taking over voice sounds")

> 

### Music diversity (was: "all demos use the same library music")

> 

### Narrator vs character music volume (was: "lower volume when characters speaking")

> 

### Qwen3 voice drifting (was: "might drift over time")

> 

### Kokoro voices too "reading text out loud" (was: "not active conversation voices")

> 
