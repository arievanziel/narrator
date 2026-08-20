# Audio Production Research — Audiobook Music + Qwen3 Drifting + Music Sources

## 1. Audiobook Music Best Practices (researched 2026-08-18)

Sources: Lex Blog (scoring AI audiobooks), Audiodrome, Bensound, SonusGearFlow

### Key findings

1. **Music should be SPARSE, not constant.** "Music is present for well under half the runtime. A cue enters for a beat, a confrontation, a vision, a departure, makes its point and leaves." (Lex)

2. **Music sits ~20dB under narration.** "At these levels the score works the way film scores work: you feel it more than you hear it." (Lex)

3. **Ambience can loop, music should NOT.** "Looping a melody under twelve consecutive paragraphs is the fastest way to send a listener back to the plain version. Ambience can loop, since wind and river are texture rather than melody, but each musical moment gets its own track. Leitmotif, not playlist." (Lex)

4. **Intimate dialogue plays DRY (no music).** "Intimate dialogue usually plays completely dry, because music under a scene like that tells the listener how to feel about words that are already doing the job." (Lex)

5. **SFX come in louder, then get out.** "One-shot effects come in a touch louder, then get out of the way." (Lex)

6. **Sidechain compression uses a combined key bus.** "If you have multiple speakers, create a Dialogue Key bus that receives all voice tracks and use that bus as the sidechain input." (SonusGearFlow)

7. **Music marks transitions, not constant bed.** "Use music to highlight transitions between chapters or significant plot twists." (Bensound)

### Application to our D&D narration app

- **Narrator sections:** music at ~20dB below (very quiet, ~10-15% volume)
- **Character dialogue:** music OFF or even quieter (dry for intimate moments, very low for action)
- **Scene transitions:** music swells briefly during pauses, then drops back
- **SFX:** play in gaps between speech, NOT overlapping with voice
- **Ambience:** can loop continuously at very low volume
- **Music:** play once per scene, don't loop the same melody endlessly

This directly addresses Arie's question: YES, it is common practice to have different music levels for narrator vs dialogue. Intimate dialogue often has NO music at all.

## 2. Qwen3-TTS Voice Drifting Prevention (researched 2026-08-18)

Sources: QwenLM/Qwen3-TTS GitHub, QwenCloud docs, W&B fine-tuning article, gabriele-mastrapasqua/qwen3-tts

### Key findings

1. **Voice cloning IS supported.** The Base model (Qwen3-TTS-12Hz-1.7B-Base) supports 3-second rapid voice clone from user audio input. You provide `ref_audio` + `ref_text` and it clones the voice.

2. **Drifting cause:** "Zero-shot models have no state between inference calls: each one re-estimates the speaker from the reference clip, and those estimates accumulate small variations that compound over many utterances." (W&B article)

3. **Solution 1 — Voice cloning (ICL mode):** Provide a reference audio sample (10-20 seconds, 24kHz WAV, clean) + its transcript. The model uses this as a voice prompt. This is more stable than VoiceDesign because it has an actual audio reference, not just a text description.

4. **Solution 2 — Fine-tuning:** Bake the speaker into the model weights. Most stable but requires training data and compute (~45 min on Colab T4).

5. **Known bug:** Voice-clone ICL mode may echo the tail of the reference audio before the requested text (1-2 seconds of leakage). This is a known issue.

6. **Our model (qwen3_voicedesign_8bit):** This is the VoiceDesign variant, not the Base model. VoiceDesign uses text descriptions, not reference audio. To use voice cloning, we'd need the Base model.

7. **mlx-audio implementation:** The `instruct` parameter we're using is VoiceDesign. For voice cloning, we'd need to use `voice_clone_prompt` or similar parameter with reference audio.

### Application to our app

- **For narrator:** VoiceDesign works well but drifts. To prevent drifting, we could:
  a. Generate a reference audio sample once (using VoiceDesign), then use it as a voice clone reference for subsequent generations
  b. Or switch to the Base model for voice cloning
  c. Or keep VoiceDesign but generate shorter segments (less room to drift per segment)

- **For characters:** If Qwen3 is fast enough (~2.5x realtime), use it for ALL voices with VoiceDesign. The voice descriptions can include scene-appropriate delivery style ("speaking while running," "whispering in a dungeon," etc.)

- **Recommended approach:** Generate a 15-20 second reference sample per character using VoiceDesign, save it, then use voice cloning with that reference for consistency. This needs testing with the Base model.

## 3. Diverse Music Sources (researched 2026-08-18)

### New sources to download

| Source | Tracks | License | Cost | Scene types |
|---|---|---|---|---|
| Ivan Duch - Dragon Tales 1 | 30+ min | Royalty-free | Free/name-your-price | tavern, dungeon, temple, epic, mysterious |
| Tom Feldmann - Wild Music Pack (free) | 7 | CC-BY-4.0 | Free | plains, snow, desert, forest, battle, ambience |
| Chris "Torone" CB - Dark Fantasy loops | 4 | CC-BY 4.0 | Free/name-your-price | exploration, combat, story |
| Gautam Srikishan - Chasing Dragons Vol. I | ~10 | CC-BY-4.0 | Free/name-your-price | tabletop gaming, atmospheric, loopable |
| Tabletop Audio | 500+ | CC-BY-NC-ND 4.0 | Free/Patreon | every D&D scene type |

### Already downloaded

| File | Source | License | Scene type |
|---|---|---|---|
| tavern_old_tower_inn.mp3 | OpenGameArt (RandomMind) | CC0 | tavern/inn |
| dark_woods.mp3 | OpenGameArt (Hitctrl) | CC-BY 3.0 | dark forest/tense |
| dungeon_ambient.ogg | OpenGameArt (JaggedStone) | CC0 | dungeon/cave ambience |

### Live-generated music options

1. **ElevenLabs Music API** — ~$0.15/min, up to 5 min. Need to check if available on free tier.
2. **MusicGen Small (local)** — ~1.2GB download, CC-BY-NC weights, ~1.3x realtime on M4 Max (slower on M1)
3. **Replicate-hosted MusicGen** — ~$0.10/run, no download needed
4. **Google Lyria** — $0.04/generation (30s clip), need paid Gemini plan

**Recommendation:** Try ElevenLabs Music API first (we already have the key). If not available on free tier, flag MusicGen download to Arie.
