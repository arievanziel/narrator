#!/usr/bin/env python3
"""
Epic scene production — multi-method TTS + music + SFX assembly.

Scene: test_scripts/4_epic_scene.txt (narrator + Kael + Lyra + 4 SFX moments)

Methods:
  1. all-local    — Kokoro TTS (local) + library music (CC0) + free CC0 SFX
  2. hybrid       — Qwen3 VoiceDesign TTS (local) + library music + ElevenLabs SFX
  3. all-eleven   — ElevenLabs TTS + Music + SFX (all API)
  4. groq-dm      — Groq generates a new scene → Kokoro TTS + library music + ElevenLabs SFX

Usage:
  .venv/bin/python produce_epic_scene.py --method 1    # all-local (no API key needed)
  .venv/bin/python produce_epic_scene.py --method 2    # hybrid (needs ELEVENLABS_API_KEY)
  .venv/bin/python produce_epic_scene.py --method 3    # all-eleven (needs ELEVENLABS_API_KEY)
  .venv/bin/python produce_epic_scene.py --method 4    # groq-dm (needs GROQ_API_KEY + ELEVENLABS_API_KEY)
  .venv/bin/python produce_epic_scene.py --method all  # run all available

Each method outputs a single WAV file in outputs/epic_scene/:
  method1_all_local.wav
  method2_hybrid.wav
  method3_all_eleven.wav
  method4_groq_dm.wav
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import soundfile as sf
from scipy import signal

# --- paths ---
HERE = os.path.dirname(os.path.abspath(__file__))
SCENE_FILE = os.path.join(HERE, "test_scripts", "4_epic_scene.txt")
OUT_DIR = os.path.join(HERE, "outputs", "epic_scene")
TRACKS_DIR = os.path.join(HERE, "outputs", "ambience_demo", "tracks")
SFX_DIR = os.path.join(OUT_DIR, "sfx")
MUSIC_TRACK = os.path.join(TRACKS_DIR, "dark_woods.mp3")  # tense strings, fits the scene

SR = 24000  # output sample rate (matches Kokoro)

# --- Kokoro voice assignments ---
KOKORO_VOICES = {
    "narrator": "af_heart",   # warm storytelling voice
    "Kael": "am_onyx",        # deep, veteran warrior
    "Lyra": "af_sky",         # bright, young mage
}

# --- Qwen3 VoiceDesign voice descriptions ---
QWEN3_VOICES = {
    "narrator": "A weathered storyteller with a calm, measured voice, speaking at a steady pace with slight warmth.",
    "Kael": "A grizzled veteran warrior with a deep, gravelly voice, speaking in short, clipped sentences.",
    "Lyra": "A young mage with a bright, curious voice, slightly higher pitch, speaking with eager intelligence.",
}

# --- SFX definitions ---
# Each SFX has: a key matching [SFX: key] in the scene, a prompt for ElevenLabs,
# and a fallback free CC0 download URL (for Method 1)
SFX_DEFS = {
    "heavy_stone_door_grinding": {
        "prompt": "Heavy ancient stone door grinding open, deep rumble, dust falling, echoing in a large stone chamber",
        "duration": 4.0,
    },
    "rocks_falling_cave_in": {
        "prompt": "Large rocks falling and cave-in collapse, thunderous crash of stone, dust and debris, echoing underground",
        "duration": 5.0,
    },
    "sword_clash_combat": {
        "prompt": "Steel sword clashing against steel, sharp metallic ring, combat impact, echoing in a large stone cathedral",
        "duration": 3.0,
    },
    "magical_explosion_energy_burst": {
        "prompt": "Magical energy explosion, deep resonant boom followed by crystalline shattering, arcane power release, echoing",
        "duration": 4.0,
    },
}


# === SCENE PARSER ===

@dataclass
class SceneSegment:
    """A segment of the scene: narrator text, character dialogue, or SFX cue."""
    kind: str  # "narrator", "dialogue", "sfx"
    speaker: str = ""  # "narrator", "Kael", "Lyra"
    text: str = ""
    sfx_key: str = ""  # for sfx segments


def parse_scene(text: str) -> list[SceneSegment]:
    """Parse the epic scene into segments, handling [Kael], [Lyra], [SFX:] tags."""
    segments = []
    lines = text.strip().split("\n")
    buffer = []

    def flush_buffer():
        """Flush accumulated narrator text as a segment."""
        if buffer:
            joined = " ".join(buffer).strip()
            if joined:
                segments.append(SceneSegment(kind="narrator", speaker="narrator", text=joined))
            buffer.clear()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            flush_buffer()
            i += 1
            continue

        # Check for SFX marker: [SFX: key] or [ SFX: key ] (allow spaces in key)
        sfx_match = re.match(r'^\[\s*SFX:\s*([\w\s]+?)\s*\]', line)
        if sfx_match:
            flush_buffer()
            sfx_key = sfx_match.group(1).strip().replace(" ", "_")
            segments.append(SceneSegment(kind="sfx", sfx_key=sfx_key))
            i += 1
            continue

        # Check for character dialogue [Name] "text" or Name "text" (no brackets)
        char_match = re.match(r'^\[(\w+)\]\s*(.*)', line)
        if not char_match:
            # Also match: Name "dialogue text" (without brackets, common in LLM output)
            char_match = re.match(r'^(\w+)\s+["\u201c](.*)["\u201d]\s*$', line)
        if char_match:
            flush_buffer()
            speaker = char_match.group(1)
            dialogue = char_match.group(2).strip()
            # Handle multi-line dialogue: if the line starts with a quote but doesn't
            # end with one, keep consuming lines until we find the closing quote
            has_open_quote = dialogue.startswith('"') or dialogue.startswith('\u201c')
            has_close_quote = dialogue.endswith('"') or dialogue.endswith('\u201d')
            if has_open_quote and not has_close_quote:
                # Keep consuming lines until we find the closing quote
                while i + 1 < len(lines):
                    i += 1
                    next_line = lines[i].strip()
                    dialogue += " " + next_line
                    if next_line.endswith('"') or next_line.endswith('\u201d'):
                        break
            # Remove surrounding quotes if present
            dialogue = re.sub(r'^["\u201c](.*)["\u201d]$', r'\1', dialogue)
            segments.append(SceneSegment(kind="dialogue", speaker=speaker, text=dialogue))
            i += 1
            continue

        # Regular narrator text — accumulate
        buffer.append(line)
        i += 1

    flush_buffer()
    return segments


# === AUDIO UTILITIES ===

def load_and_resample(path, target_sr=SR, target_channels=1):
    """Load any audio file, resample to target SR, convert to mono."""
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = audio[:, 0]
    if sr != target_sr:
        n_out = int(len(audio) * target_sr / sr)
        audio = signal.resample(audio, n_out)
    return audio.astype("float32")


def rms_envelope(x, frame=512, hop=128):
    """Smooth amplitude envelope for side-chain ducking."""
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
    env = np.clip(signal.filtfilt(*signal.butter(2, 30.0 / (SR / 2)), env), 0, 1)
    return env


def duck_track(track, narration_env, duck_depth=0.60, base_vol=0.15):
    """Side-chain duck: reduce track volume where narration is loud."""
    gain = base_vol * (1.0 - duck_depth * narration_env)
    g = np.ones(len(track)) * base_vol
    m = min(len(g), len(gain))
    g[:m] = gain[:m]
    return track * g


def loop_to_length(audio, target_len):
    """Loop audio to target length with crossfade."""
    if len(audio) >= target_len:
        return audio[:target_len]
    xfade = SR
    result = np.copy(audio)
    while len(result) < target_len:
        result = np.concatenate([result, audio])
    return result[:target_len]


def fade_in_out(audio, fade_samples=None):
    """Apply fade-in and fade-out."""
    if fade_samples is None:
        fade_samples = min(SR, len(audio) // 4)
    if fade_samples > len(audio) // 2:
        fade_samples = len(audio) // 4
    audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
    audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    return audio


def concatenate_audio(segments_audio, gaps=0.3):
    """Concatenate audio segments with silence gaps between them."""
    if not segments_audio:
        return np.zeros(0, dtype="float32")
    gap_samples = int(gaps * SR)
    result = []
    for i, aud in enumerate(segments_audio):
        if i > 0:
            result.append(np.zeros(gap_samples, dtype="float32"))
        result.append(aud)
    return np.concatenate(result)


def place_sfx(narration_audio, sfx_clips, sfx_positions_samples, sfx_vol=0.5):
    """Place SFX clips at specific positions in the narration audio."""
    result = np.copy(narration_audio)
    # Extend if needed
    max_end = max([pos + len(clip) for pos, clip in zip(sfx_positions_samples, sfx_clips)] + [len(result)])
    if max_end > len(result):
        result = np.concatenate([result, np.zeros(max_end - len(result), dtype="float32")])
    for pos, clip in zip(sfx_positions_samples, sfx_clips):
        if pos < 0:
            pos = 0
        clip_faded = fade_in_out(np.copy(clip), min(SR // 4, len(clip) // 6))
        end = min(pos + len(clip_faded), len(result))
        result[pos:end] += clip_faded[:end - pos] * sfx_vol
    return result


def soft_clip(audio):
    """Soft clip to prevent clipping."""
    return np.tanh(audio * 0.9).astype("float32")


# === METHOD 1: ALL-LOCAL (Kokoro + library music + free CC0 SFX) ===

def generate_kokoro_tts(segments, out_subdir):
    """Generate TTS for each segment using Kokoro (local). Returns list of (segment, audio)."""
    import torch
    from kokoro import KPipeline
    print("  Loading Kokoro pipeline...")
    pipeline = KPipeline(lang_code="a")  # 'a' = American English

    results = []
    os.makedirs(out_subdir, exist_ok=True)

    for i, seg in enumerate(segments):
        if seg.kind == "sfx":
            results.append((seg, None))
            continue

        voice = KOKORO_VOICES.get(seg.speaker, KOKORO_VOICES["narrator"])
        print(f"  [{i+1}/{len(segments)}] {seg.kind:8s} {seg.speaker:8s} voice={voice}  text={seg.text[:60]}...")

        # Generate using g2p + generate_from_tokens (matching run_kokoro.py pattern)
        ps, tokens = pipeline.g2p(seg.text)
        chunks = []
        for result in pipeline.generate_from_tokens(tokens=tokens, voice=voice):
            chunks.append(result.audio)
        if chunks:
            audio = torch.cat(chunks).cpu().numpy().astype("float32")
        else:
            audio = np.zeros(SR, dtype="float32")  # 1s silence fallback

        results.append((seg, audio))
        print(f"    -> {len(audio)/SR:.1f}s")

    return results


def find_free_sfx(sfx_key):
    """Try to find a free CC0 SFX for the given key. Returns path or None."""
    # Map SFX keys to OpenGameArt search terms and known free sources
    # For now, we'll use the Sonniss GDC bundles or OpenGameArt
    # As a fallback, we'll synthesize simple SFX procedurally
    return None


def synthesize_sfx(sfx_key, duration):
    """Procedurally synthesize a simple SFX as fallback when no free file is available."""
    n = int(SR * duration)
    t = np.arange(n) / SR

    if sfx_key == "heavy_stone_door_grinding":
        # Low rumble + grinding noise
        rumble = np.sin(2 * np.pi * 40 * t) * 0.5 * np.exp(-t * 0.3)
        grind = (np.random.randn(n) * 0.3) * np.exp(-t * 0.2)
        grind = signal.filtfilt(*signal.butter(4, 200 / (SR / 2)), grind)
        env = np.exp(-t * 0.3) * (1 - np.exp(-t * 5))
        return (rumble + grind) * env * 0.7

    elif sfx_key == "rocks_falling_cave_in":
        # Multiple impacts + dust noise
        audio = np.zeros(n)
        n_rocks = 15
        for _ in range(n_rocks):
            pos = np.random.randint(0, n - 2000)
            dur = np.random.randint(200, 800)
            tt = np.arange(dur) / SR
            env = np.exp(-tt * 8)
            impact = np.random.randn(dur) * env * np.random.uniform(0.3, 0.8)
            impact = signal.filtfilt(*signal.butter(4, [100 / (SR / 2), 2000 / (SR / 2)], "band"), impact)
            audio[pos:pos+dur] += impact
        # Low boom at the start
        boom = np.sin(2 * np.pi * 50 * t) * np.exp(-t * 2) * 0.6
        return (audio + boom) * 0.7

    elif sfx_key == "sword_clash_combat":
        # Sharp metallic ring
        ring = np.zeros(n)
        for f in [3200, 4100, 5300, 6800]:
            ring += np.sin(2 * np.pi * f * t) * np.exp(-t * 6) * 0.3
        # Initial impact
        impact = np.random.randn(min(500, n)) * np.exp(-np.arange(min(500, n)) / 50) * 0.5
        ring[:500] += impact
        return ring * 0.6

    elif sfx_key == "magical_explosion_energy_burst":
        # Deep boom + crystalline shatter
        boom = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 3) * 0.5
        # Crystalline high partials
        crystal = np.zeros(n)
        for f in [2200, 3300, 4400, 5500, 6600]:
            delay = np.random.uniform(0.1, 0.3)
            mask = t > delay
            crystal += np.sin(2 * np.pi * f * t) * np.exp(-(t - delay) * 5) * mask * 0.15
        # Whoosh buildup
        whoosh = np.random.randn(n) * 0.2 * (t < 0.3) * np.exp(-t * 3)
        whoosh = signal.filtfilt(*signal.butter(4, 800 / (SR / 2), "high"), whoosh)
        return (boom + crystal + whoosh) * 0.7

    return np.zeros(n, dtype="float32")


def run_method1(segments):
    """Method 1: All-local (Kokoro + library music + synthesized SFX)."""
    print("\n=== METHOD 1: All-local (Kokoro + library music + synthesized SFX) ===")
    out_subdir = os.path.join(OUT_DIR, "method1_segments")
    os.makedirs(out_subdir, exist_ok=True)

    # Generate TTS
    tts_results = generate_kokoro_tts(segments, out_subdir)

    # Concatenate TTS segments, tracking SFX positions
    tts_segments_audio = []
    sfx_positions = []  # (sfx_key, position_in_samples)
    current_pos = 0
    gap_samples = int(0.3 * SR)

    for seg, audio in tts_results:
        if seg.kind == "sfx":
            sfx_positions.append((seg.sfx_key, current_pos))
            current_pos += int(0.5 * SR)  # placeholder gap for SFX
        elif audio is not None:
            tts_segments_audio.append(audio)
            current_pos += len(audio) + gap_samples

    # Build the narration track
    narration = concatenate_audio([a for _, a in tts_results if a is not None], gaps=0.3)

    # Synthesize SFX
    print("  Synthesizing SFX (procedural fallback)...")
    sfx_clips = []
    sfx_pos_samples = []
    for sfx_key, pos in sfx_positions:
        sfx_def = SFX_DEFS[sfx_key]
        clip = synthesize_sfx(sfx_key, sfx_def["duration"])
        sfx_clips.append(clip)
        sfx_pos_samples.append(pos)
        print(f"    {sfx_key}: {len(clip)/SR:.1f}s at {pos/SR:.1f}s")

    # Place SFX in narration
    narration_with_sfx = place_sfx(narration, sfx_clips, sfx_pos_samples, sfx_vol=0.45)

    # Load and prepare music
    print(f"  Loading music: {os.path.basename(MUSIC_TRACK)}")
    music = load_and_resample(MUSIC_TRACK, SR)
    music = loop_to_length(music, len(narration_with_sfx) + SR)
    music = fade_in_out(music)

    # Side-chain duck the music
    env = rms_envelope(narration_with_sfx)
    music_ducked = duck_track(music, env, duck_depth=0.65, base_vol=0.12)

    # Mix
    final = narration_with_sfx + music_ducked[:len(narration_with_sfx)]
    final = soft_clip(final)

    out_path = os.path.join(OUT_DIR, "method1_all_local.wav")
    sf.write(out_path, final, SR)
    duration = len(final) / SR
    print(f"  -> {out_path} ({duration:.1f}s, {os.path.getsize(out_path)//1024}KB)")
    return out_path


# === METHOD 2: HYBRID (Qwen3 VoiceDesign + library music + ElevenLabs SFX) ===

def generate_qwen3_tts(segments, out_subdir):
    """Generate TTS using Qwen3-TTS VoiceDesign (local)."""
    from mlx_audio.tts import load_model
    from mlx_audio.tts.generate import generate_audio

    MODEL_PATH = os.path.join(HERE, "models", "qwen3_voicedesign_8bit")
    print(f"  Loading Qwen3-TTS VoiceDesign from {MODEL_PATH}...")
    model = load_model(MODEL_PATH)

    results = []
    for i, seg in enumerate(segments):
        if seg.kind == "sfx":
            results.append((seg, None))
            continue

        voice_desc = QWEN3_VOICES.get(seg.speaker, QWEN3_VOICES["narrator"])
        print(f"  [{i+1}/{len(segments)}] {seg.kind:8s} {seg.speaker:8s}  text={seg.text[:60]}...")

        # Generate with voice description (instruct parameter)
        prefix = f"seg_{i:03d}"
        try:
            generate_audio(
                text=seg.text,
                model=model,
                instruct=voice_desc,
                lang_code="en",
                max_tokens=2400,
                output_path=out_subdir,
                file_prefix=prefix,
                audio_format="wav",
            )
            # Find the generated file (may have _000 suffix)
            generated = None
            for f in os.listdir(out_subdir):
                if f.startswith(prefix) and f.endswith(".wav"):
                    generated = os.path.join(out_subdir, f)
                    break
            if generated:
                audio, sr = sf.read(generated, dtype="float32")
                if sr != SR:
                    audio = signal.resample(audio, int(len(audio) * SR / sr))
                if len(audio.shape) > 1:
                    audio = audio.mean(axis=1)
                results.append((seg, audio.astype("float32")))
                print(f"    -> {len(audio)/SR:.1f}s")
            else:
                print(f"    -> FAILED, using silence")
                results.append((seg, np.zeros(SR, dtype="float32")))
        except Exception as e:
            print(f"    -> ERROR: {e}")
            results.append((seg, np.zeros(SR, dtype="float32")))

    return results


def generate_elevenlabs_sfx(sfx_key, prompt, duration, api_key):
    """Generate a sound effect using ElevenLabs SFX API."""
    url = "https://api.elevenlabs.io/v1/sound-generation"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": prompt,
        "duration_seconds": duration,
        "prompt_influence": 0.5,
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={**headers, "User-Agent": "Mozilla/5.0 Python/3.12"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_data = resp.read()
            # Save to temp file and load with soundfile
            tmp_path = os.path.join(SFX_DIR, f"elevenlabs_{sfx_key}.mp3")
            with open(tmp_path, "wb") as f:
                f.write(audio_data)
            audio, sr = sf.read(tmp_path, dtype="float32")
            if sr != SR:
                audio = signal.resample(audio, int(len(audio) * SR / sr))
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)
            print(f"    ElevenLabs SFX '{sfx_key}': {len(audio)/SR:.1f}s")
            return audio.astype("float32")
    except urllib.error.HTTPError as e:
        print(f"    ElevenLabs SFX ERROR for '{sfx_key}': {e.code} {e.reason}")
        body = e.read().decode()[:200]
        print(f"    Response: {body}")
        return None
    except Exception as e:
        print(f"    ElevenLabs SFX ERROR for '{sfx_key}': {e}")
        return None


def run_method2(segments, elevenlabs_key=None):
    """Method 2: Hybrid (Qwen3 VoiceDesign + library music + ElevenLabs SFX)."""
    print("\n=== METHOD 2: Hybrid (Qwen3 VoiceDesign + library music + ElevenLabs SFX) ===")
    out_subdir = os.path.join(OUT_DIR, "method2_segments")
    os.makedirs(out_subdir, exist_ok=True)
    os.makedirs(SFX_DIR, exist_ok=True)

    # Generate TTS with Qwen3
    tts_results = generate_qwen3_tts(segments, out_subdir)

    # Build narration track + track SFX positions
    tts_audio_list = [a for _, a in tts_results if a is not None]
    narration = concatenate_audio(tts_audio_list, gaps=0.3)

    # Track SFX positions
    sfx_positions = []
    current_pos = 0
    gap_samples = int(0.3 * SR)
    for seg, audio in tts_results:
        if seg.kind == "sfx":
            sfx_positions.append((seg.sfx_key, current_pos))
            current_pos += int(0.5 * SR)
        elif audio is not None:
            current_pos += len(audio) + gap_samples

    # Generate SFX
    sfx_clips = []
    sfx_pos_samples = []
    print("  Generating SFX...")
    for sfx_key, pos in sfx_positions:
        sfx_def = SFX_DEFS[sfx_key]
        clip = None
        if elevenlabs_key:
            clip = generate_elevenlabs_sfx(sfx_key, sfx_def["prompt"], sfx_def["duration"], elevenlabs_key)
        if clip is None:
            print(f"    Falling back to synthesized SFX for '{sfx_key}'")
            clip = synthesize_sfx(sfx_key, sfx_def["duration"])
        sfx_clips.append(clip)
        sfx_pos_samples.append(pos)

    # Place SFX
    narration_with_sfx = place_sfx(narration, sfx_clips, sfx_pos_samples, sfx_vol=0.5)

    # Music
    print(f"  Loading music: {os.path.basename(MUSIC_TRACK)}")
    music = load_and_resample(MUSIC_TRACK, SR)
    music = loop_to_length(music, len(narration_with_sfx) + SR)
    music = fade_in_out(music)

    env = rms_envelope(narration_with_sfx)
    music_ducked = duck_track(music, env, duck_depth=0.65, base_vol=0.12)

    final = narration_with_sfx + music_ducked[:len(narration_with_sfx)]
    final = soft_clip(final)

    out_path = os.path.join(OUT_DIR, "method2_hybrid.wav")
    sf.write(out_path, final, SR)
    duration = len(final) / SR
    print(f"  -> {out_path} ({duration:.1f}s, {os.path.getsize(out_path)//1024}KB)")
    return out_path


# === METHOD 3: ALL-ELEVENLABS (TTS + Music + SFX) ===

def generate_elevenlabs_tts(text, voice_id, api_key, stability=0.5, clarity=0.75):
    """Generate TTS using ElevenLabs API."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": stability, "similarity_boost": clarity, "style": 0.3},
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={**headers, "User-Agent": "Mozilla/5.0 Python/3.12"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_data = resp.read()
            tmp_path = os.path.join(SFX_DIR, f"tts_{int(time.time()*1000)}.mp3")
            with open(tmp_path, "wb") as f:
                f.write(audio_data)
            audio, sr = sf.read(tmp_path, dtype="float32")
            if sr != SR:
                audio = signal.resample(audio, int(len(audio) * SR / sr))
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)
            os.unlink(tmp_path)
            return audio.astype("float32")
    except Exception as e:
        print(f"    ElevenLabs TTS ERROR: {e}")
        return None


