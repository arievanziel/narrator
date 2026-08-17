# Kokoro-82M — Phase 1 Test Notes

**Test date:** 2026-08-17
**Tester:** GLM-5.2 High (Devin Local)
**Hardware:** MacBook Pro M1 Max, 32 GB RAM, macOS 15.3.2
**Kokoro version:** 0.9.4
**torch version:** 2.13.0 (MPS available: True, but generation ran on CPU by default)

## Install steps that worked

```bash
# 1. uv + espeak-ng via Homebrew
brew install uv espeak-ng

# 2. Python 3.12 venv (kokoro 0.9.x requires >=3.10,<3.13; system Python 3.14 is too new)
cd glm-work
uv venv --python 3.12 .venv
source .venv/bin/activate

# 3. Kokoro + soundfile (pulls torch, transformers, misaki, spacy, etc.)
uv pip install "kokoro>=0.9.4" soundfile

# 4. spacy English model — NOT auto-installed by kokoro/misaki.
#    misaki/en.py calls spacy.cli.download("en_core_web_sm") on first G2P use,
#    which hit a 429 rate limit from spacy.io and called sys.exit(1).
#    Workaround: install the wheel directly from GitHub releases.
uv pip install "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"

# 5. Run
python run_kokoro.py
```

## Issues encountered + workarounds

1. **System Python 3.14 too new.** kokoro 0.9.x requires `>=3.10,<3.13`. Fixed by
   using `uv venv --python 3.12`.
2. **spacy model download 429.** `misaki/en.py` line 500-501 calls
   `spacy.cli.download("en_core_web_sm")` which fetches a compatibility table from
   spacy.io. Got rate-limited (429), and `spacy.cli.download` calls `sys.exit(1)` on
   failure — so the process died with no traceback. Fixed by installing the model
   wheel directly from the explosion/spacy-models GitHub releases.
3. **API change.** Older Kokoro docs/examples use `pipeline.generate(text, voice=...)`.
   In 0.9.4 the method is `generate_from_tokens(tokens=..., voice=...)` — you must
   call `pipeline.g2p(text)` first to get `(ps, tokens)`, then pass `tokens` to
   `generate_from_tokens`. See `run_kokoro.py` for the working pattern.
4. **`pipeline.voices` dict empty on inspection.** Voices are loaded lazily from the
   HF repo on first use; the dict reported 0 voices at inspection time but
   `af_heart` and `am_michael` both worked fine when passed by name to
   `generate_from_tokens`.

## Apple Silicon (MPS/CPU) behavior

- `torch.backends.mps.is_available()` returns `True`.
- Kokoro's `generate_from_tokens` ran on **CPU by default** — no explicit MPS
  placement in the kokoro library code. Generation was still fast (see below).
- Did not force MPS because Kokoro is so small (82M params) that CPU is already
  5-7x real-time; MPS overhead may not be worth it. Could be revisited if needed.

## Generation speed (wall-clock, CPU)

| Test | Voice(s) | Audio dur | Gen time | x real-time |
|---|---|---:|---:|---:|
| 1_single_speaker | af_heart | 30.75s | 5.28s | 5.8x |
| 2a_multi_speaker (tags stripped, 1 voice) | af_heart | 26.20s | 3.85s | 6.8x |
| 2b_multi_speaker (alternating 2 voices, stitched) | af_heart + am_michael | 35.45s | 8.16s | 4.3x |
| 3_long_form (~530 words) | af_heart | 154.82s | 22.71s | 6.8x |

**All tests beat real-time comfortably (4-7x).** For Arie's target of ~3 hours/day
of narration, this implies ~25-45 minutes of generation time per day — very workable
for a local personal tool.

The multi-voice test (2b) is slower per second of audio (4.3x vs 6.8x) because each
line is a separate `g2p` + `generate_from_tokens` call, so there's per-call overhead
and no batching across lines. A production version could batch or pipeline this.

## Output files

All in `glm-work/outputs/kokoro/`:
- `smoke_test.wav` — 4.6s, the initial hello-world test
- `test1_single_speaker.wav` — 30.75s
- `test2a_multi_speaker_single_voice.wav` — 26.20s (tags stripped, one voice)
- `test2b_multi_speaker_two_voices.wav` — 35.45s (S1=af_heart, S2=am_michael, stitched)
- `test3_long_form.wav` — 154.82s (~2.5 min)

Total: ~12 MB. All 24kHz mono.

## Multi-voice capability (per docs/SPEC.md requirement)

**Kokoro supports multi-voice, but one voice per generation call.** It ships 54
preset voices across 8 languages (American/British English, Spanish, French, Hindi,
Italian, Portuguese, Mandarin). For multi-speaker dialogue:

- **Approach A (single voice, tags stripped):** run the whole passage through one
  voice. Simplest, but no speaker differentiation. This is the spec's accepted
  adaptation for single-speaker models.
- **Approach B (alternating voices, stitched):** split text by `[S1]`/`[S2]` tags,
  generate each line with a different preset voice, concatenate the audio. This is
  what `test2b` does. It works and gives clear speaker differentiation, but:
  - No cross-speaker prosody continuity (each line is independent).
  - Per-line call overhead (4.3x real-time vs 6.8x for single-voice).
  - Voice consistency is per-preset — you pick from the 54 built-in voices, you
    don't design custom voices (unlike Qwen3-TTS's natural-language voice design).

**For Arie's NPC-distinct-voices requirement:** Kokoro can do it via Approach B, but
you're limited to the 54 preset voices. If you need more than ~10-15 distinct
character voices that sound genuinely different, Kokoro's preset library may not be
enough. Qwen3-TTS (Priority 1, not yet tested) is the stronger candidate for this.

## What worked / what didn't

**Worked:**
- Install on Apple Silicon with Python 3.12 + uv (after the spacy workaround).
- All 3 test scripts generated audio successfully.
- 5-7x real-time on CPU — fast enough for daily use.
- Multi-voice via alternating presets + stitching.
- 24kHz output, reasonable audio quality (Arie to judge subjectively).

**Didn't work / friction:**
- System Python 3.14 incompatible (needs 3.10-3.12).
- spacy model auto-download hit 429 rate limit (manual wheel install needed).
- No built-in multi-speaker mode — must stitch per-line calls manually.
- No custom voice design — only the 54 presets.
- `pipeline.voices` dict appears empty until voices are lazily loaded.

## Subjective quality

**GLM is not the judge of audio quality — Arie is.** All 5 `.wav` files are in
`glm-work/outputs/kokoro/` for Arie to listen to and form his own opinion. Per spec,
this phase does NOT recommend a final model choice.
