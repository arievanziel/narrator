# Update 2026-08-22 — Opus reviewed the World Engine, detailed spec ready, restructure first

Opus reviewed `docs/WORLD-ENGINE-DESIGN.md` (`docs/WORLD-ENGINE-REVIEW-OPUS.md`) and
found a real dependency the plan missed: **DC-then-roll and audio streaming are not
independent** — two sequential LLM calls per contested action roughly doubles latency,
tolerable only if the audio queue already hides it behind playing sound. Build order
changed accordingly. I then wrote the full line-level implementation spec:
**`sonnet-work/GLM-WORLD-ENGINE-SPEC.md` — read this before touching any World Engine
code, it supersedes `docs/WORLD-ENGINE-DESIGN.md` entirely.**

**New first step, before any of that: file restructuring (v0.3.5).** `narrator_v01/app.py`
is 1,673 lines, ~1,000 of which is a single HTML/CSS/JS string literal. Three parallel
instances are about to need this file simultaneously — split it first. Target layout and
a safe (behavior-preserving, testable) extraction order are in `docs/V1-PLAN.md`'s new
"v0.3.5" section. This is mechanical work (moving code, not redesigning it) — good fit
for whichever instance is free first, blocks nothing else once started.

**Corrected build order** (full detail + owners in `docs/V1-PLAN.md`'s versioning
table): v0.3.5 (restructure) → v0.4a (audio queue, **Instance B, do this first if only
one instance is running**) → v0.4c/d (world_store.py + GameState facade, Instance A, can
run parallel to v0.4a) → v0.4b (DC-then-roll, Instance A, **waits for v0.4a to land**) →
v0.5a/b/c (context assembler, guards, procedural opening).

Do not start DC-then-roll (v0.4b) before the audio queue (v0.4a) exists, even though
it's tempting since both touch the DM turn flow — the latency will feel bad without it,
and Arie will notice immediately.

---

# Update 2026-08-21 (v2) — scope expanded significantly, three new design docs

Arie gave detailed direction on everything: no hardcoded NPCs/encounters ever, a proper
persistent "World Engine" (never trust the LLM to remember), deterministic DC-then-roll
dice enforcement, live audio streaming faster than playback, a conversational Session
Zero wizard, voice assignment screen, full character sheet/inventory UI, and audio
polish (crossfade, normalization, adaptive ducking). This is a real subversion series
now, not a single next step — **read `docs/V1-PLAN.md` in full**, it has the versioning
plan (v0.4 → v1.0) and updated task division. Three new ready-to-build design docs:

- `docs/WORLD-ENGINE-DESIGN.md` — the persistent entity store + procedural generation +
  deterministic rules. **Note: three specific open questions in this doc are flagged
  for an Opus review before final** — don't treat the retrieval/consistency strategy as
  locked, but the entity model and rules-engine parts are solid, build those now.
- `docs/AUDIO-STREAMING-DESIGN.md` — live streaming playback, pre-generated choice
  audio, quality/speed fallback rule. Fully ready to build, no open questions.
- `docs/SESSION-ZERO-DESIGN.md` — conversational onboarding wizard reusing the existing
  turn-loop. Fully ready to build (can stub the World Engine dependency for now).

New instance assignment (supersedes the previous round — see `V1-PLAN.md` for full
detail): **A GLM** owns rules/World Engine, **B GLM** owns audio streaming + polish,
**C GLM** owns Session Zero UI + voice assignment + character sheet, **D GLM**
(optional) owns stability/regression testing once things settle. Don't start the
long-session stress test yet — the app is about to change substantially.

Bandwidth note: Arie is still on a very limited 5G connection — no new heavy
dependencies or model downloads unless truly necessary (the World Engine design doc
already accounts for this — JSON/SQLite, no vector DB, no new local models).

---

# Update 2026-08-21 — v0.3 reviewed, path to v1

Read `docs/V1-PLAN.md` (new, canonical for next steps — supersedes the open items in
`V0-PLAN.md`). I verified v0.3 by actually opening the Playwright screenshots, not just
the handoff doc — genuinely good work, the rules lawyer is confirmed working live
(saw the `[REJECTED — no roll evidence]` message in an actual screenshot). Three
parallel instances, task division in `V1-PLAN.md` §"Task division" — short version:

- **A GLM - Rules Lawyer**: add the expanded trickster scenarios (long-context,
  gradual HP inflation, fabricated items after many turns) — still not done, this is
  what's blocking the Opus review trigger. Also fix the mechanics-log display
  formatting (multiple state changes run together unreadably in one screenshot).
