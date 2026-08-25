# V2-09 — Voice & Narration Quality

**Status:** Planning — no implementation yet
**Priority:** Medium-High (core product quality)
**Estimated effort:** Medium-Large
**Feedback:** Add `>` inline notes anywhere.

## Summary

Elevate the narration from "functional TTS" to "a pleasure to listen to." This subversion focuses on voice quality, character voice consistency, narrator personality, and the listening experience.

## Current state

- Kokoro TTS: faithful, fast (~0.18 RTF), good baseline quality
- Qwen3 VoiceDesign: more expressive, may paraphrase, slower (~0.55 RTF)
- Per-character voice assignment exists but is basic
- Background music works well with mood-based selection
- No ambient sound effects yet (planned in v1.3)

## Goals

1. Every character sounds distinct and consistent across the entire story
2. The narrator's voice matches the story's tone
3. Audio quality is good enough that someone would choose to listen rather than read
4. The narration has natural pacing — pauses, emphasis, emotional inflection

## Features

### 1. Character voice consistency

**Problem:** Currently, character voices are assigned but may not be consistent across sessions or may not sound distinct enough.

**Solution:**
- When a new NPC is introduced (ENTITY_NEW), the system assigns a voice profile
- Voice profiles include: pitch, speed, style, accent, gender, age range
- The voice profile is stored in WorldStore as part of the entity record
- When the character speaks in a later passage, the same voice profile is used
- The voice assignment screen (already exists) lets the reader customize voices

**Voice profile structure:**
```json
{
  "entity_id": "npc_elara",
  "voice_name": "Elara",
  "voice_description": "A wise old woman with a gentle voice",
  "tts_voice_id": "kokoro_voice_07",
  "pitch": -2,
  "speed": 0.95,
  "style": "warm"
}
```

**Automatic voice assignment:**
- When the LLM introduces a new NPC, it also suggests a voice description
- The system maps the description to the closest available TTS voice
- The reader can override in the voice assignment screen

### 2. Narrator voice personality

**The narrator is a character too.** The narrator's voice should reflect:
- The story's genre (mystery = measured, thoughtful; adventure = energetic; horror = ominous)
- The reader's preference (set in Session Zero or Settings)
- The current scene's mood (calm passages = slower, combat = faster)

**Narrator voice presets:**
- "The Warm Storyteller" — gentle, inviting, like a grandparent telling a bedtime story
- "The Mysterious Guide" — measured, slightly hushed, with dramatic pauses
- "The Dramatic Bard" — theatrical, varied, emphasizes emotion and action
- "The Calm Companion" — steady, reassuring, like a friend reading to you
- "The Omniscient Voice" — neutral, authoritative, like a documentary narrator

**Implementation:**
- Each preset maps to TTS parameters (pitch, speed, style) and a system prompt addition
- The narrator's voice is different from character voices (lower pitch, more measured)
- The narrator's voice stays consistent throughout the story

### 3. Emotional inflection

**The TTS should reflect the emotional content of the text.**

**Approach A: SSML markup**
- The backend adds SSML (Speech Synthesis Markup Language) tags to the text
- `<prosody rate="slow" pitch="low">` for ominous passages
- `<emphasis>` for key words
- `<break time="1s">` for dramatic pauses
- Kokoro and Qwen3 may or may not support SSML — needs research

**Approach B: Prompt-based direction**
- For Qwen3 (which can follow voice directions), prepend emotional cues
- "[whispering]", "[excited]", "[ominous]", "[calm]"
- The TTS model interprets these as style directions

**Approach C: Post-processing**
- After TTS generation, apply audio effects:
  - Slight reverb for large spaces (cathedrals, caves)
  - Compression for intimate scenes
  - EQ shifts for different moods
- This is model-agnostic but less precise

**Recommendation:** Approach B for Qwen3, Approach C as a fallback for Kokoro.

### 4. Natural pacing

**Pauses:**
- The narrator pauses briefly between paragraphs
- Longer pauses between chapters
- A brief pause before dialogue (the narrator "sets up" the speaker)
- Pauses after dramatic moments for effect

**Implementation:**
- Insert silence between segments (already happens naturally)
- Add explicit pause segments: `{"kind": "pause", "duration": 1.5}`
- The audio queue handles these by inserting silence

**Pacing by mood:**
- Combat: faster narration, shorter pauses
- Mystery: slower narration, longer pauses
- Dialogue: natural conversation pacing
- Description: measured, with pauses at sentence boundaries

### 5. Multi-voice dialogue

When two characters have a conversation:
- Each character's dialogue uses their assigned voice
- The narrator's voice handles the narration between dialogue lines
- Smooth transitions between voices (brief fade or crossfade)

**Implementation:**
- The segment parser already identifies speakers
- Each segment is generated with the appropriate voice
- The audio queue plays them in sequence
- Brief crossfades between different-voice segments

### 6. Audio quality enhancement

**Normalization:**
- All segments are loudness-normalized (already done)
- Character voices should be at the same perceived loudness
- Background music should duck under narration (sidechain compression)

**Noise reduction:**
- Some TTS engines produce slight artifacts
- Apply light noise reduction or gating
- Ensure clean silence between segments

**Format:**
- Generate at 24kHz (good quality, reasonable file size)
- Export at 44.1kHz or 48kHz for audiobook standards
- Mono for narration (stereo for music)

### 7. Voice cloning (future, v3)

For the ultimate personalization:
- The reader could record a 30-second sample of their own voice
- The narrator uses the reader's voice
- This requires a voice cloning service (ElevenLabs, Coqui, or custom)
- This is a v3 feature but the architecture should support it

### 8. Narrator as audio book narrator

**The ultimate goal:** The narration should be indistinguishable from a professional audiobook narrator.

This means:
- Consistent voice throughout
- Character voices that are distinct but not cartoonish
- Emotional range that matches the story
- Natural pacing with appropriate pauses
- Clear, pleasant audio quality

This is the standard to measure against. Every audio improvement should ask: "Would this sound good in an Audible audiobook?"

## Implementation plan

1. Store voice profiles in WorldStore entity records
2. Auto-assign voices when NPCs are introduced
3. Add narrator voice presets to Settings
4. Add emotional inflection (prompt-based for Qwen3, post-processing for Kokoro)
5. Add pause segments between paragraphs and chapters
6. Implement multi-voice dialogue with smooth transitions
7. Enhance audio normalization and music ducking
8. Research SSML support in Kokoro and Qwen3
9. Prepare architecture for voice cloning (v3)
