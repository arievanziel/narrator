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
