"""Run Kokoro via mlx-audio (MLX port) for comparison with the PyTorch version.

This tests whether the MLX port of Kokoro is faster than the PyTorch CPU version
we tested earlier. Same test scripts, same voices, different runtime.
"""
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = ROOT / "test_scripts"
OUT_DIR = ROOT / "outputs" / "kokoro_mlx"
LOG = ROOT / "logs" / "kokoro_mlx.log"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.parent.mkdir(parents=True, exist_ok=True)

# MLX Kokoro model
MODEL = "mlx-community/Kokoro-82M-bf16"
DEFAULT_VOICE = "af_heart"
VOICE_S1 = "af_heart"
VOICE_S2 = "am_michael"


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def strip_speaker_tags(text):
    return re.sub(r"\[S[12]\]\s*", "", text)


def split_by_speaker(text):
    out = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[S([12])\]\s*(.*)", line)
        if m:
            out.append((f"S{m.group(1)}", m.group(2)))
        else:
            out.append(("S1", line))
    return out


def main():
    log("=" * 70)
    log(f"Kokoro MLX test run — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)
    log(f"[setup] model: {MODEL}")
    log("[setup] This is the MLX port of Kokoro for comparison with PyTorch version.")

    t0 = time.time()
    from mlx_audio.tts import load_model
    from mlx_audio.tts.generate import generate_audio
    log(f"[setup] imports done in {time.time()-t0:.1f}s")

    log("[setup] loading model...")
    t0 = time.time()
    model = load_model(MODEL)
    log(f"[setup] model loaded in {time.time()-t0:.1f}s")

    results = []

    # Test 1: single speaker
    log("")
    log("--- Test 1: 1_single_speaker.txt ---")
    text1 = (SCRIPTS_DIR / "1_single_speaker.txt").read_text().strip()
    log(f"[t1] text length: {len(text1)} chars")
    t0 = time.time()
    generate_audio(
        text=text1,
        model=model,
        voice=DEFAULT_VOICE,
        lang_code="en",
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
        log(f"[t1] {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time")
        results.append(("1_single_speaker", "af_heart", dur, dt, dur/dt if dt > 0 else 0))

    # Test 2a: single-speaker adaptation
    log("")
    log("--- Test 2a: multi-speaker single voice ---")
    text2_raw = (SCRIPTS_DIR / "2_multi_speaker.txt").read_text().strip()
    text2a = strip_speaker_tags(text2_raw)
    t0 = time.time()
    generate_audio(
        text=text2a,
        model=model,
        voice=DEFAULT_VOICE,
        lang_code="en",
        output_path=str(OUT_DIR),
        file_prefix="test2a_multi_speaker_single_voice",
        audio_format="wav",
        verbose=True,
    )
    dt = time.time() - t0
    out_file = OUT_DIR / "test2a_multi_speaker_single_voice.wav"
    if out_file.exists():
        import soundfile as sf
        audio, sr = sf.read(str(out_file))
        dur = len(audio) / sr
        log(f"[t2a] {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time")
        results.append(("2a_multi_speaker_single_voice", "af_heart", dur, dt, dur/dt if dt > 0 else 0))

    # Test 2b: multi-voice stitched
    log("")
    log("--- Test 2b: multi-voice stitched ---")
    lines = split_by_speaker(text2_raw)
    import numpy as np
    all_chunks = []
    t_total = 0.0
    for speaker, line_text in lines:
        voice = VOICE_S1 if speaker == "S1" else VOICE_S2
        t0 = time.time()
        temp_prefix = f"temp_{speaker}_{int(time.time()*1000)}"
        generate_audio(
            text=line_text,
            model=model,
            voice=voice,
            lang_code="en",
            output_path=str(OUT_DIR),
            file_prefix=temp_prefix,
            audio_format="wav",
            verbose=False,
        )
        dt = time.time() - t0
        t_total += dt
        temp_file = OUT_DIR / f"{temp_prefix}.wav"
        if temp_file.exists():
            audio, sr = sf.read(str(temp_file))
            all_chunks.append(audio)
            temp_file.unlink()

    if all_chunks:
        audio_full = np.concatenate(all_chunks)
        out_file = OUT_DIR / "test2b_multi_speaker_two_voices.wav"
        sf.write(str(out_file), audio_full, sr)
        dur = len(audio_full) / sr
        log(f"[t2b] {dur:.2f}s audio in {t_total:.2f}s -> {dur/t_total:.1f}x real-time")
        results.append(("2b_multi_speaker_two_voices", "af_heart+am_michael", dur, t_total, dur/t_total if t_total > 0 else 0))

    # Test 3: long form
    log("")
    log("--- Test 3: 3_long_form.txt ---")
    text3 = (SCRIPTS_DIR / "3_long_form.txt").read_text().strip()
    t0 = time.time()
    generate_audio(
        text=text3,
        model=model,
        voice=DEFAULT_VOICE,
        lang_code="en",
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
        log(f"[t3] {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time")
        results.append(("3_long_form", "af_heart", dur, dt, dur/dt if dt > 0 else 0))

    # Summary
    log("")
    log("=" * 70)
    log("SUMMARY — Kokoro MLX")
    log("=" * 70)
    log(f"{'test':<40} {'voice':<25} {'audio_s':>8} {'gen_s':>8} {'x_rt':>6}")
    for name, voice, dur, dt, xrt in results:
        log(f"{name:<40} {voice:<25} {dur:>8.2f} {dt:>8.2f} {xrt:>6.1f}")
    log("DONE")


if __name__ == "__main__":
    main()