- **B GLM - GUI/UX**: fix the sepia theme bug (looks identical to dark theme — verify
  the CSS actually swaps), and build Arie's requested opening wizard (guided,
  book-foreword-toned setup flow, replacing the current single form). Apply my earlier
  GUI polish instructions to the live `narrator_v01/app.py` templates now, not the
  static mockups — that exploration phase is over.
- **C GLM - Stability**: run one real 30+ turn session end-to-end (not short playtests)
  looking for crashes/degradation, fix the continuous-music gap on scene changes.

I also fixed `.gitignore` directly (node_modules + Playwright test artifacts weren't
excluded) — no action needed from you there.

Two things are Arie's call, not something to guess at: Anthropic credits (blocks Claude
testing) and how elaborate the opening wizard should be — both flagged for him in
`docs/V1-PLAN.md`'s closing section.

---

# Update 2026-08-20 (v2) — Arie answered, tasks divided for parallel GLM instances

Arie reviewed and answered everything in `sonnet-work/QUESTIONS-FOR-ARIE-2026-08-20.md`
(read it — his answers matter, especially the scope note in item 6, also now reflected
in `docs/V0-PLAN.md`'s new "Scope philosophy" section: **v0 is an audiobook-with-choices
experience — dice/inventory/state fully automatic and app-driven, visible but not
player-interactive. Don't build toward a deeper interactive RPG yet.**)

Four tasks below, split to avoid file conflicts if Arie runs multiple GLM windows at
once. If you're a single instance working through all of them, do them in this order.

## Instance "A GLM - Rules Lawyer" — owns `test_api_dm.py`, `run_trickster.py`

Arie approved starting immediately, no dependencies on anything else.

1. Fix the two known trickster vulnerabilities in `apply_mechanics()` (~line 205-262):
   - **"Waste potion":** if any `ITEM_USED:<name>` in a turn's `[MECHANICS]` block names
     an item not in `self.inventory`, don't consume ANY item that turn (currently a
     different valid item can still get silently consumed).
   - **"Control NPC":** only apply `ENEMY_DEAD`/enemy-fled if the same turn's mechanics
     include an actual roll-driven action against that enemy — not just because the
     narrative text said so.
2. Add the expanded trickster scenarios: long-context attacks (try cheating after 10+
   turns of history), gradual HP inflation across turns, fabricated-item claims.
3. **New: add Claude/Anthropic as a provider.** Anthropic has an OpenAI-SDK-compatible
   endpoint (confirmed via their docs) — point the existing `openai` client's `base_url`
   at Anthropic's compat endpoint, use a Claude model name, same pattern as the existing
   Groq/Gemini provider blocks. Arie is deciding which tier(s) to enable (Haiku/Sonnet/
   Opus) in his answer to the addendum in `QUESTIONS-FOR-ARIE-2026-08-20.md` — check
   that before assuming which one(s) to wire up. Needs `ANTHROPIC_API_KEY` in `.env`
   (add to `.env.example` too).
4. Re-run the trickster suite + a scripted DM test against whichever Claude tier(s) Arie
   picks, add results to `dm_test_results_summary.md` and `trickster_test_results.md`.

## Instance "B GLM - GUI Polish" — owns `notes/gui_v2/*.html` only (not narrator_v0/)

