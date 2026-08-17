"""Run all 3 Phase 1 test scripts through Qwen3-TTS VoiceDesign via mlx-audio.

Qwen3-TTS VoiceDesign API (mlx-audio):
  model = load_model("mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit")
  generate_audio(text=..., model=model, instruct=voice_description, lang_code="en", ...)

VoiceDesign: the `instruct` parameter is a natural-language description of the voice.
This is the key feature for Arie's NPC-voice requirement — describe a voice in words,
get that voice.

For multi-speaker test (2_multi_speaker.txt), we use two different voice descriptions
for S1 and S2, generating each line separately and stitching.
"""
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # glm-work/
SCRIPTS_DIR = ROOT / "test_scripts"
OUT_DIR = ROOT / "outputs" / "qwen3_voicedesign"
LOG = ROOT / "logs" / "qwen3_voicedesign.log"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.parent.mkdir(parents=True, exist_ok=True)

MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"

# Voice descriptions for VoiceDesign
# These are natural-language descriptions that Qwen3-TTS uses to synthesize the voice
NARRATOR_VOICE = (
    "A calm, warm female narrator with a measured pace, suitable for reading "
    "fantasy fiction. The voice should have a storyteller quality — clear, "
    "expressive, with subtle emotional undertones."
)
S1_VOICE = (
    "A young woman with a calm, observant voice. She speaks with quiet "
    "confidence and careful word choice, as someone who has seen danger "
    "before. Slightly breathy, intimate quality."
)
S2_VOICE = (
    "An older man with a weathered, gravelly voice. He sounds tired and "
    "wounded, speaking with effort. Rough edges, low pitch."
)


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


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
            out.append(("S1", line))
    return out


def main():
    log("=" * 70)
    log(f"Qwen3-TTS VoiceDesign test run — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    log(f"[setup] model: {MODEL}")
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
    log("")
    log("--- Test 1: 1_single_speaker.txt ---")
    text1 = (SCRIPTS_DIR / "1_single_speaker.txt").read_text().strip()
    log(f"[t1] text length: {len(text1)} chars")
    log(f"[t1] voice: {NARRATOR_VOICE[:80]}...")
    t0 = time.time()
    generate_audio(
        text=text1,
        model=model,
        instruct=NARRATOR_VOICE,
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
        sz = out_file.stat().st_size
        log(f"[t1] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
        results.append(("1_single_speaker", "narrator_voicedesign", dur, dt, dur/dt if dt > 0 else 0))
    else:
        log(f"[t1] ERROR: output file not found at {out_file}")

    # --- Test 2: multi-speaker ---
    log("")
    log("--- Test 2: 2_multi_speaker.txt ---")
    text2_raw = (SCRIPTS_DIR / "2_multi_speaker.txt").read_text().strip()

    # 2a: single-speaker adaptation (strip tags, narrator voice)
    log("[t2a] single-speaker adaptation (tags stripped, narrator voice)")
    text2a = strip_speaker_tags(text2_raw)
    t0 = time.time()
    generate_audio(
        text=text2a,
        model=model,
        instruct=NARRATOR_VOICE,
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
        sz = out_file.stat().st_size
        log(f"[t2a] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
        results.append(("2a_multi_speaker_single_voice", "narrator_voicedesign", dur, dt, dur/dt if dt > 0 else 0))
    else:
        log(f"[t2a] ERROR: output file not found")

    # 2b: multi-voice (alternate voices per [S1]/[S2] line, stitch together)
    log("[t2b] multi-voice (S1=young woman, S2=older man, stitched)")
    lines = split_by_speaker(text2_raw)
    import numpy as np
    import soundfile as sf
    all_chunks = []
    t_total = 0.0
    for speaker, line_text in lines:
        voice_desc = S1_VOICE if speaker == "S1" else S2_VOICE
        log(f"[t2b]   {speaker}: '{line_text[:50]}...'")
        t0 = time.time()
        # Generate to temp file, then load
        temp_prefix = f"temp_{speaker}_{int(time.time()*1000)}"
        generate_audio(
            text=line_text,
            model=model,
            instruct=voice_desc,
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
            log(f"[t2b]     -> {len(audio)/sr:.2f}s in {dt:.2f}s")
            temp_file.unlink()  # clean up temp
        else:
            log(f"[t2b]     ERROR: temp file not found")

    if all_chunks:
        audio_full = np.concatenate(all_chunks)
        out_file = OUT_DIR / "test2b_multi_speaker_two_voices.wav"
        sf.write(str(out_file), audio_full, sr)
        dur = len(audio_full) / sr
        sz = out_file.stat().st_size
        log(f"[t2b] total: {dur:.2f}s audio in {t_total:.2f}s -> {dur/t_total:.1f}x real-time, {sz} bytes")
        results.append(("2b_multi_speaker_two_voices", "S1+S2 voicedesign", dur, t_total, dur/t_total if t_total > 0 else 0))

    # --- Test 3: long form ---
    log("")
    log("--- Test 3: 3_long_form.txt ---")
    text3 = (SCRIPTS_DIR / "3_long_form.txt").read_text().strip()
    log(f"[t3] text length: {len(text3)} chars")
    t0 = time.time()
    generate_audio(
        text=text3,
        model=model,
        instruct=NARRATOR_VOICE,
        lang_code="en",
        output_path=str(OUT_DIR),
        file_prefix="test3_long_form",
        audio_format="wav",
        verbose=True,
    )
    dt = time.time() - t0
    out_file = OUT_DIR / "test3_long_form.wav"
    if out_file.exists():
        audio, sr = sf.read(str(out_file))
        dur = len(audio) / sr
        sz = out_file.stat().st_size
        log(f"[t3] generated {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x real-time, {sz} bytes")
        results.append(("3_long_form", "narrator_voicedesign", dur, dt, dur/dt if dt > 0 else 0))
    else:
        log(f"[t3] ERROR: output file not found")

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
