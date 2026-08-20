# GLM Handoff — Narrator Phase 1

**Owner:** GLM-5.2 High (running in Devin Local, free tier)
**Branch:** `glm-phase1`
**Working folder:** `glm-work/` (everything I create lives here; I do not edit Arie's docs or any other LLM's folders)
**Started:** 2026-08-17

This is a **living document**. It is updated as I go and contains explicit
"need help from a smarter model" sections whenever I hit something genuinely beyond me.
If you (Sonnet / Opus / Fable / etc.) are picking this up, read this file first, then
`docs/SPEC.md` and `docs/PHASE_1_TESTING.md` for the full project context.

---

## What the project is

Local, self-hosted TTS for D&D narration DM'd via Claude. Phase 1 = comparative test
harness for several open-source TTS models on Arie's M1 Max (32 GB RAM, macOS 15.3.2,
no CUDA). **No app gets built in Phase 1** — just install scripts, test outputs, and a
comparison writeup (`RESULTS.md`) so Arie can pick a model himself.

Hard constraints (from `docs/SPEC.md`):
- No microphone input, ever (non-negotiable unless Arie types explicit written agreement).
- Self-hosted / free or near-free. No paid cloud TTS APIs.
- Apple Silicon only — no CUDA. Models must run on CPU or MPS, or be documented as
  impractical and dropped.
- Multi-voice is required (distinct voices per NPC), not optional.
- Target usage up to ~3 hours/day of narration.
- Input is manual paste from a Claude chat (no live Claude API integration in scope).

## Environment (verified 2026-08-17)

- macOS 15.3.2, Apple M1 Max, 32 GB unified memory, 533 GB free disk.
- System Python 3.14 (Homebrew) — **too new for torch/transformers ecosystem**.
- Only `numpy 2.4.6` installed system-wide; no torch, transformers, kokoro, etc.
- `ffmpeg` available via Homebrew.
- **Arie is on a slow mountain 4G connection** — show exact download sizes BEFORE
  fetching anything, and get explicit OK per download.

## Decisions I've made (within my mandate)

1. **Python env:** `uv` + Python 3.12 in a local `.venv` inside `glm-work/`.
   - Rationale: uv is fast, isolated, easy to remove. Python 3.12 is the sweet spot for
     torch/transformers/kokoro compatibility as of mid-2026.
   - If a smarter model disagrees, the venv is disposable — no global state polluted.
2. **Branch + folder:** `glm-phase1` branch, all my work under `glm-work/`.
3. **Model order:** one at a time, Kokoro first (lightest, highest signal-to-effort
   ratio), then Qwen3-TTS, then Priority 2/3 only if Arie wants to continue.
4. **Per-model flow:** research exact download sizes → present to Arie → get OK →
   download → install → run all 3 test scripts → save `.wav` outputs → log timings →
   write up.

## Current status

### Phase 1 core testing

- [x] Branch `glm-phase1` created.
- [x] `glm-work/` folder structure created (`test_scripts/`, `outputs/`, `logs/`,
      `notes/`).
- [x] Test scripts written verbatim from spec:
      `1_single_speaker.txt`, `2_multi_speaker.txt`, `3_long_form.txt`
      (the long-form one I generated myself per spec instruction — same marsh/wilderness
      fantasy tone, ~530 words).
- [x] This handoff doc started.
- [x] Kokoro download sizes researched and presented to Arie (~600-740 MB total).
- [x] Arie approved full Kokoro download (2026-08-17).
- [x] uv + espeak-ng installed via Homebrew.
- [x] Python 3.12.14 venv created at `glm-work/.venv`.
- [x] Kokoro 0.9.4 + torch 2.13.0 + transformers 5.15.0 + deps installed.
- [x] spacy `en_core_web_sm` model installed manually (workaround for 429 rate limit).
- [x] Kokoro model weights downloaded (~312 MB, cached in ~/.cache/huggingface).
- [x] Smoke test passed (4.6s audio, 1.1x real-time).
- [x] **Kokoro (PyTorch): COMPLETE.** All 3 Phase 1 test scripts run (5-7x real-time
      on CPU). 5 output `.wav` files in `glm-work/outputs/kokoro/` (~12 MB).
      Notes at `glm-work/notes/kokoro_notes.md`. Arie's feedback logged.
