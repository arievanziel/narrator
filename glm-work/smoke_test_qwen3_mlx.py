"""Smoke test: Qwen3-TTS VoiceDesign via mlx-audio.

This triggers the model download (~3.08 GB for 8bit variant) from
huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit and caches it.

VoiceDesign: describe a voice in natural language via the `instruct` parameter,
and the model generates speech in that described voice.
"""
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent / "outputs" / "qwen3_voicedesign"
OUT.mkdir(parents=True, exist_ok=True)

# Use local path (manually downloaded via curl) — NOT the HF repo ID.
# mlx_audio.utils.get_model_path() only treats strings starting with ".", "/", or "~"
# as local paths; a bare "mlx-community/..." would trigger a re-download. (Sonnet catch.)
MODEL = str(Path(__file__).resolve().parent / "models" / "qwen3_voicedesign_8bit")

print(f"[smoke] mlx-audio Qwen3-TTS VoiceDesign smoke test", flush=True)
print(f"[smoke] model: {MODEL}", flush=True)

t0 = time.time()
from mlx_audio.tts import load_model
print(f"[smoke] import done in {time.time()-t0:.1f}s", flush=True)

print(f"[smoke] loading model (triggers download on first run)...", flush=True)
t0 = time.time()
model = load_model(MODEL)
print(f"[smoke] model loaded in {time.time()-t0:.1f}s", flush=True)

# VoiceDesign: describe a voice for narration
voice_desc = "A calm, warm female narrator with a measured pace, suitable for reading fantasy fiction."
text = "Hello. This is a smoke test of the Qwen3-TTS VoiceDesign pipeline."

print(f"[smoke] generating with VoiceDesign...", flush=True)
print(f"[smoke] voice description: {voice_desc}", flush=True)
print(f"[smoke] text: {text}", flush=True)

t0 = time.time()
from mlx_audio.tts.generate import generate_audio
generate_audio(
    text=text,
    model=model,
    instruct=voice_desc,
    lang_code="en",
    output_path=str(OUT),
    file_prefix="smoke_test",
    audio_format="wav",
    verbose=True,
)
dt = time.time() - t0
print(f"[smoke] generation done in {dt:.1f}s", flush=True)

out_file = OUT / "smoke_test.wav"
if out_file.exists():
    print(f"[smoke] wrote {out_file} ({out_file.stat().st_size} bytes)", flush=True)
    print("[smoke] OK", flush=True)
else:
    print(f"[smoke] WARNING: expected output not at {out_file}", flush=True)
    # Check what files were created
    for f in OUT.iterdir():
        print(f"[smoke] found: {f}")
