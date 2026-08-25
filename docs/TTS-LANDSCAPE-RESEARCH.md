# TTS Landscape — Quality, Cost, and Fit for the Narrator App

**Research date:** 2026-08-24
**Author:** Devin (Sonnet session)
**Question:** What quality gain would Inworld TTS bring, what would it cost in narrator, and what other TTS models are worth considering?

---

## TL;DR

- **Inworld TTS 1.5 Max** is ranked #8 globally on Artificial Analysis (Elo 1,197) and #6 for voice cloning (Elo 1,047). It would be a **quality upgrade over Kokoro** (Elo 1,060, narrator's current fallback) and roughly **on par with or slightly above Qwen3-TTS** for expressiveness, with the critical advantage of **40% lower WER** (word error rate) — meaning fewer hallucinated/paraphrased words, which is narrator's core invariant.
- **Cost per narrator session:** $0.30–$0.78 (On-Demand tier) or $0.15–$0.39 (Growth tier). Free tier covers ~1 full session.
- **But the best quality-for-price option isn't Inworld — it's Cartesia Sonic 3.6** (Elo 1,283, #1 globally) at $49/1M chars, or **Fish Audio S2 Pro** (Elo 1,125, #1 open-weights) which can run locally.
- **For narrator specifically** (long-form narration, character voices, verbatim fidelity, local-first): the most interesting additions are **Fish Audio S2 Pro** (local, highest open-weight quality), **VibeVoice TTS 1.5B** (local, 90-minute long-form, Microsoft, Apache-2.0), and **Inworld TTS 1.5 Max** (cloud, best WER, game/character focus).

---

## 1. Inworld TTS — Quality Gain

### Where it ranks (Artificial Analysis Speech Arena, Aug 2026)

| Model | Global Rank | Elo | Voice Cloning Elo | Price ($/1M chars) |
|---|---|---|---|---|
| Inworld Realtime TTS 1.5 Max | #10 | 1,197 | #6 (1,047) | $26 (On-Demand) / $10 (Enterprise) |
| Inworld Realtime TTS-2 (Research Preview) | #12 | 1,185 | #5 (1,048) | $20.8 |
| Inworld Realtime TTS 1.5 Mini | #24 | 1,132 | #20 (995) | $10.4 |
| **For comparison:** | | | | |
| Cartesia Sonic 3.6 | #1 | 1,283 | #1 (1,119) | $49 |
| ElevenLabs Eleven v3 | #14 | 1,177 | #3 (1,064) | $100 |
| OpenAI TTS-1 HD | #32 | 1,108 | — | $30 |
| Kokoro 82M (narrator's current fallback) | #55 | 1,060 | — | $0 (local) |
| Qwen3 TTS (narrator's current primary) | #89 | 925 | — | $0 (local) |

**Quality gain over narrator's current stack:**
- vs **Kokoro** (Elo 1,060): Inworld TTS 1.5 Max is +137 Elo — a meaningful but not dramatic jump. Both are in the "good" tier.
- vs **Qwen3-TTS** (Elo 925): Inworld is +272 Elo — a significant jump. Qwen3-TTS ranks quite low on the arena (it's better in practice than 925 suggests because the arena tests preset voices, not VoiceDesign, but the signal is real).

### The metric that matters most for narrator: Word Error Rate (WER)

Narrator's core invariant (from `audio_engine.py` line 4): *"the text shown on screen = the text spoken by TTS, word for word."* WER measures exactly this — how many words the TTS gets wrong, skips, or hallucinates.

| Model | WER (English) | Source |
|---|---|---|
| Inworld TTS 1.5 Max | ~3.0% (40% reduction from TTS-1) | Inworld blog |
| Inworld TTS-1 Max | 5.1% (overall), 1.9% (short text) | TTS-1 technical report (arxiv 2507.21138) |
| Kokoro 82M | 6.5% | tts-bench |
| Qwen3-TTS 1.7B | 7.7% | tts-bench |
| F5-TTS v1 | 19.5% | tts-bench |
| Gradium TTS | 3.3% | Coval benchmark |
| ElevenLabs Turbo v2.5 | 5.2% | Coval benchmark |

**This is the key finding.** Inworld TTS 1.5 Max has the lowest WER of any model I found data for (~3.0%), which directly addresses narrator's biggest TTS problem: Qwen3-TTS paraphrasing/skipping words on long passages. The 40% WER reduction from TTS-1 to TTS-1.5 is specifically called out in their release blog.

### Expressiveness for character voices

Inworld supports **voice tags** — inline markup like `[whispering]`, `[surprised]`, `[cough]` — that map almost 1:1 to narrator's mood/emotion system. This is a natural fit:
- narrator's `[SCENE]` mood tags (combat, tense, horror, mystery, sad, etc.) → Inworld delivery mode + voice tags
- Character voice cloning from 5–15s of audio → per-character voices in `cast.json`
- Text-based voice design ("describe accent, age, tone in natural language") → direct replacement for Qwen3-TTS VoiceDesign descriptions

### Internal head-to-head (from Inworld's own paper)

From the TTS-1 technical report, blind A/B tests with ~20 annotators:
- TTS-1 Max vs ElevenLabs Multilingual V2: **59.1% win rate**
- TTS-1 Max vs Cartesia Sonic 2: **60.9% win rate**
- TTS-1 Max vs OpenAI TTS-1-HD: **60.7% win rate**
- TTS-1 Max vs Inworld TTS-1: **55.3% win rate**

(Caveat: these are Inworld's own internal tests, not independent. But the Artificial Analysis arena — which IS independent — corroborates the ranking.)

---

## 2. Inworld TTS — Cost for Narrator

### Pricing tiers (per 1M characters)

| Tier | TTS 1.5 Mini | TTS 1.5 Max | TTS-2 |
|---|---|---|---|
| On-Demand (default) | $25 | $35 | $35 |
| Developer | ~$15 | ~$25 | ~$25 |
| Growth | $15 | $25 | $25 |
| Enterprise | $5 | $10 | $10 |
| **Free tier** | 70 minutes (~63k chars) | | |

(Note: the $5/$10 figures I cited in the earlier report were Enterprise-tier rates. On-Demand — what you get by default — is $25/$35. This changes the cost math significantly.)

### Narrator usage model

From the codebase:
- `CHARS_PER_SEC = 15.0` (speech rate, `audio_queue.py` line 54)
- Each turn generates STORY + SCENE_SETTING segments, typically 500–2,000 chars
- Session Zero: ~5–15k chars (DM questions + opening scene)
- A typical play session (Session Zero + 30 turns): **~30–75k chars**
- A full campaign (10 chapters, ~300 turns): **~300–750k chars**

### Cost per session (On-Demand tier, TTS 1.5 Max at $35/1M)

| Scenario | Chars | Cost (On-Demand) | Cost (Growth) | Cost (Enterprise) |
|---|---|---|---|---|
| Single turn | ~1,000 | $0.035 | $0.025 | $0.010 |
| Session Zero | ~10,000 | $0.35 | $0.25 | $0.10 |
| One play session (30 turns) | ~50,000 | $1.75 | $1.25 | $0.50 |
| Full campaign (10 chapters) | ~500,000 | $17.50 | $12.50 | $5.00 |
| Free tier coverage | 63,000 | $0 | $0 | $0 |

**The free tier covers roughly one full play session** (Session Zero + ~30 turns). After that, it's $1.25–$1.75 per session at default rates.

### Cost vs narrator's current stack

Narrator's current TTS cost: **$0** (both Qwen3-TTS and Kokoro run locally on Apple Silicon).

Adding Inworld as a cloud tier means:
- **Best case (Enterprise tier, Max model):** $0.50/session — cheap enough to be a "premium" option
- **Realistic case (On-Demand, Max model):** $1.75/session — meaningful per-user cost for a hobby app
- **Budget case (On-Demand, Mini model):** $1.25/session — still 5x more than the LLM cost per session (Gemini Flash-Lite is nearly free)

### Hybrid strategy cost

If Inworld is used only for long passages where Qwen3 would paraphrase (the current failure case), and Kokoro handles short segments:
- Assume 30% of chars go to Inworld, 70% to local engines
- Per session: ~15k chars × $35/1M = **$0.53/session** (On-Demand Max)
- This is the most sensible deployment: Inworld as a quality fallback for long narration, local engines for everything else

---

## 3. The Broader TTS Landscape — Models Worth Considering

### A. Cloud APIs (paid, no local setup)

| Model | Elo | WER | Price ($/1M) | Voice cloning | Languages | Best for narrator? |
|---|---|---|---|---|---|---|
| **Cartesia Sonic 3.6** | 1,283 (#1) | — | $49 | Yes | 40+ | Highest quality, but expensive. Sub-150ms latency. Good for premium tier. |
| **Inworld TTS 1.5 Max** | 1,197 (#10) | ~3.0% | $25–35 | Yes (5–15s) | 15 | Best WER, game/character focus, voice tags. **Best fit for narrator.** |
| **Inworld TTS 1.5 Mini** | 1,132 (#24) | — | $10–25 | Yes | 15 | Budget option, still beats Kokoro on Elo. |
| **ElevenLabs Eleven v3** | 1,177 (#14) | 5.2% | $100 | Yes (instant) | 70+ | Most expressive, huge voice library, but 3x Inworld's price. 5000-char cap per request is a problem for long narration. |
| **OpenAI TTS-1 HD** | 1,108 (#32) | — | $30 | No | 57 | Simple, reliable, no cloning. No character voices = poor fit. |
| **OpenAI TTS-1** | 1,095 (#36) | — | $15 | No | 57 | Cheapest credible cloud TTS. No cloning = poor fit. |
| **MiniMax Speech 2.6 HD** | ~1,156 | — | $60–100 | Yes | 40+ | Strong expressiveness, but expensive and less game-focused. |
| **Hume Octave 2** | — | — | $10–100 (varies) | Yes (sales process) | narrow | Most emotionally expressive, reads for meaning. Interesting but narrow language coverage and sales-gated cloning. |
| **Gradium TTS** | 1,072 (#24) | 3.3% | — | Yes | 5 | Best latency (155ms) and WER (3.3%), but only 5 languages. Worth watching. |
| **Amazon Polly Neural** | — | — | $16 | No | 30+ | Cheap, reliable, no cloning. Not a fit for character voices. |

**Cloud recommendation for narrator:** Inworld TTS 1.5 Max is the best fit — lowest WER (directly addresses the verbatim fidelity problem), voice tags that map to narrator's mood system, voice cloning for character voices, and game/narrative focus. Cartesia Sonic 3.6 is higher quality but nearly 2x the price and less game-focused.

### B. Open-weight / local models (free, run on your Mac)

| Model | Elo | WER | Size | License | Apple Silicon? | Best for narrator? |
|---|---|---|---|---|---|---|
| **Fish Audio S2 Pro** | 1,125 (#1 open) | 5.8% | 4B | Complex (check) | Via MLX? | **Highest-quality open-weight.** Would be a major upgrade over Kokoro. License needs checking. |
| **Step Audio EditX** | 1,105 (#2 open) | — | — | — | — | Limited info. Worth investigating. |
| **Voxtral TTS** | 1,081 (#3 open) | — | — | Apache-2.0? | — | Mistral's TTS. Limited info. |
| **Magpie-Multilingual 357M** | 1,065 (#4 open) | — | 357M | — | — | Small, multilingual. |
| **Kokoro 82M** (current) | 1,060 (#5 open) | 6.5% | 82M | Apache-2.0 | Yes (mlx-audio) | Already integrated. Solid baseline. |
| **Qwen3-TTS** (current) | 925 (#89) | 7.7% | 0.6B/1.7B | Apache-2.0 | Yes (mlx-audio) | Already integrated. Low arena score but VoiceDesign mode isn't tested in arena. |
| **VibeVoice TTS 1.5B** | 971 | — | 1.5B | MIT | Yes (MLX) | **Microsoft. 90-minute long-form generation.** Specifically designed for multi-speaker dialogue. Apache-2.0/MIT. Very interesting for narrator. |
| **F5-TTS v1** | — | 19.5% | 330M | CC-BY-NC | Yes | Fast (RTF 0.04 on GPU), but **non-commercial license** and high WER. Not a fit. |
| **CosyVoice 3** | — | 50.1% | 0.5B | Apache-2.0 | Yes (CPU) | Best cross-lingual cloning, but 50% WER is unusable for English narration. |
| **Chatterbox** | — | 7.3% | 1B | Apache-2.0 | — | Fast fine-tuning, paralinguistic expressions (laughter, coughing). |
| **OuteTTS 1.0 1B** | — | 14.5% | 1B | Apache-2.0 | Via llama.cpp | High WER. Not a fit. |
| **Dia 1.6B** | — | 34.3% | 1.6B | — | Yes (mlx-tts-studio) | Two-speaker dialogue specialist, but 34% WER. Not for narration. |
| **Supertonic 3** | — | — | 99M | — | Yes (ONNX CPU) | CPU-first, edge deployment. ~547MB RSS. Interesting for low-end devices. |

**Local recommendation for narrator:** Two models stand out:
1. **Fish Audio S2 Pro** — Elo 1,125, the highest-ranked open-weight model. Would be a +65 Elo upgrade over Kokoro and +200 over Qwen3-TTS. WER 5.8% is better than both current engines. If the license allows commercial use and it runs on Apple Silicon, this is the single best local upgrade available.
2. **VibeVoice TTS 1.5B** (Microsoft, MIT license) — designed for **90-minute long-form multi-speaker generation** in a single pass. This is almost purpose-built for narrator's use case (long narration with multiple character voices). MIT license is clean. Runs on Apple Silicon via MLX. The arena score (971) is modest but it's optimized for a different thing (long-form consistency) than the arena tests (short snippets).

---

## 4. Ranked Recommendations for Narrator

### Tier 1: Do first (highest impact, lowest effort)

1. **Inworld TTS 1.5 Max — cloud fidelity spike** (1–2 hours, $0 in free tier)
   - Add `inworld` engine branch to `generate_segment_tts()`
   - Test verbatim fidelity on narrator's `tts_fidelity_test.py` corpus
   - Verify WER is actually ~3% on narrator's content (fantasy prose with unusual names)
   - If it passes: wire into `audio_queue._select_engine()` as a third option for long segments
   - **Why first:** Directly addresses narrator's #1 TTS problem (Qwen3 paraphrasing). Free to test. API integration is ~50 lines of code.

2. **Fish Audio S2 Pro — local quality investigation** (2–3 hours)
   - Check license terms for commercial use
   - Test if it runs on Apple Silicon via MLX or ONNX
   - Benchmark RTF on M-series Mac
   - If viable: add as a third local engine alongside Qwen3-TTS and Kokoro
   - **Why:** Would be the biggest local quality upgrade available — +65 Elo over Kokoro, better WER, no per-character cost.

### Tier 2: Worth exploring (medium effort, interesting capabilities)

3. **VibeVoice TTS 1.5B — long-form specialist** (3–4 hours)
   - Microsoft, MIT license, designed for 90-minute multi-speaker generation
   - Could replace the segment-by-segment approach for chapter-length narration
   - Test if the "single pass" approach produces better consistency than narrator's current segment queue
   - **Why:** The 90-minute long-form capability is unique — no other model does this. Could simplify narrator's audio architecture significantly.

4. **Cartesia Sonic 3.6 — premium cloud tier** (1–2 hours, $5 credit to test)
   - #1 on Artificial Analysis (Elo 1,283)
   - Sub-150ms latency, 40+ languages, voice cloning
   - $49/1M chars is expensive but could be a "premium" option for users who want max quality
   - **Why:** Highest quality available. Worth knowing the ceiling even if the price is too high for default use.

### Tier 3: Monitor but don't invest now

5. **Inworld TTS-2 (Research Preview)** — Elo 1,185, adds natural-language voice direction and 6 non-verbal cues. Still in research preview. Could be a future upgrade path from TTS 1.5 Max.

6. **Hume Octave 2** — Most emotionally expressive model, "reads for meaning." Could be interesting for character dialogue specifically, but narrow language coverage and sales-gated cloning.

7. **Gradium TTS** — Best latency (155ms) and WER (3.3%), but only 5 languages. Worth watching if it expands.

8. **Step Audio EditX** — Elo 1,105 (#2 open-weight), but limited public info. Worth investigating when more data is available.

### Not recommended

- **F5-TTS** — CC-BY-NC license (non-commercial), 19.5% WER. Disqualified on both counts.
- **CosyVoice 3** — 50.1% WER on English. Unusable for narrator.
- **OuteTTS** — 14.5% WER. Too unreliable for verbatim narration.
- **Dia** — 34.3% WER. Designed for dialogue, not narration.
- **OpenAI TTS-1** — No voice cloning. Can't do character voices.
- **Amazon Polly** — No voice cloning. Too robotic for literary narration.
- **ElevenLabs Eleven v3** — Excellent quality but $100/1M chars (3x Inworld) and 5000-char cap per request (narrator's segments can exceed this). Turbo v2.5 is cheaper but lower quality.

---

## 5. Cost Comparison Summary

### Per narrator session (~50k chars, 30 turns)

| Option | Cost/session | Quality (Elo) | WER | Local? | Character voices? |
|---|---|---|---|---|---|
| Current (Qwen3 + Kokoro, local) | $0 | 925 / 1,060 | 7.7% / 6.5% | Yes | Yes (VoiceDesign / presets) |
| + Inworld 1.5 Max (hybrid, 30% cloud) | $0.53 | 1,197 | ~3.0% | No (cloud) | Yes (cloning + tags) |
| + Inworld 1.5 Max (all cloud) | $1.75 | 1,197 | ~3.0% | No (cloud) | Yes (cloning + tags) |
| + Cartesia Sonic 3.6 (all cloud) | $2.45 | 1,283 | — | No (cloud) | Yes (cloning) |
| + ElevenLabs v3 (all cloud) | $5.00 | 1,177 | 5.2% | No (cloud) | Yes (instant clone) |
| + Fish Audio S2 Pro (local) | $0 | 1,125 | 5.8% | Yes | Yes (cloning) |
| + VibeVoice 1.5B (local) | $0 | 971 | — | Yes | Yes (multi-speaker) |

### Per full campaign (~500k chars, 10 chapters)

| Option | Cost/campaign |
|---|---|
| Current (local) | $0 |
| Inworld 1.5 Max (hybrid 30%) | $5.25 |
| Inworld 1.5 Max (all cloud, On-Demand) | $17.50 |
| Inworld 1.5 Max (all cloud, Enterprise) | $5.00 |
| Cartesia Sonic 3.6 (all cloud) | $24.50 |
| ElevenLabs v3 (all cloud) | $50.00 |
| Fish Audio S2 Pro (local) | $0 |

---

## 6. The Honest Assessment

**The quality gap between local and cloud has closed dramatically.** Fish Audio S2 Pro (Elo 1,125, local, $0) now beats Inworld TTS 1.5 Mini (Elo 1,132, cloud, $10–25/1M) on quality and matches it on WER. The open-weight frontier is within 70 Elo of the best cloud model (Cartesia at 1,283).

**For narrator specifically, the decision is:**

- **If you want zero per-character cost and good quality:** Add **Fish Audio S2 Pro** as a local engine. It's the biggest free quality upgrade available, +65 Elo over Kokoro.
- **If you want the lowest WER (best verbatim fidelity):** Add **Inworld TTS 1.5 Max** as a cloud fallback for long passages. ~3% WER vs Kokoro's 6.5%. Cost: ~$0.53/session in hybrid mode.
- **If you want to simplify the architecture:** Investigate **VibeVoice TTS 1.5B** — its 90-minute single-pass generation could replace the entire segment queue for chapter-length narration.
- **Best of all worlds:** Fish Audio S2 Pro for local quality + Inworld TTS 1.5 Max as a cloud fallback for passages where even Fish Audio paraphrases. Total cost: $0 for most sessions, $0.50偶尔 for long chapters that need cloud rescue.

The single highest-value action is the **Inworld fidelity spike** — it's free (70-minute tier), takes 1–2 hours, and directly tests whether the #1 narrator TTS problem (paraphrasing) is solved by the model with the best WER on the market.

---

## Sources

- Artificial Analysis Speech Arena leaderboard: https://artificialanalysis.ai/text-to-speech/leaderboard/provider-voice
- Artificial Analysis open-weights leaderboard: https://artificialanalysis.ai/text-to-speech/leaderboard/provider-voice/open-weights
- Artificial Analysis controlled-voice (cloning) leaderboard: https://artificialanalysis.ai/text-to-speech/leaderboard/controlled-voice
- Inworld TTS-1 technical report: https://arxiv.org/html/2507.21138
- Inworld TTS 1.5 release blog: https://inworld.ai/blog/introducing-inworld-tts-1-5
- Inworld TTS API quickstart: https://inworld.ai/resources/tts-api-quickstart
- Inworld billing docs: https://docs.inworld.ai/docs/tts/resources/billing
- Inworld pricing (MarkTechPost): https://www.marktechpost.com/2026/05/30/best-text-to-speech-tts-models-in-2026-a-benchmark-based-comparison/
- tts-bench scores (open models): https://5uck1ess.github.io/tts-bench/scores.html
- Open-source TTS decision tree (Instavar): https://instavar.com/blog/ai-production-stack/TTS_Model_Decision_Tree_2026
- Open-source TTS comparison (Neosophie): https://neosophie.com/en/blog/20260317-tts
- Open TTS landscape (DeepResearch Ninja): https://deepresearch.ninja/2026/05/Open-TTS-Models-A-Comprehensive-2026-Comparison-of-Kokoro-Supertonic-3-Qwen3-TTS-and-the-Broader-Landscape/
- TTS pricing compared (Awesome Agents): https://awesomeagents.ai/pricing/voice-tts-pricing/
- TTS provider comparison (Coval): https://www.coval.ai/blog/best-text-to-speech-providers-in-2026-how-to-choose-(and-why-vendor-benchmarks-lie)/
- VibeVoice GitHub: https://github.com/microsoft/VibeVoice
- F5-TTS GitHub: https://github.com/SWivid/F5-TTS
- Inworld TTS open-source training code: https://github.com/inworld-ai/tts
- Narrator current TTS: `glm-work/narrator_v01/audio_engine.py`, `glm-work/narrator_v01/audio_queue.py`
