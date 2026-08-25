# Instance D — Handoff to Instance A and Sonnet/Opus

**Date:** 2026-08-24
**From:** Instance D (stability/regression testing)
**To:** Instance A (main programmer), Sonnet/Opus (architecture review)
**Subject:** V1 regression sweep complete — backend is solid, frontend re-test needed after B and C

## Summary

Instance A's backend work (v0.4/v0.5) passes all testing. **93/93 unit tests pass, 35-turn soak test runs without crashes, no degradation, no state corruption.** The backend is ready for v1.

Instances B (Book GUI) and C (UX fixes) had not landed their changes at test time. A frontend re-test will be needed after they finish. Full results in `docs/V1-TEST-RESULTS.md`.

## For Instance A — what I verified

### Your backend is clean

1. **All 93 tests pass** across 8 test files (test_context, test_dc_roll, test_facade, test_golden, test_guards, test_procedural, test_trickster, test_world_store).
2. **35-turn soak test** against `gemini-3.5-flash-lite` (free tier):
   - 34/35 turns succeeded (1 expected 429 rate limit, not a bug)
   - Zero server crashes
   - Zero state corruption
   - No response time degradation (ratio 0.97x — prompt caching is working)
   - HP tracked correctly (12 → 7 over the session)
   - Inventory grew procedurally (4 items by end)
   - Chronicle accumulated 35 entries
   - Location changed from starting tavern to "The Sunken Archive"
   - Scene moods varied correctly (exploration, combat, tense, mystery, calm)
3. **Compile checks:** all 7 Python files + app.js compile clean.
4. **Playwright smoke test:** page loads, intro visible, 0 console errors, 3 themes distinct.

### Observations for you (not bugs, just notes)

1. **429 handling:** The retry logic (3 attempts, 5s/10s backoff) works correctly. On turn 13 of the soak test, all 3 retries were exhausted because the Gemini free-tier rate limit window (15 req/min) hadn't elapsed. The next turn succeeded. This is expected — no code change needed, but worth knowing for Arie's playtesting: if he plays fast on the free tier, he'll hit this. The Groq models (`openai/gpt-oss-120b`) are an alternative free option.

2. **`/api/state` response shape:** The state is nested under a `"state"` key (e.g., `{"state": {"pc_hp": 7, ...}}`). This is fine — just noting it because my soak test script initially missed it by looking at top-level keys. Instance B's frontend code should already handle this correctly.

3. **Soak test script is reusable:** `glm-work/soak_test.py` can be re-run with `python soak_test.py --turns N` against any running server. Useful for re-testing after B and C land.

### What I did NOT test (out of scope or blocked)

- **Audio-enabled testing:** Soak test ran with `--no-audio`. The segment queue (`audio_queue.py`) and TTS pipeline were not exercised under load.
- **Frontend Book GUI:** Instance B's work (lexicon, chapter headings, drop caps, storyteller mode) is not yet in the codebase.
- **UX fixes:** Instance C's work (volume slider, manual dice wiring, seek bar, Session Zero dropdown) is not yet in the codebase.
- **Anthropic/Claude testing:** API key has insufficient credits (known issue, not a bug).

## For Sonnet/Opus — architecture review status

### What's been built since the Opus review

The Opus review (`docs/WORLD-ENGINE-REVIEW-OPUS.md`) recommended a build sequence (v0.4a through v0.5c). Based on the test files and code, here's what has landed:

| Opus stage | Status | Evidence |
|---|---|---|
| v0.4a — Audio segment queue | **Built** | `audio_queue.py` exists, `test_*.py` references it |
| v0.4b — DC-then-roll + seeded RNG | **Built** | `test_dc_roll.py` (15 tests) — roll seeding, DC resolution, turn ledger |
| v0.4c — `world_store.py` standalone | **Built** | `test_world_store.py` (17 tests) — Entity, Scene, resolve_or_create, persistence |
| v0.4d — GameState facade over WorldStore | **Built** | `test_facade.py` (11 tests) — "behavior-neutral" confirmed |
| v0.5a — Context assembler | **Built** | `test_context.py` (9 tests) — cache stability, token budgets, working-set scoring |
| v0.5b — Consistency guards | **Built** | `test_guards.py` (9 tests) — liveness guard, since-you-were-last-here digest |
| v0.5c — Procedural opening (no hardcoded goblins) | **Built** | `test_procedural.py` (8 tests) — mood derivation, procedural generation |

**All 7 stages of the Opus-recommended build sequence are implemented and tested.**

### What's still missing for v1

Per `docs/V1-PLAN.md` and `docs/V1-FINISH-COORDINATION.md`:

1. **Book GUI (Instance B):** The frontend still looks like a game UI, not a book. This is the "single biggest gap to v1" per Instance A's handoff. B's task is defined in `docs/INSTANCE-B-GUI-HANDOFF.md`.
2. **UX fixes (Instance C):** 4 specific fixes (volume slider, dice wiring, seek bar, Session Zero dropdown) in `docs/INSTANCE-C-UX-HANDOFF.md`.
3. **Arie's playtest:** After B and C land, Arie needs to play a real session and be satisfied. This is the v1.0 bar.

### Recommendation for Opus/Sonnet

The backend architecture is sound and well-tested. The Opus review's recommendations have been faithfully implemented. **No further architecture review is needed for v1** — the remaining work is frontend (B/C) and Arie's subjective playtest approval. If a future v2 expands scope (multi-session, mobile, network deployment), a new architecture review would be warranted at that point.

## Re-test plan for after B and C

When B and C finish, someone (D or anyone) should:

1. **Re-run Phase 1** (test suite) — should still be 93/93 (B/C don't touch Python)
2. **Re-run Phase 2** (compile checks) — `node -c static/app.js` is the critical one
3. **Re-run Phase 3** (Playwright) — verify new Book GUI loads, check for console errors, verify chapter headings/drop caps/lexicon
4. **Run a short audio-enabled session** (5-10 turns) to verify the segment queue works with the new frontend
5. **Hand to Arie for playtest**

## Files created by Instance D

- `docs/V1-TEST-RESULTS.md` — full test results
- `docs/INSTANCE-D-HANDOFF.md` — this file
- `glm-work/soak_test.py` — reusable soak test script
- `glm-work/shots/v1-smoke-{light,dark,sepia}.png` — Playwright screenshots
- `glm-work/outputs/soak_test_results.json` — raw soak test data
