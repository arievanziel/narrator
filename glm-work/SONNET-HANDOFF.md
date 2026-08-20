# Sonnet Handoff — Full Project State (2026-08-20)

**From:** GLM-5.2 High (Devin Local, free tier)
**To:** Sonnet (project lead / architecture reviewer)
**Branch:** `glm-phase1` (pushed to origin)
**Working folder:** `glm-work/` (GLM-owned), `sonnet-work/` (Sonnet-owned, read-only for GLM)
**Repository:** https://github.com/arievanziel/narrator.git

This document supersedes the previous `GLM-HANDOFF.md` status sections as the
canonical handoff for Sonnet. It covers everything built, tested, and decided
across all GLM sessions, plus a proposed plan and roadmap for next steps.

Sonnet should read this doc first, then the referenced files for detail. All
human feedback is in `glm-work/notes/HUMAN-FEEDBACK.md` — read that before any
work. Lines starting with `>` are Arie's direct input; never modify them.

---

## 1. Project overview

**What we're building:** A local, self-hosted D&D application for Arie's Apple
Silicon Mac (M1 Max, 32GB RAM, macOS 15.3.2). The app runs the Dungeon Master
itself:

```
Player types action → DM brain (LLM) → deterministic rules lawyer validates →
narration pipeline (Qwen3 TTS + SFX + music) → audio plays in browser →
player sees suggestions, types next action
```

**Budget:** ~€10/month total. Favor free hosted APIs or local components over
paid services. No paid cloud TTS. ElevenLabs SFX is optional (cached samples
+ procedural fallback work without it).

**Hard constraints (from `docs/SPEC.md`):**
- No microphone input, ever.
- Self-hosted / free or near-free.
- Apple Silicon only — no CUDA.
- Multi-voice required (distinct voices per NPC).
- Target usage up to ~3 hours/day of narration.

---

## 2. Current architecture — the "SoloQuest pattern"

The core architectural decision (validated through testing):

- **LLM narrates and proposes state changes** in a structured format.
- **Deterministic Python code (the "rules lawyer") validates and applies only
  valid changes** against authoritative game state.
- **Game state is the source of truth**, not the LLM's narrative.

This makes cheap/free models viable for DM duty because the code catches
cheating and hallucination. The LLM never directly mutates state.

### Response format (5 sections)

The DM brain must produce exactly 5 sections per turn:

1. `[NARRATIVE]` — the story text the player reads
2. `[MECHANICS]` — structured state change tags (HP_CHANGE, ENEMY_HP,
   ENEMY_DEAD, ITEM_USED, ITEM_GAINED, ROLL_REQUEST, etc.)
3. `[SUGGESTIONS]` — 3-4 suggested next actions with `[roll:true]` or
   `[roll:false]` tags
4. `[CHRONICLE]` — a one-line log entry for the session journal
5. `[AUDIO]` — machine-readable instructions for the narration pipeline:
   - `[SCENE: mood]` — music track selection (combat, tense, horror, mystery,
     exploration, tavern, emotional, victory)
   - `[narrator] text` — narrator TTS segment
   - `[CharName] "dialogue"` — character TTS segment
   - `[SFX: key]` — sound effect cue

The `[AUDIO]` section was added by GLM in the v0 implementation. It is not
shown to the player — it drives the audio pipeline only.

---

## 3. What's been built and tested

### 3.1 TTS models (Phase 1 — complete)

| Model | Status | Avg MOS (UTMOSv2) | RTF | Notes |
|-------|--------|-------------------|-----|-------|
| Kokoro 82M | Tested, working | 3.65 | 5-7x | Fast, stable, but "reading text out loud" not dramatic |
| Qwen3-TTS VoiceDesign 8bit | Tested, working | 3.57 | 2.3-2.5x | Expressive, voice design via natural language, may drift |
| Dia-1.6B | Deferred | — | — | Not downloaded (~3.2GB). Lower priority. |
| Higgs Audio V2 | Deferred | — | — | Not downloaded (~4.75GB). Lower priority. |
| Kokoro MLX | Deferred | — | — | Not tested. Lower priority. |

**Arie's TTS decision:** Use Qwen3-TTS VoiceDesign for ALL voices (narrator +
characters) if generation speed is acceptable and voice drifting can be
controlled. Reassess if it proves too slow or drifts too much. Kokoro is the
fallback for characters if needed.