def list_elevenlabs_voices(api_key):
    """List available ElevenLabs voices."""
    url = "https://api.elevenlabs.io/v1/voices"
    req = urllib.request.Request(url, headers={"xi-api-key": api_key, "User-Agent": "Mozilla/5.0 Python/3.12"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            for v in data.get("voices", []):
                print(f"    {v['voice_id']}  {v['name']:30s}  {v.get('labels',{}).get('gender','?'):6s}  {v.get('labels',{}).get('description','')}")
            return data.get("voices", [])
    except Exception as e:
        print(f"    Error listing voices: {e}")
        return []


def run_method3(segments, elevenlabs_key):
    """Method 3: All-ElevenLabs (TTS + SFX, music from library since Music API is more complex)."""
    print("\n=== METHOD 3: All-ElevenLabs (TTS + SFX via API, library music) ===")
    out_subdir = os.path.join(OUT_DIR, "method3_segments")
    os.makedirs(out_subdir, exist_ok=True)
    os.makedirs(SFX_DIR, exist_ok=True)

    # List available voices and let user pick, or use defaults
    print("  Available ElevenLabs voices:")
    voices = list_elevenlabs_voices(elevenlabs_key)

    # Hand-picked premade voices for our characters:
    # Narrator: George - Warm, Captivating Storyteller (British male)
    # Kael: Harry - Fierce Warrior (American male)
    # Lyra: Jessica - Playful, Bright, Warm (American female)
    ELEVENLABS_VOICE_MAP = {
        "narrator": "JBFqnCBsd6RMkjVDRZzb",  # George
        "Kael": "SOYHLrjzK2X1ezoPC6cr",      # Harry
        "Lyra": "cgSgspJ2msm6clMCkdW9",      # Jessica
    }
    # Also map Groq-generated character names (Garrick, Lira) to the same voices
    ELEVENLABS_VOICE_MAP["Garrick"] = ELEVENLABS_VOICE_MAP["Kael"]
    ELEVENLABS_VOICE_MAP["Lira"] = ELEVENLABS_VOICE_MAP["Lyra"]

    # Fallbacks: use first male voice for Kael, first female for Lyra, first overall for narrator
    if "narrator" not in ELEVENLABS_VOICE_MAP and voices:
        ELEVENLABS_VOICE_MAP["narrator"] = voices[0]["voice_id"]
    if "Kael" not in ELEVENLABS_VOICE_MAP:
        for v in voices:
            if v.get("labels", {}).get("gender", "").lower() == "male":
                ELEVENLABS_VOICE_MAP["Kael"] = v["voice_id"]
                break
    if "Lyra" not in ELEVENLABS_VOICE_MAP:
        for v in voices:
            if v.get("labels", {}).get("gender", "").lower() == "female":
                ELEVENLABS_VOICE_MAP["Lyra"] = v["voice_id"]
                break

    print(f"  Voice assignments: {ELEVENLABS_VOICE_MAP}")

    # Generate TTS
    tts_results = []
    for i, seg in enumerate(segments):
        if seg.kind == "sfx":
            tts_results.append((seg, None))
            continue

        voice_id = ELEVENLABS_VOICE_MAP.get(seg.speaker, ELEVENLABS_VOICE_MAP.get("narrator"))
        print(f"  [{i+1}/{len(segments)}] {seg.kind:8s} {seg.speaker:8s}  text={seg.text[:60]}...")
        audio = generate_elevenlabs_tts(seg.text, voice_id, elevenlabs_key)
        if audio is None:
            audio = np.zeros(SR, dtype="float32")
        tts_results.append((seg, audio))
        print(f"    -> {len(audio)/SR:.1f}s")

    # Build narration
    tts_audio_list = [a for _, a in tts_results if a is not None]
    narration = concatenate_audio(tts_audio_list, gaps=0.3)

    # SFX positions
    sfx_positions = []
    current_pos = 0
    gap_samples = int(0.3 * SR)
    for seg, audio in tts_results:
        if seg.kind == "sfx":
            sfx_positions.append((seg.sfx_key, current_pos))
            current_pos += int(0.5 * SR)
        elif audio is not None:
            current_pos += len(audio) + gap_samples

    # Generate SFX via ElevenLabs
    sfx_clips = []
    sfx_pos_samples = []
    print("  Generating SFX via ElevenLabs...")
    for sfx_key, pos in sfx_positions:
        sfx_def = SFX_DEFS[sfx_key]
        clip = generate_elevenlabs_sfx(sfx_key, sfx_def["prompt"], sfx_def["duration"], elevenlabs_key)
        if clip is None:
            clip = synthesize_sfx(sfx_key, sfx_def["duration"])
        sfx_clips.append(clip)
        sfx_pos_samples.append(pos)

    narration_with_sfx = place_sfx(narration, sfx_clips, sfx_pos_samples, sfx_vol=0.5)

    # Music (library track — using ElevenLabs Music API would be a separate step)
    print(f"  Loading music: {os.path.basename(MUSIC_TRACK)}")
    music = load_and_resample(MUSIC_TRACK, SR)
    music = loop_to_length(music, len(narration_with_sfx) + SR)
    music = fade_in_out(music)

    env = rms_envelope(narration_with_sfx)
    music_ducked = duck_track(music, env, duck_depth=0.65, base_vol=0.12)

    final = narration_with_sfx + music_ducked[:len(narration_with_sfx)]
    final = soft_clip(final)

    out_path = os.path.join(OUT_DIR, "method3_all_eleven.wav")
    sf.write(out_path, final, SR)
    duration = len(final) / SR
    print(f"  -> {out_path} ({duration:.1f}s, {os.path.getsize(out_path)//1024}KB)")
    return out_path


# === METHOD 4: GROQ DM BRAIN (Groq generates scene → Kokoro TTS + library music + ElevenLabs SFX) ===

def groq_generate_scene(api_key):
    """Use Groq to generate a new epic D&D scene with narrator + 2 characters + SFX markers."""
    import urllib.request

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    system_prompt = """You are a D&D DM. Write a 200-word epic scene with narrator + 2 characters (a veteran warrior and a young mage).

Format rules:
- Narrator text: plain paragraphs
- Dialogue: [CharacterName] "text"
- SFX: [SFX: key] on its own line
Include 4 SFX: environmental, combat, magical, and one surprise."""

    payload = {
        "model": "groq/compound",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Generate an epic dungeon exploration scene with combat and magic."},
        ],
        "temperature": 0.8,
        "max_tokens": 4000,
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={**headers, "User-Agent": "Mozilla/5.0 Python/3.12"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            scene_text = data["choices"][0]["message"]["content"]
            print(f"  Groq generated scene ({len(scene_text)} chars)")
            return scene_text
    except Exception as e:
        print(f"  Groq ERROR: {e}")
        return None


def run_method4(segments, groq_key, elevenlabs_key=None):
    """Method 4: Groq DM brain generates a NEW scene → Kokoro TTS + library music + ElevenLabs SFX."""
    print("\n=== METHOD 4: Groq DM brain → Kokoro TTS + library music + ElevenLabs SFX ===")

    # Step 1: Generate a new scene with Groq
    print("  Step 1: Generating scene with Groq (GPT-OSS 120B)...")
    scene_text = groq_generate_scene(groq_key)
    if not scene_text:
        print("  Failed to generate scene with Groq, skipping method 4")
        return None

    # Save the generated scene
    scene_path = os.path.join(OUT_DIR, "method4_groq_scene.txt")
    with open(scene_path, "w") as f:
        f.write(scene_text)
    print(f"  Saved generated scene to {scene_path}")

    # Parse the Groq-generated scene
    groq_segments = parse_scene(scene_text)
    print(f"  Parsed: {len(groq_segments)} segments")
    for i, s in enumerate(groq_segments):
        kind = s.kind
        detail = s.speaker if kind == "dialogue" else (s.sfx_key if kind == "sfx" else s.text[:50])
        print(f"    {i:2d} [{kind:8s}] {detail}")

    # Detect character names and SFX keys from the generated scene
    # Map any character names to Kokoro voices
    char_names = set()
    for seg in groq_segments:
        if seg.kind == "dialogue":
            char_names.add(seg.speaker)

    # Detect which character is male (warrior) vs female (mage) by checking
    # pronouns in the scene text near each character name
    scene_lower = scene_text.lower()
    voice_assignments = dict(KOKORO_VOICES)  # start with defaults

    for name in sorted(char_names):
        name_lower = name.lower()
        # Gather all context windows around this name
        name_context = ""
        idx = scene_lower.find(name_lower)
        while idx >= 0:
            name_context += scene_lower[max(0,idx-150):idx+150] + " "
            idx = scene_lower.find(name_lower, idx + 1)

        # Check for female pronouns near the name
        has_female = any(p in name_context for p in [" she ", " her ", " hers ", " she'd", " she'll"])
        # Check for male pronouns near the name
        has_male = any(p in name_context for p in [" he ", " his ", " him ", " he'd", " he'll"])
        # Known name lists
        known_male = name_lower in ("kael", "garrick", "thorne", "thrain", "grimgold", "elic")
        known_female = name_lower in ("lyra", "lira", "arin", "eira", "elian")

        if known_female or (has_female and not has_male and not known_male):
            voice_assignments[name] = "af_sky"   # bright young female
        elif known_male or (has_male and not has_female):
            voice_assignments[name] = "am_onyx"  # deep male veteran
        else:
            # Fallback: assign first unassigned to male, second to female
            if not any(v == "am_onyx" for k, v in voice_assignments.items() if k in char_names):
                voice_assignments[name] = "am_onyx"
            else:
                voice_assignments[name] = "af_sky"

    # Update the global KOKORO_VOICES for this run
    original_voices = dict(KOKORO_VOICES)
    KOKORO_VOICES.update(voice_assignments)

    # Detect SFX keys and create definitions for any new ones
    for seg in groq_segments:
        if seg.kind == "sfx" and seg.sfx_key not in SFX_DEFS:
            # Create a default SFX definition for unknown keys
            SFX_DEFS[seg.sfx_key] = {
                "prompt": seg.sfx_key.replace("_", " "),
                "duration": 3.0,
            }

    # Step 2: Generate TTS with Kokoro
    print("  Step 2: Generating TTS with Kokoro...")
    out_subdir = os.path.join(OUT_DIR, "method4_segments")
    os.makedirs(out_subdir, exist_ok=True)
    tts_results = generate_kokoro_tts(groq_segments, out_subdir)

    # Restore original voice assignments
    KOKORO_VOICES.clear()
    KOKORO_VOICES.update(original_voices)

    # Build narration
    tts_audio_list = [a for _, a in tts_results if a is not None]
    narration = concatenate_audio(tts_audio_list, gaps=0.3)

    # SFX positions
    sfx_positions = []
    current_pos = 0
    gap_samples = int(0.3 * SR)
    for seg, audio in tts_results:
        if seg.kind == "sfx":
            sfx_positions.append((seg.sfx_key, current_pos))
            current_pos += int(0.5 * SR)
        elif audio is not None:
            current_pos += len(audio) + gap_samples

    # Generate SFX
    sfx_clips = []
    sfx_pos_samples = []
    print("  Step 3: Generating SFX...")
    for sfx_key, pos in sfx_positions:
        sfx_def = SFX_DEFS[sfx_key]
        clip = None
        if elevenlabs_key:
            clip = generate_elevenlabs_sfx(sfx_key, sfx_def["prompt"], sfx_def["duration"], elevenlabs_key)
        if clip is None:
            clip = synthesize_sfx(sfx_key, sfx_def["duration"])
        sfx_clips.append(clip)
        sfx_pos_samples.append(pos)

    narration_with_sfx = place_sfx(narration, sfx_clips, sfx_pos_samples, sfx_vol=0.45)

    # Music
    print(f"  Step 4: Loading music: {os.path.basename(MUSIC_TRACK)}")
    music = load_and_resample(MUSIC_TRACK, SR)
    music = loop_to_length(music, len(narration_with_sfx) + SR)
    music = fade_in_out(music)

    env = rms_envelope(narration_with_sfx)
    music_ducked = duck_track(music, env, duck_depth=0.65, base_vol=0.12)

    final = narration_with_sfx + music_ducked[:len(narration_with_sfx)]
    final = soft_clip(final)

    out_path = os.path.join(OUT_DIR, "method4_groq_dm.wav")
    sf.write(out_path, final, SR)
    duration = len(final) / SR
    print(f"  -> {out_path} ({duration:.1f}s, {os.path.getsize(out_path)//1024}KB)")
    return out_path


# === MAIN ===

def main():
    parser = argparse.ArgumentParser(description="Produce epic scene with multiple methods")
    parser.add_argument("--method", default="1", help="Method number (1-4) or 'all'")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SFX_DIR, exist_ok=True)

    # Load API keys
    env_path = os.path.join(HERE, ".env")
    elevenlabs_key = None
    groq_key = None
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("ELEVENLABS_API_KEY="):
                    elevenlabs_key = line.split("=", 1)[1]
                elif line.startswith("GROQ_API_KEY="):
                    groq_key = line.split("=", 1)[1]

    # Parse scene
    print("Parsing scene...")
    scene_text = open(SCENE_FILE).read()
    segments = parse_scene(scene_text)
    print(f"  {len(segments)} segments")
    for i, s in enumerate(segments):
        kind = s.kind
        detail = s.speaker if kind == "dialogue" else (s.sfx_key if kind == "sfx" else s.text[:50])
        print(f"  {i:2d} [{kind:8s}] {detail}")

    results = {}
    method = args.method

    if method in ("1", "all"):
        try:
            results["method1"] = run_method1(segments)
        except Exception as e:
            print(f"  Method 1 FAILED: {e}")
            import traceback; traceback.print_exc()

    if method in ("2", "all"):
        if not elevenlabs_key:
            print("\n  Method 2 needs ELEVENLABS_API_KEY in .env — will use synthesized SFX fallback")
        try:
            results["method2"] = run_method2(segments, elevenlabs_key)
        except Exception as e:
            print(f"  Method 2 FAILED: {e}")
            import traceback; traceback.print_exc()

    if method in ("3", "all"):
        if not elevenlabs_key:
            print("\n  Method 3 SKIPPED — needs ELEVENLABS_API_KEY in .env")
        else:
            try:
                results["method3"] = run_method3(segments, elevenlabs_key)
            except Exception as e:
                print(f"  Method 3 FAILED: {e}")
                import traceback; traceback.print_exc()

    if method in ("4", "all"):
        if not groq_key:
            print("\n  Method 4 SKIPPED — needs GROQ_API_KEY in .env")
        else:
            try:
                results["method4"] = run_method4(segments, groq_key, elevenlabs_key)
            except Exception as e:
                print(f"  Method 4 FAILED: {e}")
                import traceback; traceback.print_exc()

    print("\n=== RESULTS ===")
    for name, path in results.items():
        if path and os.path.exists(path):
            print(f"  {name}: {path} ({os.path.getsize(path)//1024}KB)")
        else:
            print(f"  {name}: FAILED")


if __name__ == "__main__":
    main()