Read `sonnet-work/GUI-V9-POLISH-INSTRUCTIONS.md` — my detailed review based on actually
looking at the screenshots, not just the code. Three concrete fixes, in priority order:
1. Side-panel toggle anchoring (currently drifts relative to the panel edge).
2. Bottom bar consolidation (audio bar + footer bar currently compete — pick Option A
   or B from my instructions doc, don't leave both).
3. Code-quality extraction (shared CSS/JS into one file instead of 14 duplicated
   1200-line HTML blobs) — **do this step last, only once Arie confirms a final pick**,
   not before.

Stay working in `notes/gui_v2/` only — don't touch `narrator_v0/app.py` yet, that's
Instance C's territory for now, to avoid both of you editing the same file.

## Instance "C GLM - App Stability" — owns `narrator_v0/app.py`, `audio_pipeline.py`

Arie said the app was "still very buggy" last time he ran it. Before he plays a real
session (which he's about to do, per his answer to question 3), reproduce and fix
runtime issues:
1. Run `python -m narrator_v0.app --model gemini-3.5-flash-lite --port 5102` yourself,
   play several turns, and fix crashes/hangs/errors you hit.
2. Check the known limitations list in `SONNET-HANDOFF.md` §3.5 (audio gen time ~70s,
   port 5000 conflicts, no save/load) — confirm which are still real and fix what's
   reasonably fixable without a big redesign.
3. Don't touch GUI files — if the bug is GUI-related, note it for Instance B instead of
   fixing it yourself, to avoid overlapping edits.

## Sequenced after A/B/C finish: wire the polished GUI into the live app

Once B's GUI polish is done and Arie has confirmed the final design pick, one instance
(any of them, sequentially — not in parallel with the others touching the same file)
wires the polished HTML/CSS/JS into `narrator_v0/app.py`'s templates. Don't start this
until the design is actually finalized.

## Not GLM's job right now

- Claude baseline via manual chat — Arie already did this himself (see his answer to
  question 4 — went well, "lovely session," but wants it via direct API now, see
  Instance A task 3 above).
- Campaign config / onboarding wizard design — Sonnet's job once GUI settles.
- Deep audio pipeline phase-3 work (voice drift mitigation, continuous cross-turn music)
  — still valid per `SONNET-HANDOFF.md` §7 Phase 3, but lower priority than the four
  tasks above given Arie's "keep it simple" scope note — don't start this unless the
  above are done and Arie hasn't given new direction.

---

# Update 2026-08-20 — reviewed SONNET-HANDOFF.md, excellent work

I audited the handoff against the actual code, not just the doc. It holds up well —
genuinely strong work on the DM brain testing, trickster suite, and audio iteration.
Confirmed one gap and one thing worth doing while waiting on Arie:

1. **Start Phase 1 (rules-lawyer hardening) now — don't wait for Arie's feedback
   forms.** I confirmed this hasn't been started: `test_api_dm.py`'s `apply_mechanics()`
   (around line 205-262) is the single source of truth — `narrator_v0/dm_engine.py`
   imports `GameState` from it, so fixing it there fixes both. Two fixes, both already
   well-specified in your own handoff:
   - **"Waste potion" trick:** if `ITEM_USED:<name>` names an item not in
     `self.inventory`, currently it just logs `[ITEM_USED but not in inventory]` and
     does nothing — check whether a *different* valid item still gets silently consumed
     elsewhere in the same turn's mechanics block (that's the actual exploit per your
     own notes, not just an unhandled tag). Fix: if any named item in a turn's
     `[MECHANICS]` block doesn't match inventory, don't consume ANY item that turn.
   - **"Control NPC" trick:** add a check so `ENEMY_DEAD`/enemy-fled mechanics are only
     applied if the same turn's mechanics include an actual roll-driven action against
     that enemy (not just because the narrative text said so).
   - Add the expanded trickster scenarios you proposed (long-context attacks after 10+
     turns, gradual HP inflation, fabricated-item claims) to `run_trickster.py`.
2. **Consolidate the GUI mockups into a recommendation**, don't just keep generating
   variants. There are 14 now. I've asked Arie to pick a direction
   (`sonnet-work/QUESTIONS-FOR-ARIE-2026-08-20.md`) — once he does, implement that
   one faithfully into `narrator_v0/app.py` rather than continuing to explore.
3. Don't wait on Arie's answers to start #1 — it's fully unblocked. Do wait on his GUI
   pick before implementing GUI changes into the live app (exploring more mockups is
   fine, just don't build the real thing until he picks).
4. Everything else (Claude baseline, feedback forms, campaign config) is on Arie, not
   you — no action needed from you there right now.

Opus/Fable trigger point unchanged from your own recommendation: after Phase 1 fixes +
expanded trickster scenarios land, I'll bring in Opus for a rules-schema/D&D-correctness
review. Not yet.

---

# Update 2026-08-19 — excellent progress, here's what's next

Read `docs/V0-PLAN.md` (new) — I reviewed all four research docs, the DM brain test
results, the trickster adversarial test, and the 4-method epic-scene demo. This is
genuinely good, validated work. Here's the next phase:

1. **Merge the proven pieces into one working v0 loop**, not separate demo scripts:
   `test_api_dm.py` (DM brain + state engine) + `narrator_parser.py` (segment parsing)
   + TTS (Kokoro or Qwen3-TTS) + `make_ambience_demo_v2.py` (library ambient audio) →
   a single script/app where: player types an action → DM brain responds → rules
   lawyer validates the [MECHANICS] tags against state → narration pipeline generates
   audio (voice + music/SFX) → play it → wait for next input. This is the actual v0.
2. **Wire the trickster adversarial test in as a standing check** — run it against
   whichever model ends up as the DM brain before trusting the rules lawyer in
   real play.
3. Once merged, do a **real multi-turn play session** (Arie actually playing, not
   scripted actions) — this will surface UX problems the scripted tests can't.
4. **Cost/scope decision needed from Arie, don't decide unilaterally:** the epic-scene
   demo used the ElevenLabs SFX API (paid, ~$0.50 so far) for SFX quality. My
   recommendation in `docs/V0-PLAN.md` is to ship v0 with library/local SFX only and
   treat ElevenLabs as an optional later upgrade — but confirm with Arie rather than
   assuming either way.
5. Don't run the Claude Opus/Sonnet/Fable baseline test yourself — that's on Arie
   (`notes/claude_dm_test_prompt.md`), but be ready to fold the results into
   `dm_test_results_summary.md` once he's done it.

Excellent work on the DM brain testing, the SoloQuest pattern, and the trickster
adversarial suite — that's exactly the right instinct for a "programmatic rules lawyer."

---

# Update 2026-08-17 ~22:15 — PROJECT SCOPE EXPANDED, read this first

Arie has realigned the project's actual goal. Read `docs/PROJECT-ROADMAP.md` (new file,
I maintain it as the living source of truth from now on — check it at the start of every
session). Short version: this is no longer just "narrate text Arie pastes from Claude" —
the app itself now needs to run the DM (story, world/character/inventory tracking, dice,
NPCs). TTS work continues but is now the *smaller* of three workstreams (TTS, DM engine,
ambient audio/music).

**New research tasks, in priority order (all research-only, no big downloads without
asking Arie first, same rule as always):**

1. **AI-DM engine architecture research.** Re-visit the products already in
   `MARKET_RESEARCH.md` (Familiar, TableForge, Scrollbook, Eternal DM, Visionarium) plus
   any others you find, but from a new angle: HOW do they track world/character/inventory
   state? How do they structure dice rolls (visible vs. hidden)? Do they use structured
   tool-calling / a JSON state object the LLM reads and writes each turn, or something
   looser? Look at their docs, any public architecture posts, GitHub repos if open-source.
   Write findings to `glm-work/notes/dm_engine_research.md`.

2. **Local/offline LLM feasibility for DM duty — THIS IS NOW THE TOP-PRIORITY QUESTION.**
   Arie confirmed (2026-08-17) he wants to stay near the original ~€10/month budget, which
   pushes hard toward a local/offline LLM for the DM brain rather than a paid API. Research
   which open-weight models (Llama, Qwen, DeepSeek, Mixtral, etc.) are realistic to run on
   Arie's M1 Max (32GB) via Ollama or llama.cpp for creative long-context narration with
   state consistency — this is a much heavier reasoning task than TTS, so be honest about
   where local models are likely to fall short vs. Claude/GPT-5 quality. If feasible,
   propose a concrete small hands-on test Arie could try (specific model, specific short
   test scenario) rather than just reporting specs. If you conclude local models are
   clearly not good enough, say so plainly with evidence — don't default to recommending
   a paid API without flagging the cost tradeoff explicitly for Arie to decide. Write to
   `glm-work/notes/local_llm_dm_research.md`.

3. **Music/ambient sound research.** Survey two approaches: (a) generative models
   (MusicGen, Stable Audio Open, AudioLDM2, etc.) — self-hostable feasibility on the M1
   Max, model sizes, quality; (b) library/loop-based approaches (royalty-free ambience
   and music libraries, licensing terms, how triggering by scene-type keyword would work
   practically). Write to `glm-work/notes/audio_ambience_research.md`.

4. **Read `sonnet-work/CAMPAIGN-CONFIG-DRAFT.md`** — my first-pass draft of the
   campaign-setup questions (tracking granularity, dice visibility, NPC management, etc).
   Use it as the concrete target when doing task 1 above — check specifically how the
   existing AI-DM products handle each of those categories.

**Still worth finishing, lower priority now:** the Phase 1 TTS wrap-up items from the
previous update below (UTMOSv2 re-run, Dia/Higgs after approval, RESULTS.md) — don't
abandon them, just don't let them block the research above.

**Do not start implementing a DM engine yet.** This needs a real architecture decision
first (likely a focused Opus session once the research above is back) and a cost
estimate for API-based options — building ahead of that risks a rewrite.

---

# Update 2026-08-17 ~21:55 — read this section first

Full re-audit done (Qwen3-TTS results, voice catalog, ensemble story, narrator_parser.py,
play_test.py, GUI mockup all reviewed). Good progress — see `sonnet-work/` for details if
curious. Five concrete things to do next, in priority order:

1. **Re-run `score_utmos.py`.** The UTMOSv2 model file finished downloading at 20:11, but
   the one scoring attempt in the logs was at 19:48 (before the file existed) and
   silently produced nothing. Every MOS score in `RESULTS.md` is still `_pending_` for a
   fixable reason — just run it again now that the model is actually there.

2. **Update `GLM-HANDOFF.md`.** It hasn't been touched since ~19:57 and is now missing:
   Qwen3-TTS results, the voice catalog + ensemble story, narrator_parser.py, play_test.py,
   and the GUI mockup work. Bring the "Current status" checklist up to date so a future
   session (or Arie) reading this doc isn't misled about what's done.

3. **Delete `glm-work/narrator_parser.py.bak`** (or move it somewhere gitignored) — stray
   backup file, shouldn't be committed as-is.

4. **Before downloading Dia-1.6B or Higgs Audio V2:** ask Arie explicitly for approval —
   combined that's ~8GB (3.22GB + 4.75GB) on his slow connection. Present the sizes like
   you did for Kokoro/Qwen3 rather than assuming.

5. **If the Dia or Higgs download stalls and you fall back to manual `curl` into a custom
   folder (like you did for Qwen3):** remember to update `MODEL = "mlx-community/..."` in
   `run_dia_1_6b.py` / `run_higgs_audio.py` to the local path afterward — same bug pattern
   as before, now that you know what to look for it should be quick to catch yourself.

Everything else (voice catalog, parser, play_test.py, GUI mockup) looks solid — keep going
as directed by Arie in that other session.

---

# Instructions for GLM — from Sonnet, 2026-08-17

Read `sonnet-work/TTS-LANDSCAPE-RESEARCH-2026.md` first — it has the full research behind
these instructions. This doc is just the step-by-step "do this" version. As always: your
`glm-work/` folder is yours, I'm not editing anything in it, this is just handoff input
for you to act on (or push back on, if you disagree — flag it to Arie).

You've done good work so far (Kokoro end-to-end, accurate download-size research, catching
the spacy 429 bug yourself, correctly following the mlx-audio switch, Task 0 done, correctly
deferring the Kokoro pipeline fix). See `sonnet-work/STATUS-UPDATE-2.md` for a fresh audit.