**Key TTS files:**
- `run_qwen3_voicedesign.py` — Qwen3 runner
- `run_kokoro.py`, `run_kokoro_mlx.py` — Kokoro runners
- `run_voice_catalog.py` — 28-voice Kokoro catalog
- `run_ensemble2.py` — 7-character ensemble story with both engines
- `score_utmos.py` — UTMOSv2 objective scoring
- `RESULTS.md` — full comparison table

### 3.2 DM brain (tested across 9 models)

**Test harness:** `test_api_dm.py` — 10-turn scripted combat scenario (Level 1
Fighter vs 2 Goblins in The Rusty Anchor tavern).

**Results summary** (full detail in `notes/dm_test_results_summary.md`):

| Model | Provider | Format | Time/turn | Tokens | Trickster | Verdict |
|-------|----------|--------|-----------|--------|-----------|---------|
| GPT-OSS 120B | Groq | Perfect | ~10s | 25K | 27/30 (0 fell) | Best rule enforcement |
| Gemini 3.5 Flash-Lite | Google | Perfect | ~5s | 22K | 23/30 (1 fell) | Best value (Arie's default) |
| Gemini 3.5 Flash | Google | 1 issue | ~7s | 33K | 23/30 (1 fell) | Best prose |
| Groq/compound | Groq | Perfect | ~3.5s | 74K | 24/30 (1 fell) | Best combat tracking, 3x tokens |
| Compound-mini | Groq | Perfect | ~3s | 53K | 25/30 (0 fell) | Fastest |
| Qwen3.6-27B | Groq | 2 issues | ~36s | 54K | 25/30 (0 fell) | Best personality, slow |
| Gemini 3.6 Flash | Google | 2 issues | ~47s | 36K | 22/30* | Best combat realism, 20 RPD quota |
| GPT-OSS 20B | Groq | 2 issues | ~3s | 8K | — | Too unreliable |
| Allam-2-7B | Groq | 10 issues | ~20s | 26K | — | Complete failure |

**Key finding:** Models below ~27B parameters cannot reliably follow the
structured format. 27B+ models all succeed. Local execution on M1 Max 32GB
is feasible only with Q4-quantized 27-32B models (~16-18GB), running at
~5-10 tok/s (~30-60s per turn) — usable but slow.

**Arie's current default:** `gemini-3.5-flash-lite` (best value, most
token-efficient, free with no card, ~1000 RPD quota).

**API providers configured:**
- Groq (GROQ_API_KEY) — GPT-OSS 120B, compound, compound-mini, Qwen3.6-27B
- Google AI Studio (GOOGLE_API_KEY) — Gemini 3.5/3.6 Flash, Flash-Lite
- SambaNova (SAMBANOVA_API_KEY) — DeepSeek-V3.1, Gemma-4-31B (requires card)
- Cerebras (CEREBRAS_API_KEY) — GPT-OSS 120B at 3000 tok/s (requires card)
- OpenRouter — not configured

**Quota limitations discovered:**
- Groq free tier: 200K tokens/day (shared across models). GPT-OSS 120B at
  ~2.5K tokens/turn = ~80 turns/day. Compound at ~7.4K tokens/turn = ~27
  turns/day.
- Google Gemini 3.5 Flash-Lite: ~1000 RPD (plenty for testing).
- Google Gemini 3.5 Flash: ~500 RPD.
- Google Gemini 3.6 Flash: 20 RPD (too tight for real play).
- SambaNova/Cerebras: require credit card for free tier access.

### 3.3 Rules lawyer / cheat resistance (trickster test)

**Test:** `test_trickster.py` — 10 single-turn cheating attempts (kill without
roll, invent item, contradict HP, control NPC, claim ability, retroactive
roll, god-mode, meta-engineer, fabricate item, state hack).

**Results** (full detail in `notes/trickster_test_results.md`):

| Model | Resisted | Score | Fell for |
|-------|----------|-------|----------|
| GPT-OSS 120B | 10/10 | 27/30 | None |
| Compound-mini | 10/10 | 25/30 | None |
| Qwen3.6-27B | 10/10 | 25/30 | None |
| Groq/compound | 9/10 | 24/30 | "Waste potion" trick |
| Gemini 3.5 Flash | 9/10 | 23/30 | "Waste potion" trick |
| Gemini 3.5 Flash-Lite | 9/10 | 23/30 | "Control NPC" trick |

