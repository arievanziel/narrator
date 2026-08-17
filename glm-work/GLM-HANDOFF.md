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
- [x] All 3 Phase 1 test scripts run through Kokoro (5-7x real-time on CPU).
- [x] 5 output `.wav` files saved to `glm-work/outputs/kokoro/` (~12 MB total).
- [x] Kokoro notes written up at `glm-work/notes/kokoro_notes.md`.
- [ ] Arie listens to Kokoro outputs and gives subjective quality feedback.
- [ ] Qwen3-TTS download sizes researched and presented to Arie.
- [ ] Qwen3-TTS installed + 3 test scripts run + outputs saved.
- [ ] `RESULTS.md` writeup (per spec: comparison table, do NOT recommend a final model).

## Test scripts

Located at `glm-work/test_scripts/`. The first two are Arie's exact text from
`docs/PHASE_1_TESTING.md` (copied verbatim — I do not modify human input). The third
(`3_long_form.txt`) I generated per the spec's instruction to Devin to write a ~500-600
word atmospheric fantasy passage in the same tone as the first two.

For single-speaker-only models (Kokoro, Qwen3-TTS base mode), the multi-speaker script's
`[S1]`/`[S2]` tags will be stripped and run as one continuous passage, with a note in
`RESULTS.md` that this test was adapted — per spec.

## Where I need help from smarter models

*None yet.* I'll add explicit sections here when I hit a wall.

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
