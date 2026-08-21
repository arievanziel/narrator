"""Narrator v0.1 — Audio Engine.

Generates TTS for story segments in parallel, mixes with music, outputs WAV.
Key requirement: the text shown on screen = the text spoken by TTS (word for word).

Uses Qwen3-TTS VoiceDesign via mlx_audio for all voices.
Generates segments sequentially (single GPU) but efficiently — model stays loaded.
"""
import os
import re
import time
import threading
import numpy as np
import soundfile as sf
from pathlib import Path
from scipy.io import wavfile
from scipy.signal import resample_poly

from . import config

# ---------------------------------------------------------------------------
# Model singleton — stays loaded across calls
# ---------------------------------------------------------------------------

_qwen_gen = None
_qwen_model_obj = None
_qwen_lock = threading.Lock()

_kokoro_pipeline = None
_kokoro_lock = threading.Lock()


def get_qwen_model():
    """Lazy-load Qwen3 model (singleton, thread-safe).

    Pre-loads the model into memory so subsequent calls are ~0.7s instead of ~4s.
    """
    global _qwen_gen, _qwen_model_obj
    if _qwen_gen is None:
        with _qwen_lock:
            if _qwen_gen is None:
                from mlx_audio.tts import generate as gen
                from mlx_audio.utils import load_model
                from pathlib import Path
                _qwen_gen = gen
                # Pre-load the model
                model_path = Path(config.QWEN3_MODEL_PATH)
                if model_path.exists():
                    print("[audio] Pre-loading Qwen3 model...")
                    t0 = time.time()
                    _qwen_model_obj = load_model(model_path)
                    print(f"[audio] Qwen3 model loaded in {time.time()-t0:.1f}s")
                else:
                    print(f"[audio] WARNING: Model not found at {model_path}")
    return _qwen_gen, _qwen_model_obj


def get_kokoro_pipeline():
    """Lazy-load Kokoro pipeline (singleton, thread-safe)."""
    global _kokoro_pipeline
    if _kokoro_pipeline is None:
        with _kokoro_lock:
            if _kokoro_pipeline is None:
                from kokoro import KPipeline
                print("[audio] Loading Kokoro pipeline...")
                t0 = time.time()
                _kokoro_pipeline = KPipeline(lang_code='a')  # American English
                print(f"[audio] Kokoro pipeline loaded in {time.time()-t0:.1f}s")
    return _kokoro_pipeline


# ---------------------------------------------------------------------------
# Voice assignment
# ---------------------------------------------------------------------------

def get_voice_description(speaker: str, cast: dict = None) -> str:
    """Get Qwen3 voice description for a speaker."""
    if cast and speaker in cast:
        return cast[speaker]
    if speaker.lower() == "narrator":
        return config.NARRATOR_VOICE
    # Gender detection
    speaker_lower = speaker.lower()
    for male_name in config.KNOWN_MALE:
        if male_name.lower() in speaker_lower:
            return config.DEFAULT_MALE_VOICE
    for female_name in config.KNOWN_FEMALE:
        if female_name.lower() in speaker_lower:
            return config.DEFAULT_FEMALE_VOICE
    # Default: male voice
    return config.DEFAULT_MALE_VOICE


# ---------------------------------------------------------------------------
# TTS generation
# ---------------------------------------------------------------------------

def generate_segment_tts(text: str, voice_desc: str, output_path: str,
                          speed: float = 1.0, engine: str = "qwen3") -> str:
    """Generate TTS for a single text segment.

    engine: 'qwen3' (VoiceDesign, expressive) or 'kokoro' (fast, simple)
    Returns path to the generated WAV file.
    """
    if engine == "kokoro":
        return generate_segment_kokoro(text, voice_desc, output_path, speed)
    else:
        return generate_segment_qwen3(text, voice_desc, output_path, speed)


