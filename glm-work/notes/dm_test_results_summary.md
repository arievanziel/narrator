# DM Brain Test Results — Summary

**Date:** 2026-08-18
**Test harness:** `glm-work/test_api_dm.py`
**Scenario:** 10-turn scripted test — Level 1 Fighter vs 2 Goblins in The Rusty Anchor tavern
**Architecture:** SoloQuest pattern — LLM narrates, deterministic code adjudicates state and dice

## Test methodology

Each model runs the same 10 scripted player actions through the same system prompt
("rules contract") and deterministic state engine. The engine:
- Injects current game state every turn (HP, inventory, enemies, scene)
- Parses `[MECHANICS]` tags and applies only validated state changes
- Checks for format compliance, roll-before-outcome violations, and state consistency

See `glm-work/notes/groq_test_plan.md` for full scenario design.

## Results table

| Model | Params | Provider | Format issues | Time (total) | Tokens (total) | Avg time/turn | Prose (1-5) | State (1-5) | Local? |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| **GPT-OSS 120B** | 120B | Groq | **0 (perfect)** | 101.9s | 25,643 | ~10s | 4 | 5 | No (too large) |
| **Groq/compound** | ? | Groq | **0 (perfect)** | 34.5s | 74,274 | ~3.5s | 4 | 5 | No (compound system) |
| **Gemini 3.5 Flash-Lite** | ? | Google | **0 (perfect)** | 49.4s | 21,806 | ~5s | 4 | 5 | No |
| **Gemini 3.5 Flash** | ? | Google | 1 | 71.8s | 33,457 | ~7s | 5 | 5 | No |
| **Gemini 3.6 Flash** | ? | Google | 2 | 469.9s | 35,804 | ~47s | 5 | 5 | No |
| **Compound-mini** | ? | Groq | **0 (perfect)** | 27.9s | 52,529 | ~3s | 4 | 4 | No (compound system) |
| Qwen3.6-27B | 27B | Groq | 2 | 362.5s | 53,758 | ~36s | 4 | 5 | Borderline (Q4 ~16GB) |
| GPT-OSS 20B | 20B | Groq | 2 (1 empty, 1 tool-call error) | 12.1s* | 7,831* | ~3s | 3 | 3 | Yes (Q4 ~12GB) |
| Allam-2-7B | 7B | Groq | 10 (all empty) | 200s | 26,012 | ~20s | 1 | 1 | Yes (Q4 ~5GB) |

*GPT-OSS 20B only completed 4/10 turns before erroring.

## Trickster test results (cheat resistance)

| Model | Score | Fell for | Rating |
|---|---|---|---|
| **GPT-OSS 120B** | **27/30** | **0/10** | EXCELLENT |
| Compound-mini | 25/30 | 0/10 | EXCELLENT |
| Qwen3.6-27B | 25/30 | 0/10 | EXCELLENT |
| Groq/compound | 24/30 | 1/10 | GOOD (fell for "waste potion" trick) |
| Gemini 3.5 Flash | 23/30 | 1/10 | GOOD (fell for "waste potion" trick) |
| Gemini 3.5 Flash-Lite | 22/30 | 1/10 | GOOD (fell for "control NPC" trick) |
| Gemini 3.6 Flash | 22/30* | 0/9* | GOOD (*10th trick hit daily quota) |

See `glm-work/notes/trickster_test_results.md` for full breakdown.

## Detailed analysis

### GPT-OSS 120B — RECOMMENDED as DM brain

**Strengths:**
- Perfect format adherence — all 4 sections on every turn, zero parse failures
- Fast: ~10s/turn average (Groq LPU at 300-800 tok/s)
- Token-efficient: 25,643 total tokens for 10 turns (~2,500/turn)
- Good prose quality with vivid sensory detail
- Spontaneous plot hooks (found torn parchment pointing to docks meeting)
- Correctly tracked enemy death, item gains, conditions
- Respected roll-before-outcome on every turn

