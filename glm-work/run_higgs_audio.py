"""Run all 3 Phase 1 test scripts through Higgs Audio V2 via mlx-audio.

Note: Higgs Audio V2 is a voice-cloning model — it requires reference audio
for best results. Without ref_audio, it runs in "smart voice" mode (random voice
per sample). For this test, we'll use "smart voice" mode since we don't have
reference audio clips prepared.

Higgs API (mlx-audio):
  model = load_model("mlx-community/higgs-audio-v2-3B-mlx-q6")
  generate_audio(text=..., model=model, ref_audio=..., ref_text=..., ...)

For a fair comparison, we test without ref_audio first (smart voice mode).
If Arie wants to test voice cloning, he can provide reference WAV clips later.
"""
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT / "test_scripts"
OUT_DIR = ROOT / "outputs" / "higgs_audio_v2"
LOG = ROOT / "logs" / "higgs_audio_v2.log"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.parent.mkdir(parents=True, exist_ok=True)

# Using q6 (4.75GB) for smaller download — q8 (6.18GB) is also available
MODEL = "mlx-community/higgs-audio-v2-3B-mlx-q6"


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def main():
    log("=" * 70)
    log(f"Higgs Audio V2 test run — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)
    log(f"[setup] model: {MODEL}")
    log("[setup] NOTE: Using 'smart voice' mode (no ref_audio).")
    log("[setup] For voice cloning, ref_audio + ref_text would be needed.")
    log("[setup] Higgs does NOT support VoiceDesign or preset voices — only cloning.")

    t0 = time.time()
    from mlx_audio.tts import load_model
    from mlx_audio.tts.generate import generate_audio
    log(f"[setup] imports done in {time.time()-t0:.1f}s")

    log("[setup] loading model...")
    t0 = time.time()
    model = load_model(MODEL)
    log(f"[setup] model loaded in {time.time()-t0:.1f}s")

    results = []

    tests = [
        ("1_single_speaker", "1_single_speaker.txt"),
        ("2_multi_speaker", "2_multi_speaker.txt"),
        ("3_long_form", "3_long_form.txt"),
    ]

    for test_name, filename in tests:
        log("")
        log(f"--- Test: {filename} ---")
        text = (SCRIPTS_DIR / filename).read_text().strip()
        log(f"[{test_name}] text length: {len(text)} chars")

        t0 = time.time()
        try:
            generate_audio(
                text=text,
                model=model,
                output_path=str(OUT_DIR),
                file_prefix=test_name,
                audio_format="wav",
                verbose=True,
            )
            dt = time.time() - t0
            out_file = OUT_DIR / f"{test_name}.wav"
            if out_file.exists():
                import soundfile as sf
                audio, sr = sf.read(str(out_file))
                dur = len(audio) / sr
                sz = out_file.stat().st_size
                log(f"[{test_name}] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
                results.append((test_name, "smart_voice", dur, dt, dur/dt if dt > 0 else 0))
            else:
                log(f"[{test_name}] ERROR: output file not found")
                results.append((test_name, "smart_voice", 0, dt, 0))
        except Exception as e:
            dt = time.time() - t0
            log(f"[{test_name}] FAILED after {dt:.1f}s: {e}")
            results.append((test_name, "smart_voice (FAILED)", 0, dt, 0))

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
