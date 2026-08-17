"""Run all 3 Phase 1 test scripts through Dia-1.6B via mlx-audio.

Note: This is the ORIGINAL Dia-1.6B (not Dia2). mlx-audio does not support Dia2.
Dia-1.6B supports native [S1]/[S2] speaker tags — this is its key strength.

Dia API (mlx-audio):
  model = load_model("mlx-community/Dia-1.6B-fp16")
  generate_audio(text=..., model=model, ...)

For single-speaker tests, we use [S1] tags throughout.
For multi-speaker, we use the native [S1]/[S2] tags as-is.
"""
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT / "test_scripts"
OUT_DIR = ROOT / "outputs" / "dia_1_6b"
LOG = ROOT / "logs" / "dia_1_6b.log"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.parent.mkdir(parents=True, exist_ok=True)

MODEL = "mlx-community/Dia-1.6B-fp16"


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def main():
    log("=" * 70)
    log(f"Dia-1.6B test run — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)
    log(f"[setup] model: {MODEL}")
    log("[setup] NOTE: This is original Dia-1.6B, NOT Dia2. mlx-audio does not support Dia2.")
    log("[setup] Dia-1.6B supports native [S1]/[S2] speaker tags.")

    t0 = time.time()
    from mlx_audio.tts import load_model
    from mlx_audio.tts.generate import generate_audio
    log(f"[setup] imports done in {time.time()-t0:.1f}s")

    log("[setup] loading model...")
    t0 = time.time()
    model = load_model(MODEL)
    log(f"[setup] model loaded in {time.time()-t0:.1f}s")

    results = []

    # --- Test 1: single speaker ---
    # Dia requires [S1] tags, so we prepend them
    log("")
    log("--- Test 1: 1_single_speaker.txt ---")
    text1 = (SCRIPTS_DIR / "1_single_speaker.txt").read_text().strip()
    # Wrap in [S1] tag for Dia
    text1_dia = f"[S1] {text1}"
    log(f"[t1] text length: {len(text1)} chars (with [S1] tag: {len(text1_dia)})")
    t0 = time.time()
    generate_audio(
        text=text1_dia,
        model=model,
        output_path=str(OUT_DIR),
        file_prefix="test1_single_speaker",
        audio_format="wav",
        verbose=True,
    )
    dt = time.time() - t0
    out_file = OUT_DIR / "test1_single_speaker.wav"
    if out_file.exists():
        import soundfile as sf
        audio, sr = sf.read(str(out_file))
        dur = len(audio) / sr
        sz = out_file.stat().st_size
        log(f"[t1] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
        results.append(("1_single_speaker", "S1 (single)", dur, dt, dur/dt if dt > 0 else 0))
    else:
        log(f"[t1] ERROR: output file not found")

    # --- Test 2: multi-speaker (native [S1]/[S2] tags) ---
    log("")
    log("--- Test 2: 2_multi_speaker.txt (native [S1]/[S2] tags) ---")
    text2 = (SCRIPTS_DIR / "2_multi_speaker.txt").read_text().strip()
    log(f"[t2] text length: {len(text2)} chars (uses native [S1]/[S2] tags)")
    t0 = time.time()
    generate_audio(
        text=text2,
        model=model,
        output_path=str(OUT_DIR),
        file_prefix="test2_multi_speaker",
        audio_format="wav",
        verbose=True,
    )
    dt = time.time() - t0
    out_file = OUT_DIR / "test2_multi_speaker.wav"
    if out_file.exists():
        import soundfile as sf
        audio, sr = sf.read(str(out_file))
        dur = len(audio) / sr
        sz = out_file.stat().st_size
        log(f"[t2] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
        results.append(("2_multi_speaker", "S1+S2 native", dur, dt, dur/dt if dt > 0 else 0))
    else:
        log(f"[t2] ERROR: output file not found")

    # --- Test 3: long form ---
    # Dia has a ~2 min generation cap. For long text, we may need to chunk.
    # First try the full text — if it fails, we'll chunk.
    log("")
    log("--- Test 3: 3_long_form.txt ---")
    text3 = (SCRIPTS_DIR / "3_long_form.txt").read_text().strip()
    text3_dia = f"[S1] {text3}"
    log(f"[t3] text length: {len(text3)} chars")
    log("[t3] NOTE: Dia has ~2min generation cap. If this fails, will chunk.")
    t0 = time.time()
    try:
        generate_audio(
            text=text3_dia,
            model=model,
            output_path=str(OUT_DIR),
            file_prefix="test3_long_form",
            audio_format="wav",
            verbose=True,
        )
        dt = time.time() - t0
        out_file = OUT_DIR / "test3_long_form.wav"
        if out_file.exists():
            import soundfile as sf
            audio, sr = sf.read(str(out_file))
            dur = len(audio) / sr
            sz = out_file.stat().st_size
            log(f"[t3] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
            results.append(("3_long_form", "S1 (single)", dur, dt, dur/dt if dt > 0 else 0))
        else:
            log(f"[t3] ERROR: output file not found")
    except Exception as e:
        dt = time.time() - t0
        log(f"[t3] FAILED after {dt:.1f}s: {e}")
        log("[t3] This may be the ~2min generation cap. Would need chunking.")
        results.append(("3_long_form", "S1 (FAILED)", 0, dt, 0))

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
