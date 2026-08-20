#!/usr/bin/env python3
"""
Interactive D&D Audio Demo — terminal-based.

The user makes choices that steer the story. Audio is assembled live:
- Groq generates each scene segment based on user choices
- Qwen3 generates TTS for narration + dialogue (live, ~2.5x realtime)
- Pre-cached ElevenLabs SFX are selected based on scene keywords
- Pre-cached music tracks are selected based on scene mood
- Background ambience is mixed in based on environment

The demo starts in a tavern, and the user's choices determine where
the story goes: forest, dungeon, city, or mountains.

Usage:
  .venv/bin/python interactive_audio_demo.py
"""

import json, os, re, sys, time, threading, queue, urllib.request
from dataclasses import dataclass
from typing import Optional
import numpy as np
import soundfile as sf
from scipy import signal
from scipy.ndimage import uniform_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "outputs", "interactive")
SFX_DIR = os.path.join(HERE, "outputs", "epic_scene", "sfx")
TRACKS_DIR = os.path.join(HERE, "outputs", "ambience_demo", "tracks")
MUSICGEN_DIR = os.path.join(HERE, "outputs", "epic_scene", "musicgen")
SR = 24000
os.makedirs(OUT_DIR, exist_ok=True)

# === Audio utils (shared with v4) ===

def load_and_resample(path, target_sr=SR):
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if audio.shape[1] > 1: audio = audio.mean(axis=1)
    else: audio = audio[:, 0]
    if sr != target_sr: audio = signal.resample(audio, int(len(audio) * target_sr / sr))
    return audio.astype("float32")

def strip_silence(audio, threshold=0.01, padding=0.05):
    if len(audio) == 0: return audio
    above = np.abs(audio) > threshold
    if not above.any(): return audio[:int(SR*0.1)]
    first = np.argmax(above)
    last = len(audio) - np.argmax(above[::-1]) - 1
    pad = int(padding * SR)
    return audio[max(0,first-pad):min(len(audio),last+pad)]

def normalize_audio(audio, target_peak=0.7):
    if len(audio) == 0: return audio
    peak = np.abs(audio).max()
    if peak > 0: return (audio / peak * target_peak).astype("float32")
    return audio

def apply_fades(audio, fade_in_s=0.0, fade_out_s=0.0):
    fi = int(fade_in_s * SR)
    fo = int(fade_out_s * SR)
    audio = np.copy(audio)
    if fi > 0 and fi < len(audio) // 2:
        audio[:fi] *= np.linspace(0, 1, fi)
    if fo > 0 and fo < len(audio) // 2:
        audio[-fo:] *= np.linspace(1, 0, fo)
    return audio

def soft_clip(audio, threshold=0.7):
    return np.tanh(audio / threshold) * threshold

def loop_to_length(audio, target_len):
    if len(audio) >= target_len: return audio[:target_len]
    result = np.copy(audio)
    while len(result) < target_len:
        result = np.concatenate([result, audio])
    return result[:target_len]

def play_audio(audio, sr=SR):
    """Play audio through sounddevice (non-blocking)."""
    try:
        import sounddevice as sd
        sd.play(audio, sr)
        sd.wait()
    except ImportError:
        # Fallback: save to file and let user play
        path = os.path.join(OUT_DIR, "last_segment.wav")
        sf.write(path, audio, sr)
        print(f"  (Saved to {path} — install sounddevice for live playback: pip install sounddevice)")

# === Scene parser ===

@dataclass
class Segment:
    kind: str
    speaker: str = ""
    text: str = ""
    sfx_key: str = ""

