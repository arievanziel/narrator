#!/usr/bin/env python3
"""
Ambience-under-narration demo v2 — REAL library tracks.

Layers actual royalty-free music/ambience tracks (CC0 and CC-BY, downloaded from
OpenGameArt) under existing Kokoro narration, with side-chain ducking so the
narration voice stays intelligible while the ambience fills the pauses.

This is what the LIBRARY-BASED approach actually sounds like — real composed
music and ambient beds, not synthesized noise.

Tracks used (all in outputs/ambience_demo/tracks/):
  - tavern_old_tower_inn.mp3  — CC0, "The Old Tower Inn" by RandomMind (medieval tavern)
  - dark_woods.mp3            — CC-BY 3.0, "RPG Ambient 4 (The Dark Woods)" by Hitctrl
  - dungeon_ambient.ogg       — CC0, "Loopable Dungeon Ambience" by JaggedStone

Output: outputs/ambience_demo/v2_{tavern,dark_woods,dungeon}.wav

Run:    .venv/bin/python make_ambience_demo_v2.py
"""

import os
import numpy as np
import soundfile as sf
from scipy import signal

SR = 24000  # match the Kokoro narration sample rate
OUT_DIR = os.path.join(os.path.dirname(__file__), "outputs", "ambience_demo")
TRACKS_DIR = os.path.join(OUT_DIR, "tracks")
NARRATION = os.path.join(os.path.dirname(__file__), "outputs", "kokoro", "test1_single_speaker.wav")

# (output_name, track_filename, description, base_vol, duck_depth)
BEDS = [
    ("v2_dark_woods", "dark_woods.mp3",
     "dark woods (CC-BY, Hitctrl) — tense strings, matches the marsh narration", 0.18, 0.60),
    ("v2_dungeon", "dungeon_ambient.ogg",
     "dungeon ambience (CC0, JaggedStone) — low wind + water drips, matches the marsh", 0.22, 0.55),
    ("v2_tavern", "tavern_old_tower_inn.mp3",
     "tavern (CC0, RandomMind) — medieval inn theme, doesn't match story but shows a 'safe' scene", 0.15, 0.60),
]


def load_and_resample(path, target_sr, target_channels=1):
    """Load any audio file, resample to target SR, convert to mono if needed."""
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    # to mono
    if audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = audio[:, 0]
    # resample if needed
    if sr != target_sr:
        n_out = int(len(audio) * target_sr / sr)
        audio = signal.resample(audio, n_out)
    return audio.astype("float32")


def rms_envelope(x, frame=512, hop=128):
    """Smooth amplitude envelope of a signal, 0..1, used for side-chain ducking."""
    n = len(x)
    env = np.zeros(n)
    for i in range(0, n, hop):
        j = min(i + frame, n)
        seg = x[i:j]
        if len(seg) > 0:
            r = np.sqrt(np.mean(seg ** 2)) + 1e-9
            env[i:j] = max(env[i:j].max() if j > i else 0.0, r)
    if env.max() > 0:
        env = env / env.max()
    # smooth heavily so ducking doesn't pump
    env = np.clip(signal.filtfilt(*signal.butter(2, 30.0 / (SR / 2)), env), 0, 1)
    return env


def duck(ambience, narration_env, duck_depth=0.55, base_vol=0.25):
    """Side-chain duck: reduce ambience volume where narration is loud."""
    gain = base_vol * (1.0 - duck_depth * narration_env)
    g = np.ones(len(ambience)) * base_vol
    m = min(len(g), len(gain))
    g[:m] = gain[:m]
    return ambience * g


def loop_to_length(audio, target_len):
    """Loop an audio array to at least target_len samples, with crossfade."""
    if len(audio) >= target_len:
        return audio[:target_len]
    # crossfade loop: overlap the last 1s with the first 1s
    xfade = SR  # 1 second crossfade
    looped = np.copy(audio)
    while len(looped) < target_len + xfade:
        # crossfade end of current with beginning of original
        segment = np.concatenate([looped, audio])
        # apply crossfade at the junction
        junction = len(looped)
        if junction > xfade and len(audio) > xfade:
            fade_out = np.linspace(1, 0, xfade)
            fade_in = np.linspace(0, 1, xfade)
            segment[junction - xfade:junction] = looped[junction - xfade:junction] * fade_out + audio[:xfade] * fade_in
        looped = segment
    return looped[:target_len]


def fade_in_out(audio, fade_samples=None):
    """Apply gentle fade-in and fade-out to avoid clicks at start/end."""
    if fade_samples is None:
        fade_samples = min(SR, len(audio) // 4)  # 1s or 1/4 of track
    fade_in = np.linspace(0, 1, fade_samples)
    fade_out = np.linspace(1, 0, fade_samples)
    audio[:fade_samples] *= fade_in
    audio[-fade_samples:] *= fade_out
    return audio


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Load narration (mono, 24kHz)
    narr, sr_narr = sf.read(NARRATION, dtype="float32")
    assert sr_narr == SR, f"expected {SR}Hz narration, got {sr_narr}Hz"
    duration = len(narr) / SR
    print(f"Loaded narration: {duration:.1f}s @ {sr_narr}Hz")

    # Compute narration envelope once
    env = rms_envelope(narr)

    for name, track_file, desc, base_vol, duck_depth in BEDS:
        track_path = os.path.join(TRACKS_DIR, track_file)
        if not os.path.exists(track_path):
            print(f"SKIP {name}: track not found at {track_path}")
            continue

        print(f"\nLayering: {desc}")
        print(f"  Loading {track_file} ...")
        bed = load_and_resample(track_path, SR)
        print(f"  Track: {len(bed)/SR:.1f}s, looping to {duration:.1f}s ...")

        # Loop the track to match narration duration
        bed = loop_to_length(bed, len(narr))

        # Apply fade-in/out to the ambience bed
        bed = fade_in_out(bed)

        # Side-chain duck
        bed_ducked = duck(bed, env, duck_depth=duck_depth, base_vol=base_vol)

        # Mix narration (full vol) + ducked ambience
        mixed = narr + bed_ducked[:len(narr)]
        # soft clip to avoid any clipping
        mixed = np.tanh(mixed * 0.9)

        out_path = os.path.join(OUT_DIR, f"{name}.wav")
        sf.write(out_path, mixed.astype("float32"), SR)
        size_kb = os.path.getsize(out_path) // 1024
        peak = np.abs(mixed).max()
        rms = np.sqrt(np.mean(mixed ** 2))
        print(f"  -> {out_path}  ({duration:.1f}s, {size_kb}KB, peak={peak:.3f}, rms={rms:.4f})")

    print(f"\nDone. Files in: {OUT_DIR}")
    print("\nListen order:")
    print("  1. narration_dry_reference.wav  (baseline, no ambience)")
    print("  2. v2_dark_woods.wav            (tense strings — matches the marsh story)")
    print("  3. v2_dungeon.wav               (low wind + drips — also matches)")
    print("  4. v2_tavern.wav                (medieval inn — different scene type)")


if __name__ == "__main__":
    main()
