#!/usr/bin/env python3
"""
v4 Production — all fixes from v3 feedback:

1. SFX fade in/out (150ms) — prevents sharp attack spikes
2. Duck music during SFX — no volume jump from SFX+music
3. Larger SFX-to-voice gaps (0.4/0.5s)
4. Lower SFX normalization (0.6 peak)
5. Calmer narrator voices (less shouty)
6. More distinct narrator vs character voice descriptions
7. Music always fades out at end (3s fade)
8. Background ambience: recognizable sounds only, better prompts

Three demos:
  13. Forest mystery — eerie, atmospheric, slow build
  14. City chase — fast, urban, tense
  15. Campfire rest — intimate, quiet, character-driven

Usage:
  .venv/bin/python produce_demos_v4.py
  .venv/bin/python produce_demos_v4.py --only 0
"""

import json, os, re, sys, time, urllib.request, urllib.error
from dataclasses import dataclass
from typing import Optional
import numpy as np
import soundfile as sf
from scipy import signal
from scipy.ndimage import uniform_filter1d

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "outputs", "epic_scene")
TRACKS_DIR = os.path.join(HERE, "outputs", "ambience_demo", "tracks")
SFX_DIR = os.path.join(OUT_DIR, "sfx")
MUSICGEN_DIR = os.path.join(OUT_DIR, "musicgen")
SR = 24000

MUSIC_TRACKS = {
    "dark_woods": {"path": os.path.join(TRACKS_DIR, "dark_woods.mp3"), "license": "CC-BY 3.0", "author": "Hitctrl"},
    "dungeon_ambient": {"path": os.path.join(TRACKS_DIR, "dungeon_ambient.ogg"), "license": "CC0", "author": "JaggedStone"},
    "tavern": {"path": os.path.join(TRACKS_DIR, "tavern_old_tower_inn.mp3"), "license": "CC0", "author": "RandomMind"},
    "battle_theme": {"path": os.path.join(TRACKS_DIR, "battle_theme_cc0.mp3"), "license": "CC0", "author": "various"},
    "battle_march": {"path": os.path.join(TRACKS_DIR, "battle_march_epic.wav"), "license": "CC-BY 3.0", "author": "PlayOnLoop"},
    "dark_chamber": {"path": os.path.join(TRACKS_DIR, "dark_chamber_mystery.mp3"), "license": "CC-BY 4.0", "author": "Marcelo Fernandez"},
    "exploration": {"path": os.path.join(TRACKS_DIR, "exploration_peaceful.mp3"), "license": "CC-BY 3.0", "author": "Trevor Lentz"},
    "emotional": {"path": os.path.join(TRACKS_DIR, "i_want_to_go_home_cc0.wav"), "license": "CC0", "author": "Rafael Krux"},
}
MUSICGEN_TRACKS = {
    "mg_dark_tension": {"path": os.path.join(MUSICGEN_DIR, "musicgen_dark_tension.wav"), "license": "CC-BY-NC 4.0", "author": "MusicGen"},
    "mg_mystical": {"path": os.path.join(MUSICGEN_DIR, "musicgen_mystical_revelation.wav"), "license": "CC-BY-NC 4.0", "author": "MusicGen"},
    "mg_heroic": {"path": os.path.join(MUSICGEN_DIR, "musicgen_heroic_victory.wav"), "license": "CC-BY-NC 4.0", "author": "MusicGen"},
}