def generate_segment_qwen3(text: str, voice_desc: str, output_path: str,
                            speed: float = 1.0) -> str:
    """Generate TTS using Qwen3 VoiceDesign."""
    gen, model_obj = get_qwen_model()

    output_dir = str(Path(output_path).parent)
    prefix = Path(output_path).stem
    model_arg = model_obj if model_obj else config.QWEN3_MODEL_PATH

    gen.generate_audio(
        text=text, model=model_arg, voice="af_heart",
        instruct=voice_desc, speed=speed, lang_code="en",
        output_path=output_dir, file_prefix=prefix,
        audio_format="wav", save=True, verbose=False,
    )

    generated = Path(output_dir) / f"{prefix}.wav"
    if generated.exists():
        return str(generated)
    files = list(Path(output_dir).glob(f"{prefix}*.wav"))
    if files:
        return str(files[0])
    raise FileNotFoundError(f"TTS output not found: {output_path}")


# Kokoro voice mapping (character name → Kokoro voice ID)
KOKORO_VOICES = {
    "narrator": "am_michael",  # mature male narrator
    "male": "am_michael",
    "female": "af_heart",
    "goblin": "am_adam",  # deeper, rougher
    "old": "am_george",
}

def generate_segment_kokoro(text: str, voice_desc: str, output_path: str,
                             speed: float = 1.0) -> str:
    """Generate TTS using Kokoro (faster, less expressive than Qwen3)."""
    pipeline = get_kokoro_pipeline()

    # Select voice based on description keywords
    voice = "am_michael"  # default
    desc_lower = voice_desc.lower()
    if "female" in desc_lower or "woman" in desc_lower or "girl" in desc_lower:
        voice = "af_heart"
    elif "young" in desc_lower:
        voice = "am_adam"
    elif "old" in desc_lower or "aged" in desc_lower:
        voice = "am_george"
    elif "narrator" in desc_lower:
        voice = "am_michael"

    # Generate
    import numpy as np
    generator = pipeline(text, voice=voice, speed=speed)
    for i, (gs, ps, audio) in enumerate(generator):
        sf.write(output_path, audio, 24000)
        return output_path

    # Fallback: silence
    sr = 24000
    silence = np.zeros(int(sr * 0.5), dtype=np.float32)
    sf.write(output_path, silence, sr)
    return output_path


def generate_all_segments(segments: list, turn_id: str, cast: dict = None,
                           speed: float = 1.0, engine: str = "qwen3") -> list:
    """Generate TTS for all story segments.

    Returns list of {segment, audio_path, duration} dicts.
    """
    results = []
    segments_dir = config.SEGMENTS_DIR / turn_id
    segments_dir.mkdir(parents=True, exist_ok=True)

    for i, seg in enumerate(segments):
        voice_desc = get_voice_description(seg["speaker"], cast)
        output_path = segments_dir / f"seg_{i:03d}.wav"

        try:
            t0 = time.time()
            audio_path = generate_segment_tts(
                text=seg["text"], voice_desc=voice_desc,
                output_path=str(output_path), speed=speed, engine=engine,
            )
            elapsed = time.time() - t0

            # Get duration
            data, sr = sf.read(audio_path)
            duration = len(data) / sr
            results.append({
                "segment": seg,
                "audio_path": audio_path,
                "duration": duration,
                "gen_time": elapsed,
            })
            print(f"[audio] Segment {i}: {duration:.1f}s audio in {elapsed:.1f}s "
                  f"(RTF={elapsed/duration:.2f}) — {seg['speaker']}")
        except Exception as e:
            print(f"[audio] Segment {i} FAILED: {e}")
            # Create silence fallback
            sr = 24000
            silence = np.zeros(int(sr * 0.5), dtype=np.float32)
            sf.write(str(output_path), silence, sr)
            results.append({
                "segment": seg,
                "audio_path": str(output_path),
                "duration": 0.5,
                "gen_time": 0,
                "error": str(e),
            })

    return results


# ---------------------------------------------------------------------------
# Audio mixing — combine speech segments with gaps + music
# ---------------------------------------------------------------------------

def load_audio(path: str, target_sr: int = 24000) -> tuple:
    """Load audio file, resample to target SR. Returns (data, sr)."""
    data, sr = sf.read(path)
    if sr != target_sr:
        # Resample
        from scipy.signal import resample_poly
        data = resample_poly(data, target_sr, sr)
    if len(data.shape) > 1:
        data = data[:, 0]  # mono
    return data.astype(np.float32), target_sr


