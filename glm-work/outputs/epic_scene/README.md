# Epic Scene — Multi-Method Production Demo

Four methods of producing the same type of scene: **narrator + 2 character voices +
background music + 3+ ambient SFX**, each using different tools for the components.

## The scene

`test_scripts/4_epic_scene.txt` — Kael (grizzled veteran warrior) and Lyra (young mage)
descend into an ancient cathedral, trigger a cave-in, fight animated armor, and Lyra
unleashes a spell that dissolves the guardians. Four SFX moments:
1. Heavy stone door grinding open
2. Rocks falling / cave-in
3. Sword clash (combat)
4. Magical explosion / energy burst

## The four methods — ALL COMPLETE

### Method 1: All-local — `method1_all_local.wav` (239.3s, 11 MB)

**Everything runs on your M1 Max. No API calls, no network.**

| Component | Tool | Details |
|---|---|---|
| TTS | **Kokoro-82M** (local) | 3 voices: `af_heart` (narrator), `am_onyx` (Kael), `af_sky` (Lyra) |
| Music | **"RPG Ambient 4 (The Dark Woods)"** by Hitctrl | CC-BY 3.0, from OpenGameArt, with side-chain ducking |
| SFX | **Procedurally synthesized** (numpy/scipy) | 4 SFX synthesized from scratch — no downloads, no API |
| Assembly | Python (numpy/scipy) | Side-chain ducking, SFX placement, soft clipping |

**Strengths:** Zero cost, zero network, zero downloads. Runs entirely offline.
**Weaknesses:** SFX are synthesized (not realistic). Kokoro voices are good but not
as expressive as ElevenLabs. Music is a fixed library track (not custom-generated).

### Method 2: Hybrid — `method2_hybrid.wav` (289.8s, 13.6 MB)

**Local TTS with natural-language voice design + library music + real ElevenLabs SFX.**

| Component | Tool | Details |
|---|---|---|
| TTS | **Qwen3-TTS VoiceDesign** (local, MLX) | Natural-language voice descriptions: "a grizzled veteran warrior with a deep, gravelly voice" |
| Music | **"RPG Ambient 4 (The Dark Woods)"** by Hitctrl | Same CC-BY library track with ducking |
| SFX | **ElevenLabs SFX API** | Real AI-generated SFX from text prompts |
| Assembly | Python (numpy/scipy) | Same mixing pipeline |

**Strengths:** Qwen3 VoiceDesign lets you describe voices in natural language instead
of picking from a fixed catalog. Can create any character voice you can describe.
Real ElevenLabs SFX are dramatically better than synthesized.
**Weaknesses:** Slower than Kokoro (~2.5x realtime vs ~5x). Peak memory 8.5 GB.

### Method 3: All-ElevenLabs — `method3_all_eleven.wav` (241.2s, 11.3 MB)

**Everything via ElevenLabs API — professional TTS + AI-generated SFX.**

| Component | Tool | Details |
|---|---|---|
| TTS | **ElevenLabs TTS API** | Professional premade voices: George (narrator), Harry (Kael), Jessica (Lyra) |
| Music | **"RPG Ambient 4 (The Dark Woods)"** by Hitctrl | Library track with ducking (Music API is separate) |
| SFX | **ElevenLabs SFX API** | AI-generated from text prompts: "steel sword clashing, sharp metallic ring" |
| Assembly | Python (numpy/scipy) | Same mixing pipeline |

**Strengths:** Highest quality TTS — professional voice actors. Real AI-generated SFX.
**Weaknesses:** Requires network + API key. Ongoing cost (though cached = one-time).

### Method 4: Groq DM brain — `method4_groq_dm.wav` (83.0s, 3.9 MB)

**The full app pipeline: AI generates the scene, then local TTS + music + SFX.**

| Component | Tool | Details |
|---|---|---|
| Scene generation | **Groq compound model** (API) | AI writes a NEW scene with narrator + 2 characters + SFX markers |
| TTS | **Kokoro-82M** (local) | 3 voices assigned to the AI-generated characters (Thrain + Elian) |
| Music | **"RPG Ambient 4 (The Dark Woods)"** by Hitctrl | Same library track with ducking |
| SFX | **ElevenLabs SFX API** | 4 AI-generated SFX: howling wind, arcane burst, clashing steel, rumbling stone |
| Assembly | Python (numpy/scipy) | Same mixing pipeline |