SCENES = [
    {
        "id": "demo13_forest",
        "name": "demo13_forest.wav",
        "scene_file": "demo13_forest_scene.txt",
        "vibe": "forest mystery",
        "groq_system": (
            "You are a D&D DM writing a FOREST MYSTERY scene. Write a 300-word scene "
            "with narrator + 2 characters in an ancient, eerie forest. Slow build, atmospheric, "
            "unsettling but not horror. Include finding strange marks on trees, hearing "
            "something following them, and a moment of awe at a hidden grove.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 4 SFX: rustling leaves, a branch snapping, strange humming, and wind through trees. "
            "Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a forest mystery scene where two adventurers (one male tracker, one female "
            "druid) follow strange markings on ancient trees deep into a forest. They hear "
            "something following them. They discover a hidden grove with glowing flowers. "
            "Atmospheric and wondrous, not scary."
        ),
        "music_plan": [
            {"track": "dark_woods", "start_seg": 0, "end_seg": 99, "vol": 0.10, "duck": 0.35},
        ],
        "narrator_music_vol": 0.10,
        "character_music_vol": 0.05,
        # Calmer narrator — NOT shouty, NOT booming
        "narrator_voice": (
            "A calm, measured narrator with a clear, steady voice. Speaks at a moderate pace "
            "with quiet confidence, like a naturalist describing a forest walk. "
            "Not dramatic, not shouty — just observant and present. "
            "Think David Attenborough: interested, precise, never raising his voice."
        ),
        "character_voices": {
            "male": "A tracker's voice, low and alert, speaking quietly while listening for sounds. "
                    "Calm, practical, used to forests. Speaks in short sentences. Not performing — working.",
            "female": "A druid's voice, gentle and curious, speaking with wonder at the forest. "
                      "Soft but clear, attuned to nature. Not theatrical — genuinely moved by what she sees.",
        },
        "background_sfx": {
            "forest_ambience": {"duration": 60.0, "volume": 0.06, "loop": True,
                                "prompt": "Gentle forest ambience with birds, leaves rustling softly, distant creek, peaceful woodland atmosphere"},
        },
        "sfx_volumes": {
            "rustling_leaves": 0.20,
            "branch_snapping": 0.30,
            "strange_humming": 0.20,
            "wind_through_trees": 0.15,
        },
    },
    {
        "id": "demo14_chase",
        "name": "demo14_chase.wav",
        "scene_file": "demo14_chase_scene.txt",
        "vibe": "city chase",
        "groq_system": (
            "You are a D&D DM writing a CITY CHASE scene. Write a 300-word scene "
            "with narrator + 2 characters being chased through a medieval city at night. "
            "Fast, tense, urban. Include rooftop running, a near-miss with a guard, "
            "diving through a market, and escaping into the sewers.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 5 SFX: running footsteps on cobblestone, a guard shouting, "
            "rooftop landing, market crash, and a manhole cover. Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a city chase scene where two thieves (one male rogue, one female acrobat) "
            "are caught stealing from a noble's house and chased across rooftops through "
            "a medieval city at night. They barely escape through a market and into the sewers. "
            "Fast, thrilling, dangerous."
        ),
        "music_plan": [
            {"track": "battle_march", "start_seg": 0, "end_seg": 99, "vol": 0.12, "duck": 0.35},
        ],
        "narrator_music_vol": 0.12,
        "character_music_vol": 0.06,
        # Male narrator for action, but NOT shouty — fast and urgent but controlled
        "narrator_voice": (
            "A fast, urgent narrator with a clear, controlled voice. Speaks quickly but "
            "never shouts — like a sports commentator calling a close game. "
            "Tense and breathless but articulate. Energy comes from pace, not volume. "
            "Think a news reporter narrating a chase: urgent but professional."
        ),
        "character_voices": {
            "male": "A rogue's voice, sharp and quick, whispering urgently while running. "
                    "Out of breath, words coming in gasps. Not shouting — keeping quiet to avoid guards. "
                    "Practical, focused, scared but competent.",
            "female": "An acrobat's voice, light and quick, calling out directions while leaping. "
                      "Breathless but excited — she loves the thrill. Fast, precise, almost laughing "
                      "while running. Not scared — exhilarated.",
        },
        "sfx_volumes": {
            "running_footsteps_cobblestone": 0.25,
            "guard_shouting": 0.30,
            "rooftop_landing": 0.25,
            "market_crash": 0.30,
            "manhole_cover": 0.25,
        },
    },
    {
        "id": "demo15_campfire",
        "name": "demo15_campfire.wav",
        "scene_file": "demo15_campfire_scene.txt",
        "vibe": "campfire rest",
        "groq_system": (
            "You are a D&D DM writing a CAMPFIRE REST scene. Write a 300-word scene "
            "with narrator + 2 characters resting by a campfire after a long day. "
            "Intimate, quiet, character-driven. Include a personal story, a moment of "
            "vulnerability, and a quiet laugh. The scene should feel warm and human.\n\n"
            "Format rules:\n"
            "- Narrator text: plain paragraphs\n"
            "- Dialogue: [CharacterName] \"text\"\n"
            "- SFX: [SFX: key] on its own line\n"
            "Include 3 SFX: fire crackling, a wolf howling in the distance, and crickets. "
            "Use underscores in SFX keys."
        ),
        "groq_user": (
            "Write a campfire scene where two adventurers (one male fighter, one female wizard) "
            "rest after a hard battle. They share a personal story they've never told anyone. "
            "One laughs. The other cries. The fire dies down. It should feel intimate and real."
        ),
        "music_plan": [
            {"track": "emotional", "start_seg": 0, "end_seg": 99, "vol": 0.08, "duck": 0.30},
        ],
        "narrator_music_vol": 0.08,
        "character_music_vol": 0.02,  # almost silent for intimate dialogue
        # Warm, gentle narrator — NOT shouty
        "narrator_voice": (
            "A warm, gentle narrator with a soft, intimate voice. Speaks slowly and quietly, "
            "like someone telling a story to a friend by a fire. "
            "Calm, tender, unhurried. Never raises voice. "
            "Think of a quiet bedtime story for adults — soothing and present."
        ),
        "character_voices": {
            "male": "A fighter's voice, rough but softening by the fire. Normally gruff, but "
                    "now vulnerable and open. Speaks slowly, choosing words carefully. "
                    "Not performing — confessing. Raw and real.",
            "female": "A wizard's voice, usually precise and academic, now relaxed and personal. "
                      "Speaks with warmth and a hint of sadness. Not lecturing — sharing. "
                      "Gentle, reflective, human.",
        },
        "background_sfx": {
            "campfire_crackling": {"duration": 60.0, "volume": 0.10, "loop": True,
                                   "prompt": "Campfire crackling, wood popping, gentle fire ambience, warm and cozy"},
            "night_crickets": {"duration": 60.0, "volume": 0.04, "loop": True,
                               "prompt": "Crickets chirping at night, gentle insect sounds, peaceful summer evening"},
        },
        "sfx_volumes": {
            "wolf_howling_distance": 0.15,
        },
    },
]


