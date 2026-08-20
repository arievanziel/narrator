#!/usr/bin/env python3
"""
v3 Production script — fixes all feedback from v2 demos:

1. VOLUME SPIKES FIX: Smooth volume envelope with long transitions (2s ramps)
2. MUSIC NORMALIZATION: Music at stable volume, only gentle ducking
3. NARRATOR VOICE: Male voice for combat/action, female for mystery/emotional
4. SFX VOLUME: Per-SFX volume control, normalized levels
5. BACKGROUND AMBIENCE: Rain/wind as long background tracks, not 3-second SFX
6. MUSICGEN: Live-generated music for special scenes

Three new demos:
  10. Tavern/social — warm, character-driven, lively tavern scene
  11. Boss battle — epic confrontation with MusicGen-generated music
  12. Journey/travel — scenic, peaceful, with weather ambience

Usage:
  .venv/bin/python produce_demos_v3.py
  .venv/bin/python produce_demos_v3.py --only 0
"""

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
OUT_DIR = os.path.join(HERE, "outputs", "epic_scene")
TRACKS_DIR = os.path.join(HERE, "outputs", "ambience_demo", "tracks")
SFX_DIR = os.path.join(OUT_DIR, "sfx")
MUSICGEN_DIR = os.path.join(OUT_DIR, "musicgen")
SR = 24000

# --- Music library ---
MUSIC_TRACKS = {
    "dark_woods": {"path": os.path.join(TRACKS_DIR, "dark_woods.mp3"), "license": "CC-BY 3.0", "author": "Hitctrl"},
    "dungeon_ambient": {"path": os.path.join(TRACKS_DIR, "dungeon_ambient.ogg"), "license": "CC0", "author": "JaggedStone"},
    "tavern": {"path": os.path.join(TRACKS_DIR, "tavern_old_tower_inn.mp3"), "license": "CC0", "author": "RandomMind"},
    "battle_theme": {"path": os.path.join(TRACKS_DIR, "battle_theme_cc0.mp3"), "license": "CC0", "author": "various"},
    "battle_march": {"path": os.path.join(TRACKS_DIR, "battle_march_epic.wav"), "license": "CC-BY 3.0", "author": "PlayOnLoop"},
    "dark_chamber": {"path": os.path.join(TRACKS_DIR, "dark_chamber_mystery.mp3"), "license": "CC-BY 4.0", "author": "Marcelo Fernandez"},
    "exploration": {"path": os.path.join(TRACKS_DIR, "exploration_peaceful.mp3"), "license": "CC-BY 3.0", "author": "Trevor Lentz"},
    "emotional": {"path": os.path.join(TRACKS_DIR, "i_want_to_go_home_cc0.wav"), "license": "CC0", "author": "Rafael Krux (arr.)"},
}

# MusicGen tracks (pre-generated)
MUSICGEN_TRACKS = {
    "mg_dark_tension": {"path": os.path.join(MUSICGEN_DIR, "musicgen_dark_tension.wav"), "license": "CC-BY-NC 4.0", "author": "MusicGen (facebook/musicgen-small)"},
    "mg_mystical": {"path": os.path.join(MUSICGEN_DIR, "musicgen_mystical_revelation.wav"), "license": "CC-BY-NC 4.0", "author": "MusicGen"},
    "mg_heroic": {"path": os.path.join(MUSICGEN_DIR, "musicgen_heroic_victory.wav"), "license": "CC-BY-NC 4.0", "author": "MusicGen"},
}


# === SCENE CONFIGS ===

