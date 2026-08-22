#!/usr/bin/env python3
"""Narrator v0.3.5 — The D&D narration app.

HTTP server + routing ONLY. All business logic is in game_loop.py,
dm_engine.py, and audio_engine.py. Static files are served from
templates/ and static/.

Usage:
  cd glm-work && source .venv/bin/activate
  python -m narrator_v01.app --port 5102
  python -m narrator_v01.app --no-audio  # text-only mode
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure glm-work/ is on the path
GLM_WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GLM_WORK))

from dotenv import load_dotenv

from . import config
from .dm_engine import detect_provider
from .game_loop import (
    session, BudgetTracker,
    handle_newgame, handle_turn, handle_save, handle_load,
    handle_session_zero_start, handle_session_zero_turn, handle_session_zero_finish,
    handle_voice_assign, handle_voice_list,
    generate_choice_audio,
)
from .audio_queue import (
    get_queue, freetext_generator,
)

# Load .env
load_dotenv(GLM_WORK / ".env")

# Paths for static files
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

class NarratorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress logging

    def do_GET(self):
        parsed = urlparse(self.path)

        # Serve index.html
        if parsed.path == "/" or parsed.path == "/index.html":
            self._serve_file(TEMPLATES_DIR / "index.html", "text/html")

        # Serve static files
        elif parsed.path.startswith("/static/"):
            rel = parsed.path[len("/static/"):]
            file_path = STATIC_DIR / rel
            if file_path.exists() and file_path.is_file():
                ext = file_path.suffix.lower()
                ct = {".css": "text/css", ".js": "application/javascript",
                      ".png": "image/png", ".jpg": "image/jpeg",
                      ".svg": "image/svg+xml"}.get(ext, "application/octet-stream")
                self._serve_file(file_path, ct)
            else:
                self.send_response(404)
                self.end_headers()

        # Serve audio files (full turn WAV — legacy path)
        elif parsed.path.startswith("/audio/segments/"):
            # Segment-level audio: /audio/segments/{turn_id}/seg_{index}.wav
            parts = parsed.path.split("/")
            # parts: ['', 'audio', 'segments', '{turn_id}', 'seg_XXX.wav']
            if len(parts) >= 5:
                turn_id = parts[3]
                seg_file = parts[4]
                if not turn_id.replace("_", "").isalnum():
                    self.send_response(400)
                    self.end_headers()
                    return
                queue = get_queue(turn_id)
                if queue:
                    # Extract segment index from filename: seg_001.wav -> 1
                    try:
                        idx = int(seg_file.replace("seg_", "").replace(".wav", ""))
                    except ValueError:
                        self.send_response(400)
                        self.end_headers()
                        return
                    audio_path = queue.get_segment_audio_path(idx)
                    if audio_path and Path(audio_path).exists():
                        self._serve_file(Path(audio_path), "audio/wav")
                    else:
                        self.send_response(404)
                        self.end_headers()
                else:
                    self.send_response(404)
                    self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()

        elif parsed.path.startswith("/audio/"):
            turn_id = parsed.path.replace("/audio/", "").replace(".wav", "")
            if not turn_id.replace("_", "").isalnum():
                self.send_response(400)
                self.end_headers()
                return
            audio_path = config.OUTPUT_DIR / f"{turn_id}.wav"
            if audio_path.exists():
                self._serve_file(audio_path, "audio/wav")
            else:
                self.send_response(404)
                self.end_headers()

        # Audio status polling (legacy — single-file mode)
        elif parsed.path == "/api/audio_status":
            params = parse_qs(parsed.query)
            turn_id = params.get("turn_id", [""])[0]
            result = session.audio_results.get(turn_id)
            if result is None:
                self._json({"status": "unknown"})
            elif not result.get("done"):
                progress = result.get("progress", 0)
                segment_info = result.get("segment_info", "")
                self._json({"status": "generating", "progress": progress,
                            "segment_info": segment_info})
            elif result.get("error"):
                self._json({"status": "error", "error": result["error"]})
            elif result.get("audio_path"):
                self._json({
                    "status": "ready",
                    "audio_url": f"/audio/{turn_id}.wav",
                    "duration": result.get("duration", 0),
                })
            else:
                self._json({"status": "no_audio"})

        # Queue status polling (v0.4a — segment queue for live streaming)
        elif parsed.path == "/api/queue_status":
            params = parse_qs(parsed.query)
            turn_id = params.get("turn_id", [""])[0]
            queue = get_queue(turn_id)
            if queue is None:
                self._json({"status": "unknown"})
            else:
                self._json(queue.get_status())

        # Free-text audio status
        elif parsed.path == "/api/freetext_status":
            params = parse_qs(parsed.query)
            gen_id = params.get("gen_id", [""])[0]
            status = freetext_generator.get_status(gen_id if gen_id else None)
            if status is None:
                self._json({"status": "unknown"})
            else:
                self._json(status)

        # Game state
        elif parsed.path == "/api/state":
            if session.state:
                self._json({"state": session.state.to_dict()})
            else:
                self._json({"error": "no game"})

        # Music endpoint
        elif parsed.path == "/api/music":
            self._serve_music(parsed)

        # Chronicle
        elif parsed.path == "/api/chronicle":
            if session.state:
                self._json({"chronicle": session.state.chronicle})
            else:
                self._json({"chronicle": []})

        # Providers
        elif parsed.path == "/api/providers":
            self._json({
                "providers": [
                    {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash-Lite", "free": True, "available": True},
                    {"id": "openai/gpt-oss-120b", "name": "Groq GPT-OSS 120B", "free": True, "available": True},
                    {"id": "openai/gpt-oss-20b", "name": "Groq GPT-OSS 20B", "free": True, "available": True},
                    {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5", "free": False, "available": bool(os.getenv("ANTHROPIC_API_KEY"))},
                    {"id": "claude-sonnet-5", "name": "Claude Sonnet 5", "free": False, "available": bool(os.getenv("ANTHROPIC_API_KEY"))},
                ],
                "current_model": session.model,
                "budget": session.budget.to_dict() if session.budget else None,
            })

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len).decode() if content_len else "{}"
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        try:
            if parsed.path == "/api/newgame":
                self._json(handle_newgame(data))
            elif parsed.path == "/api/turn":
                self._json(handle_turn(data))
            elif parsed.path == "/api/save":
                self._json(handle_save())
            elif parsed.path == "/api/load":
                self._json(handle_load())
            elif parsed.path == "/api/session_zero/start":
                self._json(handle_session_zero_start(data))
            elif parsed.path == "/api/session_zero/turn":
                self._json(handle_session_zero_turn(data))
            elif parsed.path == "/api/session_zero/finish":
                self._json(handle_session_zero_finish(data))
            elif parsed.path == "/api/voice/assign":
                self._json(handle_voice_assign(data))
            elif parsed.path == "/api/voice/list":
                self._json(handle_voice_list())

            # v0.4a: Pre-generate choice audio
            elif parsed.path == "/api/choices/pre_generate":
                choices = data.get("choices", [])
                if not choices:
                    self._json({"error": "No choices provided"})
                else:
                    cq = generate_choice_audio(choices)
                    self._json({"started": True, "count": len(choices)})

            # v0.4a: Free-text audio generation (cancellable)
            elif parsed.path == "/api/freetext/generate":
                text = data.get("text", "").strip()
                if not text:
                    self._json({"error": "No text provided"})
                else:
                    from .game_loop import session as _session
                    gen_id = freetext_generator.generate(
                        text=text,
                        cast=_session.load_cast(),
                        tts_engine=_session.tts_engine,
                        speed=_session.tts_speed,
                    )
                    self._json({"gen_id": gen_id})

            elif parsed.path == "/api/freetext/cancel":
                freetext_generator.cancel()
                self._json({"cancelled": True})

            else:
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._json({"error": str(e)})

    def _serve_file(self, file_path: Path, content_type: str):
        """Serve a static file."""
        try:
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(500)
            self.end_headers()

    def _json(self, data):
        body = json.dumps(data, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_music(self, parsed):
        """Serve a continuous music stream based on current scene mood."""
        params = parse_qs(parsed.query)
        mood = params.get("mood", ["exploration"])[0]
        source = params.get("source", ["library"])[0]

        try:
            if source == "procedural":
                cache_path = config.OUTPUT_DIR / f"procedural_{mood}.wav"
                if not cache_path.exists():
                    from . import audio_engine
                    import soundfile as sf
                    data, sr = audio_engine.generate_procedural_ambient(30.0, mood)
                    sf.write(str(cache_path), data, sr)
                self._serve_file(cache_path, "audio/wav")
            else:
                from . import audio_engine
                track_path = audio_engine.select_music_track(mood)
                if track_path and Path(track_path).exists():
                    ext = Path(track_path).suffix.lower()
                    ct = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg"}.get(ext, "audio/mpeg")
                    self._serve_file(Path(track_path), ct)
                else:
                    self.send_response(404)
                    self.end_headers()
        except Exception as e:
            print(f"[server] Music endpoint error: {e}")
            try:
                self.send_response(500)
                self.end_headers()
            except:
                pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Narrator v0.3.5 - D&D story engine")
    parser.add_argument("--port", type=int, default=5102, help="Port (default 5102)")
    parser.add_argument("--model", default=config.DEFAULT_MODEL, help="DM model")
    parser.add_argument("--no-audio", action="store_true", help="Text-only mode")
    parser.add_argument("--budget", type=float, default=config.DEFAULT_BUDGET, help="USD budget cap")
    args = parser.parse_args()

    session.model = args.model
    session.provider = detect_provider(args.model)
    session.audio_enabled = not args.no_audio
    session.budget = BudgetTracker(args.budget)

    print(f"\n{'='*60}")
    print(f"  Narrator v0.3.5 - D&D Story Engine")
    print(f"  Model: {args.model} ({session.provider})")
    print(f"  Audio: {'enabled' if session.audio_enabled else 'disabled'}")
    print(f"  Budget: ${args.budget:.2f}")
    print(f"  URL: http://localhost:{args.port}")
    print(f"{'='*60}\n")

    # Pre-generate procedural music tracks
    if session.audio_enabled:
        try:
            from . import audio_engine
            import soundfile as sf
            moods = ["combat", "tense", "mystery", "exploration", "tavern", "sad", "horror"]
            for mood in moods:
                cache_path = config.OUTPUT_DIR / f"procedural_{mood}.wav"
                if not cache_path.exists():
                    print(f"[server] Pre-generating procedural music: {mood}...")
                    data, sr = audio_engine.generate_procedural_ambient(30.0, mood)
                    sf.write(str(cache_path), data, sr)
            print("[server] Procedural music tracks cached")
        except Exception as e:
            print(f"[server] Procedural music pre-gen failed: {e}")

    server = ThreadingHTTPServer(("0.0.0.0", args.port), NarratorHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()
