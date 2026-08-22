"""Audio segment queue — producer/consumer pipeline for live streaming.

Implements the segment-queue architecture from docs/AUDIO-STREAMING-DESIGN.md:
  PENDING → GENERATING → READY → PLAYING → DONE
  Failure path: FAILED → FALLBACK_GENERATING → READY/FAILED

The queue lives server-side.  The browser polls /api/queue_status to learn
which segments are READY and plays them in order, while later segments are
still being generated.

Three producers feed the queue:
  1. DM-response producer  — narration segments from the parsed [STORY]
  2. Player-input producer — preset-choice audio (pre-generated) and
     debounced free-text TTS (cancellable)
  3. Playback consumer      — browser, driven by polling

Quality/speed fallback uses a concrete lead-time rule (not a judgment call):
  if estimated_qwen3_gen_time > lead_time * 0.7:
      use kokoro (faster, RTF ~0.18)
  else:
      use qwen3  (better quality, RTF ~0.55)
"""
import os
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import config


# ---------------------------------------------------------------------------
# Segment state constants
# ---------------------------------------------------------------------------

PENDING = "PENDING"
GENERATING = "GENERATING"
READY = "READY"
PLAYING = "PLAYING"
DONE = "DONE"
FAILED = "FAILED"
FALLBACK_GENERATING = "FALLBACK_GENERATING"


# ---------------------------------------------------------------------------
# RTF measurements (from existing tts_fidelity_test.py results)
# ---------------------------------------------------------------------------

RTF_QWEN3 = 0.55   # ~0.5–0.6 measured
RTF_KOKORO = 0.18  # ~0.17–0.2 measured

# Speech rate: ~15 chars/sec of audio (empirical from existing segments)
CHARS_PER_SEC = 15.0

# Safety margin: if gen time > 70% of lead time, fall back to Kokoro
LEAD_TIME_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Segment data model
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    """A single audio segment in the queue."""
    index: int
    text: str
    speaker: str = "narrator"
    voice_desc: str = ""
    engine: str = ""           # selected TTS engine (qwen3/kokoro)
    state: str = PENDING
    audio_path: str = ""
    duration: float = 0.0
    gen_time: float = 0.0
    error: str = ""
    # Cancellation support
    _cancel_event: threading.Event = field(default_factory=threading.Event)

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self):
        self._cancel_event.set()

    def to_dict(self, turn_id: str = "") -> dict:
        audio_url = None
        if self.state in (READY, PLAYING, DONE) and self.audio_path:
            if turn_id:
                audio_url = f"/audio/segments/{turn_id}/seg_{self.index:03d}.wav"
            else:
                audio_url = f"/audio/{Path(self.audio_path).name}"
        return {
            "index": self.index,
            "state": self.state,
            "duration": round(self.duration, 2),
            "audio_url": audio_url,
            "text": self.text,
            "speaker": self.speaker,
            "engine": self.engine,
            "error": self.error or None,
        }


# ---------------------------------------------------------------------------
# Audio queue
# ---------------------------------------------------------------------------