def strip_reasoning(text):
    """Strip reasoning/thinking text from qwen3.6-27b and similar models.
    Removes lines that look like meta-reasoning ANYWHERE in the text."""
    lines = text.strip().split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append(line)
            continue
        lower = stripped.lower()
        # Skip reasoning patterns
        skip = False
        # Lines starting with reasoning keywords
        for pattern in [
            "thinking process", "let's count", "let me count", "trimming:",
            "here's a thinking", "here's thinking", "**analyze", "**deconstruct",
            "**draft", "**refine", "**check", "**final polish", "**word count",
            "**adjustment", "**add:", "**requirement", "**format", "**constraint",
            "word count check", "word count constraint", "final polish",
        ]:
            if lower.startswith(pattern):
                skip = True
                break
        if skip:
            continue
        # Numbered reasoning items (1. **Analyze, 2. **Draft, etc.)
        if re.match(r'^\d+\.\s\*\*', stripped):
            continue
        # Lines with word counts like "(48)" at the end
        if re.search(r'\(\d+\)\s*$', stripped) and len(stripped) < 200:
            continue
        # Lines that are just "*   *Something:*" reasoning markers
        if re.match(r'^\*\s+\*\w', stripped):
            continue
        # Lines starting with "*Final" or "*Word" or "*Adjust"
        if re.match(r'^\*(final|word|adjust|add|check|refine|polish)', lower):
            continue
        # Skip "What will Arie do?" numbered choice lines that shouldn't be read
        # (keep the question but not the numbered options)
        if re.match(r'^\d+\)\s', stripped) and "will" in lower:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)

def parse_scene(text):
    text = strip_reasoning(text)
    lines = text.strip().split("\n")
    segments = []
    buffer = []
    i = 0

    def flush():
        if buffer:
            joined = " ".join(buffer).strip()
            if joined:
                segments.append(Segment(kind="narrator", text=joined))
            buffer.clear()

    while i < len(lines):
        line = lines[i].strip()
        if not line: flush(); i += 1; continue

        sfx_m = re.match(r'^\[\s*SFX:\s*([^\]]+?)\s*\]', line)
        if sfx_m:
            flush()
            clean_key = re.sub(r'[^\w\s]', '', sfx_m.group(1)).strip().replace(" ","_").strip("_")
            segments.append(Segment(kind="sfx", sfx_key=clean_key))
            i += 1; continue

        char_m = re.match(r'^\[(\w+)\]\s*(.*)', line)
        if not char_m:
            char_m = re.match(r'^(\w+)\s+["\u201c](.*)["\u201d]\s*$', line)

        if char_m:
            flush()
            speaker = char_m.group(1)
            dialogue = char_m.group(2).strip()
            has_open = dialogue.startswith('"') or dialogue.startswith('\u201c')
            has_close = dialogue.endswith('"') or dialogue.endswith('\u201d')
            if has_open and not has_close:
                while i + 1 < len(lines):
                    i += 1
                    nl = lines[i].strip()
                    dialogue += " " + nl
                    if nl.endswith('"') or nl.endswith('\u201d'): break
            if has_open:
                qm = re.match(r'^["\u201c](.*?)["\u201d](.*)', dialogue, re.DOTALL)
                if qm: dialogue = qm.group(1)
                else: dialogue = re.sub(r'^["\u201c](.*)["\u201d]$', r'\1', dialogue)
            else:
                dialogue = re.sub(r'^["\u201c](.*)["\u201d]$', r'\1', dialogue)
            segments.append(Segment(kind="dialogue", speaker=speaker, text=dialogue))
            i += 1; continue

        # Extract inline SFX markers from narrator lines
        inline_sfx = re.findall(r'\[SFX:\s*([^\]]+?)\]', line)
        if inline_sfx:
            flush()
            for sfx_key in inline_sfx:
                # Clean the SFX key: keep only alphanumerics and underscores
                clean_key = re.sub(r'[^\w\s]', '', sfx_key).strip().replace(" ","_").strip("_")
                if clean_key:
                    segments.append(Segment(kind="sfx", sfx_key=clean_key))
            # Add the line with SFX markers stripped
            cleaned = re.sub(r'\[SFX:\s*[^\]]+?\]', '', line).strip()
            if cleaned:
                buffer.append(cleaned)
            i += 1; continue

        buffer.append(line)
        i += 1

    flush()
    return segments


# === Groq scene generation ===

GROQ_MODELS = ["groq/compound-mini", "allam-2-7b", "groq/compound"]

