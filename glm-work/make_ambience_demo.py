#!/usr/bin/env python3
"""
Ambience-under-narration demo (zero downloads).

Synthesizes three procedural ambient beds (tavern, forest, tense-marsh) and layers
each under an existing Kokoro narration clip with side-chain ducking, so Arie can
hear the "ambient bed under narration" concept without waiting on any model download.

This represents what the LIBRARY-BASED approach (Research Task 3 recommendation)
sounds like once real tracks are swapped in: an ambient bed at ~25% volume under
the narration voice, ducked slightly while the narrator speaks.

Output: glm-work/outputs/ambience_demo/{demo_tavern,demo_forest,demo_marsh}.wav
        + a dry narration reference copy for A/B comparison.

Run:    .venv/bin/python make_ambience_demo.py
"""

import os
import numpy as np
import soundfile as sf
from scipy import signal

SR = 24000  # match the Kokoro narration sample rate
OUT_DIR = os.path.join(os.path.dirname(__file__), "outputs", "ambience_demo")
NARRATION = os.path.join(os.path.dirname(__file__), "outputs", "kokoro", "test1_single_speaker.wav")


# ---------- helpers ----------------------------------------------------------

def rms_envelope(x, frame=512, hop=128):
    """Smooth amplitude envelope of a signal, 0..1, used for side-chain ducking."""
    n = len(x)
    env = np.zeros(n)
    win = np.hanning(frame)
    for i in range(0, n, hop):
        j = min(i + frame, n)
        seg = x[i:j]
        if len(seg) > 0:
            r = np.sqrt(np.mean(seg ** 2)) + 1e-9
            env[i:j] = max(env[i:j].max() if j > i else 0.0, r)
    # normalize to 0..1
    if env.max() > 0:
        env = env / env.max()
    # smooth heavily so ducking doesn't pump
    env = np.clip(signal.filtfilt(*signal.butter(2, 30.0 / (SR / 2)), env), 0, 1)
    return env


def duck(ambience, narration_env, duck_depth=0.55, base_vol=0.25):
    """Side-chain duck: reduce ambience volume where narration is loud.

    base_vol = ambience level when narration is silent (0..1)
    duck_depth = how much ambience is reduced at full narration (0=none, 1=full mute)
    Returns the ducked ambience (same length as ambience).
    """
    # gain goes from base_vol (narration silent) down to base_vol*(1-duck_depth)
    gain = base_vol * (1.0 - duck_depth * narration_env)
    # pad/trim gain to ambience length
    g = np.ones(len(ambience)) * base_vol
    m = min(len(g), len(gain))
    g[:m] = gain[:m]
    return ambience * g


def mix(narration, ambience_ducked):
    """Mix narration (full vol) with ducked ambience. Pads shorter to longer."""
    n = max(len(narration), len(ambience_ducked))
    out = np.zeros(n)
    a = np.zeros(n)
    a[:len(narration)] = narration
    b = np.zeros(n)
    b[:len(ambience_ducked)] = ambience_ducked
    out = a + b
    # soft clip to avoid clipping
    out = np.tanh(out * 0.9)
    return out


# ---------- ambient bed synthesizers ----------------------------------------