class AudioQueue:
    """Ordered queue of audio segments with background generation.

    Thread-safe.  A single worker thread generates segments sequentially
    (respecting the single-GPU model lock in audio_engine.py).
    """

    def __init__(self, turn_id: str, segments_data: list,
                 cast: dict = None, tts_engine: str = "kokoro",
                 speed: float = 1.0, scene_mood: str = "exploration"):
        self.turn_id = turn_id
        self.cast = cast or {}
        self.tts_engine = tts_engine
        self.speed = speed
        self.scene_mood = scene_mood
        self.start_time = time.time()
        self._lock = threading.Lock()
        self._done = False
        self._error = None

        # Build segment objects
        self.segments: list[Segment] = []
        for i, seg in enumerate(segments_data):
            speaker = seg.get("speaker", "narrator")
            voice_desc = ""
            # We'll resolve voice_desc during generation to avoid importing
            # audio_engine at construction time
            self.segments.append(Segment(
                index=i,
                text=seg.get("text", ""),
                speaker=speaker,
            ))

        self._worker_thread: Optional[threading.Thread] = None

    # --- Generation ---

    def start(self):
        """Start background generation of all segments."""
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()

    def _worker(self):
        """Generate segments one by one in the background."""
        from . import audio_engine

        for seg in self.segments:
            if seg.is_cancelled:
                seg.state = FAILED
                seg.error = "cancelled"
                continue

            # Resolve voice description
            seg.voice_desc = audio_engine.get_voice_description(seg.speaker, self.cast)

            # Select engine based on lead time
            engine = self._select_engine(seg)
            seg.engine = engine

            # Skip if silent mode
            if self.tts_engine == "silent":
                seg.state = READY
                seg.duration = 0
                continue

            # Generate
            with self._lock:
                seg.state = GENERATING

            segments_dir = config.SEGMENTS_DIR / self.turn_id
            segments_dir.mkdir(parents=True, exist_ok=True)
            output_path = segments_dir / f"seg_{seg.index:03d}.wav"

            t0 = time.time()
            try:
                audio_path = audio_engine.generate_segment_tts(
                    text=seg.text,
                    voice_desc=seg.voice_desc,
                    output_path=str(output_path),
                    speed=self.speed,
                    engine=engine,
                    speaker=seg.speaker,
                )
                seg.gen_time = time.time() - t0

                # Get duration
                import soundfile as sf
                data, sr = sf.read(audio_path)
                seg.duration = len(data) / sr
                seg.audio_path = audio_path
                seg.state = READY

                print(f"[queue] Seg {seg.index}: {seg.duration:.1f}s in {seg.gen_time:.1f}s "
                      f"(RTF={seg.gen_time/seg.duration:.2f}) — {seg.speaker} ({engine})")

            except Exception as e:
                seg.gen_time = time.time() - t0
                seg.error = str(e)
                print(f"[queue] Seg {seg.index} FAILED with {engine}: {e}")

                # Fallback: try Kokoro if we were using Qwen3
                if engine != "kokoro":
                    with self._lock:
                        seg.state = FALLBACK_GENERATING
                    try:
                        audio_path = audio_engine.generate_segment_tts(
                            text=seg.text,
                            voice_desc=seg.voice_desc,
                            output_path=str(output_path),
                            speed=self.speed,
                            engine="kokoro",
                            speaker=seg.speaker,
                        )
                        import soundfile as sf
                        data, sr = sf.read(audio_path)
                        seg.duration = len(data) / sr
                        seg.audio_path = audio_path
                        seg.engine = "kokoro (fallback)"
                        seg.state = READY
                        print(f"[queue] Seg {seg.index}: recovered with Kokoro fallback")
                    except Exception as e2:
                        seg.error = f"{e}; fallback also failed: {e2}"
                        seg.state = FAILED
                        print(f"[queue] Seg {seg.index}: fallback also failed: {e2}")
                else:
                    seg.state = FAILED

        self._done = True

    def _select_engine(self, seg: Segment) -> str:
        """Select TTS engine based on lead time and quality/speed fallback rule.

        If the user selected a specific engine (not 'auto'), respect it.
        For 'auto', use the lead-time-based rule from the design doc.
        """
        if self.tts_engine == "kokoro":
            return "kokoro"
        if self.tts_engine == "qwen3":
            return "qwen3"
        if self.tts_engine == "silent":
            return "kokoro"  # won't actually generate

        # 'auto' mode — use lead-time-based fallback
        lead_time = self._estimate_lead_time(seg)
        est_qwen3_time = self._estimate_gen_time(seg.text, "qwen3")

        if lead_time <= 0:
            # No lead time — must use fastest engine
            return "kokoro"

        if est_qwen3_time > lead_time * LEAD_TIME_THRESHOLD:
            return "kokoro"
        return "qwen3"

    def _estimate_lead_time(self, seg: Segment) -> float:
        """Estimate how many seconds until this segment needs to play.

        = sum of durations of all previous segments
          - time already elapsed since generation started
        """
        lead = 0.0
        for s in self.segments[:seg.index]:
            if s.duration > 0:
                lead += s.duration
            else:
                # Estimate from text length
                lead += len(s.text) / CHARS_PER_SEC

        elapsed = time.time() - self.start_time
        return max(lead - elapsed, 0.0)

    def _estimate_gen_time(self, text: str, engine: str) -> float:
        """Estimate TTS generation time from text length and RTF."""
        est_audio_duration = len(text) / CHARS_PER_SEC
        rtf = RTF_QWEN3 if engine == "qwen3" else RTF_KOKORO
        return est_audio_duration * rtf

    # --- Status / queries ---

    def get_status(self) -> dict:
        """Return queue status for browser polling."""
        with self._lock:
            ready_count = sum(1 for s in self.segments if s.state == READY)
            total = len(self.segments)
            all_done = self._done or all(s.state in (DONE, FAILED) for s in self.segments)

            return {
                "turn_id": self.turn_id,
                "total": total,
                "ready": ready_count,
                "done": all_done,
                "error": self._error,
                "segments": [s.to_dict(self.turn_id) for s in self.segments],
            }

    def get_segment_audio_path(self, index: int) -> Optional[str]:
        """Get the audio file path for a ready segment."""
        if 0 <= index < len(self.segments):
            seg = self.segments[index]
            if seg.state in (READY, PLAYING, DONE) and seg.audio_path:
                return seg.audio_path
        return None

    def mark_playing(self, index: int):
        """Mark a segment as currently playing."""
        if 0 <= index < len(self.segments):
            with self._lock:
                self.segments[index].state = PLAYING

    def mark_done(self, index: int):
        """Mark a segment as finished playing."""
        if 0 <= index < len(self.segments):
            with self._lock:
                self.segments[index].state = DONE

    @property
    def is_done(self) -> bool:
        return self._done

    def cancel(self):
        """Cancel all pending generation."""
        for seg in self.segments:
            if seg.state in (PENDING, GENERATING):
                seg.cancel()


