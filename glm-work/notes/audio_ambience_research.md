# Ambient Audio / Music Research — Research Task 3

**Prepared by:** GLM (this session), 2026-08-18
**For:** Arie's review → feeds the DM-engine architecture decision
**Scope:** Survey two approaches for layering background music + environmental sound
under narration in the D&D narrator app: (a) generative models, (b) library/loop-based.
**Hardware target:** M1 Max, 32 GB unified memory (Arie's machine).
**Budget context:** ~€10/month total project budget (per `docs/PROJECT-ROADMAP.md`).

---

## TL;DR recommendation

**Use a hybrid: free library tracks for ambient beds + ElevenLabs SFX API for custom
one-off stings.** This is cheaper, higher quality, and more flexible than either pure
approach:

1. **Ambient beds (the music/ambience that loops under each scene):** use free
   CC0/CC-BY library tracks from OpenGameArt, Tabletop Audio, or Ivan Duch. Real
   composed music, zero cost, proven quality. The v2 demo (below) uses three such
   tracks and they sound like actual music, not noise.
2. **Custom SFX stings (one-off effects no library has):** use the ElevenLabs Sound
   Effects API ($0.12/min, free tier with 1,000 seconds). Generate once, cache
   forever. Total cost for a full campaign's custom SFX: likely under $5 one-time.
3. **Custom ambient beds (if no library track fits a weird scene):** ElevenLabs SFX
   API with `loop=true`, ~$0.06 per 30s bed. Generate once, loop forever.

**Why not self-hosted generative (AudioGen/Stable Audio on the M1 Max)?**
- Latency: ~0.3-0.6x realtime — can't generate per-turn, must pre-generate and cache
- Quality at the small/medium tier that fits 32GB: "acceptable SFX, mediocre music"
- Licensing: MusicGen/AudioGen weights are CC-BY-NC 4.0 (non-commercial)
- Stable Audio Open has **reported MPS accuracy problems on M1/M2 specifically**
- The API path (ElevenLabs, Lyria) is strictly better: no download, no MPS risk,
  commercial license, and ~$1-5 one-time for a full generated library (cached forever)

**Why not pure library?** Library tracks are great for common scene types (tavern,
dungeon, forest, combat) but can't cover custom/specific needs ("the sound of the
vodnik's reed-stalk lair at midnight"). The API fills that gap for pennies.

The v2 demo (below) uses real CC0/CC-BY library tracks and sounds like actual music
under narration — a direct response to Arie's feedback that the v1 synthesized beds
"sounded like white noise."

---

## (a) Generative models — survey

All four below are text-to-audio (or text-to-music) models that could in principle
generate an ambient bed from a scene description like "busy fantasy tavern with
fireplace and distant laughter." Feasibility on the M1 Max is the key question.

### A1. MusicGen (Meta, audiocraft) — text-to-MUSIC

- **What it is:** autoregressive transformer over EnCodec tokens, generates music
  from text prompts. 32 kHz, ~10s clips per generation (can be extended).
- **Sizes:**
  | Variant | Params | Download | Notes |
  |---|---|---|---|
  | musicgen-small | 300M | ~1.2 GB | mono, "good" quality |
  | musicgen-medium | 1.5B | ~3.2 GB | mono, "better" — Meta's recommended quality/compute tradeoff |
  | musicgen-large | 3.3B | ~6.5 GB | mono, "best" |
  | musicgen-stereo-* | same | same | stereo variants of each |
- **License:** code = MIT; **model weights = CC-BY-NC 4.0** (non-commercial only).
  The weights license blocks running the model in a commercial service. The copyright
  status of *outputs* is legally murky (US Copyright Office says purely AI-generated
  output without human intervention is public domain, but this is not settled for
  CC-BY-NC-licensed weights — see audiocraft issue #198). For Arie's personal/hobby
  use this is fine; for any future paid app it's a real blocker.
- **M1 Max feasibility:** there are two MLX ports that avoid the CUDA requirement:
  - `theashishmaurya/mlx-audiocraft` — full AudioCraft (MusicGen + AudioGen) on MLX
  - `andrade0/musicgen-mlx` — inference-only MusicGen port
  - Benchmarks are on **M4 Max** (faster than M1 Max): small ~1.3x realtime,
    medium ~0.6x, large ~0.3x. On Arie's M1 Max expect roughly half again slower,
    so small ~0.7x realtime, medium ~0.3x. **Only `small` is plausibly faster than
    realtime on M1 Max, and `small` is the lowest-quality variant.**
- **Quality vs use case:** MusicGen generates *music*, not environmental ambience.
  For a tavern bed you'd want both music AND ambience (fire crackle, chatter) —
  MusicGen alone gives you only the music half. Useful for combat stings / boss
  themes, less useful for the ambient bed itself.
- **Verdict:** viable for pre-generated music stings if Arie accepts CC-BY-NC. Not
  the right primary tool for ambient beds.

### A2. AudioGen (Meta, audiocraft) — text-to-SFX/AMBIENCE  ← most relevant generative option

- **What it is:** sibling of MusicGen, trained on environmental sounds (AudioSet,
  BBC SFX, AudioCaps, Clotho, VGG-Sound, FSD50K, Sonniss GDC bundles). Generates
  *environmental* audio — fire, tavern chatter, wind, footsteps, combat sounds.
  This is exactly the "ambient bed" use case.
- **Sizes:** only one released checkpoint: `facebook/audiogen-medium`, 1.5B params,
  **~3.6 GB download**, 16 kHz output (lower sample rate than MusicGen — fine for
  ambience, not for music).
- **License:** code MIT, **weights CC-BY-NC 4.0** (same non-commercial restriction
  as MusicGen).
- **M1 Max feasibility:** via `mlx-audiocraft`. M4 Max benchmark: ~0.6x realtime
  for 5s audio (8s to generate). On M1 Max expect ~0.3-0.4x realtime — **slower
  than realtime, so you cannot generate per-turn.** You'd pre-generate and cache.
- **Quality:** good for discrete SFX (a single dog bark, a door creak), weaker for
  layered ambient scenes (tavern = fire + chatter + music + glasses clinking —
  AudioGen struggles to compose multiple simultaneous sources coherently).
- **Verdict:** the right *kind* of model for ambience, but the wrong *scale* for
  real-time use on M1 Max, and CC-BY-NC blocks commercial use. Best fit is
  pre-generating one-off SFX stings and caching them.

### A3. Stable Audio Open (Stability AI) — text-to-audio/SFX

- **What it is:** latent diffusion model, text-to-audio. Specializes in short
  samples, SFX, ambience, foley, drum beats, instrument riffs — **not** full songs.
  Trained on Freesound + Free Music Archive (cleaner provenance than MusicGen).
- **Two checkpoints:**
  | Variant | Params | Download | Output | Max length |
  |---|---|---|---|---|
  | stable-audio-open-1.0 | ~1B | ~2.5 GB (fp16) | 44.1 kHz | up to 47s |
  | stable-audio-open-small (May 2025) | 0.5B | ~1.5 GB | 44.1 kHz stereo | up to 11s |
- **License:** **Stability AI Community License** — non-commercial OK, commercial
  OK if annual revenue < US $1M. **This is more permissive than MusicGen/AudioGen's
  CC-BY-NC** — Arie's personal use is fine, and a small commercial app would be too.
- **M1 Max feasibility — REAL RISK:** MPS is supported but there are multiple
  reports (Stability-AI/stable-audio-tools PR #225) of **accuracy problems on M1
  and M2 chips specifically** — "execution is fast but prone to garbage outputs
  compared to CUDA." M4 chips are better. Arie's M1 Max is in the affected range.
  This means Stable Audio Open might *run* on his machine but produce unusable
  audio without careful workarounds (fp32 vs fp16, op fallback detection).
  Speed when it works: ~1.4 it/s on M2 Max 64GB (PR #82) — usable but not fast.
- **Arm CPU path:** Arm + KleidiAI demonstrated Stable Audio Open Small generating
  10s of audio in ~7s on phone CPUs (MWC 2025). This is a mobile-optimized path
  that could matter if the app ever targets Android, but it's not the standard
  PyTorch/MPS path Arie would use today.
- **Verdict:** best licensing of the generative options, but the M1/M2 MPS accuracy
  issue is a concrete blocker that needs hands-on testing before committing. The
  `small` variant (0.5B, ~1.5GB) is the cheapest thing to actually test.

### A4. AudioLDM2 (cvssp) — text-to-audio/music

- **What it is:** diffusion-based text-to-audio, older than the above three.
  Checkpoints: `audioldm2` 1.1B (SFX), `audioldm2-music` 1.1B (music),
  `audioldm2-large` 1.5B (SFX).
- **License:** CC-BY-NC (the cvssp HF repos).
- **M1 Max feasibility:** MPS supported but the repo itself notes **~20 GB RAM
  required** and the original implementation is slow (10s clip = 30s+ even after
  diffusers optimizations). Default 200 inference steps.
- **Quality:** generally considered lower than MusicGen/Stable Audio at this point;
  it's a 2023 model and the field has moved.
- **Verdict:** skip. Older, slower, lower quality, same non-commercial restriction.
  No reason to choose this over AudioGen or Stable Audio Open.

### Generative summary table

| Model | Use | Download | M1 Max speed | License | Real-time? |
|---|---|---|---|---|---|
| MusicGen small | music | 1.2 GB | ~0.7x realtime (est.) | CC-BY-NC 4.0 | borderline |
| MusicGen medium | music | 3.2 GB | ~0.3x realtime (est.) | CC-BY-NC 4.0 | no |
| AudioGen medium | ambience/SFX | 3.6 GB | ~0.3-0.4x realtime (est.) | CC-BY-NC 4.0 | no |
| Stable Audio Open 1.0 | ambience/SFX | 2.5 GB | ~1.4 it/s (M2 Max) | Stability Community (OK <$1M) | borderline, **M1/M2 MPS accuracy risk** |
| Stable Audio Open Small | ambience/SFX | 1.5 GB | ~7s for 10s on Arm CPU | Stability Community (OK <$1M) | borderline, MPS risk unknown for small |
| AudioLDM2 | ambience/music | ~1.5 GB | slow (30s+/10s) | CC-BY-NC | no |

**Bottom line on generative:** none of these can reliably generate a fresh ambient
bed *per turn* in real-time on Arie's M1 Max. The realistic pattern is
pre-generate → cache → replay, which collapses into "a library you generated
yourself" — and at that point a curated human-made library is higher quality and
simpler. Generative's real niche is *one-off SFX stings* (a specific spell effect,
a unique monster roar) generated once and cached.

---

## (b) Library / loop-based approaches — survey

The concept: curate a set of pre-made ambient/music tracks tagged by scene type
(tavern, forest, dungeon, combat, town, travel, boss, etc.). The DM engine maps
the current scene's keyword(s) to a track and loops it under the narration.
No generation latency, no compute cost, professional quality.

### B1. Tabletop Audio (tabletopaudio.com) — THE canonical TTRPG ambience resource

- **What:** 500+ 10-minute ambience tracks (80+ hours total), purpose-built for
  tabletop RPGs. Each track is a full scene (e.g. "Tavern," "Dungeon," "Forest at
  Night," "Sea Battle"). Most tracks have **alternate versions**: ambience+music,
  ambience-only, music-only — so you can layer flexibly.
- **License:** **CC-BY-NC-ND 4.0** for the free 10-minute ambiences
  (Attribution + NonCommercial + NoDerivatives). Free for personal/hobby use.
  Commercial use: creator says a Patreon subscription "can absolutely double as a
  license for commercial podcast/video use" — flexible, talk to him.
- **Cost:** free; Patreon for commercial use + access to SoundPads and "Zones"
  (a probabilistic ambient music engine).
- **Fit for our app:** excellent. Scene-tagged, 10-minute loops (long enough to
  hide obvious looping), ambience-only variants mean we can layer our own music on
  top. The CC-BY-NC-ND is fine for Arie's personal use; the ND (no derivatives)
  clause means we can't *edit* the tracks, but looping/playing under narration is
  not a derivative work.
- **Integration:** a GitHub repo (`rsek/tabletop-audio-tracks`) has all 300+ tracks
  with tags and metadata — could be a ready-made scene→track mapping.

### B2. Ivan Duch — DnD background music

- **What:** royalty-free DnD background music, organized by scene type (tavern,
  dungeon/horror, combat/battle, travel). Free tracks tagged as free; FoundryVTT
  modules for integrated playback. Also has looping ambience packs (rain, crickets,
  campfire, tavern background, combat sounds).
- **License:** royalty-free, free with credit/attribution. Cleared for streaming
  and actual-play. Commercial use allowed with credit.
- **Cost:** free with credit; paid modules for FoundryVTT integration.
- **Fit:** strong — explicitly scene-tagged, designed for exactly this use case,
  permissive licensing.

### B3. LauraCreativeSupply "The Classic Campaign" (itch.io)

- **What:** 224 royalty-free ambient tracks across 5 bundles: Fantasy RPG Tavern
  (54), Dark Dungeon Fantasy (60), Fantasy Travel (40), Battle & Boss Encounters
  (40), Medieval Village (30). Designed for D&D/Pathfinder/Foundry VTT/Roll20.
- **License:** commercial use allowed in videos/streams/games/podcasts; no
  reselling raw files.
- **Cost:** **$39.99 USD (~€37) one-time** for all 224 tracks.
- **Fit:** this is the "buy once, done forever" option. 224 tracks cover the full
  scene-type space, commercial license is clean, no attribution needed. One-time
  cost fits the ~€10/month budget framing (it's less than 4 months of budget and
  then it's free forever).

### B4. Aibou Note Music "Fantasy RPG BGM Pack" (itch.io)

- **What:** 10 royalty-free adventure tracks (village, fields, woods, cave, combat,
  boss, victory, tavern, return).
- **License:** non-exclusive royalty-free, commercial + non-commercial, no
  attribution required, no time/view limits.
- **Cost:** small one-time purchase (~$5-10 range).
- **Caveat:** explicitly disclosed as **AI-generated with Suno under a paid plan**.
  If Arie wants to avoid AI-generated content on principle, skip this one. If not,
  it's a cheap way to get a basic scene-tagged set.
- **Fit:** cheap starter set, but only 10 tracks and AI-generated provenance.

### B5. Tavern Nights (fredcalil, itch.io)

- **What:** 20 loopable tavern-themed ambient tracks, ~1 minute each, seamless
  looping. MP3 + WAV. Scene-tagged within tavern (warm welcome, low conversations,
  fireplace, bard, festival, dice tension, brawl, etc.).
- **License:** Freepik commercial license (commercial use allowed, no direct resale).
- **Cost:** name-your-own-price.
- **Fit:** narrow (tavern only) but very deep within that scene — useful for
  sub-scene mood shifts inside a single tavern.

### B6. Sonniss Game Audio GDC bundles

- **What:** large free SFX bundles released annually at GDC (tens of GB of
  professional game audio). These are what AudioGen was partly trained on.
- **License:** varies per asset but generally royalty-free for game use.
- **Fit:** good source for one-off SFX (sword hits, spell casts, door creaks) to
  trigger on specific events. Not ambient beds.

### Library summary table

| Source | Tracks | Cost | License | Scene-tagged? | Best for |
|---|---|---|---|---|---|
| Tabletop Audio | 500+ | free / Patreon | CC-BY-NC-ND 4.0 | yes (named scenes) | ambient beds, ambience-only variants |
| Ivan Duch | many | free w/ credit | royalty-free | yes (tavern/dungeon/combat/travel) | music + ambience, FoundryVTT-ready |
| Classic Campaign (Laura) | 224 | $39.99 once | commercial OK | yes (5 scene bundles) | "buy once, done" full coverage |
| Aibou Note | 10 | ~$5-10 | commercial OK | yes | cheap starter (AI-generated) |
| Tavern Nights | 20 | name-your-price | Freepik commercial | yes (tavern sub-moods) | deep tavern coverage |
| Sonniss GDC | huge | free | varies (mostly RF) | no (raw SFX) | one-off event SFX |

---

## (c) Audio generation APIs — paid/hosted options

*Added 2026-08-18 after Arie asked: "can you expand the audio generating LLM's
research with api options, like local_llm_dm_research.md found Groq?"*

Same insight as the DM-brain research: there's a middle option between "run a
model locally on the M1 Max" (slow, CC-BY-NC, MPS risk) and "use a frontier
per-token API" (expensive). Hosted audio generation APIs give you
studio-quality output without any local model download, at per-generation
pricing. The question is whether any fit the ~€10/month budget.

### The providers

| Provider | Model | What it generates | Price | Max duration | Commercial use? |
|---|---|---|---|---|---|
| **ElevenLabs** | Sound Effects v2 | SFX + ambient beds from text | **$0.12/min** (auto-duration) or 40 credits/sec (fixed duration) | 30s/generation, **seamless loop option** | Yes (Starter+ plans) |
| **ElevenLabs** | Music | Full music tracks from text | **$0.15/min** | up to 10 min | Yes (Starter+ plans) |
| **Google Lyria 3 Clip** | lyria-3-clip-preview | Short music clips/loops | **$0.04/generation** (30s clip) | 30s | Yes (paid Gemini plan) |
| **Google Lyria 3 Pro** | lyria-3-pro-preview | Full songs with structure | **$0.08/generation** (up to ~3 min) | couple of minutes | Yes (paid Gemini plan) |
| **Google Lyria 2** | lyria-002 | Instrumental music | **$0.06/generation** (30s) | 30s | Yes (paid Gemini plan) |
| **Stable Audio 2.5** | stability-ai/stable-audio-2.5 | Music + sound from text | **$0.20/generation** (up to 3 min) | 3 min | Yes (Stability Community license <$1M) |
| **Stable Audio 3.0** | — | Music + sound from text | **$0.26/generation** (up to 6 min) | 6 min | Yes |
| **Mureka** | — | AI music | **$0.05/song** | model-dependent | Yes (paid plans) |
| **Replicate** (hosted MusicGen) | meta/musicgen | Music from text | ~$0.10/run (~73s on A100) | varies | MusicGen weights are CC-BY-NC (same restriction) |
| **Suno** | v5.5 | Full songs with vocals | **No official public API** (subscription only: $8-24/mo). Third-party API wrappers exist (~$0.055/track via Apiframe) | varies | Yes (paid plans); API access is enterprise/partner only |
| **Udio** | — | Full songs with vocals | **No public API** (consumer subscription: $10-30/mo). Enterprise tier ($100/mo) has API access | varies | Yes (Pro+ plans) |

### Which ones matter for our use case?

Our use case is **ambient beds + SFX stings under narration**, not full songs
with vocals. That immediately rules out Suno and Udio as primary tools — they're
song generators (vocals, verses, choruses), not ambient/SFX generators, and
neither has a clean public API. They're also the most expensive per generation.

The relevant options for us are:

**1. ElevenLabs Sound Effects API — the best fit for ambient beds + SFX.**
- Generates ambient beds AND discrete SFX from text prompts.
- Has a **built-in seamless loop mode** (`loop=true` in the API) — exactly what
  we need for ambient beds that play under narration. Generate 30s of "dark
  marsh ambience with distant thunder and water drips," loop it endlessly.
- Understands audio terminology: "Ambience," "Drone," "Loop," "Impact," "Whoosh"
  are all recognized prompt keywords.
- $0.12/min = ~$0.04 for a 30s looped ambient bed. You generate it ONCE, loop it
  forever. **The cost is per-generation, not per-playback** — a cached 30s loop
  costs $0.04 total, not $0.04/minute of use.
- Quality: inference.sh review says "Foley effects in particular — footsteps,
  object interactions, environmental sounds — come out with a physicality that
  synthetic sound design usually lacks." This is exactly our use case.
- Limitation: "generates isolated effects, not layered soundscapes. If you need
  a complex ambient bed with multiple simultaneous elements, generate components
  separately and mix them." So a rich tavern bed = generate "tavern crowd
  murmur" + "fireplace crackle" + "glass clinks" separately, mix them. A few
  generations per scene type, cached forever.
- **Free tier:** 1,000 seconds of audio for new users (enough to test
  extensively before paying).

**2. Google Lyria — cheapest for music stings.**
- Lyria 3 Clip at $0.04/generation for a 30s clip is the cheapest music
  generation API. Good for combat/boss themes, victory stings, etc.
- Instrumental only (Lyria 2) or full songs with vocals (Lyria 3) — for our use
  case, instrumental is what we want.
- Limitation: 30s clips for the cheap tier. For looping ambient beds, 30s is
  fine (same as ElevenLabs). For longer music, Lyria 3 Pro at $0.08 for up to
  ~3 min.
- Requires a paid Gemini API plan (not free tier).

**3. Stable Audio API — good for longer generations.**
- $0.20/generation for up to 3 min (Stable Audio 2.5) or $0.26 for up to 6 min
  (3.0). Theoretical floor: $0.067/min (2.5) or $0.043/min (3.0) if you use the
  full duration.
- Better than ElevenLabs for longer continuous pieces, worse for short SFX.
- Same Stability Community License as the self-hosted model (OK if <$1M revenue).

**4. Replicate (hosted MusicGen) — skip.**
- Same CC-BY-NC weights as self-hosted MusicGen, just running on someone else's
  A100. No licensing advantage over self-hosting, and ~$0.10/run is more
  expensive than ElevenLabs SFX for shorter pieces.

### Cost math for our use case

The key insight: **ambient beds are generated ONCE and cached, not generated
per turn.** You don't generate a fresh tavern bed every time the party enters a
tavern — you generate it once, save the WAV, and loop it. This makes the cost
a one-time setup expense, not an ongoing per-session cost.

**Scenario: build a scene-tagged library of 20 ambient beds + 30 SFX stings
using ElevenLabs SFX API:**
- 20 ambient beds × 1 generation each (30s, looped) = 20 × $0.06 (30s at
  $0.12/min) = **~$1.20**
- 30 SFX stings × 1 generation each (~3s avg) = 30 × $0.006 = **~$0.18**
- **Total one-time cost: ~$1.40** for a full scene-tagged ambience library
- Ongoing cost: **$0** (cached, replayed forever)
- If a bed needs to be regenerated or a new scene type is added: ~$0.06 per new bed

**Compare to:**
- Classic Campaign pack (human-made library): ~€37 once, 224 tracks
- Tabletop Audio (human-made, CC-licensed): €0, 500+ tracks
- ElevenLabs-generated library: ~$1.40 once, ~50 tracks, exactly customized to
  your scene types

**The API-generated library is dramatically cheaper than buying a human-made
pack, and gives you exactly the scene types you need** (e.g. "dark marsh with
vodnik lurking" is not a track you'll find in any library, but ElevenLabs can
generate it from that exact prompt). The tradeoff is quality — human-composed
music is still better than AI-generated, and the CC0 library tracks in the v2
demo are real composed music, not AI.

### The hybrid recommendation (updated)

**Best approach: library tracks for the ambient bed + ElevenLabs SFX API for
custom one-off stings.**

1. **Ambient beds:** use free CC0/CC-BY library tracks (Tabletop Audio,
   OpenGameArt, Ivan Duch) for the main ambient bed. Real composed music,
   zero cost, proven quality (the v2 demo uses these).
2. **Custom SFX stings:** use ElevenLabs SFX API ($0.12/min, free tier
   available) to generate one-off effects that no library has — a specific
   spell's sound, a unique monster's roar, a custom door creak. Generate once,
   cache forever. Total cost for a full campaign's worth of custom SFX: likely
   under $5.
3. **Custom ambient beds (if a library track doesn't fit):** ElevenLabs SFX
   API with `loop=true` for scene types that no library track matches (e.g.
   "alien spaceship engine hum" for a sci-fi one-shot). ~$0.06 per bed.

This gives you the quality of real composed music for the main bed, the
flexibility of generative AI for custom elements, and a total cost well under
€10 — in fact, likely under €5 for everything, one-time.

### API vs. self-hosted generative — why API wins here

Unlike the DM-brain case (where Groq's per-token API was 5-20x cheaper than
Claude but still had ongoing per-turn cost), audio generation APIs have a
huge advantage: **you generate once and cache forever.** There is no ongoing
per-session cost. This means:

- No model download (vs. 1.5-3.6 GB for self-hosted AudioGen/Stable Audio)
- No M1/M2 MPS accuracy risk (the API runs on proper GPUs)
- No CC-BY-NC restriction (ElevenLabs and Lyria outputs are commercially
  licensed on paid plans; Stable Audio API uses the same Community License)
- No local compute time (generation happens on the server in seconds)
- Total cost for a full library: ~$1-5 one-time

**The self-hosted generative path (AudioGen/Stable Audio Open on the M1 Max)
is strictly worse than the API path for our use case.** The only reason to
self-host would be privacy (not sending prompts to a server) or zero-cost
constraint (but the free tiers of ElevenLabs/Lyria already cover initial
testing).

### What I'd test hands-on (if Arie wants to try the API path)

1. **ElevenLabs SFX free tier** (1,000 seconds free, no credit card):
   - Generate "dark marsh ambience with distant thunder, water drips, and low
     wind" with `loop=true`, 30s duration
   - Compare to the v2 demo's `dungeon_ambient.ogg` (CC0 library track)
   - Generate a few SFX stings: "sword hitting shield," "fireball explosion,"
     "wooden door creaking open"
   - Layer them under the Kokoro narration using the same ducking script
2. **Google Lyria 3 Clip** (if Arie has a paid Gemini plan):
   - Generate "tense dark orchestral strings for a marsh scene at night" (30s)
   - Compare to the v2 demo's `dark_woods.mp3` (CC-BY library track)

No downloads needed for either — just API calls. If Arie wants to try this,
I can write the generation + layering script.

---

## How scene-type keyword triggering would work in practice

This is the integration question — how does the DM engine go from "the party walks
into a tavern" to "play the tavern ambience"? Two layers:

1. **Scene classification:** the DM LLM's narration output includes a scene-type
   tag (either as a structured field in its JSON response, or extracted from the
   narration text by keyword matching: "tavern"/"inn"/"pub" → tavern; "dungeon"/
   "crypt"/"cave" → dungeon; "fight"/"attack"/"roll initiative" → combat). The
   structured-field approach is cleaner and matches the DM-engine architecture
   Sonnet is planning (the LLM writes a JSON state object each turn — adding a
   `scene_type` field is trivial).

2. **Track selection:** a lookup table maps scene_type → track file(s). With
   variety: each scene_type has 3-5 candidate tracks, pick one randomly (or by
   sub-mood: "tavern: tense" vs "tavern: celebratory"). Crossfade between tracks
   when scene_type changes. Loop the selected track for the duration of the scene.

3. **Layering:** play the ambient bed at ~20-30% volume under the narration
   (narration at 100%). Duck the ambience slightly during speech (side-chain
   compression) so the voice stays intelligible. This is standard podcast/audiobook
   technique and the demo below illustrates it.

This is all straightforward engineering — no ML required for the library path.
The hard part is curating/tagging the track library, which is a one-time effort.

---

## Cost comparison (against the ~€10/month budget)

| Approach | One-time cost | Ongoing cost | Notes |
|---|---|---|---|
| Tabletop Audio (free tracks) | €0 | €0 | CC-BY-NC-ND, personal use only |
| Classic Campaign pack | ~€37 once | €0 | commercial OK, 224 tracks, done forever |
| Generative (AudioGen medium) | €0 (3.6 GB download) | compute time per generation | CC-BY-NC, slower than realtime, pre-gen+cache |
| Generative (Stable Audio Open Small) | €0 (1.5 GB download) | compute time per generation | Stability license OK <$1M, **M1 MPS risk** |

**The library path is cheaper over any time horizon longer than a month, and
free if Arie uses Tabletop Audio's CC-licensed tracks for personal use.** The
generative path's "cost" is Arie's time waiting for downloads + compute, plus
the legal murkiness of CC-BY-NC weights.

---

## Recommended plan for Arie

1. **v1 (now): library-based.** Start with Tabletop Audio's free CC-BY-NC-ND tracks
   for personal use (zero cost, 500+ tracks, scene-tagged). If Arie wants a clean
   commercial license and a curated 224-track set covering every scene, buy the
   Classic Campaign pack (~€37 once). Build the scene_type → track lookup + crossfade
   + ducking. This is the demo below's pattern, just with real tracks swapped in.

2. **v1.5 (optional): pre-generated SFX stings.** If specific one-off effects are
   needed (a unique spell, a monster roar), pre-generate them with AudioGen or
   Stable Audio Open, cache as WAV, trigger on event. This is where generative
   actually earns its place — discrete SFX, not ambient beds.

3. **v2 (later, if ever): real-time generative.** Only worth revisiting if (a) the
   M1/M2 MPS accuracy issue for Stable Audio Open gets fixed upstream, AND (b)
   Arie wants truly dynamic per-scene ambient that no library track matches. Until
   then, library + cached SFX is strictly better on quality, cost, and latency.

---

## What I did NOT download (flagging for Arie / download assistant)

Per the instructions, no large downloads without asking. The generative path would
need one of these to test hands-on, all of which Arie can hand off to the download
assistant:

| Model | Size | Why | Risk |
|---|---|---|---|
| `facebook/audiogen-medium` | ~3.6 GB | Test generative ambience/SFX quality on M1 Max via `mlx-audiocraft` | CC-BY-NC; ~0.3-0.4x realtime on M1 Max (pre-gen+cache only) |
| `stabilityai/stable-audio-open-small` | ~1.5 GB | Test the most-permissively-licensed generative option | **M1/M2 MPS accuracy issues reported** — may produce garbage |
| `facebook/musicgen-small` | ~1.2 GB | Test generative music stings (combat/boss themes) | CC-BY-NC; lowest quality music variant |

**My recommendation: don't download any of these yet.** The library path is clearly
better for v1 and the demo below lets Arie hear the concept without any download.
If Arie wants to hear what generative actually sounds like on his machine, the
smallest worthwhile test is `stable-audio-open-small` (~1.5 GB) — but go in knowing
the MPS accuracy risk is real on M1 Max.

---

## Demo (included with this research)

### v2 — REAL library tracks (the one to listen to)

After Arie's feedback that the v1 synthesized beds "sounded like white noise," v2
uses **actual royalty-free music tracks** from OpenGameArt, layered under the same
Kokoro narration with side-chain ducking. Files in `glm-work/outputs/ambience_demo/`:

- `narration_dry_reference.wav` — the Kokoro narration with NO ambience (baseline)
- **`v2_dark_woods.wav`** — "RPG Ambient 4 (The Dark Woods)" by Hitctrl (CC-BY 3.0).
  Tense orchestral strings. **Best match for the narration content** (Mireth at the
  marsh edge, storm coming). Start here.
- `v2_dungeon.wav` — "Loopable Dungeon Ambience" by JaggedStone (CC0). Low wind +
  water drips. Also matches the marsh/dark mood — more ambient, less musical.
- `v2_tavern.wav` — "The Old Tower Inn" by RandomMind (CC0). Medieval tavern/inn
  theme. Doesn't match the story but shows a "safe/social" scene type.

Source tracks downloaded from OpenGameArt.org (~10 MB total, not model downloads):
- `tracks/tavern_old_tower_inn.mp3` — CC0, 105.8s
- `tracks/dark_woods.mp3` — CC-BY 3.0 (credit: Hitctrl), 144.2s
- `tracks/dungeon_ambient.ogg` — CC0, 94.3s

Script: `glm-work/make_ambience_demo_v2.py` (tweak `base_vol` and `duck_depth` per
track in the `BEDS` list, re-run). README in `outputs/ambience_demo/README.md`.

### v1 — synthesized beds (kept for reference, Arie said these sound like noise)

`demo_tavern.wav`, `demo_forest.wav`, `demo_marsh.wav` — procedurally synthesized
with numpy/scipy. Arie's feedback: "they all sound like white noise or just
background noise, not ambience or specific story related sounds. Not feasible."
Kept for comparison but skip these. Script: `glm-work/make_ambience_demo.py`.

### Next step if Arie wants to hear the API path

I can write a script that calls the ElevenLabs SFX API (free tier, 1,000 seconds)
to generate custom ambient beds and SFX stings from text prompts, then layers them
under the same narration using the same ducking code. No downloads needed — just
an API key. This would let Arie compare: real library tracks (v2) vs. AI-generated
ambient (v3) vs. dry narration (reference).