- [x] Market research written: `glm-work/MARKET_RESEARCH.md` (Task 0 from Sonnet).
- [x] Pipeline design reference written: `glm-work/notes/pipeline_design_reference.md`
      (key patterns from multivoice and TTS-Story for pause/emotion/voice handling).
- [x] mlx-audio 0.4.8 installed in the venv (MLX/Metal acceleration path).
- [x] Confirmed mlx-audio supports Qwen3-TTS VoiceDesign via `instruct` parameter.
- [x] Confirmed mlx-audio supports original Dia-1.6B (NOT Dia2 — no MLX port exists).
- [x] Confirmed mlx-audio supports Higgs Audio V2 (q6 4.75GB, q8 6.18GB).
- [x] Test runners written for all remaining models:
      `run_qwen3_voicedesign.py`, `run_dia_1_6b.py`, `run_higgs_audio.py`,
      `run_kokoro_mlx.py` (MLX Kokoro for comparison with PyTorch version).
- [x] Prototype web app written: `glm-work/prototype_app/app.py`
      (paste → generate → listen, supports all 3 model types).
- [x] UTMOSv2 installed for objective quality scoring (MOS 1-5 prediction).
- [x] **Qwen3-TTS VoiceDesign 8bit: COMPLETE.** Model downloaded to
      `glm-work/models/qwen3_voicedesign_8bit/` (~3.07 GB). All 3 test scripts run.
      Results: 2.3-2.5x real-time, peak memory ~21GB for long-form, distinct S1/S2
      voices confirmed. RESULTS.md updated with full data. Outputs in
      `glm-work/outputs/qwen3_voicedesign/` (5 WAV files).
      Bug fixed: MODEL path changed from HF repo ID to local path (Sonnet catch).
      Bug fixed: _000 suffix handling + max_tokens=2400 for long-form.
- [~] **UTMOSv2 scoring: IN PROGRESS.** Model file was corrupted (truncated at
      523 MB / 818 MB expected). Re-downloading fresh. Once complete, will score
      all Kokoro + Qwen3 outputs and update RESULTS.md.
- [ ] Test Dia-1.6B via mlx-audio (3.22 GB download, original Dia not Dia2).
      **Awaiting Arie's approval for download.**
- [ ] Test Higgs Audio V2 via mlx-audio (q6 4.75 GB or q8 6.18 GB).
      **Awaiting Arie's approval for download.**
- [ ] Test Kokoro MLX for speed comparison with PyTorch version.
- [ ] `RESULTS.md` writeup (per spec: comparison table, do NOT recommend a final model).

### Parallel tasks (Task A/B/C from PARALLEL-TASKS.md)

- [x] **Task A — Voice catalog: COMPLETE.** `run_voice_catalog.py` generates samples
      for all 28 English Kokoro voices (20 American + 8 British). 56 individual WAVs
      (narration + dialogue per voice) + 1 ensemble story "The Last Lantern" (30
      segments, all 28 voices). HTML preview page at
      `outputs/voice_catalog/index.html`. Notes at `notes/voice_catalog.md`.
- [x] **Ensemble story #2 — "The Descent of Ysolde's Light": COMPLETE.**
      `run_ensemble2.py` generates an epic 47-segment story with a fixed cast of
      7 characters + 1 narrator, 4 locations, name-calling in dialogue, dramatic
      narration. Both Kokoro and Qwen3 versions generated. Files:
      `outputs/voice_catalog/ensemble2_the_descent.{md,wav}` (Kokoro, 9.5 min) and
      `outputs/voice_catalog/ensemble2_the_descent_qwen3.{md,wav}` (Qwen3, ~20 min).