## 0. FIX THIS FIRST — `run_qwen3_voicedesign.py` will ignore your manual download

You curled the Qwen3-TTS VoiceDesign 8bit files into
`glm-work/models/qwen3_voicedesign_8bit/` because the HF download stalled — good call.
But `run_qwen3_voicedesign.py` still has:
```python
MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"
```
I checked `mlx_audio`'s actual `get_model_path()` source in your venv
(`.venv/lib/python3.12/site-packages/mlx_audio/utils.py`) — it only treats a string as a
local path if it starts with `.`, `/`, or `~`. A bare `"mlx-community/..."` string is
always treated as an HF repo ID, so as written, running this script will **ignore your
manually-downloaded files and try to re-download the same ~2.6GB again** into the default
HF cache. Fix before the current download even finishes, so there's no wasted re-download:
```python
MODEL = "models/qwen3_voicedesign_8bit"  # or an absolute path
```
Do this now, it costs nothing and saves a second multi-hour download on Arie's connection.

Two things changed based on my research: **how** to run the remaining models, and
**Task 0 is still outstanding** (now done — see below, kept for history).

## 1. Write `docs/MARKET_RESEARCH.md` (Task 0 — still not done, spec says do this before more model work)

You don't need to redo the research — it's already done in
`sonnet-work/TTS-LANDSCAPE-RESEARCH-2026.md` section 4. Turn that into
`docs/MARKET_RESEARCH.md` per the spec's requested format (what it does, maintained?,
license, cost if hosted, adopt/fork/reference-only). Feel free to copy my findings
directly — just cite sources (URLs are in my doc). This should have been done before
Kokoro, but doing it now (informed by hands-on Kokoro testing) is fine — note in the doc
that it was done out of order and why (you can just link to this instruction).