SCENES = [
    {
        "id": "demo10_tavern",
        "name": "demo10_tavern.wav",
        "scene_file": "demo10_tavern_scene.txt",
        "vibe": "tavern/social",
        "groq_system": (
            "You are a D&D DM writing a TAVERN/SOCIAL scene. Write a 300-word scene "
            "with narrator + 2 characters in a busy tavern. Warm, lively, character-driven. "
            "Include meeting a mysterious stranger, overhearing a rumor, and a moment of humor. "
            "The scene should feel cozy and alive.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 4 SFX: tavern background ambience, a mug clinking, a door opening, "
            "and laughter. Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a tavern scene where two adventurers (one male bard, one female warrior) "
            "are drinking after a long quest. A hooded stranger approaches their table with "
            "a map and a proposition. Keep it warm, funny, and intriguing."
        ),
        "music_plan": [
            {"track": "tavern", "start_seg": 0, "end_seg": 99, "vol": 0.12, "duck": 0.40},
        ],
        # Stable music volume — no narrator/character difference for tavern (it's background)
        "narrator_music_vol": 0.12,
        "character_music_vol": 0.10,  # nearly same — tavern ambience is constant
        "narrator_voice": (
            "A warm, jovial tavern storyteller with a rich, friendly voice. "
            "Speaks with the ease of someone telling a story by a fireplace with a mug of ale. "
            "Comfortable, slightly amused, welcoming. Like a favorite uncle telling tales."
        ),
        "character_voices": {
            "male": "A bard's voice, theatrical and charming, used to performing for crowds. "
                    "Speaks with flair and humor, slightly exaggerated. Loves the sound of his own voice. "
                    "Warm, witty, performing even in casual conversation.",
            "female": "A warrior's voice, deep and direct, with a dry sense of humor. "
                      "Speaks plainly and practically, but with warmth underneath. "
                      "Not impressed by the bard's theatrics but fond of him. Relaxed after a few drinks.",
        },
        # SFX that should be background ambience (long, looping) vs one-shot
        "background_sfx": {
            "tavern_background_ambience": {"duration": 30.0, "volume": 0.15, "loop": True},
        },
        # Per-SFX volume overrides
        "sfx_volumes": {
            "mug_clinking": 0.35,
            "door_opening": 0.30,
            "laughter": 0.25,
        },
    },
    {
        "id": "demo11_boss",
        "name": "demo11_boss.wav",
        "scene_file": "demo11_boss_scene.txt",
        "vibe": "boss battle",
        "groq_system": (
            "You are a D&D DM writing a BOSS BATTLE scene. Write a 300-word scene "
            "with narrator + 2 characters facing a powerful boss enemy. Epic, dangerous, "
            "desperate. Include the boss appearing, a devastating attack, a moment of near-defeat, "
            "and a climactic counterattack.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 5 SFX: a massive roar, ground shaking, magical explosion, shield shattering, "
            "and a final epic strike. Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a boss battle where two adventurers (one male barbarian, one female wizard) "
            "face an ancient dragon in its lair. The dragon breathes fire, the barbarian barely "
            "survives, and the wizard lands the final blow with a massive spell. Epic and climactic."
        ),
        # Use MusicGen for the boss battle!
        "music_plan": [
            {"track": "mg_dark_tension", "start_seg": 0, "end_seg": 4, "vol": 0.12, "duck": 0.45},  # tension
            {"track": "mg_heroic", "start_seg": 4, "end_seg": 99, "vol": 0.14, "duck": 0.40},  # epic battle
        ],
        "narrator_music_vol": 0.14,
        "character_music_vol": 0.08,
        # MALE narrator for combat (Arie's feedback: female narrator terrible for combat)
        "narrator_voice": (
            "A powerful, deep male narrator with an epic, booming voice. "
            "Speaks with the intensity of a war horn and the weight of legend. "
            "Every word hits like a hammer blow. Dramatic, commanding, larger than life. "
            "Like a veteran commander describing the greatest battle ever fought."
        ),
        "character_voices": {
            "male": "A barbarian's roar, raw and primal, screaming battle cries between swings. "
                    "Deep, guttural, furious. Not reading text — howling in rage and pain. "
                    "Breathless, bloodied, still fighting. Pure adrenaline.",
            "female": "A wizard's voice, sharp and commanding, chanting spells with authority. "
                      "Powerful, focused, incanting with precision even in chaos. "
                      "Not scared — enraged. Her voice rises with power as she channels magic.",
        },
        "sfx_volumes": {
            "massive_dragon_roar": 0.45,
            "ground_shaking": 0.35,
            "magical_explosion": 0.40,
            "shield_shattering": 0.35,
            "final_epic_strike": 0.45,
        },
    },
    {
        "id": "demo12_journey",
        "name": "demo12_journey.wav",
        "scene_file": "demo12_journey_scene.txt",
        "vibe": "journey/travel",
        "groq_system": (
            "You are a D&D DM writing a JOURNEY/TRAVEL scene. Write a 300-word scene "
            "with narrator + 2 characters traveling through a beautiful landscape. "
            "Peaceful, scenic, with a sense of wonder. Include crossing a mountain pass, "
            "a moment of awe at the view, and a quiet conversation about what lies ahead.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 4 SFX: wind on the mountain, footsteps on gravel, an eagle cry, "
            "and distant thunder. Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a journey scene where two adventurers (one male ranger, one female druid) "
            "cross a high mountain pass at dawn. They see the valley below for the first time. "
            "A storm is building in the distance. The scene should feel peaceful, awe-inspiring, "
            "and hint at adventure ahead."
        ),
        "music_plan": [
            {"track": "exploration", "start_seg": 0, "end_seg": 99, "vol": 0.10, "duck": 0.50},
        ],
        "narrator_music_vol": 0.10,
        "character_music_vol": 0.06,
        "narrator_voice": (
            "A gentle, contemplative narrator with a warm, reflective voice. "
            "Speaks slowly, like someone describing a beautiful sunrise to a friend. "
            "Peaceful, unhurried, savoring each word. Full of quiet wonder at the world."
        ),
        "character_voices": {
            "male": "A ranger's voice, calm and observant, used to long silences in the wild. "
                    "Speaks quietly, noticing details others miss. Comfortable with nature. "
                    "Relaxed, steady, at home in the mountains.",
            "female": "A druid's voice, soft and connected to the natural world. "
                      "Speaks with reverence for the landscape, as if the mountain itself is listening. "
                      "Gentle, wise, attuned to the wind and the storm building ahead.",
        },
        # Wind and thunder as background ambience
        "background_sfx": {
            "mountain_wind": {"duration": 60.0, "volume": 0.08, "loop": True},
        },
        "sfx_volumes": {
            "footsteps_gravel": 0.25,
            "eagle_cry": 0.20,
            "distant_thunder": 0.30,
        },
    },
]