def groq_turn(api_key, system_prompt, history, player_choice, scene_context):
    """Generate one DM turn based on player's choice. Tries multiple models with retry."""
    messages = [{"role": "system", "content": system_prompt}]
    for h in history:
        messages.append(h)
    messages.append({"role": "user", "content": f"PLAYER CHOICE: {player_choice}\n\nCURRENT CONTEXT: {scene_context}\n\nContinue the story with 150-200 words. Include narrator text, character dialogue in [Name] format, and 2-3 [SFX: key] markers. Do NOT include reasoning, meta-text, or word counts."})

    url = "https://api.groq.com/openai/v1/chat/completions"
    import time as _time
    for attempt in range(3):
        for model in GROQ_MODELS:
            payload = json.dumps({
                "model": model,
                "messages": messages,
                "temperature": 0.85,
                "max_tokens": 1500,
            }).encode()
            req = urllib.request.Request(url, data=payload, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 Python/3.12",
            }, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read())
                    text = data["choices"][0]["message"]["content"]
                    if text and len(text.strip()) > 50:
                        return text
                    print(f"  {model}: empty response, trying next...")
            except Exception as e:
                print(f"  {model}: {e}")
                continue
        if attempt < 2:
            print(f"  Retrying in 3s... (attempt {attempt+2}/3)")
            _time.sleep(3)
    print("  All Groq models failed after retries!")
    return None


# === ElevenLabs SFX ===

_sfx_cache = {}