## 2. Before installing Qwen3-TTS natively, try `mlx-audio` instead

Do **not** just `pip install` Qwen3-TTS's own PyTorch package as originally planned. Try
this first:

```bash
uv pip install mlx-audio
```

Then use the **1.7B-VoiceDesign** model via mlx-audio's `mlx-community` weights (check
mlx-audio's own docs/examples for the exact loading API — it's a `load_model()` +
`generate()` pattern per their README). This should be:
- Faster to run (Metal GPU acceleration, not CPU fallback)
- Smaller download if you pick a quantized variant (8bit ≈1.7GB, 4bit ≈0.85GB, vs ~4.7GB
  for the full bf16 PyTorch path you researched earlier)

**Verify VoiceDesign specifically works** through mlx-audio (not just Base/CustomVoice) —
my research found a *different* MLX port (`odiak/Qwen3-TTS-MLX`) that does NOT support
VoiceDesign yet, so don't assume; test it directly with a quick natural-language voice
description before running the full test suite.

**Fallback:** if mlx-audio's Qwen3-TTS/VoiceDesign path is broken, flaky, or missing
features you need, fall back to the original plan (native PyTorch package, MPS device).
Don't burn more than ~30 min debugging the MLX path before falling back — this is exactly
the kind of thing to note as "tried mlx-audio, hit X, fell back to native" in your notes
rather than getting stuck.

