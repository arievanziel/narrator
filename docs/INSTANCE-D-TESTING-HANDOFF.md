# Instance D — Testing: Regression Sweep and Soak Test

**Created by:** Instance A (main programmer), 2026-08-24
**Source:** `docs/GLM-V1-FINISH-INSTRUCTIONS.md` + `docs/V1-PLAN.md` v0.9/v1.0

## Your role

You are the stability/regression instance. Your job is to verify that the work of Instances A, B, and C lands cleanly and the app is ready for Arie to playtest.

## Timing

**You start after A, B, and C have all finished their code changes.** Do not start testing until all three report done.

## Phase 1 — Test suite verification

Run the full test suite and confirm all tests pass:

```bash
cd glm-work && source .venv/bin/activate
for t in narrator_v01/test_*.py; do echo "=== $t ==="; python "$t" 2>&1 | tail -4; done
```

Baseline: 74 tests across 8 files (test_context: 9, test_dc_roll: 15, test_facade: 11, test_golden: 8, test_guards: 9, test_procedural: 7, test_trickster: 16, test_world_store: 15).

If any test fails:
1. Read the failure output
2. Determine if it's a real regression or a test that needs updating due to intentional behavior change
3. If real regression: report to Arie with the failing test name and error
4. If test needs updating: update it and note why in `docs/V1-TEST-RESULTS.md`

## Phase 2 — Compile and syntax checks

```bash
cd glm-work/narrator_v01
python3 -c "import py_compile;[py_compile.compile(f,doraise=True) for f in ['app.py','game_loop.py','audio_queue.py','audio_engine.py','config.py','dm_engine.py','world_store.py']]"
cd glm-work && node -c narrator_v01/static/app.js
```

Both must pass with zero errors.

## Phase 3 — Playwright smoke test

Start the app and run a headless browser test:

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v01.app --port 5102 &
sleep 3
node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto('http://localhost:5102/', { waitUntil: 'networkidle' });
  console.log('Intro visible:', await page.isVisible('#intro-overlay'));
  // Take screenshot
  await page.screenshot({ path: 'shots/v1-smoke.png' });
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
"
```

Verify:
- Page loads without errors
- Intro/foreword screen is visible
- No console errors in browser DevTools
- All three themes (light/dark/sepia) are visually distinct

## Phase 4 — Long-session soak test (if time permits)

Per V1-PLAN.md: "A full extended session (~30+ turns) runs without crashing or requiring a server restart."

This requires API credits or a free model. Use `gemini-3.5-flash-lite` (free) or `openai/gpt-oss-120b` (free).

Write a script that:
1. Starts a new game via `POST /api/newgame`
2. Sends 30+ turns via `POST /api/turn` with varied actions
3. Checks for: crashes, memory leaks, context window overflow, state corruption
4. Logs results to `docs/V1-SOAK-TEST.md`

If the app crashes or hangs, report the turn number and error.

## Phase 5 — Write results

Create `docs/V1-TEST-RESULTS.md` with:
- Test suite results (X/Y passed)
- Compile/syntax check results
- Playwright smoke test results
- Soak test results (if run)
- Any issues found and their status

## Ground rules

- Never write lines starting with `>` in any doc — those are Arie's.
- Do not touch `sonnet-work/`.
- Do not modify source code unless fixing a test that needs updating due to intentional behavior change. If you find a real bug, report it — don't fix it yourself (that's A/B/C's job).
- If you find a critical bug that blocks v1, tell Arie immediately.