# ---------------------------------------------------------------------------
# Queue registry — maps turn_id to AudioQueue
# ---------------------------------------------------------------------------

_queues: dict[str, AudioQueue] = {}
_queues_lock = threading.Lock()


def register_queue(queue: AudioQueue):
    """Register a queue so the browser can poll it."""
    with _queues_lock:
        _queues[queue.turn_id] = queue


def get_queue(turn_id: str) -> Optional[AudioQueue]:
    """Get a registered queue by turn_id."""
    with _queues_lock:
        return _queues.get(turn_id)


def remove_queue(turn_id: str):
    """Remove a completed queue."""
    with _queues_lock:
        _queues.pop(turn_id, None)


# ---------------------------------------------------------------------------
# Choice audio pre-generation
# ---------------------------------------------------------------------------

class ChoiceAudioQueue:
    """Pre-generates audio for all preset choices when suggestions arrive.

    Short strings, generated in parallel-ish (sequential on single GPU).
    Only one will actually be used — acceptable waste for the latency win.
    """

    def __init__(self, choices: list[str], cast: dict = None,
                 tts_engine: str = "kokoro", speed: float = 1.0):
        self.choices = choices
        self.cast = cast or {}
        self.tts_engine = tts_engine
        self.speed = speed
        self._results: dict[int, dict] = {}  # choice_index -> {audio_path, duration, state}
        self._lock = threading.Lock()
        self._done = False
        self._cancel = threading.Event()

        # Build segments for the choices
        self.segments: list[Segment] = []
        for i, text in enumerate(choices):
            self.segments.append(Segment(
                index=i,
                text=text,
                speaker="player",
            ))

    def start(self):
        """Start background generation of all choice audio."""
        t = threading.Thread(target=self._worker, daemon=True)
        t.start()

    def _worker(self):
        from . import audio_engine

        segments_dir = config.SEGMENTS_DIR / f"choices_{int(time.time())}"
        segments_dir.mkdir(parents=True, exist_ok=True)

        for seg in self.segments:
            if self._cancel.is_set():
                break

            # Choices are short — always use Kokoro for speed
            engine = "kokoro" if self.tts_engine != "qwen3" else "kokoro"
            voice_desc = audio_engine.get_voice_description("player", self.cast)

            output_path = segments_dir / f"choice_{seg.index:03d}.wav"

            with self._lock:
                seg.state = GENERATING

            try:
                audio_path = audio_engine.generate_segment_tts(
                    text=seg.text,
                    voice_desc=voice_desc,
                    output_path=str(output_path),
                    speed=self.speed,
                    engine=engine,
                    speaker="player",
                )
                import soundfile as sf
                data, sr = sf.read(audio_path)
                seg.duration = len(data) / sr
                seg.audio_path = audio_path
                seg.state = READY
            except Exception as e:
                seg.error = str(e)
                seg.state = FAILED
                print(f"[choice-audio] Choice {seg.index} failed: {e}")

        self._done = True

    def get_choice_audio(self, index: int) -> Optional[dict]:
        """Get pre-generated audio for a specific choice."""
        if 0 <= index < len(self.segments):
            seg = self.segments[index]
            if seg.state == READY and seg.audio_path:
                return {"audio_path": seg.audio_path, "duration": seg.duration}
        return None

    def get_status(self) -> dict:
        with self._lock:
            return {
                "total": len(self.segments),
                "ready": sum(1 for s in self.segments if s.state == READY),
                "done": self._done,
                "choices": [s.to_dict() for s in self.segments],
            }

    def cancel(self):
        self._cancel.set()

    @property
    def is_done(self) -> bool:
        return self._done