def pink_noise(n):
    """Voss-McCartney pink noise approximation."""
    n_rows = 16
    n_cols = (n // n_rows) + 1
    rows = np.random.randn(n_rows, n_cols)
    # cumulative sum down columns = slow drift
    rows = np.cumsum(rows, axis=0)
    # normalize each row
    rows -= rows.mean(axis=1, keepdims=True)
    rows /= rows.std(axis=1, keepdims=True) + 1e-9
    # flatten column-major so each sample mixes slow + fast
    flat = rows.T.reshape(-1)
    flat = flat[:n]
    flat /= flat.std() + 1e-9
    return flat


def brown_noise(n):
    """Brown noise (integrated white)."""
    w = np.random.randn(n)
    b = np.cumsum(w)
    b -= b.mean()
    b /= b.std() + 1e-9
    return b


def lp(x, cutoff_hz):
    return signal.filtfilt(*signal.butter(4, cutoff_hz / (SR / 2)), x)


def hp(x, cutoff_hz):
    return signal.filtfilt(*signal.butter(4, cutoff_hz / (SR / 2), "high"), x)


def bp(x, lo_hz, hi_hz):
    return signal.filtfilt(*signal.butter(4, [lo_hz / (SR / 2), hi_hz / (SR / 2)], "band"), x)


def make_tavern(seconds):
    """Tavern ambience: fire crackle + crowd murmur + occasional glass clinks."""
    n = int(SR * seconds)
    out = np.zeros(n)

    # 1. Crowd murmur: low-passed pink noise with slow amplitude modulation
    murmur = pink_noise(n)
    murmur = lp(murmur, 700)  # muffled voices band
    # slow swell to simulate ebb/flow of conversation
    t = np.arange(n) / SR
    swell = 0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t) * np.sin(2 * np.pi * 0.13 * t)
    murmur *= swell
    out += 0.5 * murmur

    # 2. Fire crackle: band-passed noise bursts with random timing
    crackle = np.zeros(n)
    n_bursts = int(seconds * 18)  # ~18 crackles/sec
    for _ in range(n_bursts):
        pos = np.random.randint(0, n - 200)
        dur = np.random.randint(20, 120)
        amp = np.random.uniform(0.2, 1.0)
        burst = np.random.randn(dur) * amp
        # short decay envelope
        env = np.exp(-np.arange(dur) / (dur * 0.3))
        crackle[pos:pos + dur] += burst * env
    crackle = bp(crackle, 800, 5000)
    out += 0.35 * crackle

    # 3. Glass clinks: occasional high resonant clicks
    clinks = np.zeros(n)
    n_clinks = max(1, int(seconds / 4.0))  # ~1 clink per 4 sec
    for _ in range(n_clinks):
        pos = np.random.randint(0, n - 1500)
        dur = 600
        # a couple of high resonant partials
        t = np.arange(dur) / SR
        env = np.exp(-t * 12)
        f1 = np.random.uniform(1800, 2600)
        f2 = np.random.uniform(3200, 4200)
        click = (np.sin(2 * np.pi * f1 * t) + 0.5 * np.sin(2 * np.pi * f2 * t)) * env
        clinks[pos:pos + dur] += click * np.random.uniform(0.15, 0.3)
    out += clinks

    # 4. Low room tone
    room = brown_noise(n)
    room = lp(room, 120)
    out += 0.15 * room

    out /= np.max(np.abs(out)) + 1e-9
    return out * 0.85


def make_forest(seconds):
    """Forest ambience: wind + birds + insect bed."""
    n = int(SR * seconds)
    out = np.zeros(n)
    t = np.arange(n) / SR

    # 1. Wind: low-passed brown noise with slow LFO
    wind = brown_noise(n)
    wind = lp(wind, 500)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.08 * t)
    wind *= lfo
    out += 0.55 * wind

    # 2. Insect bed: high sustained tone cluster with slight modulation
    insects = np.zeros(n)
    for f in (5800, 6100, 6400, 7200):
        mod = 1.0 + 0.05 * np.sin(2 * np.pi * np.random.uniform(8, 14) * t)
        insects += np.sin(2 * np.pi * f * t * mod) * np.random.uniform(0.05, 0.12)
    insects = bp(insects, 4000, 9000)
    out += insects

    # 3. Bird chirps: occasional short frequency sweeps
    chirps = np.zeros(n)
    n_chirps = max(1, int(seconds / 2.5))
    for _ in range(n_chirps):
        pos = np.random.randint(0, n - 800)
        dur = np.random.randint(120, 280)
        tt = np.arange(dur) / SR
        env = np.hanning(dur)
        f0 = np.random.uniform(2200, 3800)
        f1 = f0 * np.random.uniform(0.9, 1.4)
        f_inst = np.linspace(f0, f1, dur)
        phase = 2 * np.pi * np.cumsum(f_inst) / SR
        chirp = np.sin(phase) * env * np.random.uniform(0.1, 0.22)
        chirps[pos:pos + dur] += chirp
    out += chirps

    # 4. Leaf rustle bed
    rustle = pink_noise(n)
    rustle = bp(rustle, 1500, 6000)
    rustle *= (0.3 + 0.3 * np.sin(2 * np.pi * 0.2 * t))
    out += 0.18 * rustle

    out /= np.max(np.abs(out)) + 1e-9
    return out * 0.8