- [x] **Task B (redirected) — play_test.py + GUI mockup: COMPLETE.**
      `play_test.py` for direct streaming playback. `notes/gui_mockup.html` —
      interactive HTML mockup of the narrator app UI with simulated story flow
      (Arie has been iterating on this).
- [x] **Task C — Input parser: COMPLETE.** `narrator_parser.py` — model-agnostic
      text preprocessing that parses speaker tags, emotion cues, and pause markers
      into Segment objects. `test_parser.py` — 41/41 tests passing.
      (Arie made small fixes: multiple-space collapse, dialogue detection for
      mixed narrator attribution, prefix spacing in format_segments.)
- [x] **Cleanup: `narrator_parser.py.bak` deleted** (stray backup file, per Sonnet).

### DM-engine research workstreams (per Sonnet's 2026-08-17 scope expansion)

- [x] **Research Task 3 — Ambient audio/music: COMPLETE (expanded with API options).**
      `notes/audio_ambience_research.md` surveys three approaches:
      (a) self-hosted generative models (MusicGen, AudioGen, Stable Audio Open,
      AudioLDM2) — sizes, M1 Max feasibility, licensing; (b) library/loop-based
      (Tabletop Audio, OpenGameArt, Ivan Duch, Classic Campaign pack, Sonniss GDC);
      (c) **audio generation APIs** (ElevenLabs SFX/Music, Google Lyria, Stable Audio
      API, Suno, Udio, Replicate) — pricing, quality, licensing, fit for ambient/SFX.
      **Recommendation: hybrid — free CC0/CC-BY library tracks for ambient beds +
      ElevenLabs SFX API for custom one-off stings.** API path is strictly better
      than self-hosted generative for our use case (no download, no MPS risk,
      commercial license, ~$1-5 one-time for a full generated library cached forever).
      Arie's feedback on v1 demo: synthesized beds "sound like white noise, not
      ambience" — v2 demo uses real library tracks instead.
- [x] **Ambience demo v1: COMPLETE but Arie rejected.** `make_ambience_demo.py`
      synthesized 3 procedural ambient beds (tavern, forest, tense-marsh) with
      numpy/scipy. Arie: "they all sound like white noise or just background noise,
      not ambience or specific story related sounds. Not feasible."
- [x] **Ambience demo v2: COMPLETE — real library tracks.** `make_ambience_demo_v2.py`
      layers 3 actual royalty-free music tracks from OpenGameArt (CC0 + CC-BY) under
      existing Kokoro narration with side-chain ducking. Tracks downloaded (~10 MB,
      not model downloads): "The Old Tower Inn" (CC0, tavern), "RPG Ambient 4 The
      Dark Woods" (CC-BY, tense strings — matches the marsh narration), "Loopable
      Dungeon Ambience" (CC0, wind + drips). Outputs: `v2_dark_woods.wav`,
      `v2_dungeon.wav`, `v2_tavern.wav` in `outputs/ambience_demo/`.
- [ ] **Research Task 1 — AI-DM competitor architecture:** NOT STARTED this session.
- [ ] **Research Task 2 — Local LLM feasibility for DM duty:** NOT STARTED this session.
- [ ] **Research Task 4 — Read CAMPAIGN-CONFIG-DRAFT.md as lens for Task 1:** NOT STARTED.

### Downloads flagged for Arie / download assistant (NOT downloaded this session)

Per instructions, no large downloads without asking. To hands-on test the generative
ambience path later, one of these would be needed (recommend NOT downloading yet —
library path is clearly better for v1, and the demo lets Arie hear the concept free):

| Model | Size | Why | Risk |
|---|---|---|---|
| `facebook/audiogen-medium` | ~3.6 GB | Test generative ambience/SFX | CC-BY-NC; ~0.3-0.4x realtime on M1 Max |
| `stabilityai/stable-audio-open-small` | ~1.5 GB | Most-permissive generative option | **M1/M2 MPS accuracy issues reported** |
| `facebook/musicgen-small` | ~1.2 GB | Test generative music stings | CC-BY-NC; lowest quality variant |