def select_music_track(scene_mood: str) -> str:
    """Select a music track based on scene mood."""
    mood = scene_mood.lower().strip()
    track_key = config.SCENE_MUSIC_MAP.get(mood, config.SCENE_MUSIC_MAP["default"])
    track_path = config.MUSIC_TRACKS.get(track_key)
    if track_path and track_path.exists():
        return str(track_path)
    # Try any available track as fallback
    for path in config.MUSIC_TRACKS.values():
        if path.exists():
            return str(path)
    return None


def generate_procedural_ambient(duration: float, mood: str = "calm",
                                 target_sr: int = 24000) -> tuple:
    """Generate procedural ambient music as a second music source.

    Uses simple synthesis: low drone + filtered noise + occasional tones.
    """
    samples = int(duration * target_sr)
    t = np.linspace(0, duration, samples)

    # Base drone (low frequency)
    base_freq = {"calm": 110, "tense": 87, "mystery": 98, "combat": 65,
                 "horror": 55, "sad": 73, "exploration": 123}.get(mood, 110)
    drone = 0.15 * np.sin(2 * np.pi * base_freq * t)
    # Add a fifth above
    drone += 0.08 * np.sin(2 * np.pi * base_freq * 1.5 * t)
    # Add subtle vibrato
    drone *= 1 + 0.02 * np.sin(2 * np.pi * 0.3 * t)

    # Filtered noise for texture
    noise = np.random.randn(samples) * 0.02
    # Simple low-pass: moving average
    window = int(0.05 * target_sr)
    if window > 0 and len(noise) > window:
        kernel = np.ones(window) / window
        noise = np.convolve(noise, kernel, mode='same')

    # Occasional bell tones for atmosphere
    bell_times = np.random.choice(samples, size=min(5, max(1, int(duration / 8))), replace=False)
    bells = np.zeros(samples)
    for bt in bell_times:
        bell_freq = base_freq * 2 * (1 + np.random.choice([0, 2, 4, 7]) / 12)
        decay = np.exp(-3 * (t - bt / target_sr))
        decay[decay > 1] = 0
        bells += 0.1 * np.sin(2 * np.pi * bell_freq * t) * decay

    ambient = drone + noise + bells
    # Fade in/out
    fade = int(2.0 * target_sr)
    if len(ambient) > fade * 2:
        ambient[:fade] *= np.linspace(0, 1, fade)
        ambient[-fade:] *= np.linspace(1, 0, fade)

    return ambient.astype(np.float32), target_sr