def get_sfx(sfx_key, api_key):
    if sfx_key in _sfx_cache:
        return _sfx_cache[sfx_key]
    cache_path = os.path.join(SFX_DIR, f"elevenlabs_{sfx_key}.mp3")
    if os.path.exists(cache_path):
        audio, sr = sf.read(cache_path, dtype="float32")
        if sr != SR: audio = signal.resample(audio, int(len(audio) * SR / sr))
        if len(audio.shape) > 1: audio = audio.mean(axis=1)
        _sfx_cache[sfx_key] = audio.astype("float32")
        return _sfx_cache[sfx_key]
    # Generate new SFX
    url = "https://api.elevenlabs.io/v1/sound-generation"
    payload = json.dumps({
        "text": sfx_key.replace("_", " ") + ", dramatic, cinematic",
        "duration_seconds": 3.0,
        "prompt_influence": 0.5,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "xi-api-key": api_key, "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 Python/3.12",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            with open(cache_path, "wb") as f: f.write(data)
            audio, sr = sf.read(cache_path, dtype="float32")
            if sr != SR: audio = signal.resample(audio, int(len(audio) * SR / sr))
            if len(audio.shape) > 1: audio = audio.mean(axis=1)
            _sfx_cache[sfx_key] = audio.astype("float32")
            print(f"    [SFX generated: {sfx_key}]")
            return _sfx_cache[sfx_key]
    except Exception as e:
        print(f"    [SFX failed: {sfx_key}: {e}]")
        return None


# === Music selection by mood ===

MUSIC_BY_MOOD = {
    "tavern": os.path.join(TRACKS_DIR, "tavern_old_tower_inn.mp3"),
    "mystery": os.path.join(TRACKS_DIR, "dark_chamber_mystery.mp3"),
    "combat": os.path.join(TRACKS_DIR, "battle_theme_cc0.mp3"),
    "exploration": os.path.join(TRACKS_DIR, "exploration_peaceful.mp3"),
    "emotional": os.path.join(TRACKS_DIR, "i_want_to_go_home_cc0.wav"),
    "dark": os.path.join(TRACKS_DIR, "dark_woods.mp3"),
    "heroic": os.path.join(MUSICGEN_DIR, "musicgen_heroic_victory.wav"),
    "tension": os.path.join(MUSICGEN_DIR, "musicgen_dark_tension.wav"),
}

_music_cache = {}

def get_music(mood):
    if mood not in MUSIC_BY_MOOD:
        return None
    if mood not in _music_cache:
        path = MUSIC_BY_MOOD[mood]
        if os.path.exists(path):
            _music_cache[mood] = load_and_resample(path)
        else:
            return None
    return _music_cache[mood]


def detect_mood(text):
    """Detect scene mood from text content."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["fight", "battle", "attack", "sword", "combat", "enemy", "charge"]):
        return "combat"
    if any(w in text_lower for w in ["tavern", "inn", "drink", "ale", "barkeep"]):
        return "tavern"
    if any(w in text_lower for w in ["mystery", "secret", "hidden", "ancient", "whisper", "rune"]):
        return "mystery"
    if any(w in text_lower for w in ["sad", "tears", "loss", "sacrifice", "goodbye", "farewell"]):
        return "emotional"
    if any(w in text_lower for w in ["forest", "tree", "wood", "dark", "shadow", "fear"]):
        return "dark"
    if any(w in text_lower for w in ["victory", "triumph", "win", "cheer", "celebrate"]):
        return "heroic"
    if any(w in text_lower for w in ["travel", "road", "journey", "path", "mountain", "sky"]):
        return "exploration"
    return "tension"


# === Qwen3 TTS ===

_qwen_model = None

def get_qwen_model():
    global _qwen_model
    if _qwen_model is None:
        from mlx_audio.tts import load_model
        MODEL_PATH = os.path.join(HERE, "models", "qwen3_voicedesign_8bit")
        print("  Loading Qwen3-TTS model...")
        _qwen_model = load_model(MODEL_PATH)
    return _qwen_model


def generate_tts(text, voice_desc):
    """Generate TTS for a single segment."""
    from mlx_audio.tts.generate import generate_audio as mlx_generate
    model = get_qwen_model()
    out_dir = os.path.join(OUT_DIR, "tts_temp")
    os.makedirs(out_dir, exist_ok=True)
    prefix = f"tts_{int(time.time()*1000)}"
    try:
        mlx_generate(text=text, model=model, instruct=voice_desc,
                     lang_code="en", max_tokens=2400, output_path=out_dir,
                     file_prefix=prefix, audio_format="wav")
        for f in os.listdir(out_dir):
            if f.startswith(prefix) and f.endswith(".wav"):
                path = os.path.join(out_dir, f)
                audio, sr = sf.read(path, dtype="float32")
                if sr != SR: audio = signal.resample(audio, int(len(audio) * SR / sr))
                if len(audio.shape) > 1: audio = audio.mean(axis=1)
                os.remove(path)  # cleanup
                return audio.astype("float32")
    except Exception as e:
        print(f"    TTS ERROR: {e}")
    return np.zeros(SR, dtype="float32")


# === Voice presets (calmer, less shouty) ===

NARRATOR_VOICES = {
    "default": "A calm, clear narrator with a steady, measured voice. Speaks at moderate pace. Not dramatic, not shouty — observant and present. Like a professional audiobook narrator.",
    "tense": "A narrator with a slightly tense, urgent tone. Speaks faster but never shouts. Controlled energy, like a news reporter. Clear and articulate.",
    "warm": "A warm, gentle narrator with a soft, intimate voice. Speaks slowly and quietly. Calm, tender, soothing. Like a bedtime story for adults.",
}

CHARACTER_VOICES = {
    "male": "A male character voice, natural and conversational. Not performing — speaking naturally. Calm, direct, human.",
    "female": "A female character voice, natural and conversational. Not performing — speaking naturally. Clear, warm, human.",
}


# === Audio assembly for one turn ===

def assemble_turn_audio(segments, mood, elevenlabs_key, narrator_style="default"):
    """Assemble audio for one story turn from segments."""
    print(f"  Assembling audio (mood: {mood})...")

    # Get music for mood
    music_track = get_music(mood)
    if music_track is not None:
        music_track = normalize_audio(music_track, target_peak=0.8)

    # Generate TTS for each segment + collect SFX
    tts_audios = []
    sfx_clips = []
    sfx_positions = []

    current_pos = 0
    gap_s = int(0.4 * SR)
    sfx_before_s = int(0.4 * SR)
    sfx_after_s = int(0.5 * SR)

    for i, seg in enumerate(segments):
        if seg.kind == "sfx":
            clip = get_sfx(seg.sfx_key, elevenlabs_key)
            if clip is not None:
                clip = strip_silence(clip)
                clip = normalize_audio(clip, target_peak=0.6)
                clip = apply_fades(clip, fade_in_s=0.15, fade_out_s=0.15)
                clip = clip * 0.30
                sfx_clips.append(clip)
                sfx_positions.append(current_pos + sfx_before_s)
                current_pos += sfx_before_s + len(clip) + sfx_after_s
            else:
                # Insert silence for missing SFX
                current_pos += sfx_before_s + int(0.5 * SR) + sfx_after_s
        elif seg.kind in ("narrator", "dialogue"):
            voice_desc = NARRATOR_VOICES[narrator_style] if seg.kind == "narrator" else CHARACTER_VOICES.get(
                # Detect gender from speaker name
                "female" if seg.speaker.lower() in ("lyra", "eira", "elara", "aria", "lira", "female") else "male"
            )
            print(f"    TTS: {seg.kind} {seg.speaker or ''} -> {seg.text[:50]}...")
            audio = generate_tts(seg.text, voice_desc)
            if i > 0:
                current_pos += gap_s
            tts_audios.append((current_pos, audio))
            current_pos += len(audio)

    total_length = current_pos + SR  # 1 second tail

    # Build narration track
    narration = np.zeros(total_length, dtype="float32")
    for pos, audio in tts_audios:
        end = min(pos + len(audio), total_length)
        narration[pos:end] += audio[:end - pos]

    # Build SFX track
    sfx_track = np.zeros(total_length, dtype="float32")
    for clip, pos in zip(sfx_clips, sfx_positions):
        end = min(pos + len(clip), total_length)
        sfx_track[pos:end] += clip[:end - pos]

    # Build music track (ducked, with SFX ducking, fade out)
    if music_track is not None:
        music = loop_to_length(music_track, total_length)
        # Duck music during narration
        narration_env = np.zeros(total_length, dtype="float32")
        for pos, audio in tts_audios:
            end = min(pos + len(audio), total_length)
            narration_env[pos:end] = 1.0
        narration_env = uniform_filter1d(narration_env, size=int(2.0 * SR), mode='nearest')
        # Duck music during SFX
        sfx_env = np.zeros(total_length, dtype="float32")
        for pos in sfx_positions:
            end = min(pos + int(2.0 * SR), total_length)
            sfx_env[pos:end] = 1.0
        sfx_env = uniform_filter1d(sfx_env, size=int(0.3 * SR), mode='nearest')

        music_vol = 0.12 * (1.0 - 0.30 * narration_env) * (1.0 - 0.60 * sfx_env)
        music = music * music_vol
        # Fade out music at end
        fade_out = int(3.0 * SR)
        if fade_out < len(music) // 2:
            music[-fade_out:] *= np.linspace(1, 0, fade_out)
    else:
        music = np.zeros(total_length, dtype="float32")

    # Mix
    final = narration + music + sfx_track
    final = soft_clip(final, threshold=0.72)
    final = normalize_audio(final, target_peak=0.72)

    return final


# === Interactive game ===

def load_keys():
    env_path = os.path.join(HERE, ".env")
    groq_key = elevenlabs_key = None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("GROQ_API_KEY="): groq_key = line.split("=",1)[1]
            elif line.startswith("ELEVENLABS_API_KEY="): elevenlabs_key = line.split("=",1)[1]
    return groq_key, elevenlabs_key


def main():
    print("=" * 60)
    print("  INTERACTIVE D&D AUDIO DEMO")
    print("  Your choices steer the story. Audio is generated live.")
    print("=" * 60)
    print()

    groq_key, elevenlabs_key = load_keys()
    if not groq_key or not elevenlabs_key:
        print("ERROR: Need GROQ_API_KEY and ELEVENLABS_API_KEY in .env")
        sys.exit(1)

    # Game setup
    system_prompt = """You are a D&D Dungeon Master running a live interactive story.
Write vivid, immersive narration with:
- Narrator text (plain paragraphs)
- Character dialogue: [CharacterName] "text"
- SFX markers: [SFX: descriptive_key] on its own line

CRITICAL RULES:
- Output ONLY the scene text. No reasoning, no thinking, no meta-text, no word counts.
- Do NOT output "Thinking Process", "Let's count", "Trimming", "Analysis", or any meta-commentary.
- Do NOT number your reasoning steps.
- Start immediately with the scene narration.
- End with a brief "What will Arie do?" question.

Keep each turn to 150-200 words. Include 2-3 SFX markers.
The player character is named Arie, a wandering adventurer.
The story should respond to the player's choices and create vivid scenes."""

    history = []
    scene_context = "The story begins in a small frontier town called Millbrook. It is evening. The player has just arrived after a long journey."

    # Story state
    turn = 0
    full_audio = []

    print("  The story begins in the frontier town of Millbrook.")
    print("  You are Arie, a wandering adventurer who has just arrived.")
    print()

    # First turn — no choice needed, just the opening
    print("  [Generating opening scene...]")
    opening = groq_turn(groq_key, system_prompt, history, "Start the story — describe the town and give me a choice of what to do.", scene_context)
    if opening:
        print()
        print("-" * 60)
        # Print the text (strip SFX markers for display)
        display_text = re.sub(r'\[SFX:\s*[\w\s]+\]', '', opening)
        print(display_text.strip())
        print("-" * 60)

        # Parse and assemble audio
        segments = parse_scene(opening)
        mood = detect_mood(opening)
        print(f"\n  [Generating audio for {len(segments)} segments, mood: {mood}]")
        audio = assemble_turn_audio(segments, mood, elevenlabs_key)
        full_audio.append(audio)

        # Play audio
        print(f"  [Playing audio: {len(audio)/SR:.1f}s]")
        play_audio(audio)

        history.append({"role": "assistant", "content": opening})
        turn += 1

    # Main game loop
    # Support non-interactive mode via --test or choices from stdin
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="Run with pre-set choices (no user input needed)")
    ap.add_argument("--choices", type=str, default=None, help="Comma-separated choices for non-interactive mode")
    args_ap = ap.parse_args()

    test_choices = []
    if args_ap.test:
        test_choices = [
            "I head to the old mill to investigate the strange lights.",
            "I draw my sword and enter the mill cautiously.",
            "I attack the creature with everything I have!",
            "I tend to my wounds and rest by the riverbank.",
        ]
    elif args_ap.choices:
        test_choices = [c.strip() for c in args_ap.choices.split("|")]
    test_idx = 0

    while turn < 8:  # max 8 turns
        print()
        print(f"  === TURN {turn + 1} ===")
        if test_choices:
            if test_idx >= len(test_choices):
                break
            choice = test_choices[test_idx]
            test_idx += 1
            print(f"  > {choice}")
        else:
            print("  What do you do? (type your choice, or 'quit' to exit)")
            try:
                choice = input("  > ").strip()
            except EOFError:
                print("  (No input available — ending session.)")
                break

        if choice.lower() in ("quit", "exit", "q"):
            break
        if not choice:
            choice = "I look around and see what's happening."

        print(f"\n  [Generating next scene based on your choice...]")
        response = groq_turn(groq_key, system_prompt, history, choice, scene_context)

        if not response:
            print("  [Failed to generate scene. Try again.]")
            continue

        print()
        print("-" * 60)
        display_text = re.sub(r'\[SFX:\s*[\w\s]+\]', '', response)
        print(display_text.strip())
        print("-" * 60)

        # Parse and assemble audio
        segments = parse_scene(response)
        mood = detect_mood(response)

        # Adjust narrator style based on mood
        narrator_style = "default"
        if mood == "combat": narrator_style = "tense"
        elif mood == "emotional": narrator_style = "warm"

        print(f"\n  [Generating audio for {len(segments)} segments, mood: {mood}]")
        audio = assemble_turn_audio(segments, mood, elevenlabs_key, narrator_style)
        full_audio.append(audio)

        # Play audio
        print(f"  [Playing audio: {len(audio)/SR:.1f}s]")
        play_audio(audio)

        # Update state
        history.append({"role": "user", "content": choice})
        history.append({"role": "assistant", "content": response})
        scene_context = f"Turn {turn + 1}. The player chose: {choice}. Last mood: {mood}."
        turn += 1

    # Save full session audio
    if full_audio:
        print("\n  [Saving full session audio...]")
        # Concatenate all turn audios with 1-second gaps
        gap = np.zeros(SR, dtype="float32")
        all_audio = []
        for i, a in enumerate(full_audio):
            if i > 0:
                all_audio.append(gap)
            all_audio.append(a)
        final = np.concatenate(all_audio)
        path = os.path.join(OUT_DIR, f"session_{int(time.time())}.wav")
        sf.write(path, final, SR)
        print(f"  Saved: {path} ({len(final)/SR:.1f}s, {os.path.getsize(path)//1024}KB)")

    print("\n  Thanks for playing!")


if __name__ == "__main__":
    main()
