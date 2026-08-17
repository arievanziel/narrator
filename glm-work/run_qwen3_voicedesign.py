"""Run all 3 Phase 1 test scripts through Qwen3-TTS VoiceDesign via mlx-audio.

Qwen3-TTS VoiceDesign API (mlx-audio):
  model = load_model("path/to/qwen3_voicedesign_8bit")
  generate_audio(text=..., model=model, instruct=voice_description, lang_code="en", ...)

VoiceDesign: the `instruct` parameter is a natural-language description of the voice.
This is the key feature for Arie's NPC-voice requirement — describe a voice in words,
get that voice.

For multi-speaker test (2_multi_speaker.txt), we use two different voice descriptions
for S1 and S2, generating each line separately and stitching.

NOTE: mlx-audio saves output files with a _000 suffix (e.g. test1_000.wav).
This script handles that suffix and also increases max_tokens for long-form text.
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

# Use local path (manually downloaded via curl) — NOT the HF repo ID.
# mlx_audio.utils.get_model_path() only treats strings starting with ".", "/", or "~"
# as local paths; a bare "mlx-community/..." would trigger a re-download. (Sonnet catch.)
MODEL = str(ROOT / "models" / "qwen3_voicedesign_8bit")

# Voice descriptions for VoiceDesign
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

# Qwen3-TTS has a default max_tokens of 1200 (~48s of audio).
# For long-form text, we need more. The model supports up to ~2400 tokens.
MAX_TOKENS_SHORT = 1200
MAX_TOKENS_LONG = 2400


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def find_output(output_dir, prefix):
    """Find output file with optional _000 suffix."""
    # Try exact name first
    exact = Path(output_dir) / f"{prefix}.wav"
    if exact.exists():
        return exact
    # Try with _000 suffix
    suffixed = Path(output_dir) / f"{prefix}_000.wav"
    if suffixed.exists():
        return suffixed
    # Try glob
    matches = list(Path(output_dir).glob(f"{prefix}*.wav"))
    if matches:
        return matches[0]
    return None


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


def generate_and_measure(text, model, voice_desc, prefix, max_tokens=MAX_TOKENS_SHORT):
    """Generate audio and return (duration, gen_time, rtf, output_file)."""
    from mlx_audio.tts.generate import generate_audio
    t0 = time.time()
    generate_audio(
        text=text,
        model=model,
        instruct=voice_desc,
        lang_code="en",
        max_tokens=max_tokens,
        output_path=str(OUT_DIR),
        file_prefix=prefix,
        audio_format="wav",
        verbose=True,
    )
    dt = time.time() - t0
    out_file = find_output(OUT_DIR, prefix)
    if out_file and out_file.exists():
        import soundfile as sf
        audio, sr = sf.read(str(out_file))
        dur = len(audio) / sr
        rtf = dur / dt if dt > 0 else 0
        return dur, dt, rtf, out_file
    return 0, dt, 0, None


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
    from mlx_audio.tts.generate import generate_audio
    log(f"[setup] model loaded in {time.time()-t0:.1f}s")

    results = []

    # --- Test 1: single speaker ---
    log("")
    log("--- Test 1: 1_single_speaker.txt ---")
    text1 = (SCRIPTS_DIR / "1_single_speaker.txt").read_text().strip()
    log(f"[t1] text length: {len(text1)} chars")
    log(f"[t1] voice: {NARRATOR_VOICE[:80]}...")
    dur, dt, rtf, out_file = generate_and_measure(text1, model, NARRATOR_VOICE, "test1_single_speaker")
    if out_file:
        sz = out_file.stat().st_size
        log(f"[t1] generated {dur:.2f}s audio in {dt:.2f}s -> {rtf:.1f}x real-time, {sz} bytes")
        results.append(("1_single_speaker", "narrator_voicedesign", dur, dt, rtf))
    else:
        log(f"[t1] ERROR: output file not found")

    # --- Test 2: multi-speaker ---
    log("")
    log("--- Test 2: 2_multi_speaker.txt ---")
    text2_raw = (SCRIPTS_DIR / "2_multi_speaker.txt").read_text().strip()

    # 2a: single-speaker adaptation (strip tags, narrator voice)
    log("[t2a] single-speaker adaptation (tags stripped, narrator voice)")
    text2a = strip_speaker_tags(text2_raw)
    dur, dt, rtf, out_file = generate_and_measure(text2a, model, NARRATOR_VOICE, "test2a_multi_speaker_single_voice")
    if out_file:
        sz = out_file.stat().st_size
        log(f"[t2a] generated {dur:.2f}s audio in {dt:.2f}s -> {rtf:.1f}x real-time, {sz} bytes")
        results.append(("2a_multi_speaker_single_voice", "narrator_voicedesign", dur, dt, rtf))
    else:
        log(f"[t2a] ERROR: output file not found")

    # 2b: multi-voice (alternate voices per [S1]/[S2] line, stitch together)
    log("[t2b] multi-voice (S1=young woman, S2=older man, stitched)")
    lines = split_by_speaker(text2_raw)
    import numpy as np
    import soundfile as sf
    all_chunks = []
    t_total = 0.0
    sr = None
    for speaker, line_text in lines:
        voice_desc = S1_VOICE if speaker == "S1" else S2_VOICE
        log(f"[t2b]   {speaker}: '{line_text[:50]}...'")
        t0 = time.time()
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
        temp_file = find_output(OUT_DIR, temp_prefix)
        if temp_file and temp_file.exists():
            audio, sr = sf.read(str(temp_file))
            all_chunks.append(audio)
            log(f"[t2b]     -> {len(audio)/sr:.2f}s in {dt:.2f}s")
            temp_file.unlink()  # clean up temp
        else:
            log(f"[t2b]     ERROR: temp file not found")

    if all_chunks and sr:
        audio_full = np.concatenate(all_chunks)
        out_file = OUT_DIR / "test2b_multi_speaker_two_voices.wav"
        sf.write(str(out_file), audio_full, sr)
        dur = len(audio_full) / sr
        sz = out_file.stat().st_size
        rtf = dur / t_total if t_total > 0 else 0
        log(f"[t2b] total: {dur:.2f}s audio in {t_total:.2f}s -> {rtf:.1f}x real-time, {sz} bytes")
        results.append(("2b_multi_speaker_two_voices", "S1+S2 voicedesign", dur, t_total, rtf))

    # --- Test 3: long form ---
    log("")
    log("--- Test 3: 3_long_form.txt ---")
    text3 = (SCRIPTS_DIR / "3_long_form.txt").read_text().strip()
    log(f"[t3] text length: {len(text3)} chars")
    log(f"[t3] using max_tokens={MAX_TOKENS_LONG} for long-form text")
    dur, dt, rtf, out_file = generate_and_measure(
        text3, model, NARRATOR_VOICE, "test3_long_form", max_tokens=MAX_TOKENS_LONG
    )
    if out_file:
        sz = out_file.stat().st_size
        log(f"[t3] generated {dur:.2f}s audio in {dt:.2f}s -> {rtf:.1f}x real-time, {sz} bytes")
        results.append(("3_long_form", "narrator_voicedesign", dur, dt, rtf))
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
