# Phase 1 TTS Model Comparison Results

**Generated:** 2026-08-17 (in progress)
**Hardware:** Apple M1 Max, 32 GB unified memory, macOS 15.3.2
**Branch:** `glm-phase1`
**Test scripts:** `glm-work/test_scripts/` (1_single_speaker, 2_multi_speaker, 3_long_form)

> **NOTE:** No final model recommendation is being made. Arie will review the audio
> outputs and subjective notes, then choose a direction. This document presents
> objective measurements (timing, real-time factor, MOS scores) and subjective
> observations only.

---

## Models tested

| Model | Size | Runtime | Voice method | Multi-voice |
|-------|------|---------|-------------|-------------|
| Kokoro-82M (PyTorch) | ~312 MB | CPU (MPS available but Kokoro uses CPU) | 54 preset voices | Per-line stitching |
| Kokoro-82M (MLX) | ~327 MB | MLX/Metal GPU | 54 preset voices | Per-line stitching |
| Qwen3-TTS VoiceDesign 1.7B (8-bit MLX) | ~3.08 GB | MLX/Metal GPU | Natural-language voice description | Per-line stitching with different descriptions |
| Dia-1.6B (MLX fp16) | ~3.22 GB | MLX/Metal GPU | Native [S1]/[S2] tags | Native multi-speaker |
| Higgs Audio V2 (q6 MLX) | ~4.75 GB | MLX/Metal GPU | Voice cloning (ref audio) | Per-line stitching |

**Note on Dia2:** Dia2 is NOT tested. mlx-audio does not support Dia2, and no MLX
port exists. The original Dia-1.6B is tested instead. Dia2 is CUDA-first with no
MPS path. See `glm-work/GLM-HANDOFF.md` for details.

**Note on Chatterbox:** Not tested in this round — lowest priority per Sonnet's
research, and the full repository is ~13.9 GB. Can be added later if needed.

---

## Comparison table

### Test 1: Single speaker (`1_single_speaker.txt`)

| Model | Voice | Audio (s) | Gen time (s) | Real-time factor | UTMOSv2 MOS |
|-------|-------|-----------|-------------|-----------------|-------------|
| Kokoro (PyTorch) | af_heart | 30.75 | 5.28 | 5.8x | _pending_ |
| Kokoro (MLX) | af_heart | _pending_ | _pending_ | _pending_ | _pending_ |
| Qwen3-TTS VoiceDesign | narrator desc | 44.80 | 18.55 | 2.4x | _pending_ |
| Dia-1.6B | [S1] | _pending_ | _pending_ | _pending_ | _pending_ |
| Higgs Audio V2 | smart voice | _pending_ | _pending_ | _pending_ | _pending_ |

### Test 2a: Multi-speaker, single voice (`2_multi_speaker.txt`, tags stripped)

| Model | Voice | Audio (s) | Gen time (s) | Real-time factor | UTMOSv2 MOS |
|-------|-------|-----------|-------------|-----------------|-------------|
| Kokoro (PyTorch) | af_heart | 26.20 | 3.85 | 6.8x | _pending_ |
| Kokoro (MLX) | af_heart | _pending_ | _pending_ | _pending_ | _pending_ |
| Qwen3-TTS VoiceDesign | narrator desc | 46.32 | 20.03 | 2.3x | _pending_ |
| Dia-1.6B | [S1] (native tags) | _pending_ | _pending_ | _pending_ | _pending_ |
| Higgs Audio V2 | smart voice | _pending_ | _pending_ | _pending_ | _pending_ |

### Test 2b: Multi-speaker, two voices (`2_multi_speaker.txt`, [S1]/[S2] alternating)

| Model | Voices | Audio (s) | Gen time (s) | Real-time factor | UTMOSv2 MOS |
|-------|--------|-----------|-------------|-----------------|-------------|
| Kokoro (PyTorch) | af_heart + am_michael | 35.45 | 8.16 | 4.3x | _pending_ |
| Kokoro (MLX) | af_heart + am_michael | _pending_ | _pending_ | _pending_ | _pending_ |
| Qwen3-TTS VoiceDesign | S1 desc + S2 desc | 46.64 | 19.53 | 2.4x | _pending_ |
| Dia-1.6B | [S1]+[S2] native | _pending_ | _pending_ | _pending_ | _pending_ |
| Higgs Audio V2 | smart voice (no cloning) | _pending_ | _pending_ | _pending_ | _pending_ |

### Test 3: Long form (`3_long_form.txt`, ~530 words)

| Model | Voice | Audio (s) | Gen time (s) | Real-time factor | UTMOSv2 MOS |
|-------|-------|-----------|-------------|-----------------|-------------|
| Kokoro (PyTorch) | af_heart | 154.82 | 22.71 | 6.8x | _pending_ |
| Kokoro (MLX) | af_heart | _pending_ | _pending_ | _pending_ | _pending_ |
| Qwen3-TTS VoiceDesign | narrator desc | 192.00 | 77.50 | 2.5x | _pending_ |
| Dia-1.6B | [S1] | _pending_ | _pending_ | _pending_ | _pending_ |
| Higgs Audio V2 | smart voice | _pending_ | _pending_ | _pending_ | _pending_ |

---

## Subjective notes

### Kokoro-82M (PyTorch, CPU)

**What worked:**
- Fast generation (5-7x real-time on CPU, no GPU needed)
- Small model (~312 MB), easy to install
- 54 preset voices available
- Acceptable base quality for a first version