# === PARSER ===

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
        if not stripped: continue
        if stripped.startswith("**Reasoning") or stripped.startswith("Below is") or stripped.startswith("Here is"): continue
        if stripped.startswith("#") or stripped.startswith("---"): continue
        if re.match(r'^\d+\.\s', stripped): continue
        if stripped.startswith("- ") or stripped.startswith("  - "): continue
        if stripped.startswith("`") and stripped.endswith("`"): continue
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
            flush_buffer(); i += 1; continue

        sfx_match = re.match(r'^\[\s*SFX:\s*([\w\s]+?)\s*\]', line)
        if sfx_match:
            flush_buffer()
            sfx_key = sfx_match.group(1).strip().replace(" ", "_").strip("_")
            segments.append(SceneSegment(kind="sfx", sfx_key=sfx_key))
            i += 1; continue

        char_match = re.match(r'^\[(\w+)\]\s*(.*)', line)
        if not char_match:
            char_match = re.match(r'^(\w+)\s+["\u201c](.*)["\u201d]\s*$', line)

        if char_match:
            flush_buffer()
            speaker = char_match.group(1)
            dialogue = char_match.group(2).strip()
            has_open = dialogue.startswith('"') or dialogue.startswith('\u201c')
            has_close = dialogue.endswith('"') or dialogue.endswith('\u201d')
            if has_open and not has_close:
                while i + 1 < len(lines):
                    i += 1
                    nl = lines[i].strip()
                    dialogue += " " + nl
                    if nl.endswith('"') or nl.endswith('\u201d'): break
            remaining = ""
            if has_open:
                qm = re.match(r'^["\u201c](.*?)["\u201d](.*)', dialogue, re.DOTALL)
                if qm:
                    remaining = qm.group(2).strip()
                    dialogue = qm.group(1)
                else:
                    dialogue = re.sub(r'^["\u201c](.*)["\u201d]$', r'\1', dialogue)
            else:
                dialogue = re.sub(r'^["\u201c](.*)["\u201d]$', r'\1', dialogue)

            if remaining:
                sfx_parts = re.split(r'\[\s*SFX:\s*([\w\s]+?)\s*\]', remaining)
                for j, part in enumerate(sfx_parts):
                    part = part.strip()
                    if j % 2 == 1:
                        segments.append(SceneSegment(kind="sfx", sfx_key=part.strip().replace(" ", "_").strip("_")))
                    elif part:
                        segments.append(SceneSegment(kind="narrator", speaker="narrator", text=part))

            segments.append(SceneSegment(kind="dialogue", speaker=speaker, text=dialogue))
            i += 1; continue

        buffer.append(line)
        i += 1

    flush_buffer()
    return segments


