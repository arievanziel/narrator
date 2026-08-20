# Local / Offline LLM Feasibility for DM Duty

**Author:** GLM-5.2 High, 2026-08-18
**Task:** INSTRUCTIONS-FOR-GLM.md task 2 — **TOP PRIORITY** research question.
**Hardware target:** Arie's MacBook Pro, M1 Max (32-core GPU), 32 GB unified memory,
400 GB/s memory bandwidth.
**Budget constraint:** stay near original ~€10/month total (per PROJECT-ROADMAP.md
decisions log, 2026-08-17). This is what makes "can a local model do it" the
load-bearing question rather than a secondary option.

---

## TL;DR (read this first)

1. **A 70B-class dense model does NOT fit in 32 GB.** Llama 3.3 70B at Q4_K_M needs
   ~51.9 GB; even Q2_K (~27 GB) leaves no room for context/KV cache and quality
   collapses. The strongest open-weight reasoners are effectively out of reach on
   this machine. This is a hard ceiling, not a tuning problem.

2. **The realistic local ceiling is ~32-35B dense at Q4, or MoE models with larger
   total params but small active-param counts.** The strongest candidates that
   actually fit and run at usable speed are **Qwen3-30B-A3B (MoE)** and
   **Qwen3-32B (dense)**, with **Gemma 4 31B / 26B-A4B** as alternatives. All land
   in the 15-50 tok/s range — playable for turn-based DMing, not real-time streaming.

3. **Creative-writing quality is genuinely below frontier models.** On independent
   creative-writing benchmarks, Claude Sonnet 4.6 (~4.04) and GPT-5.2 (~3.94) clearly
   outscore Qwen3-Max (~2.87) and the local-able tier. The gap is real and measurable.
   **But DMing is not pure literary fiction** — it is structured narration + rule
   following + state tracking, and the architectural pattern from task 1 (deterministic
   rules engine + structured state injection + enforced response format) substantially
   narrows the gap by offloading the parts local models are worst at.

4. **Recommendation: local is worth a real hands-on test, not a default no.** The
   combination of (a) the TableForge/SoloQuest architecture pattern separating
   narration from rules, (b) MoE models that fit and run fast, and (c) the €10/month
   budget means a concrete test is the right next step — see the proposal at the end.
   If the test shows local quality is too weak, *then* come back to Arie with real
   API cost numbers before defaulting to Claude/GPT.

5. **Honest caveat:** even with the best orchestration, a 30B local model will
   produce flatter prose, follow long-context state less reliably, and need more
   prompt engineering than Claude. The question is whether "good enough at
   narration + great orchestration" beats "great narration + manual state tracking
   by Arie" — and only a hands-on test answers that.

6. **UPDATE 2026-08-18 — there is a third option Arie raised that changes the
   picture: cheap per-token API on open-weight models (Groq, DeepInfra, etc.).**
   This gives you 70B-120B class quality (which cannot run on your 32GB Mac at
   all) at 5-20x cheaper than Claude/GPT prices — and it **fits the €10/month
   budget**. See §5a below for the full breakdown. This is likely the best
   cost/quality/speed tradeoff for the DM brain, and it wasn't covered in the
   original research.

---

## 1. What fits on M1 Max 32 GB

### Hard memory math

macOS reserves ~8 GB for the OS, leaving ~24 GB usable for model + KV cache.
llama.cpp/MLX read the Metal working-set limit (~75% of unified memory) on startup.
Source: canitrun.dev M1 Max analysis, willitrunai.com per-model fits.

| Model | Type | Quant | Footprint | Fits 32GB? | Decode (M1 Max 32GB) |
|---|---|---|---|---|---|
| Llama 3.3 70B | dense | Q4_K_M | ~51.9 GB | **NO** | (would be ~2.5 tok/s even if it fit) |
| Llama 3.3 70B | dense | Q2_K | ~27.3 GB | marginal, no KV room, quality poor | — |
| Qwen2.5 72B | dense | Q4_K_M | ~52.1 GB | **NO** | — |
| **Qwen3-32B** | dense | Q4_K_M | ~23.9 GB | **YES** (tight) | ~15 tok/s |
| **Qwen3-30B-A3B** | MoE (3B active) | Q4_K_M | ~24.4 GB | **YES** (offload ~1GB) | ~30 tok/s |
| Gemma 3 27B | dense | Q4_K_M | ~16 GB | YES | ~8.8 tok/s (oMLX, M1 Max 32c) |
| Gemma 4 31B | dense | Q4_K_M | ~18-20 GB | YES | ~16.5 tok/s (M3 Max 64GB ref) |
| Gemma 4 26B-A4B | MoE (3.8B active) | Q4_K_M | ~22 GB | YES | ~64 tok/s (M3 Max 64GB ref) |
| Qwen3.6-27B | dense | Q4_K_M | ~16 GB | YES | ~17.3 tok/s (M3 Max 64GB ref) |
| Llama 3.1 8B | dense | BF16 | ~16 GB | YES | ~19-20 tok/s |
| Qwen3-8B | dense | Q4_K_M | ~5 GB | YES (lots of headroom) | ~40+ tok/s |

