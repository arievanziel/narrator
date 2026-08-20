#!/usr/bin/env python3
"""
Method 4 variant: Groq DM brain + hybrid TTS (Qwen3 narrator + Kokoro characters)
+ ElevenLabs SFX + library music.

Generates two scenes with very different vibes:
  5. Horror/suspense — creeping dread, something hunting in the dark
  6. Triumphant/heroic — last stand, rallying speech, victory against odds

TTS split:
  - Narrator segments → Qwen3-TTS VoiceDesign (natural-language voice description,
    more expressive for narration)
  - Character dialogue → Kokoro (fixed voices, consistent character voices)

Usage:
  .venv/bin/python produce_method4_variants.py
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional

import numpy as np
import soundfile as sf
from scipy import signal

# --- paths ---
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "outputs", "epic_scene")
TRACKS_DIR = os.path.join(HERE, "outputs", "ambience_demo", "tracks")
SFX_DIR = os.path.join(OUT_DIR, "sfx")
SR = 24000

# Music tracks for different vibes
MUSIC_HORROR = os.path.join(TRACKS_DIR, "dungeon_ambient.ogg")       # CC0, low wind + drips — perfect for horror
MUSIC_HEROIC = os.path.join(TRACKS_DIR, "tavern_old_tower_inn.mp3")  # CC0, medieval inn — upbeat, heroic

# Kokoro voices for characters (fixed, consistent)
KOKORO_CHAR_VOICES = {
    # Will be assigned dynamically based on detected gender
    "male": "am_onyx",    # deep, veteran
    "female": "af_sky",   # bright, young
    "male_alt": "am_adam",  # alternative male
    "female_alt": "af_nicole",  # alternative female
}

# Qwen3 voice description for narrator (varies per scene vibe)
QWEN3_NARRATOR_HORROR = (
    "A dark, atmospheric narrator with a low, hushed voice that builds tension. "
    "Speaks slowly with deliberate pauses, as if afraid of what might be listening. "
    "Every word carries weight and dread."
)
QWEN3_NARRATOR_HEROIC = (
    "An epic storyteller with a powerful, resonant voice full of passion and triumph. "
    "Speaks with rising energy and heroic cadence, like a bard recounting a legendary battle. "
    "Bold, stirring, and triumphant."
)

# --- Scene prompts for Groq ---
SCENE_PROMPTS = [
    {
        "id": "method4_horror",
        "name": "method4_horror.wav",
        "scene_file": "method4_horror_scene.txt",
        "music": MUSIC_HORROR,
        "narrator_voice": QWEN3_NARRATOR_HORROR,
        "music_vol": 0.08,  # quieter for horror — more atmospheric
        "duck_depth": 0.70,
        "groq_system": (
            "You are a D&D DM writing a HORROR/SUSPENSE scene. Write a 250-word scene "
            "with narrator + 2 characters exploring a dark place where something is "
            "hunting them. Build creeping dread. Include whispers, things moving in "
            "the dark, a moment of pure terror.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 4 SFX: something creeping, a whisper/breath, a sudden terror moment, "
            "and one surprise. Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a horror scene where two adventurers (one male veteran, one female scholar) "
            "are trapped in a flooded catacomb with something that moves in the water. "
            "The water is rising. They can hear it breathing."
        ),
    },
    {
        "id": "method4_heroic",
        "name": "method4_heroic.wav",
        "scene_file": "method4_heroic_scene.txt",
        "music": MUSIC_HEROIC,
        "narrator_voice": QWEN3_NARRATOR_HEROIC,
        "music_vol": 0.14,  # louder for heroic — more energy
        "duck_depth": 0.60,
        "groq_system": (
            "You are a D&D DM writing a TRIUMPHANT/HEROIC scene. Write a 250-word scene "
            "with narrator + 2 characters in a last-stand battle against overwhelming odds. "
            "Include a rallying speech, a moment of sacrifice, and a hard-won victory. "
            "Epic, stirring, heroic.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 4 SFX: a war horn/trumpet, shield wall impact, a heroic spell/weapon "
            "strike, and a victory cheer. Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a heroic last-stand scene where two warriors (one male commander, "
            "one female paladin) hold a bridge against an advancing army. They're "
            "outnumbered 100 to 1. The commander gives a rallying speech. They win, "
            "but barely."
        ),
    },
]


# === SCENE PARSER (same as produce_epic_scene.py) ===

@dataclass
class SceneSegment:
    kind: str  # "narrator", "dialogue", "sfx"
    speaker: str = ""
    text: str = ""
    sfx_key: str = ""


def parse_scene(text: str) -> list[SceneSegment]:
    segments = []
    lines = text.strip().split("\n")
    buffer = []
    i = 0

    def flush_buffer():
        if buffer:
            joined = " ".join(buffer).strip()
            if joined:
                segments.append(SceneSegment(kind="narrator", speaker="narrator", text=joined))
            buffer.clear()

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            flush_buffer()
            i += 1
            continue

        sfx_match = re.match(r'^\[\s*SFX:\s*([\w\s]+?)\s*\]', line)
        if sfx_match:
            flush_buffer()
            sfx_key = sfx_match.group(1).strip().replace(" ", "_").strip("_")
            segments.append(SceneSegment(kind="sfx", sfx_key=sfx_key))
            i += 1
            continue

        char_match = re.match(r'^\[(\w+)\]\s*(.*)', line)
        if not char_match:
            char_match = re.match(r'^(\w+)\s+["\u201c](.*)["\u201d]\s*$', line)

        if char_match:
            flush_buffer()
            speaker = char_match.group(1)
            dialogue = char_match.group(2).strip()
            has_open_quote = dialogue.startswith('"') or dialogue.startswith('\u201c')
            has_close_quote = dialogue.endswith('"') or dialogue.endswith('\u201d')
            if has_open_quote and not has_close_quote:
                while i + 1 < len(lines):
                    i += 1
                    next_line = lines[i].strip()
                    dialogue += " " + next_line
                    if next_line.endswith('"') or next_line.endswith('\u201d'):
                        break
            # Extract just the quoted dialogue — anything after the closing quote
            # is narration that should be a separate segment
            remaining_narration = ""
            if has_open_quote:
                # Find the closing quote position
                quote_match = re.match(r'^["\u201c](.*?)["\u201d](.*)', dialogue, re.DOTALL)
                if quote_match:
                    remaining_narration = quote_match.group(2).strip()
                    dialogue = quote_match.group(1)
                else:
                    dialogue = re.sub(r'^["\u201c](.*)["\u201d]$', r'\1', dialogue)
            else:
                dialogue = re.sub(r'^["\u201c](.*)["\u201d]$', r'\1', dialogue)

            # Check for inline SFX in the remaining narration
            if remaining_narration:
                # Split on SFX markers
                sfx_parts = re.split(r'\[\s*SFX:\s*([\w\s]+?)\s*\]', remaining_narration)
                for j, part in enumerate(sfx_parts):
                    part = part.strip()
                    if j % 2 == 1:  # odd indices are SFX keys
                        sfx_key = part.strip().replace(" ", "_").strip("_")
                        segments.append(SceneSegment(kind="sfx", sfx_key=sfx_key))
                    elif part:
                        segments.append(SceneSegment(kind="narrator", speaker="narrator", text=part))

            segments.append(SceneSegment(kind="dialogue", speaker=speaker, text=dialogue))
            i += 1
            continue

        buffer.append(line)
        i += 1

    flush_buffer()
    return segments


# === AUDIO UTILITIES (same as produce_epic_scene.py) ===

def load_and_resample(path, target_sr=SR):
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = audio[:, 0]
    if sr != target_sr:
        audio = signal.resample(audio, int(len(audio) * target_sr / sr))
    return audio.astype("float32")


def rms_envelope(x, frame=512, hop=128):
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
    gain = base_vol * (1.0 - duck_depth * narration_env)
    g = np.ones(len(track)) * base_vol
    m = min(len(g), len(gain))
    g[:m] = gain[:m]
    return track * g


def loop_to_length(audio, target_len):
    if len(audio) >= target_len:
        return audio[:target_len]
    result = np.copy(audio)
    while len(result) < target_len:
        result = np.concatenate([result, audio])
    return result[:target_len]


def fade_in_out(audio, fade_samples=None):
    if fade_samples is None:
        fade_samples = min(SR, len(audio) // 4)
    if fade_samples > len(audio) // 2:
        fade_samples = len(audio) // 4
    audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
    audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    return audio


def concatenate_audio(segments_audio, gaps=0.3):
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
    result = np.copy(narration_audio)
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
    return np.tanh(audio * 0.9).astype("float32")


# === GROQ SCENE GENERATION ===

def groq_generate_scene(api_key, system_prompt, user_prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({
        "model": "groq/compound",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.85,
        "max_tokens": 2000,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={**headers, "User-Agent": "Mozilla/5.0 Python/3.12"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
            scene_text = data["choices"][0]["message"]["content"]
            print(f"  Groq generated scene ({len(scene_text)} chars)")
            return scene_text
    except Exception as e:
        print(f"  Groq ERROR: {e}")
        return None


# === ELEVENLABS SFX ===

def generate_elevenlabs_sfx(sfx_key, prompt, duration, api_key):
    # Check cache first
    cache_path = os.path.join(SFX_DIR, f"elevenlabs_{sfx_key}.mp3")
    if os.path.exists(cache_path):
        audio, sr = sf.read(cache_path, dtype="float32")
        if sr != SR:
            audio = signal.resample(audio, int(len(audio) * SR / sr))
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        print(f"    SFX '{sfx_key}': cached ({len(audio)/SR:.1f}s)")
        return audio.astype("float32")

    url = "https://api.elevenlabs.io/v1/sound-generation"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = json.dumps({
        "text": prompt,
        "duration_seconds": duration,
        "prompt_influence": 0.5,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={**headers, "User-Agent": "Mozilla/5.0 Python/3.12"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            audio_data = resp.read()
            with open(cache_path, "wb") as f:
                f.write(audio_data)
            audio, sr = sf.read(cache_path, dtype="float32")
            if sr != SR:
                audio = signal.resample(audio, int(len(audio) * SR / sr))
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)
            print(f"    ElevenLabs SFX '{sfx_key}': {len(audio)/SR:.1f}s")
            return audio.astype("float32")
    except Exception as e:
        print(f"    ElevenLabs SFX ERROR for '{sfx_key}': {e}")
        return None


def synthesize_sfx(sfx_key, duration):
    """Procedural fallback."""
    n = int(SR * duration)
    t = np.arange(n) / SR
    return (np.random.randn(n) * 0.3 * np.exp(-t * 2)).astype("float32")


# === HYBRID TTS: Qwen3 narrator + Kokoro characters ===

def generate_hybrid_tts(segments, narrator_voice_desc, out_subdir, elevenlabs_key):
    """
    Generate TTS with:
    - Qwen3 VoiceDesign for narrator segments (expressive, natural-language voice)
    - Kokoro for character dialogue (fixed, consistent character voices)
    """
    import torch
    from kokoro import KPipeline
    from mlx_audio.tts import load_model
    from mlx_audio.tts.generate import generate_audio as mlx_generate

    # Load Kokoro (for character voices)
    print("  Loading Kokoro pipeline (for character voices)...")
    kokoro_pipeline = KPipeline(lang_code="a")

    # Load Qwen3 (for narrator)
    MODEL_PATH = os.path.join(HERE, "models", "qwen3_voicedesign_8bit")
    print(f"  Loading Qwen3-TTS VoiceDesign (for narrator) from {MODEL_PATH}...")
    qwen_model = load_model(MODEL_PATH)

    # Detect character names and assign Kokoro voices by gender
    char_names = set()
    for seg in segments:
        if seg.kind == "dialogue":
            char_names.add(seg.speaker)

    char_voice_map = {}
    male_assigned = False
    female_assigned = False
    # We'll detect gender from the scene text as we process it
    # For now, assign based on order + known names
    for name in sorted(char_names):
        name_lower = name.lower()
        known_male = name_lower in ("kael", "garrick", "thorne", "thrain", "grimgold", "elic", "commander")
        known_female = name_lower in ("lyra", "lira", "arin", "eira", "elian", "paladin", "scholar")
        if known_male or (not male_assigned and not known_female):
            char_voice_map[name] = KOKORO_CHAR_VOICES["male"]
            male_assigned = True
        elif known_female or (not female_assigned):
            char_voice_map[name] = KOKORO_CHAR_VOICES["female"]
            female_assigned = True
        else:
            char_voice_map[name] = KOKORO_CHAR_VOICES["male_alt"] if male_assigned else KOKORO_CHAR_VOICES["female"]

    print(f"  Character voice assignments: {char_voice_map}")

    os.makedirs(out_subdir, exist_ok=True)
    results = []

    for i, seg in enumerate(segments):
        if seg.kind == "sfx":
            results.append((seg, None))
            continue

        if seg.kind == "narrator":
            # --- Qwen3 VoiceDesign for narrator ---
            print(f"  [{i+1}/{len(segments)}] NARRATOR (Qwen3)  text={seg.text[:60]}...")
            prefix = f"narr_{i:03d}"
            try:
                mlx_generate(
                    text=seg.text,
                    model=qwen_model,
                    instruct=narrator_voice_desc,
                    lang_code="en",
                    max_tokens=2400,
                    output_path=out_subdir,
                    file_prefix=prefix,
                    audio_format="wav",
                )
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
                    print(f"    -> {len(audio)/SR:.1f}s (Qwen3)")
                else:
                    print(f"    -> FAILED, using silence")
                    results.append((seg, np.zeros(SR, dtype="float32")))
            except Exception as e:
                print(f"    -> Qwen3 ERROR: {e}")
                results.append((seg, np.zeros(SR, dtype="float32")))

        elif seg.kind == "dialogue":
            # --- Kokoro for character dialogue ---
            voice = char_voice_map.get(seg.speaker, KOKORO_CHAR_VOICES["male"])
            print(f"  [{i+1}/{len(segments)}] DIALOGUE  {seg.speaker:10s} voice={voice}  text={seg.text[:60]}...")
            try:
                ps, tokens = kokoro_pipeline.g2p(seg.text)
                chunks = []
                for result in kokoro_pipeline.generate_from_tokens(tokens=tokens, voice=voice):
                    chunks.append(result.audio)
                if chunks:
                    audio = torch.cat(chunks).cpu().numpy().astype("float32")
                else:
                    audio = np.zeros(SR, dtype="float32")
                results.append((seg, audio))
                print(f"    -> {len(audio)/SR:.1f}s (Kokoro)")
            except Exception as e:
                print(f"    -> Kokoro ERROR: {e}")
                results.append((seg, np.zeros(SR, dtype="float32")))

    return results


# === MAIN PIPELINE ===

def run_scene(scene_config, groq_key, elevenlabs_key):
    """Run a single scene through the full pipeline."""
    print(f"\n{'='*60}")
    print(f"=== {scene_config['id'].upper()} ===")
    print(f"{'='*60}")

    # Step 1: Generate scene with Groq
    print("\n  Step 1: Generating scene with Groq...")
    scene_text = groq_generate_scene(groq_key, scene_config["groq_system"], scene_config["groq_user"])
    if not scene_text:
        print("  FAILED to generate scene")
        return None

    scene_path = os.path.join(OUT_DIR, scene_config["scene_file"])
    with open(scene_path, "w") as f:
        f.write(scene_text)
    print(f"  Saved to {scene_path}")

    # Parse scene
    segments = parse_scene(scene_text)
    print(f"  Parsed: {len(segments)} segments")
    for i, s in enumerate(segments):
        if s.kind == "sfx":
            print(f"    {i:2d} [SFX     ] {s.sfx_key}")
        elif s.kind == "dialogue":
            print(f"    {i:2d} [{s.speaker:10s}] {s.text[:60]}")
        else:
            print(f"    {i:2d} [NARRATOR ] {s.text[:60]}")

    # Step 2: Generate hybrid TTS (Qwen3 narrator + Kokoro characters)
    print(f"\n  Step 2: Generating hybrid TTS...")
    out_subdir = os.path.join(OUT_DIR, f"{scene_config['id']}_segments")
    tts_results = generate_hybrid_tts(segments, scene_config["narrator_voice"], out_subdir, elevenlabs_key)

    # Build narration track
    tts_audio_list = [a for _, a in tts_results if a is not None]
    narration = concatenate_audio(tts_audio_list, gaps=0.4)

    # Track SFX positions
    sfx_positions = []
    current_pos = 0
    gap_samples = int(0.4 * SR)
    for seg, audio in tts_results:
        if seg.kind == "sfx":
            sfx_positions.append((seg.sfx_key, current_pos))
            current_pos += int(0.5 * SR)
        elif audio is not None:
            current_pos += len(audio) + gap_samples

    # Step 3: Generate SFX via ElevenLabs
    print(f"\n  Step 3: Generating SFX via ElevenLabs...")
    sfx_clips = []
    sfx_pos_samples = []
    for sfx_key, pos in sfx_positions:
        prompt = sfx_key.replace("_", " ") + ", dramatic, cinematic, high quality"
        clip = generate_elevenlabs_sfx(sfx_key, prompt, 3.0, elevenlabs_key)
        if clip is None:
            clip = synthesize_sfx(sfx_key, 3.0)
        sfx_clips.append(clip)
        sfx_pos_samples.append(pos)

    # Place SFX
    narration_with_sfx = place_sfx(narration, sfx_clips, sfx_pos_samples, sfx_vol=0.5)

    # Step 4: Music
    music_path = scene_config["music"]
    print(f"\n  Step 4: Loading music: {os.path.basename(music_path)}")
    music = load_and_resample(music_path, SR)
    music = loop_to_length(music, len(narration_with_sfx) + SR)
    music = fade_in_out(music)

    env = rms_envelope(narration_with_sfx)
    music_ducked = duck_track(music, env, duck_depth=scene_config["duck_depth"], base_vol=scene_config["music_vol"])

    # Mix
    final = narration_with_sfx + music_ducked[:len(narration_with_sfx)]
    final = soft_clip(final)

    out_path = os.path.join(OUT_DIR, scene_config["name"])
    sf.write(out_path, final, SR)
    duration = len(final) / SR
    print(f"\n  -> {out_path} ({duration:.1f}s, {os.path.getsize(out_path)//1024}KB)")
    return out_path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SFX_DIR, exist_ok=True)

    # Load API keys
    env_path = os.path.join(HERE, ".env")
    elevenlabs_key = None
    groq_key = None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("ELEVENLABS_API_KEY="):
                elevenlabs_key = line.split("=", 1)[1]
            elif line.startswith("GROQ_API_KEY="):
                groq_key = line.split("=", 1)[1]

    if not groq_key:
        print("ERROR: GROQ_API_KEY not found in .env")
        sys.exit(1)
    if not elevenlabs_key:
        print("ERROR: ELEVENLABS_API_KEY not found in .env")
        sys.exit(1)

    results = {}
    for scene_config in SCENE_PROMPTS:
        try:
            results[scene_config["id"]] = run_scene(scene_config, groq_key, elevenlabs_key)
        except Exception as e:
            print(f"  {scene_config['id']} FAILED: {e}")
            import traceback; traceback.print_exc()

    print(f"\n{'='*60}")
    print("=== RESULTS ===")
    print(f"{'='*60}")
    for name, path in results.items():
        if path and os.path.exists(path):
            print(f"  {name}: {path} ({os.path.getsize(path)//1024}KB)")
        else:
            print(f"  {name}: FAILED")


if __name__ == "__main__":
    main()