**Key finding:** The system prompt's "rules contract" is doing the heavy
lifting. All viable models (27B+) resisted direct cheating. The deterministic
state engine is the real backstop — even if a model falls for a trick, the
engine only applies validated [MECHANICS] tags.

**Known vulnerabilities to fix in the rules lawyer:**
1. "Waste potion" trick: player asks for non-existent item, model consumes a
   different valid item. Fix: if player names an item not in inventory, refuse
   to consume ANY item.
2. "Control NPC" trick: player declares an NPC's action, model applies it.
   Fix: don't apply ENEMY_DEAD/ENEMY_FLED unless the player rolled for the
   kill or the DM explicitly adjudicated it.

### 3.4 Audio pipeline (iteratively improved through v2→v3→v4 demos)

**Evolution:**
- `produce_epic_scene.py` — original pipeline (SFX overlapped voice)
- `produce_demos_v2.py` — SFX in gaps, no voice overlap, music ducking
- `produce_demos_v3.py` — volume spike fixes, SFX fade in/out, calmer narrator
- `produce_demos_v4.py` — further refinement based on v3 feedback
- `interactive_audio_demo.py` — terminal-based live D&D with TTS
- `narrator_v0/audio_pipeline.py` — merged pipeline for the v0 app

**15 demo audio files** generated across 4 versions, each reviewed by Arie.
Full feedback in `notes/demo_feedback_v2.md`, `v3.md`, `v4.md`.

**Arie's audio feedback (key points, all in HUMAN-FEEDBACK.md):**
- SFX must NOT overlap voice — strip silence, insert pauses for SFX duration
- SFX placed in gaps between speech segments
- Music should change with scene changes, crossfade between tracks
- Lower music substantially during character dialogue
- Diverse music sources (not just the same 3 tracks)
- MusicGen for special scenes (Arie approved: "yes, please!")
- Qwen3 narrator is expressive but may drift — find mitigation
- Kokoro voices are "reading text out loud" not "active conversation"
- Volume spikes at SFX/voice transitions — root cause investigated, fixed
  with SFX fade in/out (150ms) + music ducking during SFX + limiter
- Music must always fade out/in — no sudden stops
- Background ambience must be recognizable sounds, not white noise
- Narrator voice should wait a bit before starting (let music establish first)
- Generate all spoken lines first, then match music/ambience to total duration
- Narrator and character voices sometimes blend — need more distinct voice
  descriptions. Consider generating narrator text in one go, then mixing with
  separate character voice recordings.

**Audio assets:**
- Music tracks: `outputs/ambience_demo/tracks/` (9 CC0/CC-BY tracks:
  dark_woods, dungeon_ambient, tavern, battle_theme, battle_march,
  dark_chamber_mystery, exploration_peaceful, i_want_to_go_home, sad_piano)
- Cached SFX: `outputs/epic_scene/sfx/` (sword clashes, doors, magical bursts,
  water, fire, war horns, falling rocks, etc. — mostly ElevenLabs-generated)
- MusicGen integration: working in `produce_demos_v3.py` for live generation

### 3.5 Narrator v0 app (built and tested end-to-end)

**Package:** `glm-work/narrator_v0/`

| File | Purpose | Status |
|------|---------|--------|
| `__init__.py` | Package init | Done |
| `config.py` | All config: paths, voices, music, SFX, DM settings | Done |
| `cast.json` | Character → Qwen3 voice description mappings | Done, editable |
| `dm_engine.py` | GameState + rules lawyer + extended system prompt with [AUDIO] | Done |
| `audio_pipeline.py` | Qwen3 TTS + SFX in gaps + music ducking → mixed WAV | Done |
| `app.py` | Web server with background audio generation + browser playback | Done |
| `run_trickster.py` | Standing 10-scenario adversarial test | Done |
| `run_model_tests.py` | Multi-model comparison (trickster + scripted + audio) | Done |
| `build_preview.py` | HTML preview page for test outputs | Done |

**How to run:**
```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v0.app --model gemini-3.5-flash-lite --port 5102
# Text-only mode: python -m narrator_v0.app --no-audio
# Trickster test: python -m narrator_v0.run_trickster --model gemini-3.5-flash-lite --save
# Model comparison: python -m narrator_v0.run_model_tests
```