# === SCENE PARSER (with reasoning stripper) ===

@dataclass
class SceneSegment:
    kind: str
    speaker: str = ""
    text: str = ""
    sfx_key: str = ""


def strip_reasoning_prefix(text: str) -> str:
    lines = text.strip().split("\n")
    scene_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("**Reasoning") or stripped.startswith("Below is") or stripped.startswith("Here is"):
            continue
        if stripped.startswith("#") or stripped.startswith("---"):
            continue
        if re.match(r'^\d+\.\s', stripped):
            continue
        if stripped.startswith("- ") or stripped.startswith("  - "):
            continue
        if stripped.startswith("`") and stripped.endswith("`"):
            continue
        if len(stripped) > 30 and not stripped.startswith("*") and not stripped.startswith(">"):
            scene_start = i
            break
    if scene_start > 0:
        return "\n".join(lines[scene_start:])
    return text


def parse_scene(text: str) -> list[SceneSegment]:
    text = strip_reasoning_prefix(text)
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
            remaining_narration = ""
            if has_open_quote:
                quote_match = re.match(r'^["\u201c](.*?)["\u201d](.*)', dialogue, re.DOTALL)
                if quote_match:
                    remaining_narration = quote_match.group(2).strip()
                    dialogue = quote_match.group(1)
                else:
                    dialogue = re.sub(r'^["\u201c](.*)["\u201d]$', r'\1', dialogue)
            else:
                dialogue = re.sub(r'^["\u201c](.*)["\u201d]$', r'\1', dialogue)

            if remaining_narration:
                sfx_parts = re.split(r'\[\s*SFX:\s*([\w\s]+?)\s*\]', remaining_narration)
                for j, part in enumerate(sfx_parts):
                    part = part.strip()
                    if j % 2 == 1:
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


# === AUDIO UTILITIES ===

def load_and_resample(path, target_sr=SR):
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if audio.shape[1] > 1:
        audio = audio.mean(axis=1)
    else:
        audio = audio[:, 0]
    if sr != target_sr:
        audio = signal.resample(audio, int(len(audio) * target_sr / sr))
    return audio.astype("float32")


def strip_silence(audio, threshold=0.01, padding=0.05):
    if len(audio) == 0:
        return audio
    above = np.abs(audio) > threshold
    if not above.any():
        return audio[:int(SR * 0.1)]
    first = np.argmax(above)
    last = len(audio) - np.argmax(above[::-1]) - 1
    pad_samples = int(padding * SR)
    first = max(0, first - pad_samples)
    last = min(len(audio), last + pad_samples)
    return audio[first:last]


def normalize_audio(audio, target_peak=0.7):
    """Normalize audio to a target peak level."""
    if len(audio) == 0:
        return audio
    peak = np.abs(audio).max()
    if peak > 0:
        return (audio / peak * target_peak).astype("float32")
    return audio


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
    if fade_samples > 0:
        audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
        audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    return audio


