# Download Proposal — Updated After Research Completion

**Prepared by:** Download assistant (GLM session), 2026-08-18
**For:** Arie's review and approval before any downloads start
**Connection:** Slow 5G (observed ~0.5-1 MB/s, unstable)
**Disk:** 517 GB free — no disk constraint
**Budget:** 20 GB authorized earlier; ~4.7 GB used (Qwen3-TTS + UTMOSv2)

---

## What changed since the last proposal

The research assistants have now completed all four research tasks:
- **Task 1** (AI-DM competitor architecture) — done, `dm_engine_research.md`
- **Task 2** (local LLM feasibility — TOP PRIORITY) — done, `local_llm_dm_research.md`
- **Task 3** (ambient audio) — done, `audio_ambience_research.md`
- **Task 4** (campaign config lens) — done

UTMOSv2 scoring is also complete — MOS scores are in RESULTS.md (Kokoro avg 3.65, Qwen3 avg 3.57).

The research has materially changed the download picture. Here's what's now known:

### Key research findings that affect downloads

1. **70B models do NOT fit on M1 Max 32GB.** Llama 3.3 70B needs ~52GB. Ruled out.
2. **The realistic local-LLM ceiling is ~32B dense / ~30B MoE.** Two candidates:
   - `qwen3:32b` (Q4_K_M, **20 GB** on Ollama) — best creative quality that fits
   - `qwen3:30b-a3b` (Q4_K_M, **19 GB** on Ollama) — MoE, ~2x faster, lower creative score
3. **The architecture pattern (LLM narrates, code adjudicates) lowers the bar** — local
   models only need to narrate + follow format, not be a full DM. This makes the hands-on
   test worth doing.
4. **Ambient audio: library-based is recommended for v1.** No download needed. Generative
   models (MusicGen/AudioGen/Stable Audio) are deferred — the zero-download demo already
   lets Arie hear the concept.
5. **TTS wrap-up (Dia/Higgs) is now lower priority** — Kokoro and Qwen3 are both working
   and scored. Dia/Higgs would add comparison data but won't change the direction.

---

## Current disk state (no download needed for these)

| Item | Size | Status |
|------|------|--------|
| Kokoro-82M (PyTorch) | 326 MB | Complete, tested, scored (MOS 3.65 avg) |
| Kokoro-82M (MLX bf16) | 339 MB | Complete, untested |
| Qwen3-TTS VoiceDesign 8bit | 2,282 MB | Complete, tested, scored (MOS 3.57 avg) |
| UTMOSv2 fold0 weights | 781 MB | Complete, scoring done |
| wav2vec2-base (UTMOSv2 dep) | 725 MB | Complete |
| Qwen3 HF cache (stalled partial) | 623 MB | **WASTE — can be deleted** |

**Reclaimable:** 623 MB (stalled Qwen3 HF cache — local copy already complete)

---

## Pending downloads — priority proposal

### Priority 1: DM Engine hands-on test (THE critical path)

This is the single most important open question per Sonnet's roadmap and the research.
The research proposes a concrete 10-turn test scenario. To run it, we need Ollama + one
or two models.

| # | Download | Exact size | Why | Time on 5G |
|---|----------|-----------|-----|-----------|
| 1 | Ollama installer | ~250 MB | Gateway to all local LLMs | ~5 min |
| 2 | `qwen3:32b` (Q4_K_M) | **20 GB** | Best creative quality that fits M1 Max. The dense pick. | ~6-10 hrs |
| 3 | `qwen3:30b-a3b` (Q4_K_M) | **19 GB** | MoE pick — ~2x faster, test if quality holds. | ~6-10 hrs |

**Subtotal: ~39 GB for both models, or ~20 GB for just one.**

**Recommendation:** Start with `qwen3:32b` only (20 GB). Run the 10-turn test. Only
download `qwen3:30b-a3b` if the 32B quality is good but speed is a problem (then test
whether MoE speed is worth the quality drop). This halves the initial download commitment.