## Test scripts

Located at `glm-work/test_scripts/`. The first two are Arie's exact text from
`docs/PHASE_1_TESTING.md` (copied verbatim — I do not modify human input). The third
(`3_long_form.txt`) I generated per the spec's instruction to Devin to write a ~500-600
word atmospheric fantasy passage in the same tone as the first two.

For single-speaker-only models (Kokoro, Qwen3-TTS base mode), the multi-speaker script's
`[S1]`/`[S2]` tags will be stripped and run as one continuous passage, with a note in
`RESULTS.md` that this test was adapted — per spec.

## Where I need help from smarter models

### 1. Dia2 on Apple Silicon (RESOLVED — no MLX port exists)

**Finding:** mlx-audio supports the **original Dia-1.6B** (via `mlx-community/Dia-1.6B-fp16`,
3.22 GB) but does **NOT** support Dia2. No mlx-community port of Dia2 exists as of
2026-08-17. Dia2 is CUDA-first with no MPS path.

**Decision:** Test the original Dia-1.6B via mlx-audio instead. It supports native
`[S1]`/`[S2]` speaker tags, which is its key strength. Dia2 is skipped unless Arie
specifically requests it and a smarter model is willing to port it.

**What I need from a smarter model (only if Arie wants Dia2 specifically):**
- A proper MLX port of Dia2 (this is real porting work, not a config change)
- Or confirmation that Dia2 runs acceptably on CPU with the 1B model

**Cost sensitivity:** Only worth a smarter-model call if Arie explicitly wants Dia2
and is unsatisfied with Dia-1.6B + Qwen3-TTS + Higgs results.

### 2. Kokoro input engineering / post-processing (per Arie's feedback)

**Stuck on:** Arie's feedback on Kokoro: "sounds ok, but not good enough, especially
the pauses and narrator voice vs character voices changes." He suspects this is an
input-engineering + post-processing problem, not a model-quality problem.

**What I think the issue is:**
- Pauses: Kokoro's g2p + generate_from_tokens doesn't give fine-grained control
  over pause length between sentences/paragraphs. The default pacing may be too
  uniform or too rushed.
- Voice transitions: in test2b, I stitched per-line generations with hard
  concatenation (no crossfade, no gap). This creates abrupt speaker changes.

**What I need from a smarter model (if Arie wants me to optimize Kokoro):**
- Best practices for pause control in Kokoro (does it respect SSML? `<break>` tags?
  punctuation-driven pacing? silence insertion between chunks?)
- Audio stitching techniques for multi-voice TTS (crossfade duration, room tone
  insertion, breath sounds between speakers)
- Whether a smarter model (Sonnet/Opus) would be better at writing the
  text-preprocessing layer that feeds Kokoro (e.g. splitting narration into
  narrator-vs-dialogue segments, inserting pause markers, assigning voices per
  segment type)

**Cost sensitivity:** This is worth a smarter-model consult IF Arie decides Kokoro
is the model he wants to use and just needs the pipeline improved. If Qwen3-TTS
tests significantly better, this becomes moot. Recommend: test Qwen3-TTS first,
then decide.

### 3. Qwen3-TTS VoiceDesign API (RESOLVED — tested and working)

**Finding:** mlx-audio 0.4.8 supports Qwen3-TTS VoiceDesign natively via the
`instruct` parameter in `generate_audio()`. The model type is detected from config
(`tts_model_type == "voice_design"`), and the `instruct` parameter is a natural-
language voice description. No PyTorch/MPS debugging needed — MLX/Metal handles
acceleration.