def soft_clip(audio):
    return np.tanh(audio * 0.9).astype("float32")


def smooth_volume_envelope(vol_env, smooth_seconds=2.0):
    """Smooth volume envelope with long transitions to prevent spikes.
    Uses a moving average with a 2-second window."""
    smooth_samples = int(smooth_seconds * SR)
    if smooth_samples <= 0 or len(vol_env) <= smooth_samples:
        return vol_env
    # Use scipy uniform filter for efficiency
    from scipy.ndimage import uniform_filter1d
    return uniform_filter1d(vol_env, size=smooth_samples, mode='nearest').astype("float32")


# === IMPROVED SFX PLACEMENT ===

def build_narration_with_sfx_gaps(tts_results, sfx_clips_map, sfx_volumes,
                                   gap_between_segments=0.4, sfx_gap_before=0.2, sfx_gap_after=0.3):
    """Build narration with SFX in gaps. Per-SFX volume control."""
    result = []
    sfx_placements = []
    current_pos = 0

    gap_samples = int(gap_between_segments * SR)
    sfx_before_samples = int(sfx_gap_before * SR)
    sfx_after_samples = int(sfx_gap_after * SR)

    for i, (seg, audio) in enumerate(tts_results):
        if seg.kind == "sfx":
            sfx_clip = sfx_clips_map.get(seg.sfx_key)
            if sfx_clip is not None:
                sfx_clip = strip_silence(sfx_clip)
                # Normalize SFX to consistent level, then apply per-SFX volume
                sfx_clip = normalize_audio(sfx_clip, target_peak=0.8)
                vol = sfx_volumes.get(seg.sfx_key, 0.35)  # default 0.35
                sfx_clip = sfx_clip * vol

                if sfx_before_samples > 0:
                    result.append(np.zeros(sfx_before_samples, dtype="float32"))
                    current_pos += sfx_before_samples
                sfx_start = current_pos
                result.append(sfx_clip)
                current_pos += len(sfx_clip)
                sfx_placements.append((seg.sfx_key, sfx_start, len(sfx_clip)))
                if sfx_after_samples > 0:
                    result.append(np.zeros(sfx_after_samples, dtype="float32"))
                    current_pos += sfx_after_samples
            else:
                print(f"    WARNING: No SFX clip for '{seg.sfx_key}', skipping")
        elif audio is not None:
            if i > 0 and result:
                result.append(np.zeros(gap_samples, dtype="float32"))
                current_pos += gap_samples
            result.append(audio)
            current_pos += len(audio)
        else:
            print(f"    WARNING: No audio for segment {i}, skipping")

    return np.concatenate(result), sfx_placements


# === IMPROVED MUSIC MIXING (no volume spikes) ===

