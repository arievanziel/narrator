# Pipeline Design Reference — from TTS-Story and multivoice

**Researched:** 2026-08-17 by GLM-5.2 High
**Sources:**
- https://github.com/wcharliebrown/multivoice (novel-to-audiobook on Qwen3-TTS)
- https://github.com/xerophayze/tts-story (web-based multi-voice TTS studio)

These are reference implementations for the "input engineering + post-processing"
fix that Arie's Kokoro feedback identified. Per Sonnet's instruction, I'm reading
their approaches before building anything custom. **Do not build a Kokoro pipeline
improvement yet** — wait until Qwen3-TTS is tested, as it may make the question moot.

## multivoice (wcharliebrown) — key patterns

### Emotion/delivery cue parsing
The project has a comprehensive `EMOTION_MAPPINGS` dict that maps stage directions
to TTS instruction text. Examples directly relevant to our test scripts:
- `"whispering": "Speak in a soft, hushed whisper."` — our test script 2 has `(whispering)`
- `"quietly": "Speak softly and quietly."`
- `"urgently": "Speak with urgency and importance."`
- ~100+ emotion/delivery mappings covering loudness, positive/negative emotions,
  fear, sadness, surprise, delivery style, pace, etc.

These are combined with the character's voice description and passed as the
`instruct` parameter to Qwen3-TTS VoiceDesign.

### Pause handling
- `[beat]` → 0.7s silence inserted
- `[long beat]` → 1.5s silence inserted
- Multi-sentence lines automatically split, 0.3s pause between sentences
  (configurable via `SENTENCE_PAUSE_SECONDS`)

This directly addresses Arie's feedback about Kokoro's pause timing.

### Audio post-processing
- RMS loudness normalization
- Noise floor removal
- End padding
- **Direction-aware volume scaling**: shouting lines are louder, whispering lines
  are softer
- **High-pass filtering for whisper directions**: removes low-frequency rumble to
  make whispers sound more intimate

### Quality scoring
- Uses UTMOSv2 (predicts MOS 1-5) to score each generated line
- If first take scores < 3.5, regenerate (up to 5 takes)
- Keep highest-scoring take
- Per-chapter stats file with MOS scores

### Voice assignment
- Characters with reference WAV samples → Qwen3-TTS Base model (voice cloning)
- Characters without samples → Qwen3-TTS VoiceDesign (text description → voice)
- Voice descriptions stored in `voice_config.json`

### Performance (Apple M1 MPS)
- ~25 seconds per line (1 take)
- ~40-60 seconds per line (with retakes)

## TTS-Story (Xerophayze) — key patterns

### Speaker tagging
- `[narrator]...[/narrator]` — narrator voice
- `[alice-female]...[/alice-female]` — named character with gender
- Per-speaker pitch/speed control
- Pause markers and silence controls

### Backend abstraction
- Supports Kokoro, Chatterbox, Qwen3-TTS as swappable backends
- Web-based UI for editing/tagging

## How this applies to Narrator

For the eventual narration pipeline (post-Phase-1), the key takeaways are:

1. **Emotion cue parsing**: parse `(whispering)`, `(shouting)`, etc. from the
   pasted Claude narration and convert to TTS instructions. multivoice's
   `EMOTION_MAPPINGS` dict is a ready-to-use reference.

2. **Pause control**: use `[beat]`/`[long beat]` tags + automatic sentence pauses.
   For Kokoro (which doesn't support instruct-based control), insert actual
   silence between generated chunks. For Qwen3-TTS, use the instruct parameter
   for pacing control.

3. **Voice assignment per segment**: split narration into narrator vs dialogue
   segments, assign a voice to each. For VoiceDesign, describe each character's
   voice in natural language. For Kokoro, pick from the 54 presets.

4. **Audio post-processing**: RMS normalization, direction-aware volume scaling,
   high-pass filtering for whispers. This addresses the "voice transitions sound
   abrupt" issue Arie flagged.

5. **Quality scoring (future)**: UTMOSv2 can score generated audio and trigger
   regeneration of low-quality takes. Not needed for Phase 1 but worth noting.

6. **Don't build this yet**: per Sonnet's instruction, test Qwen3-TTS first.
   If it sounds significantly better out of the box, the Kokoro pipeline
   improvement question may become moot.