**The AI-generated scene** (`method4_groq_scene.txt`): Thrain (veteran warrior) and
Elian (mage) explore a dungeon, break a seal, fight skeletal warriors, and face a
stone golem. 4 SFX moments.

**Strengths:** This is the actual product concept — AI DM generates the story, TTS
narrates it, music + SFX enhance it. Shows the full end-to-end pipeline working.
**Weaknesses:** Scene is shorter (Groq generated ~130 words vs my ~400 word scene).

## What to listen for

1. **Voice differentiation:** Do the narrator, Kael/Thrain, and Lyra/Elian sound
   distinctly different? Which method has the best character voice separation?

2. **Music ducking:** The music should dip when the narrator speaks and swell
   during pauses. Is the ducking depth right? (Currently 65% duck, 12% base vol)

3. **SFX quality:** Methods 2-4 use real ElevenLabs-generated SFX. Method 1 uses
   synthesized SFX. Can you hear the difference? The ElevenLabs SFX should sound
   like real recordings — actual stone grinding, actual steel clashing.

4. **SFX placement:** The SFX should hit at the right moments (door opening, rocks
   falling, sword clash, magical explosion). Can you hear them clearly?

5. **Overall immersion:** Which method feels most like a real D&D narration
   experience? Which would you want to listen to for a full campaign session?

6. **Method 4 specifically:** Does the Groq-generated scene feel like something a
   DM would produce? Is this the direction for the full app?

## Comparison summary

| | Method 1 | Method 2 | Method 3 | Method 4 |
|---|---|---|---|---|
| TTS | Kokoro (local) | Qwen3 VoiceDesign (local) | ElevenLabs (API) | Kokoro (local) |
| Music | Library CC-BY | Library CC-BY | Library CC-BY | Library CC-BY |
| SFX | Synthesized | **ElevenLabs** | **ElevenLabs** | **ElevenLabs** |
| Scene | Pre-written | Pre-written | Pre-written | **AI-generated** |
| Duration | 239s | 290s | 241s | 83s |
| Cost | €0 | €0 | ~$0.50 (one-time) | €0 (+SFX API) |
| Network | None | None (SFX: small API) | Required | Groq + SFX API |
| Quality | Good | Good (better voices) | Best (professional) | Good |

## SFX generated by ElevenLabs (cached in `sfx/`)

All SFX are generated once and cached. The same SFX files can be reused across
methods and future sessions — no need to regenerate.

| SFX key | Prompt | Duration | Used in |
|---|---|---|---|
| heavy_stone_door_grinding | Heavy ancient stone door grinding open, deep rumble, dust falling, echoing in a large stone chamber | 4.0s | Methods 2, 3 |
| rocks_falling_cave_in | Large rocks falling and cave-in collapse, thunderous crash of stone, dust and debris, echoing underground | 5.0s | Methods 2, 3 |
| sword_clash_combat | Steel sword clashing against steel, sharp metallic ring, combat impact, echoing in a large stone cathedral | 3.0s | Methods 2, 3 |
| magical_explosion_energy_burst | Magical energy explosion, deep resonant boom followed by crystalline shattering, arcane power release, echoing | 4.0s | Methods 2, 3 |
| howling_wind | Howling wind | 3.0s | Method 4 |
| arcane_burst | Arcane burst | 3.0s | Method 4 |
| clashing_steel | Clashing steel | 3.0s | Method 4 |
| rumbling_stone | Rumbling stone | 3.0s | Method 4 |

## ElevenLabs voices used (Method 3)

| Role | Voice | Voice ID | Description |
|---|---|---|---|
| Narrator | George | JBFqnCBsd6RMkjVDRZzb | Warm, Captivating Storyteller (British male) |
| Kael | Harry | SOYHLrjzK2X1ezoPC6cr | Fierce Warrior (American male) |
| Lyra | Jessica | cgSgspJ2msm6clMCkdW9 | Playful, Bright, Warm (American female) |

## Script

`glm-work/produce_epic_scene.py` — run any method with:
```
.venv/bin/python produce_epic_scene.py --method 1   # all-local
.venv/bin/python produce_epic_scene.py --method 2   # hybrid (Qwen3 + ElevenLabs SFX)
.venv/bin/python produce_epic_scene.py --method 3   # all-ElevenLabs
.venv/bin/python produce_epic_scene.py --method 4   # Groq DM brain
.venv/bin/python produce_epic_scene.py --method all # run all four
```