def build_music_track_smooth(segments, tts_results, music_plan, narrator_vol, character_vol, total_length):
    """
    Build music track with SMOOTH volume transitions.
    Key fix: use 2-second smoothing on volume envelope to prevent spikes.
    """
    # Build segment timeline
    segment_timeline = []
    current_pos = 0
    gap_samples = int(0.4 * SR)
    sfx_before_samples = int(0.2 * SR)
    sfx_after_samples = int(0.3 * SR)

    for i, (seg, audio) in enumerate(tts_results):
        if seg.kind == "sfx":
            if audio is not None:
                stripped = strip_silence(audio)
                current_pos += sfx_before_samples + len(stripped) + sfx_after_samples
        elif audio is not None:
            if i > 0:
                current_pos += gap_samples
            start = current_pos
            current_pos += len(audio)
            is_narrator = (seg.kind == "narrator")
            segment_timeline.append((start, current_pos, is_narrator))

    # Build raw volume envelope (before smoothing)
    raw_vol_env = np.ones(total_length, dtype="float32") * narrator_vol  # default to narrator vol

    for seg_start, seg_end, is_narrator in segment_timeline:
        if is_narrator:
            raw_vol_env[seg_start:seg_end] = narrator_vol
        else:
            raw_vol_env[seg_start:seg_end] = character_vol

    # SMOOTH the volume envelope with 2-second transitions (KEY FIX for volume spikes)
    smooth_vol_env = smooth_volume_envelope(raw_vol_env, smooth_seconds=2.0)

    # Build music track with transitions
    music = np.zeros(total_length, dtype="float32")

    for plan_idx, plan in enumerate(music_plan):
        track_name = plan["track"]
        track_info = None
        if track_name in MUSIC_TRACKS:
            track_info = MUSIC_TRACKS[track_name]
        elif track_name in MUSICGEN_TRACKS:
            track_info = MUSICGEN_TRACKS[track_name]
        if not track_info or not os.path.exists(track_info["path"]):
            print(f"    WARNING: Music track '{track_name}' not found, skipping")
            continue

        track_audio = load_and_resample(track_info["path"], SR)
        # Normalize music track to stable volume
        track_audio = normalize_audio(track_audio, target_peak=0.8)

        start_seg = plan["start_seg"]
        end_seg = plan["end_seg"]

        start_sample = 0
        end_sample = total_length
        if start_seg < len(segment_timeline):
            start_sample = segment_timeline[start_seg][0]
        if end_seg < len(segment_timeline):
            end_sample = segment_timeline[end_seg][0]
        elif segment_timeline:
            end_sample = segment_timeline[-1][1] + SR

        seg_length = end_sample - start_sample
        if seg_length <= 0:
            continue

        track_segment = loop_to_length(track_audio, seg_length)

        # Apply the SMOOTH volume envelope for this segment
        local_vol = smooth_vol_env[start_sample:end_sample]

        # Apply gentle ducking (much less than before — music should be stable)
        duck_depth = plan.get("duck", 0.40)
        narration_presence = np.zeros(seg_length, dtype="float32")
        for seg_start, seg_end, is_narrator in segment_timeline:
            if seg_start >= end_sample or seg_end <= start_sample:
                continue
            local_start = max(0, seg_start - start_sample)
            local_end = min(seg_length, seg_end - start_sample)
            narration_presence[local_start:local_end] = 1.0

        # Gentle ducking — only reduce by 30% when narration present (not 60%)
        ducked_vol = local_vol * (1.0 - duck_depth * narration_presence * 0.3)

        track_segment = track_segment * ducked_vol

        # Crossfade
        fade_samples = int(1.0 * SR)  # 1 second crossfade
        if start_sample > 0 and fade_samples > 0:
            fade_in = np.linspace(0, 1, min(fade_samples, seg_length // 2))
            track_segment[:len(fade_in)] *= fade_in
            fade_out_end = min(start_sample + len(fade_in), total_length)
            existing_fade = np.linspace(1, 0, fade_out_end - start_sample)
            music[start_sample:fade_out_end] *= existing_fade

        if plan_idx < len(music_plan) - 1 and fade_samples > 0:
            fade_out = np.linspace(1, 0, min(fade_samples, seg_length // 2))
            track_segment[-len(fade_out):] *= fade_out

        end_mix = min(start_sample + seg_length, total_length)
        music[start_sample:end_mix] += track_segment[:end_mix - start_sample]

    return music


# === BACKGROUND AMBIENCE (long tracks, not short SFX) ===

def build_background_ambience(background_sfx_config, total_length, elevenlabs_key):
    """Generate and place long background ambience tracks (rain, wind, tavern noise)."""
    if not background_sfx_config:
        return np.zeros(total_length, dtype="float32")

    ambience_track = np.zeros(total_length, dtype="float32")

    for sfx_key, config in background_sfx_config.items():
        duration = config.get("duration", 30.0)
        volume = config.get("volume", 0.10)
        loop = config.get("loop", True)

        # Generate or cache the ambience
        prompt = sfx_key.replace("_", " ") + ", continuous background ambience, atmospheric, loopable"
        clip = generate_elevenlabs_sfx(sfx_key, prompt, min(duration, 10.0), elevenlabs_key)
        if clip is None:
            continue

        # Strip silence and normalize
        clip = strip_silence(clip)
        clip = normalize_audio(clip, target_peak=0.6)

        if loop:
            clip = loop_to_length(clip, total_length)
        else:
            clip = fade_in_out(clip)

        # Apply volume
        clip = clip * volume

        # Fade in/out the ambience
        fade_samples = int(2.0 * SR)
        if fade_samples < len(clip) // 2:
            clip[:fade_samples] *= np.linspace(0, 1, fade_samples)
            clip[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        ambience_track[:min(len(clip), total_length)] += clip[:total_length]

    return ambience_track


# === GROQ SCENE GENERATION ===

def groq_generate_scene(api_key, system_prompt, user_prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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
    payload = json.dumps({"text": prompt, "duration_seconds": duration, "prompt_influence": 0.5}).encode()
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


# === QWEN3 TTS ===

def generate_qwen3_tts_all(segments, narrator_voice_desc, character_voice_descs, out_subdir):
    from mlx_audio.tts import load_model
    from mlx_audio.tts.generate import generate_audio as mlx_generate

    MODEL_PATH = os.path.join(HERE, "models", "qwen3_voicedesign_8bit")
    print(f"  Loading Qwen3-TTS VoiceDesign from {MODEL_PATH}...")
    qwen_model = load_model(MODEL_PATH)

    char_names = set()
    for seg in segments:
        if seg.kind == "dialogue":
            char_names.add(seg.speaker)

    scene_text = " ".join(seg.text for seg in segments)
    scene_lower = scene_text.lower()

    char_voice_map = {}
    male_assigned = False
    female_assigned = False

    for name in sorted(char_names):
        name_lower = name.lower()
        name_context = ""
        idx = scene_lower.find(name_lower)
        while idx >= 0:
            name_context += scene_lower[max(0, idx - 150):idx + 150] + " "
            idx = scene_lower.find(name_lower, idx + 1)

        has_female = any(p in name_context for p in [" she ", " her ", " hers "])
        has_male = any(p in name_context for p in [" he ", " his ", " him "])
        known_male = name_lower in ("kael", "garrick", "thorne", "thrain", "grimgold", "elic", "grimbold", "arin", "valoric")
        known_female = name_lower in ("lyra", "lira", "arin", "eira", "elian", "elara", "aria")

        if known_female or (has_female and not has_male and not known_male):
            char_voice_map[name] = "female"
            female_assigned = True
        elif known_male or (has_male and not has_female):
            char_voice_map[name] = "male"
            male_assigned = True
        else:
            if not male_assigned:
                char_voice_map[name] = "male"
                male_assigned = True
            else:
                char_voice_map[name] = "female"
                female_assigned = True

    print(f"  Character voice assignments: {char_voice_map}")

    os.makedirs(out_subdir, exist_ok=True)
    results = []

    for i, seg in enumerate(segments):
        if seg.kind == "sfx":
            results.append((seg, None))
            continue

        if seg.kind == "narrator":
            voice_desc = narrator_voice_desc
            print(f"  [{i + 1}/{len(segments)}] NARRATOR (Qwen3)  text={seg.text[:60]}...")
        elif seg.kind == "dialogue":
            gender = char_voice_map.get(seg.speaker, "male")
            voice_desc = character_voice_descs[gender]
            print(f"  [{i + 1}/{len(segments)}] DIALOGUE  {seg.speaker:10s} ({gender})  text={seg.text[:60]}...")
        else:
            results.append((seg, None))
            continue

        prefix = f"seg_{i:03d}"
        try:
            mlx_generate(
                text=seg.text, model=qwen_model, instruct=voice_desc,
                lang_code="en", max_tokens=2400, output_path=out_subdir,
                file_prefix=prefix, audio_format="wav",
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
                print(f"    -> {len(audio) / SR:.1f}s (Qwen3)")
            else:
                print(f"    -> FAILED, using silence")
                results.append((seg, np.zeros(SR, dtype="float32")))
        except Exception as e:
            print(f"    -> Qwen3 ERROR: {e}")
            results.append((seg, np.zeros(SR, dtype="float32")))

    return results


# === MAIN PIPELINE ===

def run_scene(scene_config, groq_key, elevenlabs_key):
    print(f"\n{'=' * 60}")
    print(f"=== {scene_config['id'].upper()} ({scene_config['vibe']}) ===")
    print(f"{'=' * 60}")

    # Step 1: Generate scene
    print("\n  Step 1: Generating scene with Groq...")
    scene_text = groq_generate_scene(groq_key, scene_config["groq_system"], scene_config["groq_user"])
    if not scene_text:
        return None

    scene_path = os.path.join(OUT_DIR, scene_config["scene_file"])
    with open(scene_path, "w") as f:
        f.write(scene_text)
    print(f"  Saved to {scene_path}")

    segments = parse_scene(scene_text)
    print(f"  Parsed: {len(segments)} segments")
    for i, s in enumerate(segments):
        if s.kind == "sfx":
            print(f"    {i:2d} [SFX     ] {s.sfx_key}")
        elif s.kind == "dialogue":
            print(f"    {i:2d} [{s.speaker:10s}] {s.text[:60]}")
        else:
            print(f"    {i:2d} [NARRATOR ] {s.text[:60]}")

    # Step 2: TTS
    print(f"\n  Step 2: Generating TTS with Qwen3...")
    out_subdir = os.path.join(OUT_DIR, f"{scene_config['id']}_segments")
    tts_results = generate_qwen3_tts_all(
        segments, scene_config["narrator_voice"],
        scene_config["character_voices"], out_subdir,
    )

    # Step 3: SFX
    print(f"\n  Step 3: Generating SFX via ElevenLabs...")
    sfx_clips_map = {}
    for seg in segments:
        if seg.kind == "sfx" and seg.sfx_key not in sfx_clips_map:
            # Skip if it's a background ambience (handled separately)
            if seg.sfx_key in scene_config.get("background_sfx", {}):
                continue
            prompt = seg.sfx_key.replace("_", " ") + ", dramatic, cinematic, high quality"
            clip = generate_elevenlabs_sfx(seg.sfx_key, prompt, 3.0, elevenlabs_key)
            if clip is None:
                clip = (np.random.randn(int(SR * 3)) * 0.3 * np.exp(-np.arange(int(SR * 3)) / SR * 2)).astype("float32")
            sfx_clips_map[seg.sfx_key] = clip

    # Step 4: Build narration with SFX in gaps
    print(f"\n  Step 4: Building narration with SFX in gaps...")
    sfx_volumes = scene_config.get("sfx_volumes", {})
    narration, sfx_placements = build_narration_with_sfx_gaps(
        tts_results, sfx_clips_map, sfx_volumes
    )

    # Step 5: Background ambience (long tracks for rain, wind, tavern noise)
    print(f"\n  Step 5: Building background ambience...")
    background_sfx_config = scene_config.get("background_sfx", {})
    total_length = len(narration) + SR
    ambience = build_background_ambience(background_sfx_config, total_length, elevenlabs_key)

    # Step 6: Music
    print(f"\n  Step 6: Building music track (smooth volume, no spikes)...")
    music = build_music_track_smooth(
        segments, tts_results, scene_config["music_plan"],
        scene_config["narrator_music_vol"], scene_config["character_music_vol"],
        total_length,
    )

    # Step 7: Mix
    print(f"\n  Step 7: Mixing narration + music + ambience...")
    if len(narration) < total_length:
        narration = np.concatenate([narration, np.zeros(total_length - len(narration), dtype="float32")])
    final = narration[:total_length] + music[:total_length] + ambience[:total_length]
    final = soft_clip(final)

    # Final normalization to stable level
    final = normalize_audio(final, target_peak=0.75)

    out_path = os.path.join(OUT_DIR, scene_config["name"])
    sf.write(out_path, final, SR)
    duration = len(final) / SR
    peak = np.abs(final).max()
    rms = np.sqrt(np.mean(final ** 2))
    print(f"\n  -> {out_path}")
    print(f"     Duration: {duration:.1f}s  Peak: {peak:.3f}  RMS: {rms:.4f}  Size: {os.path.getsize(out_path) // 1024}KB")
    print(f"     SFX: {len(sfx_placements)} one-shots in gaps + {len(background_sfx_config)} background ambience tracks")
    return out_path


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, default=None, help="Run only scene N (0-indexed)")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SFX_DIR, exist_ok=True)
    os.makedirs(MUSICGEN_DIR, exist_ok=True)

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

    if not groq_key or not elevenlabs_key:
        print("ERROR: API keys not found in .env")
        sys.exit(1)

    scenes_to_run = [SCENES[args.only]] if args.only is not None else SCENES

    results = {}
    for scene_config in scenes_to_run:
        try:
            results[scene_config["id"]] = run_scene(scene_config, groq_key, elevenlabs_key)
        except Exception as e:
            print(f"  {scene_config['id']} FAILED: {e}")
            import traceback; traceback.print_exc()

    print(f"\n{'=' * 60}")
    print("=== RESULTS ===")
    print(f"{'=' * 60}")
    for name, path in results.items():
        if path and os.path.exists(path):
            print(f"  {name}: {path} ({os.path.getsize(path) // 1024}KB)")
        else:
            print(f"  {name}: FAILED")


if __name__ == "__main__":
    main()
