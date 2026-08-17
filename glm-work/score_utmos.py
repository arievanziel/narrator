"""Score all Kokoro test outputs with UTMOSv2 (MOS prediction 1-5).

UTMOSv2 predicts a Mean Opinion Score (naturalness) from 1.0 to 5.0 for
synthetic speech. This gives us an objective quality metric to complement
Arie's subjective listening tests.

Higher = better. multivoice project uses 3.5 as the "acceptable" threshold.
"""
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KOKORO_DIR = ROOT / "outputs" / "kokoro"
LOG = ROOT / "logs" / "utmos_scores.log"

def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")

def main():
    log("=" * 70)
    log(f"UTMOSv2 scoring — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    log("[setup] loading UTMOSv2 model...")
    t0 = time.time()
    import utmosv2
    model = utmosv2.create_model(pretrained=True)
    log(f"[setup] model loaded in {time.time()-t0:.1f}s")

    wav_files = sorted(KOKORO_DIR.glob("*.wav"))
    log(f"[setup] found {len(wav_files)} wav files in {KOKORO_DIR}")

    log("")
    log(f"{'file':<50} {'MOS':>6}")
    log("-" * 60)

    scores = {}
    for wav in wav_files:
        try:
            t0 = time.time()
            mos = model.predict(input_path=str(wav))
            dt = time.time() - t0
            mos_val = float(mos) if hasattr(mos, '__float__') else mos
            log(f"{wav.name:<50} {mos_val:>6.2f}  ({dt:.1f}s)")
            scores[wav.name] = mos_val
        except Exception as e:
            log(f"{wav.name:<50} ERROR: {e}")
            scores[wav.name] = None

    log("")
    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    valid_scores = [v for v in scores.values() if v is not None]
    if valid_scores:
        log(f"Average MOS: {sum(valid_scores)/len(valid_scores):.2f}")
        log(f"Min: {min(valid_scores):.2f}, Max: {max(valid_scores):.2f}")
        log(f"Files scoring >= 3.5 (acceptable): {sum(1 for v in valid_scores if v >= 3.5)}/{len(valid_scores)}")
    log("DONE")

if __name__ == "__main__":
    main()
