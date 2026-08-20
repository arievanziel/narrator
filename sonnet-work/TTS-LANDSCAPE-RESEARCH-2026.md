# TTS Landscape Research — 2026 (for Narrator Phase 1)

**Author:** Sonnet 5 Medium, 2026-08-17. Web research + hardware verification, read-only
audit of GLM's work otherwise. This is input for `docs/MARKET_RESEARCH.md` (Task 0) and
for deciding what GLM tests next — it is not itself a project deliverable, GLM/Arie should
decide how much of it to fold into the actual repo docs.

## 1. Verified hardware (re-confirmed independently of GLM's notes)

- MacBook Pro (MacBookPro18,2), **Apple M1 Max**, 10-core CPU (8P+2E), **32-core GPU**,
  **32GB unified memory**, Metal 3 support, macOS 15.3.2, 532GB free disk.
- This matches what's already in `docs/PHASE_1_TESTING.md` / GLM's handoff — no
  correction needed, just independently verified.
- Implication: no CUDA, ever. But 32GB unified memory is generous — comfortably fits
  every model discussed below, including at full bf16 precision. RAM is not the
  constraint here; **software support for Apple Silicon (MPS or MLX) is the constraint.**

## 2. Big finding: `mlx-audio` — a unified Apple-Silicon-native runtime for almost every candidate model

**This should change GLM's plan for Dia2 and Higgs Audio V2, and probably Qwen3-TTS too.**

[`Blaizzy/mlx-audio`](https://github.com/Blaizzy/mlx-audio) (7.7k GitHub stars, actively
maintained) is an MLX-based (Apple's native ML framework, GPU-accelerated via Metal, no
PyTorch/CUDA needed) inference library that already supports, with pre-quantized
`mlx-community` weights on Hugging Face:

| Model | mlx-audio support | Quantized size options |
|---|---|---|
| Kokoro-82M | ✅ native MLX port | bf16, 8bit, 6bit, 4bit (tiny either way) |
| Qwen3-TTS (Base, CustomVoice, **VoiceDesign**) | ✅ `mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16` + 8bit/4bit quantized variants of Base/CustomVoice | 1.7B: ~3.4GB bf16 / ~1.7GB 8bit / ~0.85GB 4bit |
| Higgs Audio v2 (3B) | ✅ (PR merged) | bf16 6.8GB, q8 6.18GB, q6 4.75GB — **real-time voice cloning benchmarked on M-series** |
| Higgs Audio v3 (4B) | ✅ listed in mlx-audio model table | ~8GB range |
| Dia (original, 1.6B) | ✅ listed as "Dia Model" architecture in mlx-audio | not yet confirmed if Dia**2** specifically is ported — needs checking |
| Chatterbox, Sesame/CSM, Spark, OmniVoice, Voxtral TTS, KittenTTS | ✅ all listed | various, all small-to-moderate |

**Why this matters:** the original spec assumed Dia2 and Higgs Audio V2 are "CUDA-first,
likely impractical on Apple Silicon, CPU fallback probably too slow." That assumption
was reasonable for the *original PyTorch* code paths, but **mlx-audio provides
GPU-accelerated (Metal) ports of these same models**, with published Apple-Silicon
benchmarks showing real-time or near-real-time generation on M-series Macs (0.3–0.6x RTF
on an M5 Max for Higgs Audio v2 — likely somewhat slower but still very usable on your
M1 Max). This is a much better path than the native CUDA-first repos.

**Recommendation:** for any model beyond Kokoro, GLM should check for an `mlx-audio` /
`mlx-community` port *before* attempting the model's native PyTorch/CUDA repo. It will
almost always be faster to install, faster to run, and avoid the CPU-fallback slowness
the spec was worried about. One dependency (`mlx-audio` + `mlx` + `mlx-community` weights)
can potentially replace separate bespoke installs for Qwen3-TTS, Dia2, and Higgs Audio.

**Caveat / thing to verify before committing to this path:** mlx-audio's Qwen3-TTS port
looks solid (dedicated repo `odiak/Qwen3-TTS-MLX` also exists, notes VoiceDesign is
*not yet* supported in that specific fork's MLX runtime — only the main mlx-audio repo's
Qwen3-TTS port claims VoiceDesign support). GLM should confirm VoiceDesign actually works
via mlx-audio specifically (not the other MLX fork) before relying on it, since
VoiceDesign is the feature that matters most for your NPC-voice requirement.

## 3. Wider 2026 TTS landscape (context, not action items)