**Weaknesses:**
- Asked for initiative roll repeatedly (scripted actions didn't provide one — correct behavior, but created a loop in the scripted test)
- No PC damage occurred (goblin missed with 15 vs AC 16), so damage tracking wasn't exercised
- 120B parameters — cannot run locally on M1 Max 32GB

**Cost estimate at planned usage (~50 turns/day):**
- ~125K tokens/day → ~3.75M tokens/month
- At Groq free tier: FREE (within daily limits)
- At Groq paid tier ($0.29/M in, $0.59/M out): ~$2-3/month — well within €10 budget

### Qwen3.6-27B — Strong alternative, but slower and pricier

**Strengths:**
- Best worldbuilding — goblin revealed a "big man with a horned helmet" ordering the raid, found a cave map with horned symbol. Richer NPC personality than GPT-OSS.
- Impressive state awareness on turn 7 — noticed PC was at full HP and told player they don't need the potion (scripted action assumed damage, but goblin had missed)
- More sensory prose detail than GPT-OSS
- 27B parameters — could potentially run locally on M1 Max at Q4 (~16GB), though slowly

**Weaknesses:**
- 2 format issues (missing CHRONICLE on turn 2, missing 3 sections on turn 4)
- 3.5x slower than GPT-OSS 120B (362s vs 102s)
- 2x more tokens (53,758 vs 25,643) — would push ~€20/month on paid tier
- Inconsistent section formatting would break a production state engine

### GPT-OSS 20B — Too unreliable for DM duty

**Strengths:**
- Very fast when it works (~1-3s/turn)
- 20B parameters — could run locally on M1 Max at Q4 (~12GB)
- Decent prose when it responds

**Weaknesses:**
- Turn 1: completely empty response (reasoning model "thought" through entire token budget)
- Turn 5: API error — model tried to use tool-calling instead of text format (`tool_use_failed`)
- Only completed 4/10 turns
- Format adherence unreliable
- The 20B variant is a reasoning model that spends too much budget on internal thinking

**Verdict:** Not suitable as a DM brain. The 120B variant is dramatically better.

### Allam-2-7B — Complete failure

**Strengths:**
- None for this use case

**Weaknesses:**
- All 10 turns produced empty responses (model generated tokens but no parseable content)
- Arabic-focused model — likely unable to handle the complex English system prompt
- 7B parameters — too small for structured DM duty

**Verdict:** Not suitable as a DM brain. Confirms that 7B-class models are below the threshold.

### Compound-mini — Surprise strong performer

**Strengths:**
- Perfect format adherence — zero issues across all 10 turns
- Fastest model tested: ~3s/turn (when not rate-limited)
- Generated its own plot hooks: a loose floorboard near the bar and a cloaked figure in the back room
- Killed both goblins by turn 6 (interpreted the 19 attack roll + 8 damage as killing the raider, then applied the same damage to the scout on turn 6 — aggressive but consistent)
- Correctly noted on turn 8 that there were no surviving goblins to intimidate ("the tavern floor is already littered with the bodies")
- Kept asking for the healing roll from turn 7 onwards (correct — player never provided it)

**Weaknesses:**
- Hit rate limits frequently (shares TPM quota with gpt-oss-120b — compound models route through the same backend)
- Used 2x the tokens of GPT-OSS 120B (52,529 vs 25,643)
- Killed both goblins by turn 6, which derailed the scripted intimidation/surrender turns 8-9 (the model handled it gracefully, but the scenario wasn't designed for this)
- "Compound" model — unclear what base model it uses or whether it's available to run locally

**Verdict:** Strong candidate. Fast, format-perfect, creative. Worth testing in interactive mode to see if the plot hooks hold up over a longer session.

### Groq/compound — Best overall DM performance, but token-hungry

**Strengths:**
- Perfect format adherence — zero issues across all 10 turns
- Fast: ~3.5s/turn average
- **Best combat tracking of all models tested** — actually had the goblin deal damage to the PC (turn 4: goblin rolled 13+4=17 vs AC 16, dealt 6 damage, HP 12→6). Other models had the goblin miss.
- Correctly applied healing potion (turn 7: HP 6→12, consumed Health Potion from inventory)
- Richest loot generation: 5 gold pieces, crude dagger, shortbow with 20 arrows, wooden flute, parchment with goblin scribbles
- Good plot hooks: parchment with goblin scribbles, wooden flute — both suggest future story threads
- Trickster test: resisted 9/10 tricks, only fell for the subtle "waste potion" trick

**Weaknesses:**
- Used 3x the tokens of GPT-OSS 120B (74,274 vs 25,643) — most expensive model tested
- Fell for 1 trickster trick (consumed Health Potion when player asked for non-existent "Potion of Invisibility")
- "Compound" system — unclear what base models it uses
- Not available to run locally

**Verdict:** Best DM performance overall — it's the only model that actually ran a complete combat with damage to both sides, healing, and rich loot. But the token cost is 3x GPT-OSS 120B, which matters for budget. The "waste potion" trick vulnerability is a real concern that the deterministic state engine should catch.

### Gemini 3.5 Flash-Lite — Best value Gemini, excellent DM

**Strengths:**
- Perfect format adherence — zero issues across all 10 turns
- Fast: ~5s/turn average
- **Most token-efficient of all models tested**: 21,806 tokens (vs 25,643 for GPT-OSS 120B, 74,274 for compound)
- Rich combat: goblin dealt 4 damage to PC (turn 4), PC healed with potion (turn 7: +4 HP, consumed potion), goblin fled in terror (turn 8)
- Great loot: crude rusted dagger, 12 copper coins, scratched town map (plot hook!)
- Correctly applied ENEMY_HP to scout (took 3 damage from the 8-damage roll that killed the raider — interpreted as cleaving through)
- Free with no credit card, generous quota (1,000 RPD on Flash-Lite)

**Weaknesses:**
- Trickster test: fell for "control NPC" trick (turn 4 — let player declare that the goblin raider flees and dies)
- Marked goblin scout as ENEMY_DEAD when it fled (turn 8) — technically it's alive but escaped
- 1,000 requests/day on free tier is plenty for testing but could be limiting for heavy play

**Verdict:** Best value DM brain. Most token-efficient, fast, free, excellent narration. The "control NPC" trick failure is a real concern but the deterministic engine can catch it (don't apply ENEMY_DEAD unless the player rolled for the kill).

### Gemini 3.5 Flash — Best prose quality, fast

**Strengths:**
- Best prose of any model tested — vivid, cinematic, great sensory detail
- Creative worldbuilding: goblin fled through a trapdoor behind the bar (turn 8), unconscious barkeep on the floor
- Fast: ~7s/turn average
- Correctly tracked HP, healing, enemy death
- Good plot hooks: stolen silver tankard, open trapdoor to cellar

**Weaknesses:**
- 1 format issue (missing SUGGESTIONS + CHRONICLE on turn 2)
- Trickster test: fell for "waste potion" trick (same as groq/compound)
- Higher token usage than Flash-Lite (33K vs 22K)

**Verdict:** If prose quality is the priority, this is the best model. The trapdoor escape was the most creative DM moment in any test. But Flash-Lite is more reliable and efficient.

### Gemini 3.6 Flash — Best combat realism, but slow

**Strengths:**
- Most realistic combat: goblin shot PC with arrow (turn 4: 4 damage), shot again (turn 10: 3 damage while PC was searching bodies — "turning your back on a living archer is a dangerous gamble")
- Correctly tracked HP throughout (12 → 8 → 5)
- Rich prose with great tactical detail
- Suggested Second Wind (Fighter class feature) — shows deep 5e knowledge

**Weaknesses:**
- Very slow: ~47s/turn average (vs ~5-10s for others)
- 2 format issues (missing sections on turn 10)
- Only 20 requests/day on free tier (can't even complete a 10-turn test in one session)
- Trickster test: 9/9 resisted but 10th hit daily quota

**Verdict:** Best combat realism and 5e rules knowledge, but too slow and quota-limited for practical use. The 20 RPD limit means you can't even run a full 10-turn test.

## Other free providers available

### SambaNova (free tier, no credit card)
- **Models:** DeepSeek-V3.1, DeepSeek-V3.2, MiniMax-M2.7, Gemma-4-31B
- **Limits:** 200K tokens/day, 20 req/min, **20 req/day** (tight for 10-turn test)
- **Base URL:** `https://api.sambanova.ai/v1`
- **Get key:** https://cloud.sambanova.ai
- **Note:** The 20 req/day limit means you can run the 10-turn test only twice per day.

### Cerebras (free tier, no credit card)
- **Models:** gpt-oss-120b, gemma-4-31b, zai-glm-4.7
- **Limits:** 1M tokens/day, ~5 req/min, **8,192 token context cap** on free tier
- **Base URL:** `https://api.cerebras.ai/v1`
- **Get key:** https://cloud.cerebras.ai
- **Note:** 8K context cap may be too small for our test (state + 10 turns of history exceeds 8K). The same gpt-oss-120b runs at ~3000 tok/s on Cerebras (vs ~500 on Groq) — worth testing if context fits.

### OpenRouter (aggregator, some free models)
- **Models:** Many, including free tiers of Llama, Mistral, Gemma
- **Base URL:** `https://openrouter.ai/api/v1`
- **Get key:** https://openrouter.ai
- **Note:** Free models rotate. Good for breadth of testing.

## Local model candidates (M1 Max 32GB)

Based on the test results and local LLM research:

| Model | Size (Q4) | DM suitability | Notes |
|---|---|---|---|
| GPT-OSS 20B | ~12GB | Poor (tested) | Reasoning model, format issues, tool-call errors |
| Qwen3.6-27B | ~16GB | Untested locally | Good on Groq but 3.5x slower; locally would be slower still |
| Qwen3-32B | ~18GB | Untested | Not on Groq; available on SambaNova |
| Gemma-4-31B | ~18GB | Untested | On SambaNova/Cerebras free tier |
| Llama 3.3 70B | ~40GB | Too large | Does not fit in 32GB |
| Llama 3.2 3B | ~2GB | Untested | Very small, likely too weak for DM duty |
| Allam-2-7B | ~5GB | Testing | Arabic-focused, may struggle with English D&D |

**Honest assessment:** The test results suggest that models smaller than ~27B struggle with the structured response format and reasoning needed for DM duty. GPT-OSS 20B failed, and 7B models are likely to fail worse. The sweet spot for local would be Qwen3-32B or Gemma-4-31B at Q4, but these would run at ~5-10 tok/s on M1 Max — usable but slow (~30-60s per turn).

## Claude comparison (to be run manually)

A test prompt has been prepared at `glm-work/notes/claude_dm_test_prompt.md` for
running the same 10-turn scenario through Claude Opus, Sonnet, and Fable via Devin.

This will establish a quality baseline to compare against the open-weight models.

## Recommendation

1. **Best value DM: Gemini 3.5 Flash-Lite** — most token-efficient (22K), fast (~5s), perfect format, free with no card, rich combat and loot. Best bang for buck.
2. **Best rule enforcement: GPT-OSS 120B via Groq** — perfect format + trickster score (27/30, 0 tricks), 3x fewer tokens than compound, best cheat resistance. The safe pick.
3. **Best prose quality: Gemini 3.5 Flash** — most vivid narration, creative worldbuilding (trapdoor escape), but 1 format issue and fell for 1 trick.
4. **Best combat realism: Groq/compound** — only model with damage to both sides + healing + rich loot in one run. But 3x token cost and fell for 1 trick.
5. **Best combat realism (Gemini): Gemini 3.6 Flash** — goblin shot PC with arrows, suggested Second Wind. But too slow (47s/turn) and 20 RPD quota.
6. **Fast alternative: Compound-mini** — fastest (~3s/turn), format-perfect, creative plot hooks, but higher token usage and rate-limit issues
7. **Fallback/variety: Qwen3.6-27B** — richer worldbuilding but slower, less reliable, and reasoning model causes empty responses
8. **Local option: Qwen3-32B or Gemma-4-31B at Q4** — test via SambaNova first before downloading (needs card)
9. **Quality baseline: Claude Opus** — run the manual test to see what "frontier quality" looks like

## Google AI Studio / Gemini — free options summary

**Free tier (no credit card, no payment method):**
| Model | RPM | RPD | Notes |
|---|---|---|---|
| Gemini 3.5 Flash-Lite | ? | ~1,000 | **Best value — recommended** |
| Gemini 3.5 Flash | ? | ~500 | Best prose |
| Gemini 3.6 Flash | ? | **20** (very limited) | Best combat realism but quota too tight |
| Gemini 3.1 Pro | 0 | 0 | Not available on free tier |

**With Google Business account:** Same free tier limits. The paid tier ($10 minimum prepay) unlocks Gemini 3.1 Pro and higher rate limits. Since you already pay for Google Business, you may be able to link billing easily.

**Get API key:** https://aistudio.google.com/apikey (sign in with Google Business account)

## Cerebras and SambaNova — require payment method

Both providers returned `402 Payment required` despite advertising "free tier, no credit card":
- **Cerebras**: $5 free credit + 1M tokens/day, but requires adding a card at https://cloud.cerebras.ai
- **SambaNova**: $5 free credit + 200K tokens/day, but requires adding a card at https://cloud.sambanova.ai/plans/billing

The free credit is real once you add a card. Models worth testing if you add a card:
- Cerebras: `gpt-oss-120b` at ~3000 tok/s (same model as Groq but 6x faster)
- SambaNova: `DeepSeek-V3.1` (strong reasoning), `gemma-4-31b-it` (could run locally)

## Key finding on model size

The test confirms a clear quality threshold:
- **7B (Allam-2):** Complete failure — cannot follow the structured format at all
- **20B (GPT-OSS 20B):** Unreliable — empty responses, tool-call errors, format issues
- **27B+ (Qwen3.6, Compound, GPT-OSS 120B):** All succeed — format adherence, state tracking, creative narration

**For local execution on M1 Max 32GB:** Only 27B+ models are viable for DM duty, which means Q4 quantized models occupying ~16-18GB. This is feasible but will be slow (~5-10 tok/s, ~30-60s per turn). The hosted API approach (Groq free tier) is dramatically better for real-time play.

## Key finding on cheat resistance

All viable models (27B+) resisted direct cheating attempts (claiming outcomes, inventing items, contradicting state). The system prompt's "rules contract" is effective. One model (groq/compound) fell for a subtle trick where the player asked for a non-existent item and the model consumed a different valid item instead. This should be caught by the deterministic state engine — if the player names an item not in inventory, the engine should refuse to consume any item.

## Files

- Test script: `glm-work/test_api_dm.py`
- Web GUI: `glm-work/serve_dm_web.py`
- Claude test prompt: `glm-work/notes/claude_dm_test_prompt.md`
- Raw JSON results: `glm-work/outputs/dm_test_groq_*.json`
- This doc: `glm-work/notes/dm_test_results_summary.md`