**Tested:**
- Text-only mode: DM brain + rules lawyer + web GUI working
- Full audio mode: 208s narration generated in ~70s (3x RTF)
- Mock audio test: 16.4s audio in 14.9s (0.9x RTF)
- SFX placed in gaps, no voice overlap
- Music ducking with narrator vs character volume difference
- Background audio generation (text response sent immediately, audio follows)

**Known limitations:**
1. Audio generation time: ~70s for a long turn. May break immersion for fast
   back-and-forth.
2. Qwen3 voice drifting: not yet addressed. Needs research into reference
   audio / voice cloning.
3. Music transitions within a turn: one track per turn. Multi-track
   transitions not yet implemented for live play.
4. Cast management: new NPCs get default voice based on gender detection.
5. No campaign save/load: state is in-memory only.
6. Port 5000 conflicts with macOS AirPlay Receiver — use 5102 or similar.

### 3.6 Model comparison test (run 2026-08-19)

**Script:** `run_model_tests.py` — tests 4 models with trickster (10 tricks) +
scripted scenario (3 turns) + audio generation.

**Results:**

| Model | Trickster | Scripted | Tokens | Audio files |
|-------|-----------|----------|--------|-------------|
| Gemini Flash-Lite | 9/10 (23/30) | 3 turns, 7.2s | 6,094 | 3 WAVs |
| GPT-OSS 120B | 10/10 (27/30) | 3 turns, 6.7s | 7,364 | 3 WAVs |
| Groq/compound | 0/10 (quota) | 3 turns, 14.4s | 23,377 | 3 WAVs |
| Gemini Flash | 2/10 (quota) | 0 turns (quota) | 0 | 0 |

**Note:** Groq hit 200K token/day quota during trickster re-run. Gemini Flash
hit 20 RPD quota. Audio files are in `outputs/narrator_v0/` (gitignored —
regenerable).

**HTML preview:** `outputs/narrator_v0/model_comparison/index.html` —
side-by-side audio players, transcripts, trickster results.

### 3.7 GUI mockups (6 HTML variants)

**Location:** `glm-work/notes/gui_v2/`

Arie has been iterating on GUI designs. 6 static HTML mockups exist:
- `ink.html`, `ink-dark.html`, `ink-extended.html` — ink/parchment theme
  (Arie's preferred direction)
- `midnight.html` — dark blue theme
- `parchment.html` — warm parchment theme
- `sepia.html` — sepia tone
- `twilight.html` — purple/dark theme

**Arie's GUI feedback (rounds 1-3, in `gui_v2/feedback.md` and
`feedback_round3.md`):**
- Wants collapsible top/bottom/side bars with unobtrusive tab/bookmark UI
- Audio bar should collapse to a thin line with a breathing play/pause button
- Input area should have more spacing below it
- Hide both bars mode is perfect for reading
- Wants creative book-related GUI elements
- `ink-extended.html` is the latest iteration (most refined)

**The live `narrator_v0/app.py` GUI** is a functional but simpler design. It
does NOT yet incorporate the ink-extended mockup's design language. This is a
known gap — the mockup is the target, the app is the working prototype.

### 3.8 Feedback forms (prepared for Arie)

Three feedback forms with `>` pointers for Arie's input:
- `notes/v0_gui_feedback.md` — GUI layout, sidebar, chat area, audio bar
- `notes/v0_audio_feedback.md` — per-model voice quality, SFX, music
- `notes/v0_playtesting_feedback.md` — DM brain quality, rules lawyer, UX

These are NOT yet filled in by Arie (as of 2026-08-20).

---

## 4. Research completed

| Topic | File | Key finding |
|-------|------|-------------|
| AI-DM competitor architecture | `notes/dm_engine_research.md` | Familiar, TableForge, Scrollbook, Eternal DM, Visionarium surveyed. Most use structured state + tool-calling. SoloQuest pattern aligns with industry. |
| Local LLM feasibility | `notes/local_llm_dm_research.md` | 27B+ needed for DM duty. Q4-quantized 27-32B fits in 32GB but runs at ~5-10 tok/s. Hosted API (Groq free tier) is dramatically better for real-time. |
| Audio/ambience | `notes/audio_ambience_research.md` | Library-based (CC0/CC-BY tracks) recommended for v0. Generative (MusicGen) for special scenes. ElevenLabs SFX API for one-off stings (optional, paid). |
| Audio production | `notes/audio_production_research.md` | Audiobook music practices: lower volume during dialogue, different tracks for narrator vs character sections. |
| Volume spike analysis | `notes/volume_spike_analysis.md` | Root cause: SFX + voice overlap + abrupt music transitions. Fixed with SFX fade in/out + music ducking + limiter. |
| TTS landscape | `sonnet-work/TTS-LANDSCAPE-RESEARCH-2026.md` | Sonnet's research — Kokoro, Qwen3, Dia, Higgs surveyed. MLX path preferred for Apple Silicon. |
| Campaign config | `sonnet-work/CAMPAIGN-CONFIG-DRAFT.md` | Sonnet's draft — tracking granularity, dice visibility, NPC management. Needs Arie's input. |