# ---------------------------------------------------------------------------
# Free-text audio generation (cancellable, debounced)
# ---------------------------------------------------------------------------

class FreeTextGenerator:
    """Cancellable TTS generation for free-text player input.

    The browser debounces typing (2-3 words / ~1s of inactivity) and sends
    the text here.  If more input arrives, the browser calls cancel() and
    starts a new generation — no stale audio plays.
    """

    def __init__(self):
        self._current: Optional[dict] = None
        self._lock = threading.Lock()
        self._gen_id = 0

    def generate(self, text: str, cast: dict = None,
                 tts_engine: str = "kokoro", speed: float = 1.0) -> str:
        """Start generating audio for free text.  Returns a generation ID.

        If a previous generation is in flight, it is cancelled.
        """
        with self._lock:
            self._gen_id += 1
            gen_id = f"freetext_{self._gen_id}"
            self._current = {
                "gen_id": gen_id,
                "text": text,
                "state": GENERATING,
                "audio_path": None,
                "duration": 0,
                "cancel": threading.Event(),
            }

        # Start generation in background
        t = threading.Thread(
            target=self._worker,
            args=(gen_id, text, cast, tts_engine, speed),
            daemon=True,
        )
        t.start()
        return gen_id

    def _worker(self, gen_id: str, text: str, cast: dict,
                tts_engine: str, speed: float):
        from . import audio_engine

        current = self._current
        if current is None or current["gen_id"] != gen_id:
            return  # superseded by a newer generation

        cancel_event = current["cancel"]

        if cancel_event.is_set():
            return

        # Always use Kokoro for free text (short, needs to be fast)
        engine = "kokoro"
        voice_desc = audio_engine.get_voice_description("player", cast)

        segments_dir = config.SEGMENTS_DIR / "freetext"
        segments_dir.mkdir(parents=True, exist_ok=True)
        output_path = segments_dir / f"{gen_id}.wav"

        try:
            audio_path = audio_engine.generate_segment_tts(
                text=text,
                voice_desc=voice_desc,
                output_path=str(output_path),
                speed=speed,
                engine=engine,
                speaker="player",
            )

            if cancel_event.is_set():
                return  # stale — don't update state

            import soundfile as sf
            data, sr = sf.read(audio_path)
            duration = len(data) / sr

            with self._lock:
                if self._current and self._current["gen_id"] == gen_id:
                    self._current["state"] = READY
                    self._current["audio_path"] = audio_path
                    self._current["duration"] = duration

        except Exception as e:
            with self._lock:
                if self._current and self._current["gen_id"] == gen_id:
                    self._current["state"] = FAILED
                    self._current["error"] = str(e)
            print(f"[freetext] Generation failed: {e}")

    def cancel(self):
        """Cancel the current generation."""
        with self._lock:
            if self._current:
                self._current["cancel"].set()
                self._current["state"] = FAILED
                self._current["error"] = "cancelled"

    def get_status(self, gen_id: str = None) -> Optional[dict]:
        """Get status of the current or specified generation."""
        with self._lock:
            if not self._current:
                return None
            if gen_id and self._current["gen_id"] != gen_id:
                return {"state": "superseded"}
            current = self._current.copy()
            # Don't expose the cancel event
            current.pop("cancel", None)
            return current


# Singleton free-text generator
freetext_generator = FreeTextGenerator()
