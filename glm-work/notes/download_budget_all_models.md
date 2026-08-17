# All Remaining Models — Download Budget

**Researched:** 2026-08-17 by GLM-5.2 High
**Constraint:** Arie is on slow mountain 4G. No downloads without explicit per-model approval.

All sizes are exact Hugging Face file sizes (verified via HF file trees, not estimates).
"Already installed" = torch/transformers/numpy etc. from the Kokoro setup are reused.

---

## Qwen3-TTS (Priority 1) — ✅ CONFIRMED works on Apple Silicon MPS

Multiple variants exist. The one most relevant to Arie's NPC-voice requirement is
**VoiceDesign** (describe voices in natural language — "a gruff old marsh-dweller
with a gravelly voice" — and the model generates that voice).

| Variant | model.safetensors | Total repo | Use case |
|---|---:|---:|---|
| 0.6B-Base | 1.83 GB | 2.52 GB | Voice cloning from 3s audio, 9 preset timbres |
| 1.7B-Base | 3.86 GB | ~4.5 GB | Same, bigger/slower |
| 1.7B-CustomVoice | ~3.8 GB | ~4.5 GB | Style control over 9 premium timbres |
| **1.7B-VoiceDesign** | **3.83 GB** | **4.52 GB** | **Natural-language voice design — BEST for NPC voices** |

**Additional shared download:**
- `Qwen3-TTS-Tokenizer-12Hz`: ~200 MB (shared across all variants)
- `qwen-tts` pip package + deps: ~50-100 MB (most deps already installed from Kokoro)

**Apple Silicon status:** Confirmed working on MPS via official PR #124 + multiple
user reports (M3 Ultra, M4 Pro). Key notes:
- `device_map="mps"`, `attn_implementation="sdpa"` (no FlashAttention on Mac)
- VoiceDesign: `dtype=torch.float16` works on MPS
- Voice Clone (Base): `dtype=torch.float32` required on MPS (float16 → nan errors)
- Also available via `mlx-audio` (Apple's native ML framework) — potentially faster

**Recommended for Arie:** 1.7B-VoiceDesign (~4.7 GB total with tokenizer)
- This is the variant that directly addresses the multi-voice/NPC requirement
- Can describe voices in natural language → unlimited distinct character voices
- Downside: biggest download of the Priority 1 options

**Alternative:** 0.6B-Base (~2.7 GB total) — smaller but only preset timbres + cloning,
no natural-language voice design. Could test first if 4G is too slow for 4.7 GB.

---

## Dia2 (Priority 2) — CUDA-first, CPU fallback likely slow

| Variant | model.safetensors | Total repo | Notes |
|---|---:|---:|---|
| Dia2-1B | 4.31 GB | 4.31 GB | F32 weights |
| Dia2-2B | 7.68 GB | 7.68 GB | Bigger, better quality |

**Additional:** Mimi audio tokenizer (small, bundled in repo)

**Apple Silicon status:** CUDA-first. CLI auto-selects CUDA or CPU. No explicit MPS
support found. CPU fallback will likely be VERY slow for a 1B+ param transformer.
The spec says: "test on Mac and clearly report if it fails, degrades, or needs CPU
fallback."

**Multi-voice:** Native `[S1]`/`[S2]` speaker tags — this is Dia2's strength.
**Limit:** Capped at ~2 min generation per run (chunking needed for long text).

**Recommended:** Dia2-1B (4.31 GB) — start with the smaller variant. If CPU is too
slow, document and stop per spec. Don't download the 2B (7.68 GB) unless 1B shows
promise AND speed is acceptable.

---

## Higgs Audio V2 (Priority 3 / stretch) — almost certainly impractical on M1 Max

| Variant | Weights | Total | Notes |
|---|---:|---:|---|
| 3B-base (original) | 11.55 GB (3 shards) | ~11.6 GB | "24GB GPU recommended" |
| 3B-base MLX q8 | 6.18 GB | ~6.2 GB | Community MLX quantization — COULD work on Apple Silicon |

**Apple Silicon status:** Built on Llama-3.2-3B, designed for CUDA/vLLM. Official
docs say "24GB GPU memory" for optimal performance. M1 Max has 32GB unified memory
but no CUDA. The MLX q8 community version (6.18 GB) is a possible path but
unofficial and may have issues.

**Spec guidance:** "if it clearly won't run reasonably, document why and stop rather
than fighting it."

**Recommendation:** Skip the 11.6 GB original. If Arie wants to attempt it, try the
MLX q8 version (6.18 GB) — but this is lowest priority and most likely to fail.

---

## Chatterbox (Priority 3 / stretch) — has CPU support, but spec says "sounded weak"

| Variant | Key files | Total | Notes |
|---|---|---:|---|
| English (original) | t3_cfg.safetensors (2.13 GB) + s3gen.safetensors (1.06 GB) + ve (5.7 MB) | ~3.2 GB | CFG + exaggeration tuning |
| Multilingual V3 | t3_mtl23ls_v3 (2.14 GB) + s3gen_v3 (1.06 GB) | ~3.2 GB | 23 languages |
| Chatterbox-Nano | 110M params | ~? (need to check) | "3x faster than realtime on 8 CPU cores" |

**Apple Silicon status:** Has CPU inference support (confirmed via GitHub issue #70).
User-provided CPU patch exists. MPS support unclear.

**Spec guidance:** "already informally tested via HF Space and sounded weak, so low
priority, but include for a fair side-by-side if time allows."

**Recommendation:** Lowest priority. Only if Arie wants completeness. The Nano
variant (110M) is interesting for speed but quality is the concern per spec.

---

## Summary table — all models sorted by priority + download size

| Model | Priority | Download | Apple Silicon? | Multi-voice? | Verdict |
|---|---|---:|---|---|---|
| Kokoro-82M | P1 ✅ done | ~0.6 GB | ✅ CPU, 5-7x RT | Presets only (54) | Tested |
| **Qwen3-TTS 1.7B-VoiceDesign** | **P1** | **~4.7 GB** | **✅ MPS confirmed** | **Natural-language voice design** | **Best next step** |
| Qwen3-TTS 0.6B-Base | P1 (alt) | ~2.7 GB | ✅ MPS | Presets + cloning | Smaller fallback |
| Dia2-1B | P2 | 4.31 GB | ⚠️ CPU only, likely slow | Native [S1]/[S2] | Worth attempting |
| Dia2-2B | P2 | 7.68 GB | ⚠️ CPU only, likely slow | Native [S1]/[S2] | Only if 1B is promising |
| Higgs Audio V2 (MLX q8) | P3 stretch | 6.18 GB | ⚠️ Unofficial MLX, may fail | Unknown | Skip unless curious |
| Higgs Audio V2 (original) | P3 stretch | 11.6 GB | ❌ CUDA-only | Unknown | Skip |
| Chatterbox (English) | P3 stretch | ~3.2 GB | ✅ CPU | Voice cloning | Low priority, "sounded weak" |
| Chatterbox-Nano | P3 stretch | ~? GB | ✅ CPU, 3x RT | Voice cloning | Smallest, fastest, weakest |
