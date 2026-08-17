"""Smoke test: load Kokoro, generate a tiny 'hello' string, save wav.

kokoro 0.9.4 API: g2p(text) -> (ps, tokens); generate_from_tokens(tokens, voice) -> generator of Result(audio=...).
"""
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "outputs" / "kokoro"
OUT.mkdir(parents=True, exist_ok=True)

print("[smoke] importing kokoro + torch...", flush=True)
t0 = time.time()
import torch
from kokoro import KPipeline

print(f"[smoke] imports done in {time.time()-t0:.1f}s", flush=True)
print(f"[smoke] torch version: {torch.__version__}", flush=True)
print(f"[smoke] MPS available: {torch.backends.mps.is_available()}", flush=True)

print("[smoke] building KPipeline(lang_code='a')...", flush=True)
t0 = time.time()
pipeline = KPipeline(lang_code="a")  # 'a' = American English
print(f"[smoke] pipeline ready in {time.time()-t0:.1f}s", flush=True)

text = "Hello. This is a smoke test of the Kokoro text to speech pipeline."
print(f"[smoke] g2p + generate: {text}", flush=True)
t0 = time.time()
ps, tokens = pipeline.g2p(text)
audio_chunks = []
for result in pipeline.generate_from_tokens(tokens=tokens, voice="af_heart"):
    audio_chunks.append(result.audio)
dt = time.time() - t0
print(f"[smoke] generate done in {dt:.2f}s, {len(audio_chunks)} chunks", flush=True)

import soundfile as sf
import numpy as np
audio = torch.cat(audio_chunks).cpu().numpy() if audio_chunks else np.array([])
out_path = OUT / "smoke_test.wav"
sf.write(str(out_path), audio, 24000)
dur = len(audio) / 24000
print(f"[smoke] wrote {out_path} ({out_path.stat().st_size} bytes)", flush=True)
print(f"[smoke] audio duration: {dur:.2f}s, generation took {dt:.2f}s -> {dur/dt:.1f}x real-time" if dt > 0 else "[smoke] no audio", flush=True)
print("[smoke] OK", flush=True)
