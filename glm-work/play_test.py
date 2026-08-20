"""Direct-playback TTS test harness.

Reads a pre-written test script, generates speech with the chosen model, and
plays it through the Mac speakers AS IT GENERATES (streaming via mlx-audio's
AudioPlayer + sounddevice — not generate-then-wait-then-listen).

No GUI, no paste. Just CLI args. Reads from glm-work/test_scripts/.

Uses mlx-audio's generate_audio(stream=True, play=True), which queues ~2-second
audio chunks to a sounddevice output stream as they're produced. Works uniformly
across Kokoro (MLX), Qwen3-TTS VoiceDesign, Dia, and Higgs — all loaded via
mlx-audio so they share the same streaming playback path.

Usage:
  python play_test.py --list-scripts
  python play_test.py --list-voices
  python play_test.py --script 2_multi_speaker --model kokoro --voice af_heart
  python play_test.py --script 3_long_form --model kokoro --voice am_michael
  python play_test.py --script 1_single_speaker --model qwen3_vd \\
      --voice-desc "A calm, warm female narrator with a measured pace."
  python play_test.py --script 3_long_form --model kokoro --voice af_heart --save

Tag handling: [S1]/[S2] speaker tags are stripped (Kokoro would read them
literally). Emotion cues like (whispering) are left in for now — proper
emotion-cue handling is a future enhancement (see narrator_parser.py).
"""
import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # glm-work/
SCRIPTS_DIR = ROOT / "test_scripts"

# Model registry: name -> (mlx-audio model id or local path, kind)
# kind determines which generate_audio params are used (voice vs instruct).
# Local paths avoid the Sonnet-caught re-download bug (see INSTRUCTIONS-FOR-GLM.md).
QWEN3_LOCAL = ROOT / "models" / "qwen3_voicedesign_8bit"
MODELS = {
    "kokoro": {
        "id": "mlx-community/Kokoro-82M-bf16",
        "kind": "preset",  # voice = preset name e.g. "af_heart"
        "voices": [
            "af_heart", "af_bella", "af_sky", "af_nicole", "af_sarah", "af_emma",
            "am_michael", "am_adam", "am_eric", "am_liam",
            "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
        ],
    },
    "qwen3_vd": {
        "id": str(QWEN3_LOCAL),
        "kind": "designed",  # instruct = natural-language voice description
        "voices": [],
    },
    # These are registered so --list-models shows them, but will error gracefully
    # until their models are downloaded (Task D / Task E).
    "dia": {
        "id": "mlx-community/Dia-1.6B",
        "kind": "preset",
        "voices": [],
    },
    "higgs": {
        "id": "mlx-community/Higgs-Audio-v2-3B-q6",
        "kind": "preset",
        "voices": [],
    },
}

DEFAULT_VOICE_DESC = (
    "A calm, warm female narrator with a measured pace, suitable for reading "
    "fantasy fiction."
)


def strip_speaker_tags(text: str) -> str:
    """Remove [S1]/[S2] tags so they aren't read aloud by preset-voice models."""
    return re.sub(r"\[S\d+\]\s*", "", text)


def list_scripts():
    scripts = sorted(p for p in SCRIPTS_DIR.glob("*.txt"))
    if not scripts:
        print(f"No test scripts found in {SCRIPTS_DIR}")
        return
    print("Available test scripts:")
    for p in scripts:
        chars = len(p.read_text().strip())
        print(f"  {p.stem:<30} {chars:>6} chars")


def list_voices():
    print("Models and voices:")
    for name, info in MODELS.items():
        kind = info["kind"]
        if kind == "preset":
            if info["voices"]:
                print(f"  {name:<12} (preset): {', '.join(info['voices'][:8])}"
                      + (" ..." if len(info["voices"]) > 8 else ""))
            else:
                print(f"  {name:<12} (preset): voices listed by model at runtime")
        else:
            print(f"  {name:<12} (voice-design): describe voice via --voice-desc")


