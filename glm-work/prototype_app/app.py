"""Simple local web app for D&D narration TTS.

A minimal prototype that lets Arie:
1. Paste narration text from a Claude chat
2. Pick a TTS model (Kokoro PyTorch, Kokoro MLX, Qwen3-TTS VoiceDesign)
3. Pick a voice (preset for Kokoro, natural-language description for VoiceDesign)
4. Generate audio and play it back in the browser

This is a PROTOTYPE — not the final app. It exists to:
- Test the end-to-end workflow (paste → generate → listen)
- Compare models side-by-side in a real usage context
- Identify UX issues before building the real app

Run: python app.py
Open: http://localhost:8765
"""
import json
import os
import sys
import time
import uuid
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent.parent  # glm-work/
OUTPUT_DIR = ROOT / "outputs" / "app_generations"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8765

# Available models (lazy-loaded)
_MODELS = {}

def get_kokoro_pytorch():
    """Load Kokoro via PyTorch (original)."""
    if "kokoro_pt" not in _MODELS:
        from kokoro import KPipeline
        _MODELS["kokoro_pt"] = KPipeline(lang_code="a")
    return _MODELS["kokoro_pt"]

def get_kokoro_mlx():
    """Load Kokoro via MLX."""
    if "kokoro_mlx" not in _MODELS:
        from mlx_audio.tts import load_model
        _MODELS["kokoro_mlx"] = load_model("mlx-community/Kokoro-82M-bf16")
    return _MODELS["kokoro_mlx"]

def get_qwen3_voicedesign():
    """Load Qwen3-TTS VoiceDesign via MLX (local path, not HF repo ID)."""
    if "qwen3_vd" not in _MODELS:
        from mlx_audio.tts import load_model
        # Use local path — see run_qwen3_voicedesign.py for the Sonnet-caught bug rationale
        model_path = str(ROOT / "models" / "qwen3_voicedesign_8bit")
        _MODELS["qwen3_vd"] = load_model(model_path)
    return _MODELS["qwen3_vd"]