**What didn't work:**
- Pauses between sentences/paragraphs are weak and uniform
- Narrator-to-character voice transitions sound abrupt (hard stitching, no crossfade)
- Multi-speaker parsing split some lines unexpectedly (known limitation)
- No natural-language voice control — must pick from presets

**Arie's feedback (verbatim, from `glm-work/notes/kokoro_notes.md`):**
> Kokoro sounds ok, but not good enough, especially the pauses and narrator voice vs character voices changes.
> I think this is an input engineering + post-processing problem, not a model quality problem.
> Fixed voices are acceptable for a first version, and 54 voices is sufficient.

**Potential improvements (from `pipeline_design_reference.md`):**
- Insert real silence between chunks (multivoice uses 0.3s sentence pauses, 0.7s [beat], 1.5s [long beat])
- RMS loudness normalization and direction-aware volume scaling
- High-pass filtering for whisper directions
- UTMOSv2 quality scoring with automatic regeneration of low-MOS takes

### Qwen3-TTS VoiceDesign (MLX, 8-bit)

**What worked:**
- Natural-language voice descriptions produce distinct, controllable voices
- S1 (young woman) and S2 (older man) descriptions produced clearly different voices
- Long-form generation works (192s / 3.2 min of audio in one call with max_tokens=2400)
- MLX/Metal GPU acceleration — 2.3-2.5x real-time on M1 Max
- No stitching needed for single-speaker long-form (unlike Kokoro)

**What didn't work / concerns:**
- Slower than Kokoro (2.4x vs 5.8x real-time) — ~2.5x slower generation
- Peak memory 20.89 GB for long-form (vs Kokoro's <1 GB) — significant but within 32 GB
- Multi-voice requires per-line generation + stitching (no native multi-speaker like Dia)
- Voice consistency across separate calls needs Arie's listening verification
- 8-bit quantization quality impact needs listening evaluation
- The transformers warning ("using qwen3_tts to instantiate a model of type ''") is cosmetic — generation works fine

### Dia-1.6B (MLX)

_pending_ — not yet tested

**Expected strengths:**
- Native [S1]/[S2] speaker tag support (no stitching needed)
- Designed for dialogue/conversational TTS

**Expected concerns:**
- ~2 minute generation cap (long-form test may need chunking)
- Original Dia, not Dia2 (Dia2 has streaming but no MLX port)
- May not handle narration as well as dialogue

### Higgs Audio V2 (MLX, q6)

_pending_ — not yet tested

**Expected strengths:**
- Voice cloning from reference audio (best for consistent character voices)
- Llama-3.2-3B backbone (strong language model)
- RAS (repetition-avoidance sampling) for long-form stability

**Expected concerns:**
- Requires reference audio for best results (we're testing "smart voice" mode)
- Largest model (~4.75 GB q6)
- Without ref_audio, voice is random per sample (not suitable for production)

---

## Output files

All WAV outputs are in `glm-work/outputs/`:

- `kokoro/` — Kokoro PyTorch outputs (5 files, ~12 MB)
  - `smoke_test.wav`
  - `test1_single_speaker.wav`
  - `test2a_multi_speaker_single_voice.wav`
  - `test2b_multi_speaker_two_voices.wav`
  - `test3_long_form.wav`
- `qwen3_voicedesign/` — 5 files, ~15 MB
  - `smoke_test_000.wav`
  - `test1_single_speaker_000.wav`
  - `test2a_multi_speaker_single_voice_000.wav`
  - `test2b_multi_speaker_two_voices.wav`
  - `test3_long_form_000.wav`
- `dia_1_6b/` — _pending_
- `higgs_audio_v2/` — _pending_
- `kokoro_mlx/` — _pending_

---

## UTMOSv2 quality scores

UTMOSv2 predicts a Mean Opinion Score (MOS) from 1.0 to 5.0 for synthetic speech
naturalness. The multivoice project uses 3.5 as the "acceptable" threshold.

_pending_ — UTMOSv2 model downloading, will score all outputs once ready.

---

## Installation and runtime issues

### Kokoro (PyTorch)
- Python 3.14 too new — needed Python 3.12 via uv
- spaCy model download hit HTTP 429 rate limit — installed manually from GitHub release wheel
- Kokoro 0.9.4 API mismatch — no `generate()` method, used `g2p()` + `generate_from_tokens()` instead
- MPS available but Kokoro runs on CPU effectively

### mlx-audio
- Installed cleanly via `uv pip install mlx-audio`
- No `generate_speech` export (Sonnet's instruction referenced this) — actual API is `load_model()` + `generate_audio()`
- Supports Qwen3-TTS VoiceDesign, original Dia-1.6B, Higgs Audio V2, Kokoro, and many others

### Dia2
- NOT supported by mlx-audio (only original Dia-1.6B)
- No MLX port exists as of 2026-08-17
- Would require real porting work for Apple Silicon — escalated in handoff doc

### UTMOSv2
- Required `wget` (not installed by default on macOS) — installed via Homebrew
- Downloads ~800 MB of pretrained weights on first run

---

## What's next

1. Complete Qwen3-TTS VoiceDesign download and run all 3 test scripts
2. Score all outputs (including Kokoro) with UTMOSv2
3. Test Dia-1.6B via mlx-audio
4. Test Higgs Audio V2 via mlx-audio (q6)
5. Test Kokoro MLX for speed comparison
6. Fill in this RESULTS.md with all measurements
7. Arie reviews audio and chooses a direction
8. NO final model recommendation will be made in this document