# === AUDIO UTILITIES ===

def load_and_resample(path, target_sr=SR):
    audio, sr = sf.read(path, dtype="float32", always_2d=True)
    if audio.shape[1] > 1: audio = audio.mean(axis=1)
    else: audio = audio[:, 0]
    if sr != target_sr:
        audio = signal.resample(audio, int(len(audio) * target_sr / sr))
    return audio.astype("float32")


def strip_silence(audio, threshold=0.01, padding=0.05):
    if len(audio) == 0: return audio
    above = np.abs(audio) > threshold
    if not above.any(): return audio[:int(SR * 0.1)]
    first = np.argmax(above)
    last = len(audio) - np.argmax(above[::-1]) - 1
    pad = int(padding * SR)
    return audio[max(0, first - pad):min(len(audio), last + pad)]


def normalize_audio(audio, target_peak=0.7):
    if len(audio) == 0: return audio
    peak = np.abs(audio).max()
    if peak > 0: return (audio / peak * target_peak).astype("float32")
    return audio


def smooth_volume_envelope(vol_env, smooth_seconds=2.0):
    smooth_samples = int(smooth_seconds * SR)
    if smooth_samples <= 0 or len(vol_env) <= smooth_samples: return vol_env
    return uniform_filter1d(vol_env, size=smooth_samples, mode='nearest').astype("float32")


def loop_to_length(audio, target_len):
    if len(audio) >= target_len: return audio[:target_len]
    result = np.copy(audio)
    while len(result) < target_len:
        result = np.concatenate([result, audio])
    return result[:target_len]


def apply_fades(audio, fade_in_s=0.0, fade_out_s=0.0):
    """Apply fade in and fade out."""
    fi = int(fade_in_s * SR)
    fo = int(fade_out_s * SR)
    if fi > 0 and fi < len(audio) // 2:
        audio = np.copy(audio)
        audio[:fi] *= np.linspace(0, 1, fi)
    if fo > 0 and fo < len(audio) // 2:
        audio = np.copy(audio)
        audio[-fo:] *= np.linspace(1, 0, fo)
    return audio


def soft_clip(audio, threshold=0.7):
    """Soft clip to prevent any transient spikes."""
    return np.tanh(audio / threshold) * threshold


def limiter(audio, threshold=0.75, attack_ms=5, release_ms=50):
    """Simple brick-wall limiter to catch transients."""
    if len(audio) == 0: return audio
    threshold_abs = threshold
    above = np.abs(audio) > threshold_abs
    if not above.any(): return audio
    # Simple approach: scale down peaks above threshold
    ratio = np.ones_like(audio)
    ratio[above] = threshold_abs / np.abs(audio[above])
    # Smooth the ratio with attack/release
    attack = int(attack_ms * SR / 1000)
    release = int(release_ms * SR / 1000)
    if attack > 0:
        ratio = uniform_filter1d(ratio, size=attack, mode='nearest')
    return (audio * ratio).astype("float32")


# === SFX PLACEMENT with fade in/out + music ducking during SFX ===