Sources: willitrunai.com, omlx.ai benchmarks (M1 Max 24c/32c, 64GB), hiesch.eu
llama.cpp benchmarks (M3 Max 64GB), canitrun.dev M1 Max page, siliconscore.com.
Note: M1 Max is ~20-30% slower than M3 Max at equal memory due to bandwidth/core
differences, so M3 Max numbers are an optimistic upper bound — discount
accordingly for Arie's machine.

### The two standouts for DM duty

**Qwen3-30B-A3B (MoE)** — the strongest fit. Only 3B params active per token, so
despite 30B total it decodes at ~30 tok/s on M1 Max 32GB (willitrunai estimate;
oMLX measured 47.9 tok/s at 1k context on M1 Max 64GB). 256K context window.
Qwen3 family has native function-calling support. The MoE tradeoff: quality per
active parameter is lower than a dense 30B, but for structured DM output
(following a response format, calling tools) this matters less than for free-form
prose. **This is my top pick for the hands-on test.**

**Qwen3-32B (dense)** — the strongest dense model that fits. ~15 tok/s is slower
but still playable (a 200-token narration = ~13s). Qwen3-32B with thinking enabled
scores 81.00 on DataLearner's creative writing benchmark (vs Claude Sonnet 4 at
83.05, Claude Opus 4 at 83.75 — a ~2-3 point gap, not a chasm). On EQ-Bench
Creative Writing v3, Qwen3 VL 32B Instruct ranks #6 at 0.856, ahead of several
larger/closed models. **Second pick — use if MoE quality proves weak in testing.**

### What does NOT fit (be honest about this)

- **Llama 3.3 70B** — the open-weight model closest to frontier reasoning. Out.
- **Qwen2.5 72B / Qwen3-235B-A22B** — the strongest Qwen creative models. Out.
- **DeepSeek V3 / R1** (671B MoE) — far too large. Out.
- **Mixtral 8x22B** — too large. Out.
- **Mixtral 8x7B** at Q2_K fits (~18 tok/s) but is a 2024 model, outclassed by
  Qwen3/Gemma 4 at similar speed. Skip.

The practical consequence: **Arie cannot run the strongest open-weight reasoners
locally.** The local tier caps at ~32B dense / ~30B MoE. This is the single most
important constraint and it is not negotiable — it is physics (memory bandwidth +
capacity).

---

## 2. Creative-writing quality: the honest comparison

### Benchmark evidence

**makerpulse.ai "Creative Gap" (2026):** creative vs. task scores.
- Claude Sonnet 4.6: 4.04 creative / 4.34 task
- Claude Opus 4.6: 3.95 creative
- GPT-5.2: 3.94 creative / 4.61 task
- DeepSeek V3.2: 3.27 creative
- **Qwen3-Max: 2.87 creative** — "largest task-to-creative gap in our dataset
  (1.20 points)... Don't use Qwen3-Max for creative work. Not because it's
  incapable, but because it's optimized for something else."

**lechmazur/writing benchmark (relative comparison scores, 2026):**
- Claude Fable 5: 3.3 (rank 1)
- GPT-5.5: 3.0
- Claude Opus 4.7: 2.4 (rank 8)
- Claude Sonnet 4.6: 2.2 (rank 9)
- GLM-5.2 max: 0.9 (rank 14)
- (Qwen3-32B not separately listed in the top-rated slice shown)

**DataLearner creative writing benchmark:**
- Claude Opus 4: 83.75
- Claude Sonnet 4: 83.05
- DeepSeek-V3: 81.60
- **Qwen3-32B (thinking): 81.00**
- Qwen3-235B-A22B: 80.40
- **Qwen3-32B (standard): 78.30**
- Qwen3-30B-A3B (standard): 68.10 ← the MoE candidate scores notably lower
- Qwen3-8B: 64.50