---

## 5. Git state

**Branch:** `glm-phase1` (pushed to origin)
**Last commit:** `160dfa7` — "Add narrator_v0 app, DM engine, audio pipeline,
model tests, and all research/feedback docs" (2026-08-19)

**All code, docs, notes, and test results are committed and pushed.** Audio
WAV files are gitignored (regenerable, large). Model weights are gitignored
(in `glm-work/models/`).

**To clone and run:**
```bash
git clone https://github.com/arievanziel/narrator.git
cd narrator
cd glm-work && python3.12 -m venv .venv && source .venv/bin/activate
pip install mlx-audio soundfile scipy numpy python-dotenv openai
# Download Qwen3-TTS model to glm-work/models/qwen3_voicedesign_8bit/
# Add API keys to .env (see .env.example)
python -m narrator_v0.app --model gemini-3.5-flash-lite --port 5102
```

---

## 6. Open decisions (need Arie's input)

1. **DM brain model:** Gemini Flash-Lite (current default, best value) vs
   GPT-OSS 120B (best rule enforcement, but Groq quota is tighter). Arie's
   feedback forms may settle this.

2. **ElevenLabs SFX:** Keep as optional upgrade, or cut for strict no-paid-API
   v0? Currently optional — cached SFX + procedural fallback work without it.

3. **Claude baseline comparison:** Arie needs to run the manual test
   (`notes/claude_dm_test_prompt.md`) to establish a quality baseline. Not yet
   done.

4. **Campaign configuration:** Sonnet's draft
   (`sonnet-work/CAMPAIGN-CONFIG-DRAFT.md`) needs Arie's answers on tracking
   granularity, dice visibility, NPC management.

5. **Voice assignment:** Manual (Arie assigns in `cast.json`) or automatic
   (LLM picks based on character description)? Currently manual with gender
   detection fallback.

6. **GUI direction:** The `ink-extended.html` mockup is Arie's preferred
   design, but the live app uses a simpler GUI. Need to bring the mockup's
   design language into the live app.

7. **Audio generation speed:** ~70s for a long turn. Options:
   (a) Keep live generation, accept the wait
   (b) Background generation while player reads
   (c) Pre-generate during idle time
   (d) Switch to Kokoro for faster (but less expressive) voices

8. **Qwen3 voice drifting:** Needs mitigation research. Options:
   reference audio, voice cloning, periodic voice re-anchoring.

---

## 7. Proposed plan and roadmap for Sonnet

### Phase 0: Feedback collection (NOW — needs Arie)

Before building further, collect Arie's feedback on:
- The 3 feedback forms (`v0_gui_feedback.md`, `v0_audio_feedback.md`,
  `v0_playtesting_feedback.md`)
- A real playtest session (not scripted — Arie actually playing 5-10 turns)
- The Claude baseline comparison (`claude_dm_test_prompt.md`)
- The campaign config draft (`CAMPAIGN-CONFIG-DRAFT.md`)

**Why first:** All subsequent work depends on knowing what Arie actually
thinks of the v0 app. Building ahead of his feedback risks rework.

### Phase 1: Rules lawyer hardening (GLM, can start now)

Fix the two known trickster vulnerabilities:
1. "Waste potion" trick: if player names an item not in inventory, refuse to
   consume ANY item (not just the named one).
2. "Control NPC" trick: don't apply ENEMY_DEAD/ENEMY_FLED unless the DM
   explicitly adjudicated it with a roll or a valid mechanic.