**Download size to confirm with Arie before pulling:** ~1.7GB (8bit) or ~4.7GB (bf16,
original plan) — smaller than your original estimate if quantized route works, so
mention that to him.

## 3. For Dia2 and Higgs Audio V2 (when/if you get to them), check `mlx-audio` first too

Same idea — `mlx-audio`'s model table lists "Dia" and "Higgs Audio v2/v3" as supported
architectures with published Apple Silicon benchmarks (Higgs Audio v2 3B ran with
real-time voice cloning on M-series in the project's own benchmarks). This directly
addresses the spec's worry that these are "CUDA-first, likely impractical on Apple
Silicon" — that was true for the original repos, may not be true via mlx-audio.

One open question I couldn't fully confirm: whether mlx-audio's "Dia Model" support
covers **Dia2** specifically (the model in your download-budget doc) or only the older
single "Dia" 1.6B model. Check this before downloading anything — if only original Dia is
supported, that's a different (smaller, 1.6B vs 1B/2B) model than what's in your budget
doc, and worth flagging to Arie as a substitution before proceeding.

Sizes if mlx-audio path works: Higgs Audio v2 q6 ≈4.75GB, q8 ≈6.18GB (vs 11.6GB original)
— meaningfully smaller downloads on Arie's 4G connection, worth mentioning when you ask
for approval.

## 4. Kokoro pipeline improvement (Arie's feedback: pauses + voice transitions)

Don't build this from scratch yet. Two existing open-source projects already solve
close variants of this problem — read their approach before writing new code:
- `Xerophayze/TTS-Story` — pause markers, per-speaker pitch/speed, silence controls
- `wcharliebrown/multivoice` — `[beat]`/`[long beat]` pause tags, automatic sentence-pause
  insertion, emotion cue parsing, all built around Qwen3-TTS

**Do not attempt this yourself yet** — wait until Qwen3-TTS is tested. If Qwen3-TTS
sounds significantly better out of the box (plausible, since it's a much bigger, more
recent model with native prosody/emotion control), the whole Kokoro-pipeline-improvement
question may become moot. Test Qwen3-TTS first, then ask Arie whether it's still worth
optimizing Kokoro specifically.

## 5. Things you do NOT need to ask a smarter model about (handle yourself)

- Standard install/download/test loop for any model, mlx-audio or not
- Writing the `RESULTS.md` comparison table once ≥2 models are tested
- Chatterbox / Higgs Audio original-repo attempts — low priority, your existing
  judgment on when to stop applies

## 6. Escalate to Sonnet/Opus if

- mlx-audio's Qwen3-TTS VoiceDesign genuinely doesn't work and native PyTorch/MPS also
  fails in a way you can't debug in ~30 min
- Dia2 (native or mlx-audio) needs real porting/debugging work, not just "try the
  documented API and see if it works"
- You want a second opinion on the Kokoro pipeline redesign once you get to it — this is
  a legitimate small-scope engineering task worth a stronger model's first pass rather
  than iterating from scratch

Everything else — keep going, you've been doing this well.
