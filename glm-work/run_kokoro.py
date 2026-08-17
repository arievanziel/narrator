"""Run all 3 Phase 1 test scripts through Kokoro, save wavs + log timings.

kokoro 0.9.4 API:
  pipeline = KPipeline(lang_code='a')   # 'a' = American English
  ps, tokens = pipeline.g2p(text)
  for result in pipeline.generate_from_tokens(tokens=tokens, voice=VOICE):
      result.audio  # torch.FloatTensor

Multi-voice note (per docs/SPEC.md): Kokoro is single-speaker-per-call. For the
multi-speaker test script (2_multi_speaker.txt), we strip [S1]/[S2] tags and run
it as one continuous passage (spec says this is the accepted adaptation). We also
generate a second version alternating voices per [S1]/[S2] line to demonstrate
Kokoro's multi-voice capability (different preset voices per speaker).
"""
import re
import time
import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parent  # glm-work/
SCRIPTS_DIR = ROOT / "test_scripts"
OUT_DIR = ROOT / "outputs" / "kokoro"
LOG = ROOT / "logs" / "kokoro.log"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.parent.mkdir(parents=True, exist_ok=True)

SAMPLE_RATE = 24000
# Default narrator voice (American female, warm)
DEFAULT_VOICE = "af_heart"
# Voice for S1 (Mireth — female, calm)
VOICE_S1 = "af_heart"
# Voice for S2 (male, older/rougher)
VOICE_S2 = "am_michael"


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def gen(pipeline, text, voice, device=None):
    """g2p + generate_from_tokens, return (audio_np, wall_clock_seconds)."""
    t0 = time.time()
    ps, tokens = pipeline.g2p(text)
    chunks = []
    for result in pipeline.generate_from_tokens(tokens=tokens, voice=voice):
        chunks.append(result.audio)
    dt = time.time() - t0
    audio = torch.cat(chunks).cpu().numpy() if chunks else np.array([])
    return audio, dt


def save_wav(audio, path):
    sf.write(str(path), audio, SAMPLE_RATE)
    return path.stat().st_size


def strip_speaker_tags(text):
    """Remove [S1]/[S2] tags for single-speaker rendering."""
    return re.sub(r"\[S[12]\]\s*", "", text)


def split_by_speaker(text):
    """Return list of (speaker, line_text) from [S1]/[S2]-tagged text."""
    out = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[S([12])\]\s*(.*)", line)
        if m:
            out.append((f"S{m.group(1)}", m.group(2)))
        else:
            # untagged narration line — assign to S1 (narrator)
            out.append(("S1", line))
    return out


def main():
    log("=" * 70)
    log(f"Kokoro test run — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    log("[setup] importing kokoro + torch...")
    t0 = time.time()
    log(f"[setup] torch {torch.__version__}, MPS available: {torch.backends.mps.is_available()}")
    log("[setup] building KPipeline(lang_code='a')...")
    pipeline = KPipeline(lang_code="a")
    log(f"[setup] pipeline ready in {time.time()-t0:.1f}s")

    # List available voices
    voices = list(pipeline.voices.keys()) if hasattr(pipeline, 'voices') else []
    log(f"[setup] available voices: {len(voices)} total")
    if voices:
        log(f"[setup] sample voices: {voices[:10]}")
        # Confirm our chosen voices exist
        for v in [DEFAULT_VOICE, VOICE_S1, VOICE_S2]:
            if v in voices:
                log(f"[setup]   voice '{v}' available")
            else:
                log(f"[setup]   WARNING: voice '{v}' NOT found")

    results = []

    # --- Test 1: single speaker ---
    log("")
    log("--- Test 1: 1_single_speaker.txt ---")
    text1 = (SCRIPTS_DIR / "1_single_speaker.txt").read_text().strip()
    log(f"[t1] text length: {len(text1)} chars")
    audio, dt = gen(pipeline, text1, DEFAULT_VOICE)
    sz = save_wav(audio, OUT_DIR / "test1_single_speaker.wav")
    dur = len(audio) / SAMPLE_RATE
    log(f"[t1] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
    results.append(("1_single_speaker", "af_heart", dur, dt, dur/dt if dt > 0 else 0))

    # --- Test 2: multi-speaker ---
    log("")
    log("--- Test 2: 2_multi_speaker.txt ---")
    text2_raw = (SCRIPTS_DIR / "2_multi_speaker.txt").read_text().strip()

    # 2a: single-speaker adaptation (strip tags, one voice) — per spec
    log("[t2a] single-speaker adaptation (tags stripped, af_heart)")
    text2a = strip_speaker_tags(text2_raw)
    audio, dt = gen(pipeline, text2a, DEFAULT_VOICE)
    sz = save_wav(audio, OUT_DIR / "test2a_multi_speaker_single_voice.wav")
    dur = len(audio) / SAMPLE_RATE
    log(f"[t2a] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
    results.append(("2a_multi_speaker_single_voice", "af_heart", dur, dt, dur/dt if dt > 0 else 0))

    # 2b: multi-voice (alternate voices per [S1]/[S2] line, stitch together)
    log("[t2b] multi-voice (S1=af_heart, S2=am_michael, stitched)")
    lines = split_by_speaker(text2_raw)
    all_chunks = []
    t_total = 0.0
    for speaker, line_text in lines:
        voice = VOICE_S1 if speaker == "S1" else VOICE_S2
        audio, dt = gen(pipeline, line_text, voice)
        all_chunks.append(audio)
        t_total += dt
        log(f"[t2b]   {speaker} ({voice}): '{line_text[:50]}...' -> {len(audio)/SAMPLE_RATE:.2f}s in {dt:.2f}s")
    audio_full = np.concatenate(all_chunks) if all_chunks else np.array([])
    sz = save_wav(audio_full, OUT_DIR / "test2b_multi_speaker_two_voices.wav")
    dur = len(audio_full) / SAMPLE_RATE
    log(f"[t2b] total: {dur:.2f}s audio in {t_total:.2f}s -> {dur/t_total:.1f}x real-time, {sz} bytes")
    results.append(("2b_multi_speaker_two_voices", "af_heart+am_michael", dur, t_total, dur/t_total if t_total > 0 else 0))

    # --- Test 3: long form ---
    log("")
    log("--- Test 3: 3_long_form.txt ---")
    text3 = (SCRIPTS_DIR / "3_long_form.txt").read_text().strip()
    log(f"[t3] text length: {len(text3)} chars")
    audio, dt = gen(pipeline, text3, DEFAULT_VOICE)
    sz = save_wav(audio, OUT_DIR / "test3_long_form.wav")
    dur = len(audio) / SAMPLE_RATE
    log(f"[t3] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
    results.append(("3_long_form", "af_heart", dur, dt, dur/dt if dt > 0 else 0))

    # --- Summary ---
    log("")
    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    log(f"{'test':<40} {'voice':<25} {'audio_s':>8} {'gen_s':>8} {'x_rt':>6}")
    for name, voice, dur, dt, xrt in results:
        log(f"{name:<40} {voice:<25} {dur:>8.2f} {dt:>8.2f} {xrt:>6.1f}")
    log("")
    log(f"Output files in: {OUT_DIR}")
    log(f"Log file: {LOG}")
    log("DONE")


if __name__ == "__main__":
    main()
