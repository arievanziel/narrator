# Task B redirect — handoff note

**Written by:** Sonnet (Arie's auditor session), 2026-08-17 ~21:10
**For:** GLM and future auditors reviewing Task B status

## What happened to Task B

`PARALLEL-TASKS.md` originally defined Task B as "GUI design wireframes" with
output `glm-work/notes/gui_design.md`. Arie redirected it during this session.

Arie's verbatim guidance (from the session):
> the paste tag generate app is just for testing the models, i do not care about
> the gui AT ALL. I would like to test direct playback though, so not first
> generate > wait > listen, but direct playback from the model.
> The pasting of test text is not needed at all either, it can just read from
> pre-written test scripts.

So Task B's *deliverable* changed from a wireframe doc to a working direct-playback
CLI: **`glm-work/play_test.py`**.

## What `play_test.py` does

- Reads pre-written test scripts from `glm-work/test_scripts/` (no paste UI)
- Uses mlx-audio's `generate_audio(stream=True, play=True)` to play audio through
  Mac speakers AS it generates (via `sounddevice`), not generate-then-wait
- Works across Kokoro (MLX), Qwen3-TTS VoiceDesign, Dia, Higgs — all via mlx-audio
- Strips `[S1]`/`[S2]` tags so they aren't read aloud
- `--save` optionally writes the stream to `outputs/play_test/`

## Verified

Kokoro MLX direct playback ran end-to-end on `1_single_speaker.txt`:
- Load from cache: 1.3s
- First chunk: 8.88s warmup, then all subsequent chunks 0.13–0.48s each
  (10–20x faster than playback → continuous playback after warmup)
- Total: 49.5s wall clock for ~33s audio

## What this means for `gui_design.md`

`gui_design.md` was NOT created. The original Task B output file doesn't exist
and doesn't need to — the testing GUI was descoped per Arie.

**However:** Arie then asked to separately work on GUI for the *eventual* Narrator
app (the real product, post-Phase-1). That work is happening in this same session
*after* this note was written, and may produce design artifacts. If you see GUI
design files appearing in `glm-work/notes/` or elsewhere after this timestamp,
they're for the eventual product, not the Phase 1 testing scaffold.

## Qwen3 status (for Task D)

`play_test.py --model qwen3_vd` is wired correctly (uses local path, not HF repo
ID — avoids the re-download bug Sonnet flagged earlier). Download was ~79% complete
at time of writing (1.88 GB / 2.39 GB). It'll work once Task D's download finishes.
