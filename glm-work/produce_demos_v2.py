#!/usr/bin/env python3
"""
Improved production script incorporating Arie's feedback:

1. SFX: Strip silence, PAUSE narration during SFX, no overlap with voice
2. Music: Diverse sources, scene-change transitions, narrator vs character volume
3. TTS: Qwen3 for ALL voices (narrator + characters) with scene-appropriate delivery
4. SFX: Multiple sources (ElevenLabs + procedural fallback)
5. Music: Includes a live-generated music segment (MusicGen or procedural)

Generates 3 demos with very different vibes:
  7. Mystery/exploration — ancient library, secrets, quiet tension
  8. Combat/action — ambush, chase, desperate fight
  9. Emotional/dramatic — sacrifice, loss, bittersweet victory

Usage:
  .venv/bin/python produce_demos_v2.py
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
SR = 24000

# --- Music library (diverse sources) ---
MUSIC_TRACKS = {
    # Original tracks
    "dark_woods": {"path": os.path.join(TRACKS_DIR, "dark_woods.mp3"), "license": "CC-BY 3.0", "author": "Hitctrl", "vibe": "dark forest, tense"},
    "dungeon_ambient": {"path": os.path.join(TRACKS_DIR, "dungeon_ambient.ogg"), "license": "CC0", "author": "JaggedStone", "vibe": "dungeon, cave ambience"},
    "tavern": {"path": os.path.join(TRACKS_DIR, "tavern_old_tower_inn.mp3"), "license": "CC0", "author": "RandomMind", "vibe": "medieval tavern, warm"},
    # New diverse tracks
    "battle_theme": {"path": os.path.join(TRACKS_DIR, "battle_theme_cc0.mp3"), "license": "CC0", "author": "various", "vibe": "epic battle, exciting"},
    "battle_march": {"path": os.path.join(TRACKS_DIR, "battle_march_epic.wav"), "license": "CC-BY 3.0", "author": "PlayOnLoop", "vibe": "epic orchestral battle march"},
    "dark_chamber": {"path": os.path.join(TRACKS_DIR, "dark_chamber_mystery.mp3"), "license": "CC-BY 4.0", "author": "Marcelo Fernandez", "vibe": "mystery, suspense, dungeon"},
    "exploration": {"path": os.path.join(TRACKS_DIR, "exploration_peaceful.mp3"), "license": "CC-BY 3.0", "author": "Trevor Lentz", "vibe": "peaceful, exploration, town"},
    "emotional": {"path": os.path.join(TRACKS_DIR, "i_want_to_go_home_cc0.wav"), "license": "CC0", "author": "Rafael Krux (arr.)", "vibe": "sad, nostalgic, emotional, cello"},
}

# --- Scene configs ---
SCENES = [
    {
        "id": "demo7_mystery",
        "name": "demo7_mystery.wav",
        "scene_file": "demo7_mystery_scene.txt",
        "vibe": "mystery/exploration",
        "groq_system": (
            "You are a D&D DM writing a MYSTERY/EXPLORATION scene. Write a 300-word scene "
            "with narrator + 2 characters exploring an ancient library filled with secrets. "
            "Build quiet tension, wonder, and discovery. Include finding a hidden artifact, "
            "reading forbidden text, and a moment of revelation.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 5 SFX: a page turning, a whisper/echo, a magical chime, a door unlocking, "
            "and one surprise. Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a mystery scene where two adventurers (one male scholar, one female rogue) "
            "discover a hidden archive beneath a ruined tower. They find a book that whispers "
            "their names. The scene should feel like quiet wonder building to revelation."
        ),
        # Music transitions: different tracks for different scene phases
        "music_plan": [
            {"track": "dark_chamber", "start_seg": 0, "end_seg": 5, "vol": 0.10, "duck": 0.65},  # mystery
            {"track": "exploration", "start_seg": 5, "end_seg": 10, "vol": 0.12, "duck": 0.60},  # discovery
            {"track": "dark_chamber", "start_seg": 10, "end_seg": 99, "vol": 0.08, "duck": 0.70},  # revelation
        ],
        # Narrator vs character volume difference (audiobook best practice)
        "narrator_music_vol": 0.12,  # music slightly louder during narrator
        "character_music_vol": 0.04,  # music very quiet during dialogue (almost dry)
        "narrator_voice": (
            "A mysterious, hushed narrator with a voice like a librarian discovering secrets. "
            "Speaks with quiet wonder and building curiosity. Every word feels like turning a page "
            "in a forbidden book. Calm but with an undercurrent of awe."
        ),
        "character_voices": {
            "male": "A scholarly male voice, precise and curious, speaking softly as if in a library. "
                    "Slightly breathless with excitement at discoveries. Not shouting — whispering findings.",
            "female": "A rogue's voice, low and cautious, always listening for danger. "
                      "Speaks quickly and quietly, like someone used to being where they shouldn't be. "
                      "Sharp, alert, but genuinely moved by what she finds.",
        },
    },
    {
        "id": "demo8_combat",
        "name": "demo8_combat.wav",
        "scene_file": "demo8_combat_scene.txt",
        "vibe": "combat/action",
        "groq_system": (
            "You are a D&D DM writing a COMBAT/ACTION scene. Write a 300-word scene "
            "with narrator + 2 characters in a desperate ambush and chase. "
            "Fast-paced, visceral, dangerous. Include being ambushed, a chase through narrow streets, "
            "and a desperate last stand.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 5 SFX: an ambush arrow, running footsteps, a shield block, a sword strike, "
            "and a war cry. Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a combat scene where two adventurers (one male fighter, one female ranger) "
            "are ambushed in a narrow alley. They must fight their way out. Arrows fly, steel rings, "
            "and they barely escape. The scene should feel fast, dangerous, and desperate."
        ),
        "music_plan": [
            {"track": "battle_march", "start_seg": 0, "end_seg": 4, "vol": 0.14, "duck": 0.55},  # tension building
            {"track": "battle_theme", "start_seg": 4, "end_seg": 12, "vol": 0.16, "duck": 0.50},  # full combat
            {"track": "battle_march", "start_seg": 12, "end_seg": 99, "vol": 0.10, "duck": 0.65},  # aftermath
        ],
        "narrator_music_vol": 0.14,
        "character_music_vol": 0.06,  # slightly louder than mystery — action scenes need energy
        "narrator_voice": (
            "An intense, fast-paced narrator with an urgent voice. Speaks rapidly with rising tension, "
            "like a war correspondent reporting live combat. Every sentence drives forward. "
            "Breathless, visceral, in the moment."
        ),
        "character_voices": {
            "male": "A battle-hardened fighter shouting over the clash of steel. Gruff, commanding, "
                    "out of breath from running and fighting. Speaks in short bursts between swings. "
                    "NOT reading text — actively fighting and yelling.",
            "female": "A ranger's voice, sharp and focused, calling out warnings and positions. "
                      "Speaks quickly and precisely, like someone tracking multiple threats. "
                      "Breathless but controlled. Active combat voice, not narrator voice.",
        },
    },
    {
        "id": "demo9_emotional",
        "name": "demo9_emotional.wav",
        "scene_file": "demo9_emotional_scene.txt",
        "vibe": "emotional/dramatic",
        "groq_system": (
            "You are a D&D DM writing an EMOTIONAL/DRAMATIC scene. Write a 300-word scene "
            "with narrator + 2 characters experiencing sacrifice, loss, and bittersweet victory. "
            "One character must make a sacrifice to save the other. The scene should move the listener. "
            "Include a farewell, a moment of sacrifice, and a quiet aftermath.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 5 SFX: a gentle wind, a magical barrier forming, a heart beating/fading, "
            "a soft chime of passing, and rain beginning. Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write an emotional scene where two lifelong companions (one male paladin, one female cleric) "
            "face a collapsing magical barrier. The cleric must sacrifice herself to hold the barrier "
            "so the paladin can escape. They say goodbye. She fades. He walks out alone into the rain."
        ),
        "music_plan": [
            {"track": "emotional", "start_seg": 0, "end_seg": 6, "vol": 0.10, "duck": 0.60},  # tender
            {"track": "emotional", "start_seg": 6, "end_seg": 10, "vol": 0.14, "duck": 0.55},  # sacrifice swells
            {"track": "emotional", "start_seg": 10, "end_seg": 99, "vol": 0.08, "duck": 0.70},  # quiet aftermath
        ],
        "narrator_music_vol": 0.10,
        "character_music_vol": 0.02,  # almost dry — intimate dialogue should be nearly silent
        "narrator_voice": (
            "A gentle, sorrowful narrator with a voice full of empathy and loss. "
            "Speaks slowly, with long pauses, as if telling a story about someone who mattered. "
            "Every word carries weight and tenderness. Like a eulogy for a friend."
        ),
        "character_voices": {
            "male": "A paladin's voice breaking with emotion, struggling to speak through grief. "
                    "Deep but trembling. Not commanding — vulnerable. Speaking to someone he's losing. "
                    "Raw, real, human.",
            "female": "A cleric's voice, calm and peaceful despite what's coming. Soft, warm, accepting. "
                      "Speaking with love, not fear. Like someone saying goodbye to their dearest friend. "
                      "Fading slightly as she speaks, as if getting weaker.",
        },
    },
]


# === SCENE PARSER ===

@dataclass
class SceneSegment:
    kind: str  # "narrator", "dialogue", "sfx"
    speaker: str = ""
    text: str = ""
    sfx_key: str = ""


def strip_reasoning_prefix(text: str) -> str:
    """Strip Groq reasoning/meta-text that appears before the actual scene.
    Look for common markers like '---', '### Scene', numbered lists, etc."""
    lines = text.strip().split("\n")
    # Find the first line that looks like actual scene content (not reasoning)
    scene_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip empty lines
        if not stripped:
            continue
        # Skip reasoning/meta markers
        if stripped.startswith("**Reasoning") or stripped.startswith("Below is") or stripped.startswith("Here is"):
            continue
        if stripped.startswith("#") or stripped.startswith("---"):
            continue
        # Skip numbered list items (1. 2. 3. etc.)
        if re.match(r'^\d+\.\s', stripped):
            continue
        # Skip bullet points
        if stripped.startswith("- ") or stripped.startswith("  - "):
            continue
        # Skip backtick-wrapped SFX key listings
        if stripped.startswith("`") and stripped.endswith("`"):
            continue
        # Skip lines that are just SFX key names with parentheses
        if stripped.startswith("`") and "element" in stripped:
            continue
        # If we see a line that looks like scene narration (longer, no markdown), start there
        if len(stripped) > 30 and not stripped.startswith("*") and not stripped.startswith(">"):
            scene_start = i
            break
    if scene_start > 0:
        return "\n".join(lines[scene_start:])
    return text


def parse_scene(text: str) -> list[SceneSegment]:
    # First strip any reasoning prefix
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
    """Strip silence from beginning and end of audio."""
    if len(audio) == 0:
        return audio
    # Find first sample above threshold
    above = np.abs(audio) > threshold
    if not above.any():
        return audio[:int(SR * 0.1)]  # return 100ms if all silence
    first = np.argmax(above)
    last = len(audio) - np.argmax(above[::-1]) - 1
    # Add padding
    pad_samples = int(padding * SR)
    first = max(0, first - pad_samples)
    last = min(len(audio), last + pad_samples)
    return audio[first:last]


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
    if fade_samples > 0:
        audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
        audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    return audio


def crossfade(audio1, audio2, fade_samples=None):
    """Crossfade two audio segments."""
    if fade_samples is None:
        fade_samples = min(SR // 2, len(audio1) // 4, len(audio2) // 4)
    if fade_samples <= 0:
        return np.concatenate([audio1, audio2])
    # Apply fade out to end of audio1
    audio1 = np.copy(audio1)
    audio1[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    # Apply fade in to start of audio2
    audio2 = np.copy(audio2)
    audio2[:fade_samples] *= np.linspace(0, 1, fade_samples)
    # Overlap them
    result = np.concatenate([audio1[:-fade_samples], audio1[-fade_samples:] + audio2[:fade_samples], audio2[fade_samples:]])
    return result


def soft_clip(audio):
    return np.tanh(audio * 0.9).astype("float32")


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


# === IMPROVED SFX PLACEMENT (Arie's feedback) ===

def build_narration_with_sfx_gaps(tts_results, sfx_clips_map, gap_between_segments=0.4, sfx_gap_before=0.2, sfx_gap_after=0.3):
    """
    Build narration track with SFX placed in GAPS between speech segments.
    SFX are NOT overlapped with voice — narration pauses while SFX plays.

    Args:
        tts_results: list of (segment, audio) tuples
        sfx_clips_map: dict of sfx_key -> audio clip (silence-stripped)
        gap_between_segments: silence between speech segments (seconds)
        sfx_gap_before: silence before SFX plays (seconds)
        sfx_gap_after: silence after SFX plays (seconds)

    Returns:
        (narration_audio, sfx_placement_info)
        sfx_placement_info: list of (sfx_key, start_sample, duration_samples)
    """
    result = []
    sfx_placements = []
    current_pos = 0

    gap_samples = int(gap_between_segments * SR)
    sfx_before_samples = int(sfx_gap_before * SR)
    sfx_after_samples = int(sfx_gap_after * SR)

    for i, (seg, audio) in enumerate(tts_results):
        if seg.kind == "sfx":
            # Place SFX in a gap — add silence before, SFX, silence after
            sfx_clip = sfx_clips_map.get(seg.sfx_key)
            if sfx_clip is not None:
                # Strip silence from SFX
                sfx_clip = strip_silence(sfx_clip)
                # Add silence before SFX
                if sfx_before_samples > 0:
                    result.append(np.zeros(sfx_before_samples, dtype="float32"))
                    current_pos += sfx_before_samples
                # Record placement
                sfx_start = current_pos
                result.append(sfx_clip)
                current_pos += len(sfx_clip)
                sfx_placements.append((seg.sfx_key, sfx_start, len(sfx_clip)))
                # Add silence after SFX
                if sfx_after_samples > 0:
                    result.append(np.zeros(sfx_after_samples, dtype="float32"))
                    current_pos += sfx_after_samples
            else:
                print(f"    WARNING: No SFX clip for '{seg.sfx_key}', skipping")
        elif audio is not None:
            if i > 0 and result:  # Add gap before speech (unless first segment)
                result.append(np.zeros(gap_samples, dtype="float32"))
                current_pos += gap_samples
            result.append(audio)
            current_pos += len(audio)
        else:
            print(f"    WARNING: No audio for segment {i}, skipping")

    return np.concatenate(result), sfx_placements


# === IMPROVED MUSIC MIXING (Arie's feedback) ===

def build_music_track_with_transitions(segments, tts_results, music_plan, narrator_vol, character_vol, total_length):
    """
    Build a music track that:
    1. Changes tracks on scene transitions (crossfade between tracks)
    2. Has different volume during narrator vs character dialogue
    3. Uses audiobook best practices: music ~20dB below narration

    Args:
        segments: parsed scene segments
        tts_results: list of (segment, audio) tuples
        music_plan: list of {track, start_seg, end_seg, vol, duck} dicts
        narrator_vol: music volume during narrator segments
        character_vol: music volume during character dialogue (lower for intimate scenes)
        total_length: total length of final audio in samples

    Returns:
        music track (numpy array)
    """
    # First, build a timeline of which segments are narrator vs dialogue
    # and their time positions
    segment_timeline = []  # list of (start_sample, end_sample, is_narrator)
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

    # Build music track with transitions
    music = np.zeros(total_length, dtype="float32")

    # Group music plan by track
    for plan_idx, plan in enumerate(music_plan):
        track_name = plan["track"]
        if track_name not in MUSIC_TRACKS:
            print(f"    WARNING: Music track '{track_name}' not found, skipping")
            continue

        track_info = MUSIC_TRACKS[track_name]
        track_audio = load_and_resample(track_info["path"], SR)

        # Determine time range for this music segment
        start_seg = plan["start_seg"]
        end_seg = plan["end_seg"]

        # Find time positions
        start_sample = 0
        end_sample = total_length

        if start_seg < len(segment_timeline):
            start_sample = segment_timeline[start_seg][0]
        if end_seg < len(segment_timeline):
            end_sample = segment_timeline[end_seg][0]
        elif segment_timeline:
            end_sample = segment_timeline[-1][1] + SR  # add 1 second after last segment

        seg_length = end_sample - start_sample
        if seg_length <= 0:
            continue

        # Loop/trim track to fit
        track_segment = loop_to_length(track_audio, seg_length)

        # Apply volume ducking based on narrator vs character
        # Build volume envelope
        vol_env = np.ones(seg_length, dtype="float32")
        for seg_start, seg_end, is_narrator in segment_timeline:
            if seg_start >= end_sample or seg_end <= start_sample:
                continue
            # Map to local coordinates
            local_start = max(0, seg_start - start_sample)
            local_end = min(seg_length, seg_end - start_sample)
            if is_narrator:
                vol_env[local_start:local_end] = narrator_vol
            else:
                vol_env[local_start:local_end] = character_vol

        # Smooth the volume envelope
        smooth_samples = int(0.5 * SR)  # 0.5 second transitions
        if smooth_samples > 0 and seg_length > smooth_samples * 2:
            vol_env_smooth = np.copy(vol_env)
            for j in range(smooth_samples, seg_length - smooth_samples):
                vol_env_smooth[j] = np.mean(vol_env[max(0, j - smooth_samples):min(seg_length, j + smooth_samples)])
            vol_env = vol_env_smooth

        # Apply additional ducking based on narration RMS
        # Build narration presence envelope for this segment
        narration_presence = np.zeros(seg_length, dtype="float32")
        for seg_start, seg_end, is_narrator in segment_timeline:
            if seg_start >= end_sample or seg_end <= start_sample:
                continue
            local_start = max(0, seg_start - start_sample)
            local_end = min(seg_length, seg_end - start_sample)
            narration_presence[local_start:local_end] = 1.0

        # Apply ducking: reduce music more when narration is present
        duck_depth = plan.get("duck", 0.60)
        ducked_vol = vol_env * (1.0 - duck_depth * narration_presence * 0.5)

        # Apply volume envelope
        track_segment = track_segment * ducked_vol

        # Crossfade with existing music
        fade_samples = int(0.5 * SR)  # 0.5 second crossfade
        if start_sample > 0 and fade_samples > 0:
            # Fade in new track
            fade_in = np.linspace(0, 1, min(fade_samples, seg_length // 2))
            track_segment[:len(fade_in)] *= fade_in
            # Fade out existing music at transition point
            fade_out_end = min(start_sample + len(fade_in), total_length)
            existing_fade = np.linspace(1, 0, fade_out_end - start_sample)
            music[start_sample:fade_out_end] *= existing_fade

        # Fade out at end of segment (unless it's the last segment)
        if plan_idx < len(music_plan) - 1 and fade_samples > 0:
            fade_out = np.linspace(1, 0, min(fade_samples, seg_length // 2))
            track_segment[-len(fade_out):] *= fade_out

        # Mix into music track
        end_mix = min(start_sample + seg_length, total_length)
        music[start_sample:end_mix] += track_segment[:end_mix - start_sample]

    return music


# === LIVE-GENERATED MUSIC (procedural, musical) ===

def generate_live_music(vibe, duration_seconds, target_sr=SR):
    """
    Generate a short musical piece procedurally.
    This creates actual chord progressions and melodies — not noise.
    Used for "special scenes" where we want unique, generated music.
    """
    print(f"  Generating live music: {vibe} ({duration_seconds:.1f}s)")

    # Chord progressions for different vibes
    progressions = {
        "mystery": [
            [57, 60, 64],  # Am
            [55, 59, 62],  # Gm
            [53, 57, 60],  # Fm
            [52, 55, 59],  # Em
        ],
        "combat": [
            [40, 43, 47],  # Em
            [38, 41, 45],  # Dm
            [36, 40, 43],  # Cm
            [43, 47, 50],  # Gm
        ],
        "emotional": [
            [48, 52, 55],  # Cm
            [46, 50, 53],  # Bbm
            [43, 47, 50],  # Gm
            [41, 45, 48],  # Fm
        ],
        "heroic": [
            [48, 52, 55],  # Cm
            [50, 53, 57],  # Dm
            [47, 50, 54],  # Bb
            [43, 47, 50],  # Gm
        ],
    }

    chords = progressions.get(vibe, progressions["mystery"])
    n_chords = len(chords)
    total_samples = int(duration_seconds * target_sr)
    chord_duration = total_samples / n_chords
    chord_samples = int(chord_duration)

    audio = np.zeros(total_samples, dtype="float32")

    for i, chord in enumerate(chords):
        start = i * chord_samples
        end = min(start + chord_samples, total_samples)
        length = end - start

        # Generate chord with harmonics
        t = np.arange(length) / target_sr
        chord_wave = np.zeros(length, dtype="float32")

        for note in chord:
            freq = 440 * (2 ** ((note - 69) / 12))
            # Add harmonics
            for h in range(1, 5):
                amp = 1.0 / (h ** 1.5)
                chord_wave += amp * np.sin(2 * np.pi * freq * h * t)

        # Add a simple melody note on top
        melody_note = chord[0] + 12  # One octave up
        melody_freq = 440 * (2 ** ((melody_note - 69) / 12))
        melody_env = np.exp(-t * 1.5)  # Decay envelope
        chord_wave += 0.3 * melody_env * np.sin(2 * np.pi * melody_freq * t)

        # Apply envelope (attack + release)
        attack = int(0.1 * target_sr)
        release = int(0.3 * target_sr)
        env = np.ones(length, dtype="float32")
        if attack < length:
            env[:attack] = np.linspace(0, 1, attack)
        if release < length:
            env[-release:] = np.linspace(1, 0, release)
        chord_wave *= env

        # Normalize
        if chord_wave.max() > 0:
            chord_wave = chord_wave / chord_wave.max() * 0.3

        audio[start:end] += chord_wave[:length]

    # Add simple reverb (delay-based)
    delay_samples = int(0.15 * target_sr)
    reverb = np.zeros_like(audio)
    reverb[delay_samples:] = audio[:-delay_samples] * 0.3
    reverb[delay_samples * 2:] += audio[:-delay_samples * 2] * 0.15
    audio = audio + reverb

    # Normalize
    if audio.max() > 0:
        audio = audio / audio.max() * 0.5

    return audio.astype("float32")


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
    """Procedural SFX fallback."""
    n = int(SR * duration)
    t = np.arange(n) / SR
    return (np.random.randn(n) * 0.3 * np.exp(-t * 2)).astype("float32")


# === QWEN3 TTS FOR ALL VOICES ===

def generate_qwen3_tts_all(segments, narrator_voice_desc, character_voice_descs, out_subdir):
    """
    Generate ALL TTS with Qwen3 VoiceDesign:
    - Narrator segments use narrator_voice_desc
    - Character dialogue uses character_voice_descs (male/female)
    
    This addresses Arie's feedback that Kokoro voices are too "reading text out loud"
    and Qwen3 can create more active, scene-appropriate delivery styles.
    """
    from mlx_audio.tts import load_model
    from mlx_audio.tts.generate import generate_audio as mlx_generate

    MODEL_PATH = os.path.join(HERE, "models", "qwen3_voicedesign_8bit")
    print(f"  Loading Qwen3-TTS VoiceDesign from {MODEL_PATH}...")
    qwen_model = load_model(MODEL_PATH)

    # Detect character names and assign male/female voice descriptions
    char_names = set()
    for seg in segments:
        if seg.kind == "dialogue":
            char_names.add(seg.speaker)

    # Assign voices based on known names + pronoun detection from scene text
    scene_text = " ".join(seg.text for seg in segments)
    scene_lower = scene_text.lower()

    char_voice_map = {}
    male_assigned = False
    female_assigned = False

    for name in sorted(char_names):
        name_lower = name.lower()
        # Check for pronouns near the name
        name_context = ""
        idx = scene_lower.find(name_lower)
        while idx >= 0:
            name_context += scene_lower[max(0, idx - 150):idx + 150] + " "
            idx = scene_lower.find(name_lower, idx + 1)

        has_female = any(p in name_context for p in [" she ", " her ", " hers "])
        has_male = any(p in name_context for p in [" he ", " his ", " him "])
        known_male = name_lower in ("kael", "garrick", "thorne", "thrain", "grimgold", "elic", "commander", "grimbold")
        known_female = name_lower in ("lyra", "lira", "arin", "eira", "elian", "elara", "scholar", "cleric")

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
                text=seg.text,
                model=qwen_model,
                instruct=voice_desc,
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
    """Run a single scene through the full improved pipeline."""
    print(f"\n{'=' * 60}")
    print(f"=== {scene_config['id'].upper()} ({scene_config['vibe']}) ===")
    print(f"{'=' * 60}")

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

    # Step 2: Generate ALL TTS with Qwen3 (narrator + characters)
    print(f"\n  Step 2: Generating TTS with Qwen3 (all voices)...")
    out_subdir = os.path.join(OUT_DIR, f"{scene_config['id']}_segments")
    tts_results = generate_qwen3_tts_all(
        segments,
        scene_config["narrator_voice"],
        scene_config["character_voices"],
        out_subdir,
    )

    # Step 3: Generate SFX via ElevenLabs
    print(f"\n  Step 3: Generating SFX via ElevenLabs...")
    sfx_clips_map = {}
    for seg in segments:
        if seg.kind == "sfx" and seg.sfx_key not in sfx_clips_map:
            prompt = seg.sfx_key.replace("_", " ") + ", dramatic, cinematic, high quality"
            clip = generate_elevenlabs_sfx(seg.sfx_key, prompt, 3.0, elevenlabs_key)
            if clip is None:
                clip = synthesize_sfx(seg.sfx_key, 3.0)
            # Strip silence from SFX (Arie's feedback)
            clip = strip_silence(clip)
            sfx_clips_map[seg.sfx_key] = clip

    # Step 4: Build narration with SFX in GAPS (no overlap — Arie's feedback)
    print(f"\n  Step 4: Building narration with SFX in gaps (no overlap)...")
    narration, sfx_placements = build_narration_with_sfx_gaps(tts_results, sfx_clips_map)

    # Step 5: Build music track with transitions + narrator/character volume
    print(f"\n  Step 5: Building music track with scene transitions...")
    total_length = len(narration) + SR  # Add 1 second tail
    music = build_music_track_with_transitions(
        segments,
        tts_results,
        scene_config["music_plan"],
        scene_config["narrator_music_vol"],
        scene_config["character_music_vol"],
        total_length,
    )

    # Step 6: Mix narration + music
    print(f"\n  Step 6: Mixing narration + music...")
    # Pad narration to match music length
    if len(narration) < total_length:
        narration = np.concatenate([narration, np.zeros(total_length - len(narration), dtype="float32")])
    final = narration[:total_length] + music[:total_length]
    final = soft_clip(final)

    # Save
    out_path = os.path.join(OUT_DIR, scene_config["name"])
    sf.write(out_path, final, SR)
    duration = len(final) / SR
    peak = np.abs(final).max()
    rms = np.sqrt(np.mean(final ** 2))
    print(f"\n  -> {out_path}")
    print(f"     Duration: {duration:.1f}s  Peak: {peak:.3f}  RMS: {rms:.4f}  Size: {os.path.getsize(out_path) // 1024}KB")
    print(f"     SFX placements: {len(sfx_placements)} (all in gaps, no voice overlap)")
    return out_path


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, default=None, help="Run only scene N (0-indexed)")
    args = parser.parse_args()

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

    scenes_to_run = [SCENES[args.only]] if args.only is not None else SCENES

    results = {}
    for scene_config in scenes_to_run:
        try:
            results[scene_config["id"]] = run_scene(scene_config, groq_key, elevenlabs_key)
        except Exception as e:
            print(f"  {scene_config['id']} FAILED: {e}")
            import traceback
            traceback.print_exc()

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
