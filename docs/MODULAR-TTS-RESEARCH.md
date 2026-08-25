# Modular TTS — Fit Assessment for the Narrator App

**Research date:** 2026-08-24
**Author:** Devin (Sonnet session)
**Question:** Is Modular's TTS offering a good extra fit for the narrator app?

---

## What's actually going on (read this first)

The core confusion: **"Powered by Modular" ≠ "Available from Modular."** Modular is an *infrastructure* company. They make MAX (a serving framework) and Mojo (a kernel language). They do not make TTS models. The #1 TTS on the Artificial Analysis leaderboard is **Inworld's** model. Inworld built the model; Modular built the engine it runs on. **You buy the TTS from Inworld's API, not from Modular.**

Modular advertises it heavily because Inworld is their marquee customer — it's the same pattern as NVIDIA advertising "the fastest AI training runs on NVIDIA GPUs." The model belongs to someone else; the hardware/framework vendor takes credit for proving their infra is fast. Modular's audio solutions page is a sales pitch for their *infrastructure* (MAX + Mojo + Modular Cloud), using Inworld as the proof point. The "Get started FREE" button takes you to MAX, which has no TTS model to run. The "Book a demo" button takes you to sales, where they'll deploy *your* proprietary TTS on their infra (exactly what they did for Inworld).

There are four separately-real things, and Modular's marketing deliberately blurs them together:

