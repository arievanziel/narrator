# Sonnet 5 Medium — Devin Local Usage/Quota Log

**Purpose:** track my own Devin CLI quota/credit consumption on this project, per Arie's
instruction. This file is mine only — I do not edit `glm-work/` or any other LLM's files.

## How to read real numbers (I cannot self-report exact ACU/token counts)

I don't have programmatic access to the CLI's own billing counters — those are only
exposed via interactive slash commands that Arie has to run himself:

- `/usage` — thin credit/ACU summary for the session (includes prior resumes)
- `/session-stats` (alias `/stats`) — full breakdown: credits, ACUs, agent messages,
  turn continuations, token usage, and which model actually served each turn
- `/context` — current context window usage

**Ask:** if you want a running log of real numbers, run `/session-stats` at the end of a
session and paste the output here (or tell me the numbers) and I'll append them below.
I'll note qualitatively what each session did in the meantime.

## Session log

| Date | Model | What I did | Notes |
|---|---|---|---|
| 2026-08-17 | Sonnet 5 Medium | Audited GLM's Phase 1 progress (read-only: git log, filesystem, notes, spec docs). No code/files changed except my own `sonnet-work/` docs. Produced `ANALYSIS.md` with current status + model-routing recommendations for remaining tasks. | No `/session-stats` numbers captured yet — ask Arie to run `/usage` or `/session-stats` and paste here if you want it tracked |
| 2026-08-17 (cont.) | Sonnet 5 Medium | Verified MacBook hardware directly (sysctl/system_profiler). Web research: 2026 TTS landscape, `mlx-audio` Apple-Silicon runtime (major finding — supports Qwen3-TTS/Dia/Higgs Audio via MLX instead of CPU-fallback PyTorch), Task 0 market research (open-source: TTS-Story, multivoice, VibeVoice fork, RPAudiobook; commercial: Familiar, TableForge, Eternal DM, Scrollbook, Visionarium — all AI-DM products with cloud TTS, none fit Arie's constraints). Wrote `TTS-LANDSCAPE-RESEARCH-2026.md` and `INSTRUCTIONS-FOR-GLM.md`. No downloads or installs performed — analysis/research only, ~6-8 web searches + 1 page fetch. | Still no exact ACU numbers — same `/usage` limitation as before |
| 2026-08-17 (cont. 2) | Sonnet 5 Medium | Re-audited GLM's progress after it followed the mlx-audio instructions (Task 0 done, pipeline reference notes, test runners, prototype app). Verified download progress live (2 snapshots, confirmed genuinely progressing, ~300-400KB/s on the 5G connection). Traced `mlx_audio.utils.get_model_path()` source in GLM's venv to confirm a real bug: `run_qwen3_voicedesign.py`'s `MODEL` string won't resolve to GLM's manually-curled local files, would trigger a wasted re-download. Wrote `STATUS-UPDATE-2.md`, updated `INSTRUCTIONS-FOR-GLM.md` with the fix at top priority. No files in `glm-work/` touched, no downloads/installs run by me. | Still no exact ACU numbers |