**Alternative smaller option:** `qwen3:8b` (5.2 GB) or `qwen3:14b` (9.3 GB) could be
tested first as a quick "does the orchestration pattern work at all" check before
committing to the 20 GB download. The research notes 8B scores much lower on creative
(64.50 vs 81.00 for 32B), but it would validate the test harness in ~2-3 hours of
download instead of ~8.

### Priority 2: TTS wrap-up (conditional — defer until Arie decides)

| # | Download | Size | Why | Condition |
|---|----------|------|-----|-----------|
| 4 | Dia-1.6B (MLX) | 3.22 GB | Native [S1]/[S2] multi-speaker comparison | Only if Arie wants more TTS comparison |
| 5 | Higgs Audio V2 (MLX q6) | 4.75 GB | Voice cloning test | Only if voice cloning is needed |

**Recommendation: DEFER.** Kokoro and Qwen3 are both working and scored. The research
hasn't identified a gap that Dia or Higgs would fill. Download only if Arie listens to
the existing outputs and says "I need better multi-speaker" (Dia) or "I need voice
cloning" (Higgs).

### Priority 3: Ambient audio generative models (DEFER — research says skip for v1)

| # | Download | Size | Why | Condition |
|---|----------|------|-----|-----------|
| 6 | AudioGen medium | ~3.6 GB | Generative ambience/SFX test | Only if Arie wants to test generative after hearing the demo |
| 7 | Stable Audio Open Small | ~1.5 GB | Permissive generative option | **MPS accuracy risk on M1/M2** — research flagged this |
| 8 | MusicGen small | ~1.2 GB | Generative music stings | CC-BY-NC license; lowest quality variant |

**Recommendation: SKIP for now.** The research clearly recommends library-based for v1.
The zero-download demo (`outputs/ambience_demo/`) already lets Arie hear the concept.
If Arie wants to test generative later, AudioGen medium is the most useful of the three.

---

## Recommended download plan

### Step 0: Cleanup (now, 0 download)
- Delete stalled Qwen3 HF cache: `rm -rf ~/.cache/huggingface/hub/models--mlx-community--Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit/`
- Reclaims 623 MB, zero risk

### Step 1: Install Ollama (~250 MB, ~5 min)
- `brew install ollama` or download from ollama.com
- Start the service: `ollama serve`

### Step 2: Quick harness validation with small model (optional, 5.2 GB, ~2-3 hrs)
- `ollama pull qwen3:8b`
- Run the 10-turn test from the research proposal
- Purpose: validate the test script works, see if even a small model can follow the
  response format. NOT a quality verdict — 8B is expected to be weak on creative.

### Step 3: The real test (20 GB, ~6-10 hrs — can run overnight)
- `ollama pull qwen3:32b`
- Run the same 10-turn test
- This is the actual decision input: is local viable for DM duty?

### Step 4 (conditional): MoE speed comparison (19 GB, ~6-10 hrs)
- Only if 32B quality is good but speed is problematic
- `ollama pull qwen3:30b-a3b`
- Test whether ~2x speed is worth the creative quality drop

### Deferred: TTS + ambient models
- Dia/Higgs: wait for Arie's listening verdict on existing TTS
- Generative ambient: wait for Arie's verdict on the library-based approach

---

## Total download budget if everything is approved

| Tier | What | Size |
|------|------|------|
| Minimum viable test | Ollama + qwen3:32b | **20.3 GB** |
| + Quick validation | + qwen3:8b first | **25.5 GB** |
| + MoE comparison | + qwen3:30b-a3b | **39.3 GB** |
| + TTS wrap-up | + Dia + Higgs | **47.3 GB** |
| + Generative ambient | + AudioGen + Stable Audio + MusicGen | **53.6 GB** |

**My recommendation: approve Ollama + qwen3:32b (20.3 GB) for the DM engine test.
Everything else is conditional on test results or Arie's listening verdicts.**