**EQ-Bench Creative Writing v3 (0-1 scale, LLM-judged):**
- Qwen3-235B-A22B-Instruct: 0.875 (rank 1)
- Qwen3 VL 32B Instruct: 0.856 (rank 6) — strong
- Qwen3-Next-80B-A3B-Instruct: 0.853
- Qwen3 VL 30B A3B Instruct: 0.846

### What this means for DMing

The picture is nuanced, not "local is bad":

1. **Qwen3-32B dense is genuinely competitive on some creative benchmarks**
   (EQ-Bench rank 6, DataLearner 81 with thinking). The gap to Claude Sonnet 4
   is ~2 points on DataLearner, not 20. For DM narration — which is structured,
   scene-driven, and rewards consistency over literary flourish — this tier is
   plausibly "good enough" on prose.

2. **The MoE candidate (Qwen3-30B-A3B) scores much lower on pure creative
   writing (68.10 standard)** — this is the real risk. Speed wins come at a
   creative-quality cost. The hands-on test should specifically compare 30B-A3B
   vs 32B-dense quality on the same DM scenario.

3. **Qwen3-Max (the closed Qwen flagship) scoring 2.87 on makerpulse is a
   warning about the Qwen family's creative ceiling**, but Qwen3-Max is
   optimized differently from Qwen3-32B-instruct; the 32B instruct model is
   tuned for following instructions, which is closer to DM duty than free
   fiction. Still, flag this: the Qwen family is not the strongest creative
   writer among open weights.

4. **The gap matters less when orchestration handles state.** Per task 1's
   findings (TableForge, SoloQuest, Gemma4 DM Companion): when deterministic
   code handles rules/state and the LLM only narrates + emits structured tags,
   the model's job shifts from "remember everything and be brilliant" to
   "follow format and write a good scene beat." Local models are materially
   better at the latter than the former.

### Where local models will fall short (honest list)

- **Long-context consistency:** even at 256K context, attention degrades over
  long sessions (the "lost in the middle" problem). Frontier models handle this
  better. Mitigation: external state log injected every turn (Arcanum RPGs /
  SoloQuest pattern) — but this is prompt engineering work, not free.
- **Prose quality / voice variety:** flatter narration, less distinct NPC
  voices, more repetitive phrasing across a long session. Arie will notice this
  vs. Claude.
- **Instruction adherence on edge cases:** SoloQuest's author documents needing
  v9 of the system prompt with explicit "wrong pattern / correct pattern"
  examples to stop the model narrating outcomes before dice rolls. Local models
  need this even more aggressively.
- **Tool-calling reliability:** Qwen3 has native function-calling but smaller
  models drop/hallucinate tool args more often than Claude. The Gemma4 DM
  Companion's 3-pass (state-before → generate → state-after → diff → commit)
  pattern exists precisely because one-pass state updates desync. Plan for this.
- **Reasoning on novel rules interactions:** a 30B model will misrule edge cases
  (grapple + shove + opportunity attack sequencing) more often than Claude.
  Mitigation: deterministic rules engine handles mechanics (TableForge pattern),
  LLM never adjudicates.

---

## 3. The architectural enabler (from task 1)

This is the key insight that makes local feasibility plausible rather than
doomed: **the products getting DMing right do NOT ask the LLM to be the whole DM.**
They split the job:

| Job | Who does it | Why |
|---|---|---|
| Narration, NPC dialogue, scene description | LLM | This is what LLMs are good at |
| Dice rolls, HP, combat resolution, spell slots | Deterministic code | LLMs hallucinate numbers; code doesn't |
| World/character/inventory state | Structured store (JSON/SQLite), injected into prompt each turn | Conversation history is unreliable; a state object is authoritative |
| Rules adjudication | Rules engine (5e SRD in code) | LLMs misrule edge cases; code is correct |
| Memory across sessions | Event log + vector DB + summaries | Context window can't hold a campaign |