| Thing | Owner | Available? | Where |
|---|---|---|---|
| **Inworld TTS-1 / TTS-1-Max (the #1 model, the actual product)** | Inworld (proprietary weights) | Yes — paid cloud API | `api.inworld.ai/tts/v1/voice` |
| **Inworld's training/modeling code** | Inworld (MIT license) | Yes — but it's *training code, not weights* | `github.com/inworld-ai/tts` |
| **MAX Framework (serving engine + TTS pipeline scaffolding)** | Modular (open source) | Yes — but ships with **zero TTS model architectures** | `github.com/modular/max` |
| **Modular Cloud (hosted endpoints)** | Modular | Yes for LLMs + image gen; **no TTS endpoints listed** | `modular.com/pricing` |

Three specific traps to name:

1. **"Open source" doesn't mean what it sounds like.** Inworld open-sourced their *training code* under MIT — not the model weights. To get a working TTS-1 you'd have to train it yourself on ~1M hours of audio + ~200B text tokens on a multi-H100 cluster (per their own technical report, arxiv 2507.21138). That's a multi-million-dollar research project, not "trying it out." The repo even credits the codec architecture to Llasa — it's a recipe, not a meal.

2. **The Apple Silicon local-TTS claim on Modular's solutions page is aspirational.** "MAX compiles voice models natively for Apple Silicon — run TTS inference locally with no network round-trip." This is a true statement about MAX's *capability* (it can compile for Apple Silicon) but there is no open TTS model registered in MAX you could actually run on your Mac today. The only team that's ported a TTS model to MAX is Inworld, and their port is proprietary and not shared back as a MAX architecture.

3. **Modular Cloud does not serve TTS.** I checked the pricing page — hosted endpoints are LLMs (DeepSeek, Gemma, Qwen, GLM, Kimi, gpt-oss, MiniMax, Nemotron) and image gen (FLUX.2). No TTS row. So even if you wanted to pay Modular for TTS, there's no endpoint to hit. You pay Inworld.

**Bottom line for the original question:** The "#1 TTS" is real and available — just not from Modular, and not as a local model. It's a paid cloud API from Inworld. Modular's name on the marketing is infrastructure co-engineering credit, not a product they sell.

---

## TL;DR

**Short answer: Not as a local engine, no. Not today.**

Modular markets TTS prominently, but what they actually ship splits into two very different things, and **neither** is a drop-in upgrade over what narrator already runs (Qwen3-TTS + Kokoro via `mlx_audio` on Apple Silicon):

1. **MAX Framework (open source, self-hosted)** — has TTS *pipeline scaffolding* (`AudioGeneratorPipeline`, `SpeechTokenGenerationPipeline`, `TTSContext`) but **ships with zero open TTS model architectures**. As of v26.5 the supported-models table lists LLMs, vision models, image/video diffusion — no Kokoro, no Qwen3-TTS, no OuteTTS, no Llasa. You'd be writing the model integration yourself in Mojo/Python.
2. **Inworld TTS 1 / TTS 1 Max (proprietary, via Modular Cloud or Inworld API)** — this is the "#1 on Artificial Analysis" model Modular advertises. It is excellent, but it is a **paid cloud API**, not something you run locally. It competes with ElevenLabs/Cartesia, not with your local MLX stack.

There is a real, narrow use case where it *could* help narrator (a high-quality cloud fallback for long-form narration when local RTF is too slow), but it is **not** the "extra local TTS model" the question implies. Details below.

---

## What Modular actually offers

### 1. MAX Framework — open source, self-hostable

- Repo: `github.com/modular/max` (Apache-2.0 for kernels/Pipeline APIs)
- Pitch: "Serve TTS models on NVIDIA, AMD, and Apple Silicon with the same codebase. No rewrites."
- Apple Silicon path is real and is the relevant one for narrator (Arie develops on a Mac): MAX compiles models natively for M-series chips, no network round-trip.

**The catch — checked against the official supported-models table (`docs.modular.com/max/models/`, v26.5):**

| Modality present in the table | TTS present? |
|---|---|
| text-to-text (Llama3, Gemma3, Qwen3, DeepSeek, GLM, gpt-oss, …) | — |
| image-to-text, text-to-image (FLUX.2), text-to-video (Wan) | — |
| embeddings (Bert) | — |
| **text-to-audio / text-to-speech** | **No registered architecture** |

The TTS pipeline *code* exists:
- `max/pipelines/lib/audio_generator_pipeline.py` — `AudioGeneratorPipeline` (delegates everything to a `PipelineModel` that must supply `speech_lm_pipeline`, `next_chunk`, `decoder_sample_rate`)
- `max/python/max/pipelines/lib/speech_token_pipeline.py` — `SpeechTokenGenerationPipeline` (a `TextGenerationPipeline` subclass for SpeechLM token generation)

…but these are **empty shells**. They `assert hasattr(self.pipeline_model, "speech_lm_pipeline")` — i.e. you must bring a model that implements that interface. No such model is shipped. Release notes confirm this is WIP:
- v25.4: "Added audio generator APIs for text-to-speech models … **still a work in progress**."
- v25.7: "Added more APIs for text-to-speech models such as `AudioGenerationInputs` and `AudioGenerationOutput`."

The only public, end-to-end TTS deployment on MAX is the **Inworld partnership** (see below), and Inworld's model is proprietary — they brought their own SpeechLM + neural codec and Modular wrote custom Mojo kernels for it. That is not a path available to narrator without (a) a proprietary model or (b) writing a MAX architecture adapter for an open TTS model ourselves.

### 2. Inworld TTS 1 / TTS 1 Max — the actual product behind the marketing

This is what "#1 on Artificial Analysis" and "70% lower TTS cost" refer to. Key facts:

- **It is a cloud API**, not a downloadable model. Endpoint: `POST https://api.inworld.ai/tts/v1/voice` (sync) or `/tts/v1/voice:stream` (NDJSON streaming).
- Auth: `Authorization: Basic <base64(apiKey:)>` (not Bearer).
- Pricing (per million characters synthesized):
  - Inworld TTS 1 — $5 / 1M chars (~$0.005/min)
  - Inworld TTS 1 Max — $10 / 1M chars (~$0.01/min)
  - TTS 1.5 Mini $5/1M, TTS 1.5 Max $10/1M (latest sku, 75% cheaper than next-best competitor per Inworld's blog)
- Free tier: 70 minutes TTS on on-demand accounts.
- Capabilities: 12 languages, zero-shot voice cloning from 2–15s of audio, voice tags (`whispering`, `cough`, `surprised`), streaming first-audio-chunk ~200ms P90 (Max), ~100–130ms P90 (Mini).
- OpenAI-SDK compatibility is via their **Realtime Router** for LLM calls; the TTS endpoint itself is REST with its own field names (`voiceId`, `modelId`, `audioConfig.audioEncoding`, `sampleRateHertz`). Response is base64 `audioContent` (sync) or NDJSON chunks (stream).

It is genuinely good. It is genuinely not local.

---

## How narrator currently does TTS

From `glm-work/narrator_v01/audio_engine.py` and `audio_queue.py`:

- **Qwen3-TTS** (VoiceDesign, via `mlx_audio`) — primary, expressive, local on Apple Silicon. RTF ≈ 0.55. Known to paraphrase/skip words on long passages; `temperature=0.0` is used to mitigate this.
- **Kokoro-82M** (via `kokoro.KPipeline`) — fast fallback, local. RTF ≈ 0.18. 9 preset voices, keyword-mapped from voice descriptions.
- **Lead-time fallback rule** (concrete, not a judgment call):
  ```
  if estimated_qwen3_gen_time > lead_time * 0.7:
      use kokoro
  else:
      use qwen3
  ```
  (`audio_queue.py` lines 18–21, 47–57, 260)
- Both engines run **on-device, no API key, no per-character cost, no network**. Single-GPU lock respected via a worker thread that generates segments sequentially.
- Failure path: Qwen3 fail → automatic Kokoro retry (`audio_queue.py` lines 210–229).

The architecture is explicitly built around **hiding latency behind a segment queue** (Opus review's #1 finding: audio queue must land first to hide the two-call DC-then-roll latency). Any new engine has to slot into this queue, not replace it.

---

## Fit analysis

### As a *local* engine (the implied question) — ❌ Not a fit today

| Criterion | MAX open-source TTS | Narrator need |
|---|---|---|
| Open TTS model shipped | None | Need ≥1 working model |
| Apple Silicon support | Claimed, but no model to run | Required (Arie's dev machine) |
| Drop-in vs `mlx_audio` | Would require writing a MAX `PipelineModel` adapter in Python + likely Mojo kernels for the codec/vocoder | `mlx_audio` already runs Kokoro + Qwen3-TTS with one `load_model()` call |
| RTF improvement | Unknown — no benchmark exists for any open model on MAX | Need measurable win over RTF 0.18 (Kokoro) / 0.55 (Qwen3) |
| Risk | High — "work in progress" APIs, no reference open deployment | App is in v1 push; no budget for infra science projects |

**Verdict:** Adding MAX as a local engine right now means *building* the integration, not *installing* it. We'd be doing R&D that Modular hasn't published results for. The existing `mlx_audio` stack already covers the "local TTS on Apple Silicon" niche better, today, with two working engines.

### As a *cloud* engine (Inworld TTS 1 Max) — ⚠️ Plausible narrow fallback, with caveats

Where it could actually help narrator:

1. **Long-form narration where Qwen3 paraphrases.** Qwen3-TTS is documented in our own `audio_engine.py` as unreliable on long passages. Inworld TTS 1 Max is #1 on the leaderboard for exactly this kind of expressive long-form synthesis, with voice tags (`whispering`, `surprised`, `cough`) that map almost 1:1 onto the mood/emotion tags our World Engine already emits.
2. **A "premium quality" tier** for users who want max expressiveness and are OK paying.
3. **Streaming first-chunk ~200ms** is competitive with our local RTF for short segments, and the NDJSON stream would slot naturally into the existing segment queue (each NDJSON chunk ≈ one segment-piece).

Where it does **not** help:

1. **Cost.** Narrator is currently $0/character. A typical session-zero + first chapter is easily 30–60k characters → $0.15–0.60 per session at Max rates. Fine for a hosted product, odd for a local-first app Arie runs on his Mac.
2. **Network dependency.** The whole point of the current stack is offline/low-latency local audio. Adding a cloud hop reintroduces the latency the segment queue was designed to hide. Streaming mitigates but doesn't eliminate this.
3. **API-key friction.** Every narrator user would need an Inworld key. The app currently ships with zero API keys for TTS (only for the LLM provider, which is already a configured thing).
4. **Voice identity continuity.** Our `cast.json` maps characters → Qwen3 voice *descriptions* (free text). Inworld uses `voiceId` strings from a voice library or cloned-voice IDs. We'd need a mapping layer and probably a per-campaign clone step (free, 2–15s sample) to preserve character voices across sessions.
5. **Text-fidelity.** A core narrator invariant (stated at the top of `audio_engine.py`: "the text shown on screen = the text spoken by TTS, word for word") is something we *enforce* with Kokoro when Qwen3 paraphrases. We'd need to verify Inworld TTS 1 Max respects input text exactly before trusting it for narration. Their docs emphasize expressiveness, not verbatim fidelity — this is an open risk.

**Verdict:** Worth a *spike* (a single `audio_engine.generate_segment_inworld()` function + an A/B fidelity test against Kokoro on a 200-char passage), not a commitment. If it passes the verbatim-fidelity test and Arie is OK with a cloud tier, it becomes a third engine in `audio_queue`'s selection rule. If it paraphrases like Qwen3 does, it's useless to us regardless of leaderboard rank.

---

## Recommendation

1. **Do not adopt MAX Framework as a local TTS backend now.** No open TTS model is shipped; we'd be building unproven infra during a v1 push. Revisit in 6–12 months — if Modular registers Kokoro or Qwen3-TTS as a `SupportedArchitecture`, the Apple-Silicon-local + same-codebase-NVIDIA/AMD story becomes genuinely attractive for a future hosted deployment.
2. **Do not add Inworld cloud TTS as a default.** It breaks the local-first, $0/char, no-key model that's core to narrator's current UX.
3. **Optionally: a small, time-boxed Inworld fidelity spike.** ~1–2 hours. Add an `inworld` engine branch to `generate_segment_tts()` behind a config flag, run the existing `tts_fidelity_test.py` corpus against `inworld-tts-1-max`, and check:
   - Verbatim text fidelity (does output text match input exactly?)
   - RTF equivalent (wall-clock / audio-duration) over a 56k-char session
   - Voice-tag mapping from our mood tags → Inworld voice tags
   If it passes fidelity and Arie wants a premium cloud tier, wire it into `_select_engine()` as a third option with its own lead-time rule (cloud RTF is dominated by network, not compute, so the rule would be `if offline or budget_constrained: skip`).
4. **Track MAX releases.** Set a reminder to check `docs.modular.com/max/models/` quarterly for a `KokoroForTTS` / `Qwen3TTSForAudioGeneration` row. The day one appears, the cost/benefit flips and this should be re-evaluated.

---

## Sources

- Modular audio solutions page: https://www.modular.com/solutions/audio
- "TTS 1 Max ranked #1" announcement: https://www.modular.com/blog/tts-1-max-ranked-1-speech-model-on-artificial-analysis
- Inworld + Modular case study: https://inworld.ai/blog/how-we-made-state-of-the-art-speech-synthesis-scalable-with-modular
- MAX supported models (v26.5, no TTS architecture): https://docs.modular.com/max/models/
- MAX TTS pipeline code (WIP shells): https://github.com/modular/max/blob/eb65e736/max/pipelines/lib/audio_generator_pipeline.py , https://github.com/modular/modular/blob/29a2f54c/max/python/max/pipelines/lib/speech_token_pipeline.py
- MAX v25.4 / v25.7 release notes (TTS APIs still WIP)
- Inworld TTS API quickstart: https://inworld.ai/resources/tts-api-quickstart
- Inworld billing: https://docs.inworld.ai/docs/tts/resources/billing
- Inworld TTS 1.5 pricing blog: https://inworld.ai/blog/introducing-inworld-tts-1-5
- Per-minute cost derivation: https://codeables.dev/article/inworld-pricing-how-do-tts-1-5-mini-vs-tts-1-5-max-translate-to-cost
- Narrator current TTS: `glm-work/narrator_v01/audio_engine.py`, `glm-work/narrator_v01/audio_queue.py`