KOKORO_VOICES = [
    "af_heart", "af_bella", "af_sky", "af_nicole", "af_sarah", "af_emma",
    "am_michael", "am_adam", "am_eric", "am_liam",
    "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
]

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
<title>Narrator — D&D TTS Prototype</title>
<style>
body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; background: #1a1a2e; color: #e0e0e0; }
h1 { color: #e94560; }
textarea { width: 100%%; height: 200px; background: #16213e; color: #e0e0e0; border: 1px solid #0f3460; border-radius: 4px; padding: 10px; font-family: monospace; }
select, input[type=text] { background: #16213e; color: #e0e0e0; border: 1px solid #0f3460; border-radius: 4px; padding: 8px; margin: 5px 0; }
button { background: #e94560; color: white; border: none; border-radius: 4px; padding: 10px 20px; cursor: pointer; font-size: 16px; }
button:hover { background: #c73e54; }
button:disabled { background: #555; cursor: wait; }
.model-section { background: #16213e; padding: 15px; border-radius: 8px; margin: 10px 0; }
.voice-section { margin: 10px 0; }
#audio-player { margin: 20px 0; }
#status { color: #e94560; margin: 10px 0; }
label { display: block; margin: 5px 0 2px 0; color: #a0a0a0; }
.hint { font-size: 12px; color: #666; margin: 2px 0 10px 0; }
</style>
</head>
<body>
<h1>Narrator — D&D TTS Prototype</h1>
<p>Paste narration text from your Claude chat, pick a model and voice, generate audio.</p>

<div class="model-section">
<label>Model:</label>
<select id="model" onchange="onModelChange()">
<option value="kokoro_pt">Kokoro (PyTorch CPU) — 54 preset voices, fast</option>
<option value="kokoro_mlx">Kokoro (MLX Metal GPU) — 54 preset voices, may be faster</option>
<option value="qwen3_vd">Qwen3-TTS VoiceDesign (MLX) — describe voice in words</option>
</select>

<div id="voice-presets" class="voice-section">
<label>Voice (preset):</label>
<select id="voice">
</select>
<p class="hint">Kokoro ships 54 preset voices. af_ = American female, am_ = American male, bf/bm = British.</p>
</div>

<div id="voice-design" class="voice-section" style="display:none">
<label>Voice description (natural language):</label>
<input type="text" id="voice_desc" size="60" value="A calm, warm female narrator with a measured pace, suitable for reading fantasy fiction." />
<p class="hint">Describe the voice you want in words. Qwen3-TTS VoiceDesign will synthesize it.</p>
</div>
</div>

<div class="model-section">
<label>Narration text:</label>
<textarea id="text" placeholder="Paste your D&D narration here..."></textarea>
<p class="hint">For multi-speaker dialogue, use [S1] and [S2] tags. For VoiceDesign, the description applies to all text.</p>
</div>

<button id="generate-btn" onclick="generate()">Generate Audio</button>
<div id="status"></div>
<div id="audio-player"></div>

<script>
const KOKORO_VOICES = %s;

function onModelChange() {
    const model = document.getElementById('model').value;
    const presets = document.getElementById('voice-presets');
    const design = document.getElementById('voice-design');
    if (model === 'qwen3_vd') {
        presets.style.display = 'none';
        design.style.display = 'block';
    } else {
        presets.style.display = 'block';
        design.style.display = 'none';
    }
}

// Populate voice dropdown
const voiceSelect = document.getElementById('voice');
KOKORO_VOICES.forEach(v => {
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = v;
    voiceSelect.appendChild(opt);
});

async function generate() {
    const btn = document.getElementById('generate-btn');
    const status = document.getElementById('status');
    const player = document.getElementById('audio-player');
    const model = document.getElementById('model').value;
    const text = document.getElementById('text').value;
    const voice = document.getElementById('voice').value;
    const voiceDesc = document.getElementById('voice_desc').value;

    if (!text.trim()) {
        status.textContent = 'Please enter some text.';
        return;
    }

    btn.disabled = true;
    status.textContent = 'Generating... (this may take a while)';
    player.innerHTML = '';

    try {
        const params = new URLSearchParams();
        params.append('model', model);
        params.append('text', text);
        if (model === 'qwen3_vd') {
            params.append('voice_desc', voiceDesc);
        } else {
            params.append('voice', voice);
        }

        const response = await fetch('/generate', {
            method: 'POST',
            body: params
        });
        const result = await response.json();

        if (result.error) {
            status.textContent = 'Error: ' + result.error;
        } else {
            status.textContent = `Generated ${result.duration.toFixed(1)}s audio in ${result.gen_time.toFixed(1)}s (${result.rtf.toFixed(1)}x real-time)`;
            player.innerHTML = `<audio controls src="/audio/${result.filename}" style="width:100%%"></audio>`;
        }
    } catch (e) {
        status.textContent = 'Error: ' + e.message;
    }
    btn.disabled = false;
}
</script>
</body>
</html>
""" % json.dumps(KOKORO_VOICES)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())
        elif self.path.startswith('/audio/'):
            filename = self.path.split('/audio/')[1]
            filepath = OUTPUT_DIR / filename
            if filepath.exists():
                self.send_response(200)
                self.send_header('Content-Type', 'audio/wav')
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/generate':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length).decode()
            params = parse_qs(body)

            model_type = params.get('model', [''])[0]
            text = params.get('text', [''])[0]
            voice = params.get('voice', ['af_heart'])[0]
            voice_desc = params.get('voice_desc', [''])[0]

            try:
                result = self.generate_audio(model_type, text, voice, voice_desc)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def generate_audio(self, model_type, text, voice, voice_desc):
        filename = f"gen_{uuid.uuid4().hex[:8]}.wav"
        out_path = OUTPUT_DIR / filename

        t0 = time.time()

        if model_type == "kokoro_pt":
            pipeline = get_kokoro_pytorch()
            import torch
            import soundfile as sf
            import numpy as np
            ps, tokens = pipeline.g2p(text)
            chunks = []
            for result in pipeline.generate_from_tokens(tokens=tokens, voice=voice):
                chunks.append(result.audio)
            audio = torch.cat(chunks).cpu().numpy() if chunks else np.array([])
            sf.write(str(out_path), audio, 24000)
            sr = 24000

        elif model_type == "kokoro_mlx":
            model = get_kokoro_mlx()
            from mlx_audio.tts.generate import generate_audio as gen
            temp_prefix = f"temp_{uuid.uuid4().hex[:8]}"
            gen(text=text, model=model, voice=voice, lang_code="en",
                output_path=str(OUTPUT_DIR), file_prefix=temp_prefix,
                audio_format="wav", verbose=False)
            temp_file = OUTPUT_DIR / f"{temp_prefix}.wav"
            if temp_file.exists():
                temp_file.rename(out_path)
            import soundfile as sf
            audio, sr = sf.read(str(out_path))

        elif model_type == "qwen3_vd":
            model = get_qwen3_voicedesign()
            from mlx_audio.tts.generate import generate_audio as gen
            temp_prefix = f"temp_{uuid.uuid4().hex[:8]}"
            gen(text=text, model=model, instruct=voice_desc, lang_code="en",
                output_path=str(OUTPUT_DIR), file_prefix=temp_prefix,
                audio_format="wav", verbose=False)
            temp_file = OUTPUT_DIR / f"{temp_prefix}.wav"
            if temp_file.exists():
                temp_file.rename(out_path)
            import soundfile as sf
            audio, sr = sf.read(str(out_path))

        else:
            raise ValueError(f"Unknown model: {model_type}")

        dt = time.time() - t0
        duration = len(audio) / sr

        return {
            "filename": filename,
            "duration": duration,
            "gen_time": dt,
            "rtf": duration / dt if dt > 0 else 0,
        }

    def log_message(self, format, *args):
        print(f"[app] {args[0]}")


def main():
    print(f"[app] Narrator prototype starting on http://localhost:{PORT}")
    print(f"[app] Output directory: {OUTPUT_DIR}")
    server = HTTPServer(('localhost', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[app] Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