Community leaderboards (Elo-style blind rankings) as of mid-2026 rank open-weight TTS
roughly: Step Audio EditX, Fish Audio S2 Pro (non-commercial), Voxtral TTS
(non-commercial), **Kokoro** (Apache 2.0, still highly competitive despite being tiny),
Maya1, NVIDIA Magpie, **Chatterbox** (MIT), Zonos, OpenVoice v2. Notably Kokoro punches
way above its weight class (82M params vs multi-billion competitors) and several of the
"better" models are non-commercial-licensed, which matters given your long-term
commercial ambition (see SPEC.md). **Qwen3-TTS and Higgs Audio v3 remain the strongest
Apache-2.0-licensed options with real multi-voice/voice-design capability** — this lines
up with the spec's existing Priority 1 choice of Qwen3-TTS.

No genuinely new "must-test" model emerged that isn't already on GLM's list — Qwen3-TTS,
Dia2, Higgs Audio, Chatterbox, Kokoro remain the right shortlist. The main actionable
change is *how* to run them (mlx-audio) not *which* to run.

## 4. Task 0 — Market research findings (existing tools in this niche)

### Open-source, self-hostable — directly relevant, some potentially adoptable

- **[Xerophayze/TTS-Story](https://github.com/xerophayze/tts-story)** — a web-based
  multi-voice TTS *studio* app. Supports Kokoro, Chatterbox, Qwen3-TTS, and others as
  swappable backends. Has speaker tagging (`[narrator]...[/narrator]`,
  `[alice-female]...[/alice-female]`), **per-speaker pitch/speed, pause markers, silence
  controls** — this directly targets your exact complaint about Kokoro's pause timing
  and narrator/character voice transitions. Worth a look before GLM hand-builds a
  pause/stitching pipeline from scratch — this may already solve it, or at least be a
  strong reference implementation.
- **[wcharliebrown/multivoice](https://github.com/wcharliebrown/multivoice)** — a
  novel-to-audiobook pipeline built on Qwen3-TTS with `[beat]`/`[long beat]` pause tags,
  automatic sentence-pause insertion, emotion/delivery cue parsing (e.g. `(whispering)`),
  and quality-scored regeneration. This is close to a reference implementation of
  exactly the "input engineering" fix your Kokoro feedback was asking for, just built
  for Qwen3-TTS instead.
- **[vorojar/VibeVoice](https://github.com/vorojar/VibeVoice)** fork — local audiobook
  studio on Qwen3-TTS with **LLM-based automatic character/emotion detection** (no manual
  speaker tagging needed) and per-sentence voice/emotion control. Relevant since you're
  pasting narration from a Claude chat that already has implicit narrator/dialogue
  structure — automatic character detection could remove a manual-tagging step later.
- **[ekale007/RPAudiobook](https://github.com/ekale007/RPAudiobook)** — browser-based
  interactive fiction/RPG narrator using local Kokoro. Smaller/less mature than the
  above two but shows the space is active.

None of these are a drop-in replacement for your workflow (they all assume you're
writing/importing story text into their own app, not pasting from a separate Claude
chat), but they're strong prior art for the "text markup → multi-voice stitched
audio with good pacing" problem — worth reading their tagging/pause-handling code even
if you don't adopt the whole app.

### Commercial — competitive context only, none fit your constraints

All of these are **AI Dungeon Master products** (they run the game, not just narrate
your own Claude-driven session), and all use **paid cloud TTS APIs** (ElevenLabs,
Cartesia, OpenAI TTS) — exactly what your budget/self-hosting constraints rule out:

| Product | What it is | TTS | Fit |
|---|---|---|---|
| Familiar (Foundry VTT module) | AI co-DM plugin, bring-your-own-LLM | ElevenLabs/Cartesia/OpenAI, per-NPC voices | No — needs Foundry VTT, cloud TTS |
| TableForge | Full AI DM web app | Not detailed, likely cloud | No — full AI DM, not a narration layer |
| Eternal DM | Fully-voiced AI DM web app | Cloud (unspecified) | No — full AI DM |
| Scrollbook | AI co-DM via Discord | Cloud | No — different use case entirely |
| Visionarium | TTRPG multimedia control hub (maps/lighting/music + narration) | Cloud AI tools | No — much broader scope, not focused on narration |

**Conclusion for Task 0:** nothing existing fits "self-hosted, local-only, narrates
Claude-authored text I paste in, no AI-DM logic of its own, no mic." The commercial market
has converged on full AI-DM products with cloud TTS, which is the opposite of your
constraints — this actually validates that your project fills a real gap rather than
duplicating an existing tool. The open-source finds above are useful building blocks
(especially TTS-Story's and multivoice's pause/tagging approach) but none should block
or replace Phase 1 — recommend proceeding with local model testing as planned, per spec.