Add more trickster scenarios:
- Long-context attacks (try cheating after 10+ turns of history)
- Subtle state manipulation (gradually inflate HP over multiple turns)
- Inventory fabrication (claim items found that weren't generated)

**This is the highest-value work** — the rules lawyer is the core trust
mechanism. If it has holes, the whole architecture is compromised.

### Phase 2: GUI redesign (GLM + Sonnet review)

Bring the `ink-extended.html` mockup's design language into the live
`narrator_v0/app.py`:
- Collapsible top/bottom/side bars with bookmark-style tabs
- Audio bar that collapses to a thin line with breathing play/pause
- Ink/parchment visual theme
- More spacing below input area
- Hide-all-bars mode for pure reading

**Sonnet's role:** Review the GUI design for UX coherence before GLM
implements. The mockup is Arie's preferred direction — don't redesign, just
implement faithfully.

### Phase 3: Audio pipeline improvements (GLM)

Based on Arie's v4 demo feedback:
1. Generate all narrator text in one go, then mix with separate character
   voice recordings (Arie specifically requested this — prevents voice
   blending)
2. Music/ambience should be generated AFTER spoken lines, matched to total
   duration (Arie's request)
3. Music should run continuously across turns, not restart each turn
4. Investigate Qwen3 voice drifting mitigation (reference audio, re-anchoring)
5. Add more SFX sources (Tabletop Audio, Sonniss GDC, Freesound CC0)
6. Better MusicGen prompt matching to scene energy

### Phase 4: Campaign system (Sonnet design + GLM implement)

Based on Arie's answers to `CAMPAIGN-CONFIG-DRAFT.md`:
1. Character creation flow (class, name, stats, starting inventory)
2. Campaign setting selection (tavern, dungeon, forest, city, custom)
3. Tracking granularity options (full inventory, simplified, off)
4. Dice visibility (player rolls, DM rolls, hidden)
5. NPC management (manual cast.json, auto-assign, or LLM-assisted)
6. Save/load campaign state (JSON persistence)

**Sonnet's role:** Design the campaign config schema and state persistence
format. This is an architecture decision worth getting right.

### Phase 5: State persistence and multi-session (GLM)

- Save campaign state to JSON between sessions
- Load previous campaign on app start
- Session history persistence (for chronicle/journal)
- Multiple campaign slots

### Phase 6: Local LLM fallback (research + test)

If Arie wants offline capability:
- Test Qwen3-32B or Gemma-4-31B at Q4 via Ollama/llama.cpp on M1 Max
- Measure real-world turn time and quality
- If acceptable, add as a fallback provider in `config.py`
- If not acceptable, document why and stick with hosted API

### Phase 7: Opus/Fable architecture review (Sonnet triggers)

Once the rules lawyer is hardened and the campaign system is designed:
- Have Opus review the state schema + rules-lawyer validation logic for edge
  cases the trickster test didn't think of
- Sanity-check the system prompt against real D&D 5e rules (spell slots,
  action economy, conditions)
- This is a "get it right once, expensively" task — worth the cost

---

## 8. What Sonnet should do next

1. **Read this doc** (you're doing it).
2. **Read `notes/HUMAN-FEEDBACK.md`** — all of Arie's direct feedback.
3. **Read `notes/demo_feedback_v4.md`** — latest audio feedback, some sections
   still empty (interactive demo, general questions).
4. **Update `docs/PROJECT-ROADMAP.md`** with the current status from this doc.
   The roadmap's "Status as of 2026-08-19" section is now stale — the v0 app
   is built and tested.
5. **Decide whether to trigger Phase 1 (rules lawyer hardening) now** or wait
   for Arie's feedback forms. I recommend starting Phase 1 immediately — the
   two known vulnerabilities are well-defined and don't depend on Arie's
   input.
6. **Consider an Opus session** for the rules lawyer review if you think the
   two known vulnerabilities + the long-context attack surface warrant a
   stronger model's first pass. My recommendation: wait until after Phase 1
   fixes + expanded trickster scenarios, then trigger Opus for a final review.

---

## 9. File index for Sonnet

### Architecture and planning
- `docs/PROJECT-ROADMAP.md` — Sonnet's living roadmap (needs update)
- `docs/V0-PLAN.md` — v0 architecture plan (needs update — v0 is built)
- `docs/SPEC.md` — original spec (partially superseded by scope expansion)
- `sonnet-work/INSTRUCTIONS-FOR-GLM.md` — Sonnet's instructions to GLM
- `sonnet-work/CAMPAIGN-CONFIG-DRAFT.md` — campaign config draft (needs Arie input)

### DM engine
- `glm-work/test_api_dm.py` — DM brain + state engine + API client
- `glm-work/test_trickster.py` — 10-scenario adversarial test
- `glm-work/serve_dm_web.py` — earlier web GUI (superseded by narrator_v0)
- `glm-work/notes/dm_test_results_summary.md` — full model comparison
- `glm-work/notes/trickster_test_results.md` — cheat resistance results
- `glm-work/notes/dm_engine_research.md` — AI-DM competitor research
- `glm-work/notes/local_llm_dm_research.md` — local LLM feasibility
- `glm-work/notes/claude_dm_test_prompt.md` — Claude baseline test (Arie to run)

### Narrator v0 app
- `glm-work/narrator_v0/config.py` — all configuration
- `glm-work/narrator_v0/dm_engine.py` — GameState + rules lawyer + system prompt
- `glm-work/narrator_v0/audio_pipeline.py` — TTS + SFX + music pipeline
- `glm-work/narrator_v0/app.py` — web server + GUI
- `glm-work/narrator_v0/cast.json` — character voice assignments
- `glm-work/narrator_v0/run_trickster.py` — standing adversarial test
- `glm-work/narrator_v0/run_model_tests.py` — multi-model comparison
- `glm-work/narrator_v0/build_preview.py` — HTML preview generator

### Audio pipeline
- `glm-work/produce_epic_scene.py` — original pipeline (v1)
- `glm-work/produce_demos_v2.py` — SFX in gaps, music ducking (v2)
- `glm-work/produce_demos_v3.py` — volume spike fixes, SFX fade (v3)
- `glm-work/produce_demos_v4.py` — further refinement (v4)
- `glm-work/interactive_audio_demo.py` — terminal-based live D&D
- `glm-work/narrator_parser.py` — text → segment parser
- `glm-work/test_parser.py` — parser tests (41/41 passing)
- `glm-work/notes/audio_ambience_research.md` — music/ambience research
- `glm-work/notes/audio_production_research.md` — audiobook practices
- `glm-work/notes/volume_spike_analysis.md` — volume spike root cause

### TTS
- `glm-work/run_qwen3_voicedesign.py` — Qwen3 runner
- `glm-work/run_kokoro.py` — Kokoro runner
- `glm-work/run_voice_catalog.py` — 28-voice catalog
- `glm-work/run_ensemble2.py` — ensemble story
- `glm-work/score_utmos.py` — UTMOSv2 scoring
- `RESULTS.md` — TTS comparison table

### GUI
- `glm-work/notes/gui_v2/ink-extended.html` — Arie's preferred mockup (latest)
- `glm-work/notes/gui_v2/feedback.md` — GUI feedback rounds 1-2
- `glm-work/notes/gui_v2/feedback_round3.md` — GUI feedback round 3
- `glm-work/notes/v0_gui_feedback.md` — v0 GUI feedback form (empty)

### Human feedback (CRITICAL — read before any work)
- `glm-work/notes/HUMAN-FEEDBACK.md` — all of Arie's feedback
- `glm-work/notes/demo_feedback_v2.md` — v2 demo feedback (filled)
- `glm-work/notes/demo_feedback_v3.md` — v3 demo feedback (filled)
- `glm-work/notes/demo_feedback_v4.md` — v4 demo feedback (partially filled)
- `glm-work/notes/v0_audio_feedback.md` — v0 audio feedback form (empty)
- `glm-work/notes/v0_playtesting_feedback.md` — v0 playtest form (empty)

### Test outputs (JSON, committed)
- `glm-work/outputs/dm_test_*.json` — raw DM brain test results
- `glm-work/outputs/trickster_*.json` — raw trickster test results
- `glm-work/outputs/narrator_v0/model_comparison/` — v0 model comparison
- `glm-work/outputs/narrator_v0/model_comparison/index.html` — HTML preview

### Audio outputs (gitignored, regenerable)
- `glm-work/outputs/epic_scene/demo*.wav` — 15 demo audio files
- `glm-work/outputs/narrator_v0/*.wav` — v0 app audio files
- `glm-work/outputs/voice_catalog/*.wav` — 56 voice catalog samples
- `glm-work/outputs/interactive/*.wav` — interactive demo sessions