def build_narration_with_sfx_gaps(tts_results, sfx_clips_map, sfx_volumes,
                                   gap_between=0.4, sfx_gap_before=0.4, sfx_gap_after=0.5):
    """Build narration with SFX in gaps. SFX have fade in/out to prevent spikes."""
    result = []
    sfx_placements = []
    current_pos = 0

    gap_s = int(gap_between * SR)
    sfx_before_s = int(sfx_gap_before * SR)
    sfx_after_s = int(sfx_gap_after * SR)

    for i, (seg, audio) in enumerate(tts_results):
        if seg.kind == "sfx":
            sfx_clip = sfx_clips_map.get(seg.sfx_key)
            if sfx_clip is not None:
                sfx_clip = strip_silence(sfx_clip)
                # KEY FIX: normalize to 0.6 (not 0.8) and apply fade in/out
                sfx_clip = normalize_audio(sfx_clip, target_peak=0.6)
                sfx_clip = apply_fades(sfx_clip, fade_in_s=0.15, fade_out_s=0.15)
                vol = sfx_volumes.get(seg.sfx_key, 0.30)
                sfx_clip = sfx_clip * vol

                if sfx_before_s > 0:
                    result.append(np.zeros(sfx_before_s, dtype="float32"))
                    current_pos += sfx_before_s
                sfx_start = current_pos
                result.append(sfx_clip)
                current_pos += len(sfx_clip)
                sfx_placements.append((seg.sfx_key, sfx_start, len(sfx_clip)))
                if sfx_after_s > 0:
                    result.append(np.zeros(sfx_after_s, dtype="float32"))
                    current_pos += sfx_after_s
            else:
                print(f"    WARNING: No SFX clip for '{seg.sfx_key}'")
        elif audio is not None:
            if i > 0 and result:
                result.append(np.zeros(gap_s, dtype="float32"))
                current_pos += gap_s
            result.append(audio)
            current_pos += len(audio)

    return np.concatenate(result), sfx_placements


# === MUSIC with SFX ducking + always fade out ===