def load_music(path: str, target_duration: float, target_sr: int = 24000) -> tuple:
    """Load music file, loop/trim to target duration. Returns (data, sr)."""
    try:
        data, sr = sf.read(path)
        if len(data.shape) > 1:
            data = data[:, 0]  # mono
        data = data.astype(np.float32)

        # Resample if needed
        if sr != target_sr:
            data = resample_poly(data, target_sr, sr)
            sr = target_sr

        # Loop or trim to target duration
        target_samples = int(target_duration * target_sr)
        if len(data) < target_samples:
            # Loop
            loops = (target_samples // len(data)) + 1
            data = np.tile(data, loops)
        data = data[:target_samples]

        # Fade in/out (2 seconds each)
        fade_samples = int(2.0 * target_sr)
        if len(data) > fade_samples * 2:
            data[:fade_samples] *= np.linspace(0, 1, fade_samples)
            data[-fade_samples:] *= np.linspace(1, 0, fade_samples)

        return data, sr
    except Exception as e:
        print(f"[audio] Music load failed: {e}")
        return np.zeros(int(target_duration * target_sr), dtype=np.float32), target_sr


def mix_narration(segment_results: list, music_path: str = None,
                   music_volume: float = 0.12, music_source: str = "library",
                   scene_mood: str = "calm") -> tuple:
    """Mix speech segments with gaps and background music.

    music_source: 'library' (use music files) or 'procedural' (synthesized ambient)
    Returns (mixed_audio, sample_rate).
    """
    target_sr = 24000
    gap = config.SPEECH_GAP

    # Calculate total duration with gaps
    total_speech = sum(r["duration"] for r in segment_results)
    total_gaps = gap * (len(segment_results) - 1) if len(segment_results) > 1 else 0
    total_duration = total_speech + total_gaps + 1.0  # +1s lead-in

    # Build speech track
    speech_track = np.zeros(int(total_duration * target_sr), dtype=np.float32)
    pos = int(1.0 * target_sr)  # 1s lead-in

    for r in segment_results:
        audio_data, _ = load_audio(r["audio_path"], target_sr)
        end = pos + len(audio_data)
        if end > len(speech_track):
            speech_track = np.pad(speech_track, (0, end - len(speech_track)))
        speech_track[pos:end] += audio_data
        pos = end + int(gap * target_sr)

    # Trim or pad to actual content end
    actual_end = pos
    speech_track = speech_track[:actual_end]

    # Load and mix music
    if music_source == "procedural":
        music_data, _ = generate_procedural_ambient(
            len(speech_track) / target_sr, scene_mood, target_sr)
    elif music_path:
        music_data, _ = load_music(music_path, len(speech_track) / target_sr, target_sr)
        # Duck music during speech — lower volume where speech is present
        music_gain = np.ones(len(speech_track), dtype=np.float32) * music_volume
        # Simple ducking: reduce music where speech amplitude is high
        speech_envelope = np.abs(speech_track)
        # Smooth the envelope
        window = int(0.1 * target_sr)
        if len(speech_envelope) > window:
            kernel = np.ones(window) / window
            speech_envelope_smooth = np.convolve(speech_envelope, kernel, mode='same')
            # Duck to 30% where speech is present
            duck_factor = 1.0 - 0.7 * np.clip(speech_envelope_smooth * 5, 0, 1)
            music_gain *= duck_factor

        music_track = music_data[:len(speech_track)] * music_gain[:len(music_data)]
        if len(music_track) < len(speech_track):
            music_track = np.pad(music_track, (0, len(speech_track) - len(music_track)))

        mixed = speech_track + music_track
    else:
        mixed = speech_track

    # Normalize to prevent clipping
    max_val = np.max(np.abs(mixed))
    if max_val > 0.95:
        mixed = mixed * (0.95 / max_val)

    return mixed, target_sr


def render_narration(segments: list, scene_mood: str, turn_id: str,
                     cast: dict = None, tts_engine: str = "qwen3",
                     speed: float = 1.0, music_enabled: bool = True,
                     music_source: str = "library", music_volume: float = 0.12) -> dict:
    """Full narration rendering pipeline.

    music_source: 'library' (curated files) or 'procedural' (synthesized ambient)
    Returns {audio_path, duration, segment_count, gen_time, errors}
    """
    t0 = time.time()

    # Generate TTS for all segments
    if tts_engine == "silent":
        # No TTS — just return empty
        return {"audio_path": None, "duration": 0, "segment_count": 0,
                "gen_time": 0, "errors": ["TTS disabled"]}

    segment_results = generate_all_segments(segments, turn_id, cast, speed, tts_engine)

    # Select music
    music_path = None
    if music_enabled and music_source == "library":
        music_path = select_music_track(scene_mood)
        if music_path:
            print(f"[audio] Music: {scene_mood} → {Path(music_path).name}")
    elif music_enabled and music_source == "procedural":
        print(f"[audio] Procedural ambient: {scene_mood}")

    # Mix
    mixed, sr = mix_narration(segment_results, music_path,
                               music_volume=music_volume,
                               music_source=music_source if music_enabled else "none",
                               scene_mood=scene_mood)

    # Save
    output_path = config.OUTPUT_DIR / f"{turn_id}.wav"
    sf.write(str(output_path), mixed, sr)

    total_gen = time.time() - t0
    duration = len(mixed) / sr

    print(f"[audio] Rendered {duration:.1f}s audio in {total_gen:.1f}s "
          f"(RTF={total_gen/duration:.2f}) — {len(segment_results)} segments")

    return {
        "audio_path": str(output_path),
        "duration": round(duration, 1),
        "segment_count": len(segment_results),
        "gen_time": round(total_gen, 1),
        "rtf": round(total_gen / duration, 3) if duration > 0 else 0,
        "errors": [r.get("error") for r in segment_results if r.get("error")],
    }