def load_model(model_name: str):
    """Load an mlx-audio model by registry name. Errors clearly if missing."""
    from mlx_audio.tts import load_model
    info = MODELS[model_name]
    model_id = info["id"]
    # For local-path models, verify the directory exists before attempting load
    # (avoids a confusing HF re-download attempt — the Sonnet-caught bug class).
    if model_id.startswith("/") or model_id.startswith(str(ROOT)):
        p = Path(model_id)
        if not p.exists():
            print(f"ERROR: model directory not found: {p}", file=sys.stderr)
            print(f"  '{model_name}' may not be downloaded yet. "
                  f"Check Task D / Task E status.", file=sys.stderr)
            sys.exit(1)
    print(f"[load] {model_name} <- {model_id}")
    t0 = time.time()
    model = load_model(model_id)
    print(f"[load] ready in {time.time()-t0:.1f}s")
    return model


def play(script: str, model_name: str, voice: str, voice_desc: str,
         save: bool, streaming_interval: float):
    from mlx_audio.tts.generate import generate_audio

    script_path = SCRIPTS_DIR / f"{script}.txt"
    if not script_path.exists():
        print(f"ERROR: test script not found: {script_path}", file=sys.stderr)
        print(f"  Run --list-scripts to see available scripts.", file=sys.stderr)
        sys.exit(1)

    text = script_path.read_text().strip()
    info = MODELS[model_name]
    kind = info["kind"]

    # Strip speaker tags for preset-voice models (they'd be read literally).
    # For voice-design models, tags are also stripped — Qwen3 VoiceDesign takes
    # one voice description for the whole text, not per-speaker.
    text = strip_speaker_tags(text)

    model = load_model(model_name)

    common = dict(
        text=text,
        model=model,
        lang_code="en",
        stream=True,
        play=True,
        streaming_interval=streaming_interval,
        verbose=True,
    )
    if kind == "preset":
        common["voice"] = voice
    elif kind == "designed":
        common["instruct"] = voice_desc
        # Qwen3 VoiceDesign uses 'voice' as the speaker label; leave default.
    if save:
        common["save"] = True
        common["output_path"] = str(ROOT / "outputs" / "play_test")
        common["file_prefix"] = f"{script}_{model_name}_{int(time.time())}"
        common["audio_format"] = "wav"
        common["join_audio"] = True

    print(f"\n[play] script={script} model={model_name} "
          f"{'voice='+voice if kind=='preset' else 'voice-desc=\"'+voice_desc[:40]+'...\"'}")
    print(f"[play] {len(text)} chars, streaming interval {streaming_interval}s")
    print(f"[play] audio will play through Mac speakers as it generates...\n")

    t0 = time.time()
    generate_audio(**common)
    dt = time.time() - t0
    print(f"\n[play] done in {dt:.1f}s (wall clock, includes playback time)")


def main():
    ap = argparse.ArgumentParser(
        description="Direct-playback TTS test harness. Plays test scripts as they generate.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--list-scripts", action="store_true", help="List available test scripts")
    ap.add_argument("--list-voices", action="store_true", help="List models and voices")
    ap.add_argument("--script", metavar="NAME", help="Test script name (without .txt)")
    ap.add_argument("--model", choices=list(MODELS.keys()), help="TTS model to use")
    ap.add_argument("--voice", default="af_heart", help="Preset voice name (preset-voice models)")
    ap.add_argument("--voice-desc", default=DEFAULT_VOICE_DESC,
                    help="Natural-language voice description (voice-design models)")
    ap.add_argument("--save", action="store_true",
                    help="Also save the streamed audio to outputs/play_test/")
    ap.add_argument("--streaming-interval", type=float, default=2.0,
                    help="Seconds of audio per streaming chunk (default 2.0)")
    args = ap.parse_args()

    if args.list_scripts:
        list_scripts()
        return
    if args.list_voices:
        list_voices()
        return
    if not args.script or not args.model:
        ap.error("--script and --model are required (or use --list-scripts / --list-voices)")

    play(
        script=args.script,
        model_name=args.model,
        voice=args.voice,
        voice_desc=args.voice_desc,
        save=args.save,
        streaming_interval=args.streaming_interval,
    )


if __name__ == "__main__":
    main()