def build_music_smooth(segments, tts_results, music_plan, narrator_vol, character_vol, total_length, sfx_placements):
    """Build music with smooth volume, ducking during SFX, and fade out at end."""
    # Build segment timeline
    segment_timeline = []
    current_pos = 0
    gap_s = int(0.4 * SR)
    sfx_before_s = int(0.4 * SR)
    sfx_after_s = int(0.5 * SR)

    for i, (seg, audio) in enumerate(tts_results):
        if seg.kind == "sfx":
            if audio is not None:
                stripped = strip_silence(audio)
                current_pos += sfx_before_s + len(stripped) + sfx_after_s
        elif audio is not None:
            if i > 0: current_pos += gap_s
            start = current_pos
            current_pos += len(audio)
            segment_timeline.append((start, current_pos, seg.kind == "narrator"))

    # Build SFX presence map (when SFX is playing, duck music more)
    sfx_presence = np.zeros(total_length, dtype="float32")
    for sfx_key, sfx_start, sfx_len in sfx_placements:
        end = min(sfx_start + sfx_len, total_length)
        sfx_presence[sfx_start:end] = 1.0
    # Smooth the SFX presence
    sfx_presence = uniform_filter1d(sfx_presence, size=int(0.3 * SR), mode='nearest')

    # Raw volume envelope
    raw_vol = np.ones(total_length, dtype="float32") * narrator_vol
    for seg_start, seg_end, is_narrator in segment_timeline:
        raw_vol[seg_start:seg_end] = narrator_vol if is_narrator else character_vol
    smooth_vol = smooth_volume_envelope(raw_vol, smooth_seconds=2.0)

    # Duck music during SFX (reduce by 60% when SFX plays)
    smooth_vol = smooth_vol * (1.0 - 0.60 * sfx_presence)

    # Build music track
    music = np.zeros(total_length, dtype="float32")

    for plan_idx, plan in enumerate(music_plan):
        track_name = plan["track"]
        track_info = None
        if track_name in MUSIC_TRACKS: track_info = MUSIC_TRACKS[track_name]
        elif track_name in MUSICGEN_TRACKS: track_info = MUSICGEN_TRACKS[track_name]
        if not track_info or not os.path.exists(track_info["path"]):
            print(f"    WARNING: Music track '{track_name}' not found")
            continue

        track_audio = load_and_resample(track_info["path"], SR)
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
        if seg_length <= 0: continue

        track_segment = loop_to_length(track_audio, seg_length)
        local_vol = smooth_vol[start_sample:end_sample]

        # Gentle ducking during narration
        duck_depth = plan.get("duck", 0.35)
        narration_presence = np.zeros(seg_length, dtype="float32")
        for ss, se, isn in segment_timeline:
            if ss >= end_sample or se <= start_sample: continue
            ls = max(0, ss - start_sample)
            le = min(seg_length, se - start_sample)
            narration_presence[ls:le] = 1.0
        ducked_vol = local_vol * (1.0 - duck_depth * narration_presence * 0.25)

        track_segment = track_segment * ducked_vol

        # Crossfade between music segments
        fade_samples = int(1.0 * SR)
        if start_sample > 0 and fade_samples > 0:
            fi = np.linspace(0, 1, min(fade_samples, seg_length // 2))
            track_segment[:len(fi)] *= fi
            fo_end = min(start_sample + len(fi), total_length)
            music[start_sample:fo_end] *= np.linspace(1, 0, fo_end - start_sample)
        if plan_idx < len(music_plan) - 1 and fade_samples > 0:
            fo = np.linspace(1, 0, min(fade_samples, seg_length // 2))
            track_segment[-len(fo):] *= fo

        end_mix = min(start_sample + seg_length, total_length)
        music[start_sample:end_mix] += track_segment[:end_mix - start_sample]

    # KEY FIX: Always fade out music at end (3 seconds)
    fade_out_s = int(3.0 * SR)
    if fade_out_s > 0 and fade_out_s < len(music) // 2:
        music[-fade_out_s:] *= np.linspace(1, 0, fade_out_s)

    return music


# === BACKGROUND AMBIENCE ===

def build_background_ambience(bg_sfx_config, total_length, elevenlabs_key):
    if not bg_sfx_config:
        return np.zeros(total_length, dtype="float32")
    ambience = np.zeros(total_length, dtype="float32")
    for sfx_key, config in bg_sfx_config.items():
        duration = config.get("duration", 30.0)
        volume = config.get("volume", 0.08)
        loop = config.get("loop", True)
        prompt = config.get("prompt", sfx_key.replace("_", " ") + ", continuous background ambience")
        clip = generate_elevenlabs_sfx(sfx_key, prompt, min(duration, 10.0), elevenlabs_key)
        if clip is None: continue
        clip = strip_silence(clip)
        clip = normalize_audio(clip, target_peak=0.5)  # lower for background
        if loop:
            clip = loop_to_length(clip, total_length)
        clip = clip * volume
        # 3-second fade in/out for ambience
        clip = apply_fades(clip, fade_in_s=3.0, fade_out_s=3.0)
        ambience[:min(len(clip), total_length)] += clip[:total_length]
    return ambience


# === GROQ ===

def groq_generate_scene(api_key, system_prompt, user_prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = json.dumps({
        "model": "groq/compound",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.85,
        "max_tokens": 2000,
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 Python/3.12",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"]
            print(f"  Groq generated scene ({len(text)} chars)")
            return text
    except Exception as e:
        print(f"  Groq ERROR: {e}")
        return None


# === ELEVENLABS SFX ===

def generate_elevenlabs_sfx(sfx_key, prompt, duration, api_key):
    cache_path = os.path.join(SFX_DIR, f"elevenlabs_{sfx_key}.mp3")
    if os.path.exists(cache_path):
        audio, sr = sf.read(cache_path, dtype="float32")
        if sr != SR: audio = signal.resample(audio, int(len(audio) * SR / sr))
        if len(audio.shape) > 1: audio = audio.mean(axis=1)
        print(f"    SFX '{sfx_key}': cached ({len(audio)/SR:.1f}s)")
        return audio.astype("float32")
    url = "https://api.elevenlabs.io/v1/sound-generation"
    payload = json.dumps({"text": prompt, "duration_seconds": duration, "prompt_influence": 0.5}).encode()
    req = urllib.request.Request(url, data=payload, headers={
        "xi-api-key": api_key, "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 Python/3.12",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            with open(cache_path, "wb") as f: f.write(data)
            audio, sr = sf.read(cache_path, dtype="float32")
            if sr != SR: audio = signal.resample(audio, int(len(audio) * SR / sr))
            if len(audio.shape) > 1: audio = audio.mean(axis=1)
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
    print(f"  Loading Qwen3-TTS VoiceDesign...")
    qwen_model = load_model(MODEL_PATH)

    char_names = set(seg.speaker for seg in segments if seg.kind == "dialogue")
    scene_text = " ".join(seg.text for seg in segments)
    scene_lower = scene_text.lower()
    char_voice_map = {}
    male_assigned = female_assigned = False

    for name in sorted(char_names):
        name_lower = name.lower()
        ctx = ""
        idx = scene_lower.find(name_lower)
        while idx >= 0:
            ctx += scene_lower[max(0, idx-150):idx+150] + " "
            idx = scene_lower.find(name_lower, idx+1)
        has_f = any(p in ctx for p in [" she ", " her ", " hers "])
        has_m = any(p in ctx for p in [" he ", " his ", " him "])
        known_m = name_lower in ("kael", "garrick", "thorne", "thrain", "grimgold", "grimbold", "arin", "valoric", "riven")
        known_f = name_lower in ("lyra", "lira", "eira", "elian", "elara", "aria")
        if known_f or (has_f and not has_m and not known_m):
            char_voice_map[name] = "female"; female_assigned = True
        elif known_m or (has_m and not has_f):
            char_voice_map[name] = "male"; male_assigned = True
        else:
            if not male_assigned: char_voice_map[name] = "male"; male_assigned = True
            else: char_voice_map[name] = "female"; female_assigned = True

    print(f"  Character voice assignments: {char_voice_map}")
    os.makedirs(out_subdir, exist_ok=True)
    results = []

    for i, seg in enumerate(segments):
        if seg.kind == "sfx":
            results.append((seg, None)); continue
        if seg.kind == "narrator":
            voice_desc = narrator_voice_desc
            print(f"  [{i+1}/{len(segments)}] NARRATOR  text={seg.text[:60]}...")
        elif seg.kind == "dialogue":
            gender = char_voice_map.get(seg.speaker, "male")
            voice_desc = character_voice_descs[gender]
            print(f"  [{i+1}/{len(segments)}] DIALOGUE  {seg.speaker:10s} ({gender})  text={seg.text[:60]}...")
        else:
            results.append((seg, None)); continue

        prefix = f"seg_{i:03d}"
        try:
            mlx_generate(text=seg.text, model=qwen_model, instruct=voice_desc,
                         lang_code="en", max_tokens=2400, output_path=out_subdir,
                         file_prefix=prefix, audio_format="wav")
            generated = None
            for f in os.listdir(out_subdir):
                if f.startswith(prefix) and f.endswith(".wav"):
                    generated = os.path.join(out_subdir, f); break
            if generated:
                audio, sr = sf.read(generated, dtype="float32")
                if sr != SR: audio = signal.resample(audio, int(len(audio) * SR / sr))
                if len(audio.shape) > 1: audio = audio.mean(axis=1)
                results.append((seg, audio.astype("float32")))
                print(f"    -> {len(audio)/SR:.1f}s")
            else:
                results.append((seg, np.zeros(SR, dtype="float32")))
        except Exception as e:
            print(f"    -> ERROR: {e}")
            results.append((seg, np.zeros(SR, dtype="float32")))

    return results


# === MAIN PIPELINE ===

def run_scene(scene_config, groq_key, elevenlabs_key):
    print(f"\n{'='*60}")
    print(f"=== {scene_config['id'].upper()} ({scene_config['vibe']}) ===")
    print(f"{'='*60}")

    print("\n  Step 1: Generating scene with Groq...")
    scene_text = groq_generate_scene(groq_key, scene_config["groq_system"], scene_config["groq_user"])
    if not scene_text: return None
    scene_path = os.path.join(OUT_DIR, scene_config["scene_file"])
    with open(scene_path, "w") as f: f.write(scene_text)

    segments = parse_scene(scene_text)
    print(f"  Parsed: {len(segments)} segments")
    for i, s in enumerate(segments):
        if s.kind == "sfx": print(f"    {i:2d} [SFX] {s.sfx_key}")
        elif s.kind == "dialogue": print(f"    {i:2d} [{s.speaker:10s}] {s.text[:60]}")
        else: print(f"    {i:2d} [NARR] {s.text[:60]}")

    print(f"\n  Step 2: Generating TTS with Qwen3...")
    out_subdir = os.path.join(OUT_DIR, f"{scene_config['id']}_segments")
    tts_results = generate_qwen3_tts_all(
        segments, scene_config["narrator_voice"],
        scene_config["character_voices"], out_subdir)

    print(f"\n  Step 3: Generating SFX...")
    sfx_clips_map = {}
    for seg in segments:
        if seg.kind == "sfx" and seg.sfx_key not in sfx_clips_map:
            if seg.sfx_key in scene_config.get("background_sfx", {}): continue
            prompt = seg.sfx_key.replace("_", " ") + ", dramatic, cinematic, high quality"
            clip = generate_elevenlabs_sfx(seg.sfx_key, prompt, 3.0, elevenlabs_key)
            if clip is None:
                clip = (np.random.randn(int(SR*3)) * 0.3 * np.exp(-np.arange(int(SR*3))/SR*2)).astype("float32")
            sfx_clips_map[seg.sfx_key] = clip

    print(f"\n  Step 4: Building narration with SFX (fade in/out, no spikes)...")
    sfx_volumes = scene_config.get("sfx_volumes", {})
    narration, sfx_placements = build_narration_with_sfx_gaps(tts_results, sfx_clips_map, sfx_volumes)

    print(f"\n  Step 5: Building background ambience...")
    total_length = len(narration) + SR
    ambience = build_background_ambience(scene_config.get("background_sfx", {}), total_length, elevenlabs_key)

    print(f"\n  Step 6: Building music (smooth, SFX ducking, fade out)...")
    music = build_music_smooth(segments, tts_results, scene_config["music_plan"],
                                scene_config["narrator_music_vol"],
                                scene_config["character_music_vol"],
                                total_length, sfx_placements)

    print(f"\n  Step 7: Mixing + limiting...")
    if len(narration) < total_length:
        narration = np.concatenate([narration, np.zeros(total_length - len(narration), dtype="float32")])
    final = narration[:total_length] + music[:total_length] + ambience[:total_length]
    # Apply limiter to catch any remaining transients
    final = limiter(final, threshold=0.72)
    final = normalize_audio(final, target_peak=0.72)

    out_path = os.path.join(OUT_DIR, scene_config["name"])
    sf.write(out_path, final, SR)
    dur = len(final) / SR
    peak = np.abs(final).max()
    rms = np.sqrt(np.mean(final**2))
    print(f"\n  -> {out_path}")
    print(f"     Duration: {dur:.1f}s  Peak: {peak:.3f}  RMS: {rms:.4f}  Size: {os.path.getsize(out_path)//1024}KB")
    return out_path


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", type=int, default=None)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(SFX_DIR, exist_ok=True)

    env_path = os.path.join(HERE, ".env")
    elevenlabs_key = groq_key = None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("ELEVENLABS_API_KEY="): elevenlabs_key = line.split("=",1)[1]
            elif line.startswith("GROQ_API_KEY="): groq_key = line.split("=",1)[1]
    if not groq_key or not elevenlabs_key:
        print("ERROR: API keys not found"); sys.exit(1)

    scenes = [SCENES[args.only]] if args.only is not None else SCENES
    results = {}
    for cfg in scenes:
        try: results[cfg["id"]] = run_scene(cfg, groq_key, elevenlabs_key)
        except Exception as e:
            print(f"  {cfg['id']} FAILED: {e}")
            import traceback; traceback.print_exc()

    print(f"\n{'='*60}\n=== RESULTS ===\n{'='*60}")
    for name, path in results.items():
        if path and os.path.exists(path):
            print(f"  {name}: {path} ({os.path.getsize(path)//1024}KB)")
        else:
            print(f"  {name}: FAILED")


if __name__ == "__main__":
    main()
