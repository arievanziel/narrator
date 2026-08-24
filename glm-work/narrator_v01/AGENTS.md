# Narrator v0.1 — Build & Test Commands

## Running the app

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v01.app --port 5102
python -m narrator_v01.app --no-audio  # text-only mode
```

## Compile checks

```bash
cd glm-work/narrator_v01
python3 -c "import py_compile; [py_compile.compile(f, doraise=True) for f in ['app.py', 'game_loop.py', 'audio_queue.py', 'audio_engine.py', 'config.py', 'dm_engine.py']]"
```

## JS syntax check

```bash
cd glm-work && node -c narrator_v01/static/app.js
```

## Playwright smoke test

```bash
# Start the app first, then:
cd glm-work && node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto('http://localhost:PORT/', { waitUntil: 'networkidle' });
  console.log('Intro visible:', await page.isVisible('#intro-overlay'));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
"
```

## Architecture (v0.3.5+)

- `app.py` — HTTP server + routing only (thin)
- `game_loop.py` — turn orchestration, session state, budget tracking
- `audio_queue.py` — segment queue state machine (v0.4a)
- `audio_engine.py` — TTS generation, music mixing, loudness normalization
- `dm_engine.py` — LLM API calls, response parsing
- `config.py` — configuration constants
- `templates/index.html` — page structure
- `static/style.css` — extracted CSS
- `static/app.js` — extracted JavaScript

## API endpoints

- `GET /` — serve index.html
- `GET /static/{style.css,app.js}` — static assets
- `GET /api/queue_status?turn_id=...` — segment queue status (v0.4a)
- `GET /api/audio_status?turn_id=...` — legacy single-file audio status
- `GET /api/freetext_status?gen_id=...` — free-text TTS status
- `GET /api/state` — game state
- `GET /api/music?mood=...&source=...` — background music
- `GET /api/chronicle` — chronicle entries
- `GET /api/providers` — available LLM providers
- `GET /audio/segments/{turn_id}/seg_{index}.wav` — individual segment audio (v0.4a)
- `GET /audio/{turn_id}.wav` — legacy full-turn audio
- `POST /api/newgame` — start new game
- `POST /api/turn` — send player action
- `POST /api/save` / `POST /api/load` — save/load
- `POST /api/session_zero/{start,turn,finish}` — Session Zero wizard
- `POST /api/voice/{assign,list}` — voice assignment
- `POST /api/choices/pre_generate` — pre-generate choice audio (v0.4a)
- `POST /api/freetext/generate` — start free-text TTS (v0.4a)
- `POST /api/freetext/cancel` — cancel in-flight free-text TTS (v0.4a)