**Model used:** `mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit` (3.08 GB),
downloaded manually via curl to `glm-work/models/qwen3_voicedesign_8bit/` (local
path, not HF cache — avoids re-download due to mlx-audio's get_model_path() only
treating strings starting with `.`, `/`, or `~` as local paths).

**API confirmed working:**
```python
from mlx_audio.tts import load_model
from mlx_audio.tts.generate import generate_audio
model = load_model("models/qwen3_voicedesign_8bit")  # local path
generate_audio(text="...", model=model, instruct="A calm, warm female narrator...",
               lang_code="en", max_tokens=2400)  # 2400 for long-form
```

**Results (in RESULTS.md):**
- Real-time factor: 2.3-2.5x (slower than Kokoro's 5-7x but usable)
- Peak memory: ~21 GB for long-form (fits in 32 GB)
- S1/S2 voice descriptions produce clearly different voices
- Long-form: 192s audio in one call with max_tokens=2400
- Output files have _000 suffix (handled in script)
- Also generated ensemble story #2 with Qwen3 voices (~20 min audio)

### Template for when I get stuck

> **Stuck on:** <one-line description>
> **What I tried:** <bullet list>
> **What I think the issue is:** <my best guess>
> **What I need from a smarter model:** <specific question>
> **Cost sensitivity:** only worth spending a smarter-model call on this if <criterion>.

## Notes for whoever picks this up after me

- I am GLM-5.2 High on Devin Local's **free tier**. I should not be treated as
  authoritative on subtle PyTorch/MPS issues, CUDA-first model porting, or anything
  requiring deep ML systems knowledge. When in doubt, I will write a handoff section
  here rather than guess.
- Arie cares about cost of smarter-model calls. Don't escalate trivial issues — only
  hand off things that genuinely need a smarter model.
- Arie's docs (`docs/`, `README.md`) and any other LLM's working folders are
  **off-limits** for editing. Read them, don't write them.
- All my outputs (audio, logs, notes) stay under `glm-work/`.

---

## Narrator v0 — Merged App (2026-08-19)

**Status: BUILT and tested end-to-end. Ready for Arie's real play session.**

Per Sonnet's instructions (`sonnet-work/INSTRUCTIONS-FOR-GLM.md` update 2026-08-19)
and `docs/V0-PLAN.md`, I merged the proven pieces into a single working app:

```
Player types action → DM brain (LLM) → rules lawyer validates →
narration pipeline (Qwen3 TTS + SFX + music) → audio plays in browser →
player sees suggestions, types next action
```

### Files created

| File | Purpose |
|------|---------|
| `narrator_v0/__init__.py` | Package init |
| `narrator_v0/config.py` | All config: paths, voices, music, SFX, DM brain settings |
| `narrator_v0/cast.json` | Character → voice description mappings (editable by Arie) |
| `narrator_v0/dm_engine.py` | GameState + rules lawyer + extended system prompt with [AUDIO] section |
| `narrator_v0/audio_pipeline.py` | Qwen3 TTS + SFX placement + music ducking → mixed WAV |
| `narrator_v0/app.py` | Web server with audio generation + playback |
| `narrator_v0/run_trickster.py` | Standing adversarial test (10 cheating attempts) |

### What it does

1. **DM brain**: Gemini 3.5 Flash-Lite (Arie's pick, best value) via Google AI Studio
   free tier. Auto-detects provider from model name. Also supports Groq, SambaNova,
   Cerebras, OpenRouter.
2. **Rules lawyer**: deterministic Python state engine from `test_api_dm.py` —
   validates all [MECHANICS] tags against actual game state. Catches cheating.
3. **Extended system prompt**: adds a 5th section `[AUDIO]` to the DM response —
   structured data for the narration pipeline:
   - `[narrator] text` → narrator TTS
   - `[CharName] "dialogue"` → character TTS
   - `[SFX: key]` → sound effect
   - `[SCENE: mood]` → music track selection
4. **Audio pipeline**: Qwen3 VoiceDesign for ALL voices (per Arie's feedback:
   "if we can run everything fast enough on qwen3, it is preferrable"). Imports
   proven audio functions from `produce_demos_v2.py` (strip silence, SFX in gaps
   with no voice overlap, music ducking with narrator vs character volume).
5. **SFX**: cached ElevenLabs + new API calls + procedural fallback. Per Arie's
   decision: "B + C" (cached + new API + free library support).
6. **Music**: 9 CC0/CC-BY tracks mapped to scene moods (combat, tense, horror,
   mystery, exploration, tavern, emotional, victory). Different volume during
   narrator vs character dialogue (per Arie's audiobook research request).
7. **Web GUI**: extends `serve_dm_web.py` with audio playback bar. Audio generates
   in background thread; browser polls for status and shows player when ready.
   Autoplay toggle, dice roller, suggestion buttons, live state sidebar.

### How to run

```bash
cd glm-work
source .venv/bin/activate

# With audio (default — loads Qwen3 model on first turn):
python -m narrator_v0.app --model gemini-3.5-flash-lite
python -m narrator_v0.app --model openai/gpt-oss-120b --provider groq

# Text-only mode (for quick testing without TTS):
python -m narrator_v0.app --no-audio

# Run trickster adversarial test:
python -m narrator_v0.run_trickster --model gemini-3.5-flash-lite --save
```

Then open `http://localhost:5000` (or whichever port you set).

**Note:** Port 5000 conflicts with macOS AirPlay Receiver. Use `--port 5102`
or similar.

### Test results (2026-08-19)

- **Text-only mode**: DM brain + rules lawyer + web GUI all working. Gemini 3.5
  Flash-Lite generates all 5 sections including [AUDIO].
- **Full audio mode**: End-to-end pipeline tested. A combat turn produced 208s
  of narration (10MB WAV) with Qwen3 TTS + SFX + music. Generation took ~70s
  (~3x real-time factor, matching Qwen3's expected performance).
- **Mock audio test**: A short 4-segment [AUDIO] section produced 16.4s of audio
  in 14.9s (0.9x RTF). SFX placed in gaps, no voice overlap. Music ducking
  working with narrator vs character volume difference.
- **Trickster test**: `run_trickster.py` imports the proven 10-scenario suite
  from `test_trickster.py` and runs it against the v0 system prompt. Ready to
  run before a real play session.

### Decisions made (per Arie's input)

- **SFX**: Cached ElevenLabs + new API calls + free library support (Arie: "B + C")
- **TTS**: Qwen3 VoiceDesign for all voices (Arie: "C if possible for live
  generation, if it proves too slow or no fix for drifting voices, we can
  reassess later")
- **Audio generation**: Live per-turn (Arie: "live generation, if it proves too
  slow or breaks immersion, we'll reassess")
- **DM brain**: Gemini 3.5 Flash-Lite (Arie's default in serve_dm_web.py)
- **Port**: Avoid 5000 (macOS AirPlay conflict)

### Known limitations / next steps

1. **Audio generation time**: ~70s for a long turn (208s audio). This may break
   immersion for fast back-and-forth turns. Arie will assess during real play.
2. **Qwen3 voice drifting**: Arie flagged concern about voice drifting over
   time. Not yet addressed — needs research into reference audio / voice cloning
   with Qwen3.
3. **Music transitions within a turn**: Currently uses one track per turn based
   on [SCENE: mood]. Multi-track transitions within a turn (like
   `produce_demos_v2.py` does) not yet implemented for live play.
4. **Cast management**: New NPCs get a default voice based on gender detection.
   Arie can edit `cast.json` to add specific voices. No automatic LLM-based
   voice assignment yet.
5. **No campaign save/load**: State is in-memory only. A page refresh starts a
   new game. Adding save/load is a natural next step.
6. **Trickster test not yet run against v0 prompt**: The script is ready but
   hasn't been executed with the v0 system prompt (which adds [AUDIO]). Run it
   before a real play session.
