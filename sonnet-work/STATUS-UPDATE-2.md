# Status Update 2 — Sonnet audit, 2026-08-17 ~20:05

Read-only audit while GLM's downloads run. No `glm-work/` files touched.

## Downloads currently running (all on your 5G connection)

| Download | Target size | Current | Rate (measured) | ETA |
|---|---|---|---|---|
| Qwen3-TTS VoiceDesign 8bit — `model.safetensors` | ~2.05 GB | ~410 MB (~20%) | ~300-370 KB/s | **~75-90 min** |
| Qwen3-TTS VoiceDesign 8bit — `speech_tokenizer/model.safetensors` | ~549 MB | ~180 MB (~33%) | similar, shares bandwidth | ~20-25 min |
| UTMOSv2 `fold0_s42_best_model.pth` | unclear exact total (likely needs more than one fold file) | 390 MB and growing | faster, ~1+ MB/s | unclear, check again later |

All three are downloading concurrently and sharing your bandwidth, which is why each is
slower than it would be alone. Nothing is stalled — I verified with two snapshots 12s
apart and all three grew. This is genuinely just a slow-connection wait, not a bug.

**Practical suggestion:** if you want the Qwen3-TTS test to finish sooner, ask GLM to
pause the UTMOSv2 download (`kill` the wget, resume later with `-c`) until the Qwen3-TTS
files finish — UTMOSv2 is a nice-to-have (objective quality scoring) and not blocking any
Phase 1 deliverable, whereas Qwen3-TTS is the actual next model under test. Not urgent,
just an option if you're impatient.

## Bug found — will silently waste the Qwen3-TTS download if not fixed

GLM downloaded the Qwen3-TTS VoiceDesign model files manually via `curl` into
`glm-work/models/qwen3_voicedesign_8bit/` (because the normal `huggingface_hub` download
was stalling). Good workaround instinct — **but `run_qwen3_voicedesign.py` still has:**

```python
MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"
```

I traced through `mlx_audio`'s actual `get_model_path()` code (installed at
`glm-work/.venv/lib/python3.12/site-packages/mlx_audio/utils.py`): it only treats a string
as a local path if it starts with `.`, `/`, or `~`. A bare `"mlx-community/..."` string is
treated as a Hugging Face repo ID, which means **when GLM runs the test script, mlx-audio
will ignore the manually-downloaded files entirely and try to re-download the same ~2.6GB
from Hugging Face into the default HF cache** — on the same slow connection, doubling the
wait for nothing.

**Fix (trivial, GLM can do this in one line):** change `MODEL` in
`run_qwen3_voicedesign.py` (and anywhere else that references the same string) to a local
path, e.g.:
```python
MODEL = "models/qwen3_voicedesign_8bit"  # relative to glm-work/, or use an absolute path
```
Verify the directory structure matches what `mlx-audio` expects (config.json,
model.safetensors, speech_tokenizer/ subfolder — looks right from what's on disk already).

I've added this to `INSTRUCTIONS-FOR-GLM.md` as the top priority item — worth doing now,
before the download even finishes, so there's no wasted re-download once it's done.

## Everything else looks solid

- `MARKET_RESEARCH.md`, `notes/pipeline_design_reference.md`: well-sourced, correctly
  scoped, correctly deferred (not building a Kokoro pipeline fix yet, per my earlier
  instruction — good adherence).
- `prototype_app/app.py`: clean, minimal stdlib HTTP server, no framework dependency
  issues, handles all 3 model paths (Kokoro PyTorch, Kokoro MLX, Qwen3-TTS VoiceDesign)
  correctly as far as I can read statically. **One scope note, not a bug:** the spec
  (`docs/PHASE_1_TESTING.md`) says explicitly "no app gets built in Phase 1." GLM built a
  small prototype web app anyway. It's low-cost and genuinely useful for side-by-side
  listening, so I wouldn't tell GLM to delete it — but flagging it as a deliberate small
  scope deviation for you to bless or veto, since it's not what was originally asked.
- `run_dia_1_6b.py`, `run_higgs_audio.py`, `run_kokoro_mlx.py`: not yet exercised (waiting
  on downloads), written consistently with the pattern of the working Kokoro/smoke-test
  scripts. Nothing to flag until they actually run.
- Test correctly confirmed Dia2 has no MLX port (only original Dia-1.6B) — matches what I
  found in my own research, good independent convergence.

## No Opus/Fable escalation needed right now

Nothing here needs a smarter/costlier model. The `MODEL` path bug is a one-line fix GLM
can make itself once flagged (which I've done in the instructions doc). Keep GLM going.
