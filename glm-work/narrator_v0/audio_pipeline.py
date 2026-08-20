"""Audio pipeline for Narrator v0.

Takes the [AUDIO] section from the DM brain's response and produces a
fully mixed audio track: Qwen3 TTS for all voices + SFX in gaps (no voice
overlap) + music with scene-appropriate ducking.

Imports the proven audio utilities from produce_demos_v2.py:
  - parse_scene, SceneSegment
  - load_and_resample, strip_silence, rms_envelope, duck_track
  - loop_to_length, fade_in_out, crossfade, soft_clip, concatenate_audio
  - build_narration_with_sfx_gaps, build_music_track_with_transitions
  - generate_elevenlabs_sfx, synthesize_sfx
  - generate_live_music

The main entry point is render_narration() which takes the [AUDIO] text
and returns a WAV file path.
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from scipy import signal

# Add glm-work/ to path so we can import from produce_demos_v2.py
GLM_WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GLM_WORK))

# Import proven audio utilities from produce_demos_v2.py
from produce_demos_v2 import (
    SceneSegment,
    parse_scene,
    load_and_resample,
    strip_silence,
    rms_envelope,
    duck_track,
    loop_to_length,
    fade_in_out,
    crossfade,
    soft_clip,
    concatenate_audio,
    build_narration_with_sfx_gaps,
    build_music_track_with_transitions,
    generate_elevenlabs_sfx,
    synthesize_sfx,
    generate_live_music,
    MUSIC_TRACKS as DEMOS_MUSIC_TRACKS,
    SR as DEMOS_SR,
)

from . import config


# ---------------------------------------------------------------------------
# Cast management — character name -> Qwen3 voice description
# ---------------------------------------------------------------------------

def load_cast() -> dict:
    """Load the cast.json file with character voice assignments."""
    with open(config.CAST_FILE) as f:
        return json.load(f)


def get_voice_for_character(speaker: str, cast: dict, scene_text: str = "") -> str:
    """Get the Qwen3 voice description for a character.

    Priority:
    1. Exact match in cast.json
    2. Gender detection from known names + pronoun context
    3. Default voice (male)
    """
    # Exact match in cast
    if speaker in cast:
        return cast[speaker]

    # Try case-insensitive match
    for name, voice in cast.items():
        if name.startswith("_"):
            continue
        if name.lower() == speaker.lower():
            return voice

    # Gender detection
    speaker_lower = speaker.lower()
    scene_lower = scene_text.lower()

    # Check known names
    if speaker_lower in config.KNOWN_FEMALE_NAMES:
        return cast.get("_defaults", {}).get("female", config.DEFAULT_CHARACTER_VOICES["female"])
    if speaker_lower in config.KNOWN_MALE_NAMES:
        return cast.get("_defaults", {}).get("male", config.DEFAULT_CHARACTER_VOICES["male"])

    # Check pronouns near the name in scene text
    idx = scene_lower.find(speaker_lower)
    if idx >= 0:
        context = scene_lower[max(0, idx - 150):idx + 150]
        has_female = any(p in context for p in [" she ", " her ", " hers "])
        has_male = any(p in context for p in [" he ", " his ", " him "])
        if has_female and not has_male:
            return cast.get("_defaults", {}).get("female", config.DEFAULT_CHARACTER_VOICES["female"])
        if has_male and not has_female:
            return cast.get("_defaults", {}).get("male", config.DEFAULT_CHARACTER_VOICES["male"])

    # Default: male voice
    return cast.get("_defaults", {}).get("male", config.DEFAULT_CHARACTER_VOICES["male"])


# ---------------------------------------------------------------------------
# Scene mood detection from [AUDIO] section
# ---------------------------------------------------------------------------

def normalize_segments(segments: list) -> list:
    """Fix segment kinds after parse_scene.

    parse_scene treats [narrator] as a character name (dialogue kind).
    This converts any dialogue segment with speaker="narrator" (case-insensitive)
    to narrator kind, so it gets the narrator voice instead of a character voice.
    """
    for seg in segments:
        if seg.kind == "dialogue" and seg.speaker.lower() == "narrator":
            seg.kind = "narrator"
            seg.speaker = "narrator"
    return segments


def detect_scene_mood(audio_text: str) -> str:
    """Extract [SCENE: mood] from the [AUDIO] section.

    Returns the mood string, or "exploration" as default.
    """
    match = re.search(r'\[SCENE:\s*(\w+)\s*\]', audio_text, re.IGNORECASE)
    if match:
        mood = match.group(1).strip().lower()
        if mood in config.SCENE_MUSIC_MAP:
            return mood
        # Try partial match
        for key in config.SCENE_MUSIC_MAP:
            if key in mood or mood in key:
                return key
    return "exploration"


# ---------------------------------------------------------------------------
# Qwen3 TTS generation for all segments
# ---------------------------------------------------------------------------

_qwen_model = None  # lazy-loaded singleton

def _load_qwen_model():
    """Lazy-load the Qwen3 model (only once per session)."""
    global _qwen_model
    if _qwen_model is None:
        from mlx_audio.tts import load_model
        model_path = str(config.QWEN3_MODEL_PATH)
        print(f"  [audio] Loading Qwen3-TTS from {model_path}...")
        _qwen_model = load_model(model_path)
        print(f"  [audio] Qwen3 loaded.")
    return _qwen_model


def generate_tts_segments(segments: list, cast: dict, out_dir: Path,
                          scene_text: str = "") -> list:
    """Generate TTS audio for all narrator + dialogue segments using Qwen3.

    Returns list of (segment, audio_array) tuples.
    SFX segments get (segment, None).
    """
    from mlx_audio.tts.generate import generate_audio as mlx_generate

    model = _load_qwen_model()
    os.makedirs(out_dir, exist_ok=True)

    narrator_voice = cast.get("narrator", config.DEFAULT_NARRATOR_VOICE)
    results = []

    for i, seg in enumerate(segments):
        if seg.kind == "sfx":
            results.append((seg, None))
            continue

        if seg.kind == "narrator":
            voice_desc = narrator_voice
            label = "NARRATOR"
        elif seg.kind == "dialogue":
            voice_desc = get_voice_for_character(seg.speaker, cast, scene_text)
            label = seg.speaker
        else:
            results.append((seg, None))
            continue

        print(f"  [audio] [{i+1}/{len(segments)}] {label:12s} text={seg.text[:60]}...")

        prefix = f"seg_{i:03d}"
        try:
            mlx_generate(
                text=seg.text,
                model=model,
                instruct=voice_desc,
                lang_code=config.QWEN3_LANG_CODE,
                max_tokens=config.QWEN3_MAX_TOKENS,
                output_path=str(out_dir),
                file_prefix=prefix,
                audio_format="wav",
            )
            # Find the generated file (may have _000 suffix)
            generated = None
            for f in os.listdir(out_dir):
                if f.startswith(prefix) and f.endswith(".wav"):
                    generated = os.path.join(out_dir, f)
                    break
            if generated:
                audio, sr = sf.read(generated, dtype="float32")
                if sr != config.SR:
                    audio = signal.resample(audio, int(len(audio) * config.SR / sr))
                if len(audio.shape) > 1:
                    audio = audio.mean(axis=1)
                results.append((seg, audio.astype("float32")))
                print(f"    -> {len(audio)/config.SR:.1f}s")
            else:
                print(f"    -> FAILED, using silence")
                results.append((seg, np.zeros(config.SR, dtype="float32")))
        except Exception as e:
            print(f"    -> Qwen3 ERROR: {e}")
            results.append((seg, np.zeros(config.SR, dtype="float32")))

    return results


# ---------------------------------------------------------------------------
# SFX resolution — cached ElevenLabs + API generation + procedural fallback
# ---------------------------------------------------------------------------

def resolve_sfx(sfx_key: str, elevenlabs_key: Optional[str] = None) -> np.ndarray:
    """Get an SFX clip for the given key.

    Priority:
    1. Cached file in SFX_DIR (elevenlabs_{key}.mp3)
    2. Generate via ElevenLabs API (if key provided)
    3. Procedural synthesis fallback

    Returns silence-stripped audio array.
    """
    # Check cache first
    cache_path = config.SFX_DIR / f"elevenlabs_{sfx_key}.mp3"
    if cache_path.exists():
        audio, sr = sf.read(str(cache_path), dtype="float32")
        if sr != config.SR:
            audio = signal.resample(audio, int(len(audio) * config.SR / sr))
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        print(f"    [sfx] {sfx_key}: cached ({len(audio)/config.SR:.1f}s)")
        return strip_silence(audio.astype("float32"))

    # Try ElevenLabs API
    if elevenlabs_key:
        prompt = sfx_key.replace("_", " ") + ", dramatic, cinematic, high quality"
        clip = generate_elevenlabs_sfx(sfx_key, prompt, 3.0, elevenlabs_key)
        if clip is not None:
            return strip_silence(clip)

    # Procedural fallback
    print(f"    [sfx] {sfx_key}: procedural fallback")
    clip = synthesize_sfx(sfx_key, 3.0)
    return strip_silence(clip)


def resolve_all_sfx(segments: list, elevenlabs_key: Optional[str] = None) -> dict:
    """Resolve SFX for all sfx segments. Returns {sfx_key: audio_clip}."""
    sfx_clips = {}
    for seg in segments:
        if seg.kind == "sfx" and seg.sfx_key not in sfx_clips:
            sfx_clips[seg.sfx_key] = resolve_sfx(seg.sfx_key, elevenlabs_key)
    return sfx_clips


# ---------------------------------------------------------------------------
# Music selection and mixing
# ---------------------------------------------------------------------------

def select_music_track(mood: str) -> Optional[str]:
    """Select a music track name based on scene mood.

    Returns the track name (key in MUSIC_TRACKS), or None if no match.
    """
    track_name = config.SCENE_MUSIC_MAP.get(mood, config.SCENE_MUSIC_MAP.get("exploration"))
    if track_name and track_name in DEMOS_MUSIC_TRACKS:
        path = DEMOS_MUSIC_TRACKS[track_name]["path"]
        if os.path.exists(path):
            return track_name
    return None


def build_simple_music_track(tts_results: list, mood: str, total_length: int) -> np.ndarray:
    """Build a music track for a single scene mood.

    Simpler than build_music_track_with_transitions (which handles multi-track
    transitions) — v0 turns are short, so one track per turn is fine.

    Applies:
    - Different volume during narrator vs character dialogue
    - Side-chain ducking based on narration RMS
    - Fade in/out
    """
    track_name = select_music_track(mood)
    if track_name is None:
        return np.zeros(total_length, dtype="float32")

    track_info = DEMOS_MUSIC_TRACKS[track_name]
    track_audio = load_and_resample(str(track_info["path"]), config.SR)
    track_audio = loop_to_length(track_audio, total_length)
    track_audio = fade_in_out(track_audio)

    # Build segment timeline (narrator vs dialogue)
    segment_timeline = []
    current_pos = 0
    gap_samples = int(config.SPEECH_GAP * config.SR)
    sfx_before = int(config.SFX_GAP_BEFORE * config.SR)
    sfx_after = int(config.SFX_GAP_AFTER * config.SR)

    for i, (seg, audio) in enumerate(tts_results):
        if seg.kind == "sfx":
            if audio is not None:
                stripped = strip_silence(audio)
                current_pos += sfx_before + len(stripped) + sfx_after
        elif audio is not None:
            if i > 0:
                current_pos += gap_samples
            start = current_pos
            current_pos += len(audio)
            is_narrator = (seg.kind == "narrator")
            segment_timeline.append((start, current_pos, is_narrator))

    # Build volume envelope: narrator_vol during narrator, character_vol during dialogue
    vol_env = np.ones(total_length, dtype="float32") * config.DEFAULT_MUSIC_VOL
    for seg_start, seg_end, is_narrator in segment_timeline:
        if seg_start >= total_length or seg_end <= 0:
            continue
        local_start = max(0, seg_start)
        local_end = min(total_length, seg_end)
        vol = config.NARRATOR_MUSIC_VOL if is_narrator else config.CHARACTER_MUSIC_VOL
        vol_env[local_start:local_end] = vol

    # Smooth the volume envelope (0.5s transitions)
    smooth_samples = int(0.5 * config.SR)
    if smooth_samples > 0 and total_length > smooth_samples * 2:
        vol_env_smooth = np.copy(vol_env)
        for j in range(smooth_samples, total_length - smooth_samples):
            vol_env_smooth[j] = np.mean(vol_env[max(0, j - smooth_samples):min(total_length, j + smooth_samples)])
        vol_env = vol_env_smooth

    # Build narration presence envelope for ducking
    narration_presence = np.zeros(total_length, dtype="float32")
    for seg_start, seg_end, is_narrator in segment_timeline:
        if seg_start >= total_length or seg_end <= 0:
            continue
        local_start = max(0, seg_start)
        local_end = min(total_length, seg_end)
        narration_presence[local_start:local_end] = 1.0

    # Apply ducking
    ducked_vol = vol_env * (1.0 - config.DEFAULT_DUCK_DEPTH * narration_presence * 0.5)
    track_audio = track_audio[:total_length] * ducked_vol[:total_length]

    return track_audio


# ---------------------------------------------------------------------------
# Main entry point — render a full narration from [AUDIO] text
# ---------------------------------------------------------------------------

def render_narration(audio_text: str, turn_id: str = "turn",
                     elevenlabs_key: Optional[str] = None,
                     cast: Optional[dict] = None) -> Optional[str]:
    """Render the [AUDIO] section into a mixed WAV file.

    Args:
        audio_text: The [AUDIO] section text from the DM brain
        turn_id: Unique ID for this turn (used for output filenames)
        elevenlabs_key: ElevenLabs API key for SFX generation (optional)
        cast: Cast dict from load_cast() (loaded if None)

    Returns:
        Path to the generated WAV file, or None if audio_text is empty.
    """
    if not audio_text or not audio_text.strip():
        return None

    if cast is None:
        cast = load_cast()

    # Create output directories
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    turn_dir = config.SEGMENTS_DIR / turn_id
    turn_dir.mkdir(parents=True, exist_ok=True)

    t_start = time.time()

    # Step 1: Parse the [AUDIO] section into segments
    # Strip [SCENE: mood] tags before parsing (parse_scene doesn't handle them)
    audio_clean = re.sub(r'\[SCENE:\s*\w+\s*\]', '', audio_text, flags=re.IGNORECASE)
    segments = parse_scene(audio_clean)
    # Fix: parse_scene treats [narrator] as a character name; normalize it
    segments = normalize_segments(segments)

    if not segments:
        print(f"  [audio] No segments parsed from [AUDIO] section")
        return None

    print(f"  [audio] Parsed {len(segments)} segments from [AUDIO]")

    # Detect scene mood
    mood = detect_scene_mood(audio_text)
    print(f"  [audio] Scene mood: {mood}")

    # Step 2: Generate TTS for all narrator + dialogue segments
    print(f"  [audio] Generating TTS with Qwen3...")
    scene_text = " ".join(seg.text for seg in segments if seg.text)
    tts_results = generate_tts_segments(segments, cast, turn_dir, scene_text)

    # Step 3: Resolve SFX
    print(f"  [audio] Resolving SFX...")
    sfx_clips_map = resolve_all_sfx(segments, elevenlabs_key)

    # Step 4: Build narration track with SFX in gaps (no voice overlap)
    print(f"  [audio] Building narration with SFX in gaps...")
    narration, sfx_placements = build_narration_with_sfx_gaps(
        tts_results,
        sfx_clips_map,
        gap_between_segments=config.SPEECH_GAP,
        sfx_gap_before=config.SFX_GAP_BEFORE,
        sfx_gap_after=config.SFX_GAP_AFTER,
    )

    # Step 5: Build music track
    print(f"  [audio] Building music track (mood: {mood})...")
    total_length = len(narration) + config.SR  # 1 second tail
    music = build_simple_music_track(tts_results, mood, total_length)

    # Step 6: Mix narration + music
    print(f"  [audio] Mixing...")
    if len(narration) < total_length:
        narration = np.concatenate([narration, np.zeros(total_length - len(narration), dtype="float32")])
    final = narration[:total_length] + music[:total_length]
    final = soft_clip(final)

    # Save
    out_path = config.OUTPUT_DIR / f"{turn_id}.wav"
    sf.write(str(out_path), final, config.SR)

    elapsed = time.time() - t_start
    duration = len(final) / config.SR
    print(f"  [audio] Done: {out_path.name} ({duration:.1f}s, {elapsed:.1f}s to generate, "
          f"{os.path.getsize(out_path) // 1024}KB)")
    print(f"  [audio] SFX placements: {len(sfx_placements)} (all in gaps, no voice overlap)")

    return str(out_path)