def make_marsh(seconds):
    """Tense marsh/dark ambience: low drone + wind + distant thunder + water drips.

    This one matches the actual narration content (Mireth at the marsh edge, storm
    coming, vodnik lurking) — so it's the most 'realistic' demo pairing.
    """
    n = int(SR * seconds)
    out = np.zeros(n)
    t = np.arange(n) / SR

    # 1. Low drone: two detuned low sines + sub
    drone = (np.sin(2 * np.pi * 55 * t)
             + 0.7 * np.sin(2 * np.pi * 58.3 * t)
             + 0.5 * np.sin(2 * np.pi * 82 * t)
             + 0.4 * np.sin(2 * np.pi * 27.5 * t))
    # slow swell
    drone *= (0.7 + 0.3 * np.sin(2 * np.pi * 0.05 * t))
    out += 0.45 * drone

    # 2. Wind: darker, lower than forest
    wind = brown_noise(n)
    wind = lp(wind, 350)
    lfo = 0.4 + 0.6 * np.sin(2 * np.pi * 0.06 * t) * np.sin(2 * np.pi * 0.11 * t)
    wind *= lfo
    out += 0.5 * wind

    # 3. Distant thunder: occasional low rumbles
    thunder = np.zeros(n)
    n_rumbles = max(1, int(seconds / 9.0))
    for _ in range(n_rumbles):
        pos = np.random.randint(0, n - 4000)
        dur = np.random.randint(2500, 4000)
        tt = np.arange(dur) / SR
        # attack-decay envelope
        env = np.exp(-tt * 1.2) * (1 - np.exp(-tt * 8))
        rumble = brown_noise(dur) * env
        rumble = lp(rumble, 90)
        thunder[pos:pos + dur] += rumble * np.random.uniform(0.4, 0.8)
    out += thunder

    # 4. Water drips: occasional resonant plinks
    drips = np.zeros(n)
    n_drips = max(1, int(seconds / 3.5))
    for _ in range(n_drips):
        pos = np.random.randint(0, n - 600)
        dur = 400
        tt = np.arange(dur) / SR
        env = np.exp(-tt * 18)
        f = np.random.uniform(900, 1600)
        drip = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.2 * tt)) * env
        drips[pos:pos + dur] += drip * np.random.uniform(0.08, 0.16)
    out += drips

    # 5. Insect/frog bed: sparse low chirps
    frogs = np.zeros(n)
    n_frogs = max(1, int(seconds / 5.0))
    for _ in range(n_frogs):
        pos = np.random.randint(0, n - 300)
        dur = np.random.randint(80, 180)
        tt = np.arange(dur) / SR
        env = np.hanning(dur)
        f = np.random.uniform(180, 320)
        frog = np.sin(2 * np.pi * f * tt) * env * 0.18
        frogs[pos:pos + dur] += frog
    out += frogs

    out /= np.max(np.abs(out)) + 1e-9
    return out * 0.85


# ---------- main -------------------------------------------------------------

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # Load narration (mono, 24kHz)
    narr, sr_narr = sf.read(NARRATION, dtype="float32")
    assert sr_narr == SR, f"expected {SR}Hz narration, got {sr_narr}Hz"
    duration = len(narr) / SR
    print(f"Loaded narration: {duration:.1f}s @ {sr_narr}Hz")

    # Compute narration envelope once (used for ducking all beds)
    env = rms_envelope(narr)

    # Save a dry reference copy of the narration for A/B
    ref_path = os.path.join(OUT_DIR, "narration_dry_reference.wav")
    sf.write(ref_path, narr, SR)
    print(f"Wrote dry reference: {ref_path}")

    beds = [
        ("demo_tavern", make_tavern, "tavern (fire + crowd + clinks)"),
        ("demo_forest", make_forest, "forest (wind + birds + insects)"),
        ("demo_marsh", make_marsh, "tense marsh (drone + thunder + drips)  <-- matches narration content"),
    ]

    for name, synth, desc in beds:
        print(f"Synthesizing {desc} ...")
        bed = synth(duration).astype("float32")
        bed_ducked = duck(bed, env, duck_depth=0.55, base_vol=0.25)
        mixed = mix(narr, bed_ducked).astype("float32")
        out_path = os.path.join(OUT_DIR, f"{name}.wav")
        sf.write(out_path, mixed, SR)
        size_kb = os.path.getsize(out_path) // 1024
        print(f"  -> {out_path}  ({duration:.1f}s, {size_kb} KB)")

    print("\nDone. Files in:", OUT_DIR)
    print("Listen to narration_dry_reference.wav first, then compare with the three demo_*.wav")


if __name__ == "__main__":
    main()