Sources: TableForge ("AI narrates, rules engine adjudicates — two different jobs,
two different tools"), Familiar (194 tools, rules engine checks every move),
Project Infinity ("AI reads but cannot invent"), SoloQuest (game state as source
of truth, [MECHANICS] tags), Scrollbook (5-layer cached context + tool use),
Gemma4 DM Companion (3-pass state diff), dnd-llm-game (separate utility model
for state extraction).

**Implication for local LLM choice:** if Arie's app adopts this architecture,
the local LLM only needs to:
1. Write good scene-level narration (Qwen3-32B can do this respectably)
2. Follow a structured response format ([NARRATIVE]/[MECHANICS] sections)
3. Call tools for dice/state lookups (Qwen3 has native function-calling)

It does NOT need to: remember a 40-hour campaign, adjudicate grapple rules,
track spell slots, or be a literary novelist. That's a much lower bar than
"replace Claude as a DM," and it's the bar the local-able tier can plausibly
clear. **This is why I'm not defaulting to "local is not good enough" despite
the benchmark gap.**

---

## 4. Concrete hands-on test proposal

Goal: answer "is a local model good enough to DM, with proper orchestration?"
in one evening of testing, without building the full app.

### Option A (fastest): use an existing local-DM harness

Two open-source projects already solve the orchestration and run on Ollama:

- **nickc672/gemma4-dungeon-master** — Gemma 4 31B, 3-pass state-diff, Ollama,
  Streamlit UI, closed-world benchmark suite. The most engineered local-DM
  project I found. Caveat: designed for Gemma 4; would need adapter work for
  Qwen3, but the orchestration code is reusable.
- **tegridydev/dnd-llm-game** — FastAPI + React, Ollama, separate utility
  model for dice/state, LanceDB for lore RAG. Uses llama3.2:1b by default
  (too weak) but is model-agnostic — swap `OLLAMA_CHAT_MODEL=qwen3:32b` and
  test. Lower-effort starting point than Gemma4 DM.

**Recommended:** clone `dnd-llm-game`, point it at Qwen3-32B, run a 10-turn
combat scenario. Lowest setup cost, real orchestration, model-agnostic.

### Option B (more controlled): minimal SoloQuest-style prompt

Write a ~150-line Python script using `ollama` Python client:

1. **System prompt** (~50 lines): "You are a D&D 5e DM. Rules contract: rolls
   before outcomes, state is authoritative, respond in 4 sections
   [NARRATIVE]/[MECHANICS]/[SUGGESTIONS]/[CHRONICLE]." Use SoloQuest's pattern
   (dev.to/austin_amento article) as the template.
2. **State injection:** serialize a small JSON state (PC: HP/AC/inventory/spell
   slots; NPC: HP/attitude; scene: location/light/time) into each turn's prompt.
3. **Response parser:** extract [MECHANICS] tags (HP_CHANGE, ROLL, ITEM_USED)
   and apply to state deterministically.
4. **Run the scenario:** level-1 fighter vs. 2 goblins in a tavern, 10 turns.
   Free-text player input.

### The test scenario (use for either option)

**Setup:** Level 1 Fighter (STR 16, HP 12, AC 16, longsword + shield) enters a
tavern. Two goblins (HP 7 each, AC 15, scimitar) attack.

**10 turns covering:** initiative, 2 rounds of combat (attack rolls, damage,
goblin reactions), a skill check (Perception to notice a third goblin hiding),
an inventory interaction (drink a healing potion), and a social beat
(intimidate the surviving goblin).

**What to grade (write down answers):**
1. **Roll-before-outcome:** does the model ever narrate "you hit for 8 damage"
   before the roll? (SoloQuest's #1 failure mode)
2. **State consistency after 10 turns:** is PC HP correct? Is the dead goblin
   marked dead? Is the potion removed from inventory? (The Gemma4 DM desync test)
3. **Prose quality:** is the narration flat/repetitive, or does it have scene
   texture? Compare to what Claude produces for the same scenario (Arie can
   run the same prompt in his Claude chat in 2 minutes).
4. **Speed:** tok/s observed, wall-clock per turn. Is it playable?
5. **Instruction adherence:** does it follow the 4-section response format
   reliably, or does it free-form?

**Decision rule (propose to Arie):**
- If ≥8/10 turns pass roll-before-outcome AND state is consistent at turn 10
  AND prose is "acceptable, not great" → **local is viable**, proceed to
  architecture design with local as the DM brain.
- If state desyncs or rolls are skipped → **local needs the full
  orchestration stack before it's usable** (still viable, but more build work).
- If prose is "obviously worse than Claude to the point of breaking
  immersion" → **local is not good enough for DMing quality**, come back to
  Arie with real API cost numbers (see §5) and let him decide on budget.

### Models to test (in order)

1. `qwen3:32b` (Q4_K_M, ~24GB) — the dense pick, best creative quality that fits
2. `qwen3:30b-a3b` (Q4_K_M, ~24GB) — the MoE pick, ~2x faster, test if quality
   holds
3. (optional) `gemma3:27b-it-qat` — if Qwen3 instruction adherence is weak,
   Gemma follows formats well

Install: `brew install ollama && ollama pull qwen3:32b` (~24GB download —
**ask Arie before pulling**, per the standing download-approval rule).

---

## 5. Cost comparison: local vs. API (for Arie's decision)

If local fails the test, here is the real cost picture so Arie decides with
numbers, not vibes. All figures are order-of-magnitude estimates, not quotes.

### Claude Sonnet 4.6 API (Anthropic, list price)
- Input: ~$3 / MTok, Output: ~$15 / MTok (verify current pricing before relying)
- Per-turn estimate: ~5K tokens input (system prompt + world state + history
  window) + ~500 tokens output (narration + mechanics) = $0.015 + $0.0075 ≈
  **$0.022/turn**
- 3hr session at ~1 turn/min = 180 turns ≈ **$4/session**
- 30 sessions/month = **~$120/month** — blows the €10 budget by ~12x
- **Prompt caching (Scrollbook's 90% savings) materially changes this.** If the
  system prompt + world state are cached (stable across turns), input cost
  drops ~90% → ~$0.004/turn → ~$0.70/session → ~$21/month. Still over budget
  but much closer. This is the single most important cost lever and worth
  modeling properly before deciding.

### GPT-5.2 API — similar shape, comparable cost. No clear advantage for DMing
over Claude Sonnet per the creative benchmarks (Claude leads creative).

### Local (Ollama, any model)
- $0 ongoing, electricity negligible on a laptop
- One-time: ~24GB download (Arie's connection — ask first)
- Cost is in **quality and build effort**, not money

### Hybrid (speculative, not for v1)
- Local model for 90% of turns (narration, simple scenes)
- Claude API for hard/creative moments (boss fight reveals, emotional NPC
  confrontations, session recaps)
- Could land near budget if API calls are rare — but this is architecturally
  complex and premature. Note only.

**Bottom line for Arie:** pure API at Arie's planned usage (~3hrs/day) breaks
the €10 budget unless prompt caching gets it to ~€20/month, which is still 2x
over. Local is free but quality-uncertain. **This is why the hands-on test
matters — it's the decision input.**

---

## 5a. Cloud options: running the DM brain off the MacBook (€10/month)

*Added 2026-08-18 after Arie asked: "what are the options when we run it, not on
my MacBook, but on a €10/month online service or VPS?"*

This question exposed a gap in the original research: I only compared "local on
M1 Max" vs. "Claude/GPT per-token API." There are actually **three** distinct
cloud options, and one of them is the likely winner.

### Option A: Rent a whole GPU VPS (dedicated or on-demand pod)

You control the machine, run any open model via Ollama/vLLM, pay by the hour or
month whether you use it or not.

| Provider | GPU | VRAM | Price | €/month (24/7) | Fits 70B? |
|---|---|---|---|---|---|
| Vast.ai (spot) | RTX 3090 | 24 GB | $0.07/hr | ~€51 | No (needs ~40GB at Q4) |
| Vast.ai (spot) | RTX 4090 | 24 GB | $0.27/hr | ~€197 | No |
| RunPod (on-demand) | RTX 4090 | 24 GB | $0.34/hr | ~€248 | No |
| RunPod (on-demand) | A100 80GB | 80 GB | $1.39/hr | ~€1,015 | Yes (easily) |
| Hetzner GEX44 (dedicated) | RTX 4000 SFF Ada | 20 GB | €0.38/hr | ~€234-281 | No |
| Hetzner GEX131 (dedicated) | RTX PRO 6000 Blackwell | 96 GB | (enterprise pricing) | — | Yes |

**Verdict: does NOT fit €10/month for 24/7.** The cheapest GPU VPS that can run
a 70B model 24/7 is an A100 at ~€1,000/month. A 24GB card (RTX 4090/3090) can
only run up to ~32B models — the same ceiling as Arie's Mac, just faster. The
only way a dedicated GPU fits €10/month is if Arie spins it up only during play
sessions (~3hrs/day = ~90hrs/month): an RTX 4090 spot on Vast.ai at $0.27/hr
would cost ~$24/month (~€22) for 90 hours — still over budget, and spot
instances can be interrupted.

**This option is not competitive for Arie's use case.** Skip it unless he wants
a dedicated always-on server for other reasons.

### Option B: Serverless GPU (pay per second while generating)

RunPod Serverless and similar: the GPU scales to zero between requests, you only
pay while the model is actively generating tokens. D&D turns are bursty (seconds
of generation, then idle while the player reads/decides), so this fits in theory.

| Provider/GPU | Per-second rate | Hourly equiv. | 70B fits? |
|---|---|---|---|
| RunPod Serverless RTX 4090 | ~$0.0003/s | ~$1.08/hr | No (24GB) |
| RunPod Serverless A100 80GB | ~$0.0006/s | ~$2.16/hr | Yes |
| RunPod Serverless H100 80GB | ~$0.0008/s | ~$2.90/hr | Yes |

**The cold-start problem:** every time a serverless worker scales from zero, it
has to load the model onto the GPU (a 70B Q4 model is ~40GB — load time can be
30-60 seconds). RunPod's FlashBoot claims <200ms cold starts for small models,
but a 70B will be slower. For D&D (one turn every ~30-60 seconds), the cold-start
overhead could dominate. Keep-warm workers cost money 24/7 even when idle —
back to the dedicated-GPU cost problem.

**Verdict: marginal fit.** Could work if Arie plays in focused sessions (spin up
a warm worker, play for 3hrs, spin down). An A100 at $2.16/hr × 3hrs × 30
sessions = ~$194/month — way over €10. Only fits if Arie plays much less than
3hrs/day. **Skip for now — Option C below is strictly better for the same
quality.**

### Option C: Per-token API on open-weight models (THE SWEET SPOT)

This is the option the original research missed. Providers like **Groq,
DeepInfra, Together AI, Fireworks, OpenRouter** serve open-weight models
(Llama 3.3 70B, Qwen3 32B, GPT-OSS 120B, DeepSeek) at per-token prices
**5-20x cheaper than Claude/GPT**. You get 70B-120B class quality (which cannot
run on Arie's 32GB Mac) without managing any GPU infrastructure.

**Key providers and pricing (per 1M tokens, USD):**

| Provider | Model | Input $/M | Output $/M | Speed (tok/s) | Notes |
|---|---|---|---|---|---|
| **DeepInfra** | Llama 3.3 70B Turbo | **$0.10** | **$0.32** | ~78 | Cheapest verified per-token rate |
| **Groq** | GPT-OSS 120B | $0.15 | $0.60 | ~500 | 120B params — biggest model that fits budget. Replaced Llama 70B on Groq 2026-08-16 |
| **Groq** | Qwen3 32B | $0.29 | $0.59 | ~662 | Fast; same model family as the local pick |
| **Groq** | Llama 3.3 70B | $0.59 | $0.79 | ~394 | **RETIRED from Groq 2026-08-16** — use GPT-OSS 120B instead |
| Together AI | Llama 3.3 70B | $0.88-1.04 | $0.88-1.04 | ~78 | More expensive than DeepInfra/Groq |
| Fireworks AI | Llama 3.3 70B | $0.90 | $0.90 | ~78 | Flat rate |
| OpenRouter | (routes to cheapest) | varies | varies | varies | Aggregator — adds small fee on top |

**Cost math for Arie's usage (~3hrs/day, ~1 turn/min = 180 turns/session, 30
sessions/month):**

Per-turn estimate: ~5K tokens input (system prompt + world state + history
window) + ~500 tokens output (narration + mechanics tags).

| Provider/Model | Per-turn cost | Per session (180 turns) | Per month (30 sessions) | Fits €10? |
|---|---|---|---|---|
| **DeepInfra Llama 3.3 70B** | $0.00066 | $0.12 | **$3.60** | **YES — easily** |
| **Groq GPT-OSS 120B** | $0.00105 | $0.19 | **$5.70** | **YES** |
| **Groq Qwen3 32B** | $0.00175 | $0.32 | **$9.60** | **YES (just)** |
| Groq Llama 3.3 70B (retired) | $0.00335 | $0.60 | $18.00 | No (but was close) |
| Claude Sonnet 4.6 (for comparison) | $0.022 | $4.00 | $120.00 | No (12x over) |
| Claude Sonnet 4.6 + 90% prompt caching | $0.004 | $0.70 | $21.00 | No (2x over) |

**With Groq Batch API + prompt caching stacked (effective rate ~25% of
on-demand):**
- Groq GPT-OSS 120B: ~$1.43/month — **well under €10**
- Groq Qwen3 32B: ~$2.40/month — **well under €10**

**Groq also has a FREE tier:** 30 requests/min, 6K tokens/min, 14,400
requests/day, no credit card required, all models available. This is enough to
test the DM brain extensively before paying anything. The free tier caps at
~500 req/day on larger models before rate-limiting — fine for solo D&D testing.

### What this means: the real decision matrix

| Option | Model quality | Speed | €/month | Privacy | Setup effort |
|---|---|---|---|---|---|
| Local (M1 Max, Qwen3-32B) | 32B — good but below 70B | ~15 tok/s | €0 | Full privacy | Medium (Ollama + 20GB download) |
| **DeepInfra Llama 70B** | **70B — much stronger** | ~78 tok/s | **~€3.60** | Data sent to server | Low (API call, no download) |
| **Groq GPT-OSS 120B** | **120B — strongest that fits budget** | ~500 tok/s | **~€5.70** | Data sent to server | Low (API call, no download) |
| Claude Sonnet 4.6 + caching | Frontier — best creative | fast | ~€21 | Data sent to Anthropic | Low (API call) |

### Recommendation (updated)

**The per-token open-model API route (Option C) is likely the best
cost/quality/speed tradeoff for Arie's DM brain**, and it wasn't covered in the
original research. Specifically:

1. **DeepInfra Llama 3.3 70B Turbo at ~$3.60/month** is the cheapest option that
   fits the budget with headroom. A 70B model is a meaningful quality step up
   from the 32B local ceiling — it's the model class the original research said
   "doesn't fit on your Mac" and dismissed. It does fit the *budget* via this
   route.

2. **Groq GPT-OSS 120B at ~$5.70/month** is the strongest model that fits the
   budget — a 120B parameter model at 500 tok/s (real-time streaming quality).
   This is a bigger model than anything that runs on a single 24GB GPU or on
   Arie's Mac. Groq's free tier lets Arie test it before paying.

3. **Both options need no downloads, no GPU management, and no local setup
   beyond an API key.** This is materially simpler than the local Ollama path.

**Tradeoffs vs. local:**
- **Privacy:** campaign data (story, character state, dialogue) is sent to a
  third-party server. For Arie's solo use this is likely acceptable; for a
  future multi-user product it needs a privacy policy and opt-in. Local keeps
  everything on-device.
- **Dependency on external service:** if Groq/DeepInfra has an outage, the DM
  brain is down. Local always works offline. Mitigation: the app could support
  both (API primary, local fallback) — but that's a v2 concern.
- **Open models are still weaker at creative writing than Claude** (per §2
  benchmarks). But 70B-120B is much closer to frontier than 30B local. The
  quality gap that matters is "70B open model vs. Claude Sonnet," not "30B
  local vs. Claude Sonnet" — and that gap is smaller.

**Tradeoffs vs. Claude/GPT API:**
- **5-20x cheaper** — fits €10/month vs. €20-120/month.
- **Weaker at creative writing** — Claude Sonnet 4.6 (4.04) vs Qwen3-Max (2.87)
  on makerpulse. But GPT-OSS 120B and Llama 3.3 70B are closer to Claude than
  the 32B local tier is. The architecture pattern (LLM narrates, code
  adjudicates) narrows this gap further.
- **No prompt caching on DeepInfra** (check current features). Groq offers
  caching + batch stacking. Claude's prompt caching is the most mature.

**Revised recommendation for the hands-on test:**
Instead of (or in addition to) the local Ollama test in §4, Arie should test
**Groq GPT-OSS 120B via the free tier** — no download, no setup beyond an API
key, and it's the strongest model that fits his budget. Run the same 10-turn
goblin-tavern scenario from §4. If the quality is good enough, the local-vs-API
decision may be settled in favor of "cheap open-model API" without ever
needing to download 20GB to the MacBook.

If Arie wants to compare local vs. cloud head-to-head: test Qwen3-32B locally
(Ollama, 20GB download) AND GPT-OSS 120B on Groq (free tier, no download) on
the same scenario. The quality and speed difference will be directly
comparable.

---

## 6. Open questions for Opus/architecture session (later)

- **State schema design:** JSON shape for world/character/inventory/quest
  state. Project Infinity, Pr0degie/dungeonmaster, and SoloQuest all have
  concrete examples — Opus should synthesize.
- **Memory tiering:** event log (SQLite) + vector DB (Qdrant/pgvector) +
  rolling summaries. SEP's 3-tier and TTA's 6-tier WorldContextBuilder v2 are
  the reference designs. How much is needed for Arie's solo use case vs.
  multi-user?
- **Tool-calling protocol:** SoloQuest's [MECHANICS] tag protocol vs. native
  function-calling vs. Familiar's 194-tool MCP approach. Tradeoff: simplicity
  vs. expressiveness vs. local-model reliability.
- **Local model final selection:** pending the hands-on test results above.
- **Cloud API provider selection (NEW):** if the per-token open-model route
  (§5a) wins, which provider — DeepInfra (cheapest, Llama 70B), Groq (fastest,
  GPT-OSS 120B / Qwen3 32B, free tier for testing), or OpenRouter (aggregator)?
  The architecture should be provider-agnostic (OpenAI-compatible API) so Arie
  can switch without rewriting the app.
- **Privacy decision (NEW):** is sending campaign data to a third-party
  inference provider acceptable for Arie's solo use? (Almost certainly yes.)
  For a future multi-user product? (Needs a privacy policy + opt-in.) This
  affects whether local-only is a hard requirement or a preference.

---

## 7. Sources

- canitrun.dev — Apple M1 Max 32GB/64GB LLM fit analysis
- willitrunai.com — per-model fit + tok/s estimates for M1 Max 32GB
  (Llama 3.3 70B, Qwen3-30B-A3B pages)
- omlx.ai — Qwen3-30B-A3B and gemma-3-27b-it-qat benchmarks on M1 Max
- hiesch.eu — llama.cpp GGUF benchmarks on M3 Max 64GB (29 models)
- siliconscore.com — Qwen3-Coder-30B-A3B Mac benchmarks
- makerpulse.ai — "The Creative Gap: Models Split on Writing" (2026)
- lechmazur/writing — LLM creative story-writing benchmark (2026)
- datalearner.com — creative writing benchmark results table
- llm-stats.com — EQ-Bench Creative Writing v3 leaderboard
- github.com/nickc672/gemma4-dungeon-master — local DM with 3-pass state diff
- github.com/tegridydev/dnd-llm-game — local D&D web app, Ollama, model-agnostic
- github.com/newideas99/open-dungeon — fully local AI roleplay app
- dev.to/austin_amento — SoloQuest prompt architecture (the rules-contract pattern)
- tableforge.gg/about — "AI narrates, rules engine adjudicates" separation
- sep.com — 3-tier memory (NoSQL + vector + knowledge graph)
- arcanumrpgs.com — "Why Your AI Campaign Falls Apart at Turn 50"
- scrollbook.app/blog — prompt caching 90% cost savings

### Sources for §5a (cloud options, added 2026-08-18)

- nelsa.cloud/blog — Vast.ai vs RunPod vs Lambda GPU rental pricing comparison (2026)
- runaihome.com/blog — Cloud GPU pricing compared: RunPod vs Vast.ai vs Lambda (2026)
- klymentiev.com/blog — RunPod vs Lambda vs Vast.ai comparison (2026)
- gpucloudlist.com — Lambda Labs vs RunPod vs Vast.ai complete comparison (2026)
- k8scalc.com/blog — GPU cloud providers for AI/ML 2026 (pricing table with spot rates)
- gmicloud.ai/en/blog — RunPod Serverless BYO-container GPU pricing
- deploybase.ai — RTX 4090 cloud price comparison (24GB ceiling for 70B models)
- hetzner.com — GEX44 dedicated GPU server (RTX 4000 SFF Ada, 20GB, ~€234-281/mo)
- together.ai/pricing — per-token pricing for Llama 3.3 70B and other open models
- hostfleet.net — OpenRouter vs Together vs Groq vs Fireworks per-token comparison (April 2026)
- computeprices.com/models/llama-3-3-70b — Llama 70B API pricing across 8+ providers
- amnic.com/blogs/llama-api-pricing — Llama 70B API pricing by provider (DeepInfra cheapest)
- artificialanalysis.ai — Llama 3.3 70B provider performance benchmarking (Groq fastest at 328 t/s)
- modelpricewatch.com — Groq Llama 3.3 70B pricing + retirement notice (Aug 16, 2026)
- klymentiev.com/blog/groq-pricing — Groq API pricing & free tier rate limits (2026)
- tokenmix.ai/blog/groq-api-pricing — Groq pricing 2026: free tier, 315 TPS, per-model breakdown
- cloudzero.com/blog/groq-pricing — Groq pricing 2026: batch + caching stack to 25% of on-demand
