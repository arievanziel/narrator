# V2-03 — Audio Improvements

**Status:** Planning — no implementation yet
**Priority:** High — audio is the core product
**Estimated effort:** Medium
**Feedback:** Add `>` inline notes anywhere.

## Summary

Audio is what makes Narrator an audiobook, not just a text story. This subversion addresses all audio-related feedback from v1 and adds new capabilities.

## Issues from v1 feedback

### 1. Per-paragraph replay buttons

**Request:** Add a small replay button next to each paragraph to restart narration from that point.

**Design:**
- Each story segment (`div.story-passage`) gets a small "replay" icon button on hover
- Clicking it plays that segment's audio from the beginning
- If the segment's audio isn't generated yet (e.g., it's an older segment that was cleaned up), it regenerates on demand
- The main audio player switches to this segment and plays it

**Implementation:**
- The segment audio files already exist at `/audio/segments/{turn_id}/seg_{index}.wav`
- Each `div.story-passage` needs a `data-turn-id` and `data-seg-index` attribute
- A new `replaySegment(turnId, segIndex)` function in app.js
- CSS: `.story-passage:hover .seg-replay-btn { opacity: 0.6; }`

### 2. User actions narrated as part of the story

**Request:** User actions should be narrated — rephrased by the narrator as part of the ongoing story. Currently only free-text input is narrated, and it plays live as the user types.

**Design:**
- When the user sends an action (free text or choice), it should NOT be narrated as-is
- Instead, the narrator's next response should incorporate the action naturally
- The LLM already receives the user's action as input and responds to it — the issue is that the user's action text appears as a separate "dialogue" block in the story
- In book mode, the user's action should be woven into the narrator's prose, not shown as a separate block
- In storyteller mode, the raw action can still be shown

**Two approaches:**

**A. Hide user action, let narrator weave it (simpler)**
- In book mode, don't render the player action block at all
- The narrator's response already reflects what the player did
- The reader sees only the narrator's prose, which naturally includes "You decide to..." or "Choosing the left path, you..."

**B. Render user action as italicized "steering" text (more book-like)**
- Show the user's action as a short italic line, like a stage direction
- e.g., *"You choose to examine the ancient tome."*
- Then the narrator's response follows
- This gives the reader a sense of agency and sees their input acknowledged

**Recommendation:** Option B — it preserves the reader's sense of agency while keeping the book feel. The action is rendered as a brief italic line, not as dialogue.

### 3. Free-text audio timing fix

**Request:** Free-text TTS should only generate when the user stops typing, and only play when the user sends the input.

**Design:**
- Remove `oninput` listener from the input field
- When the user sends (clicks Send or presses Enter):
  1. Generate free-text TTS for the user's action
  2. Show "voicing..." indicator
  3. When ready, play the user's action audio
  4. Then play the narrator's response audio (which has been generating in parallel)
- If the narrator's response audio is ready before the user's action audio, queue it to play after
- This creates a natural flow: user speaks → narrator responds

**Implementation:**
- In `sendAction()`: after sending the action, call `generateFreetext(action)` and wait for it
- The narrator response audio generation happens in parallel (already does)
- Playback order: user action audio → narrator response audio

### 4. Audio debugging

**Request:** Full debug logging for audio (covered in v1.2, but specific audio needs):
- Which TTS engine was selected for each segment and why
- Generation time vs. audio duration (RTF)
- Queue state transitions
- When audio was played vs. when it was ready
- Any audio errors (generation failures, file not found, playback errors)

## New audio features for v2

### 5. Ambient sound effects

Beyond background music, add occasional ambient sound effects:
- Door creaking when entering a new location
- Sword clashing during combat
- Fire crackling in a tavern
- Wind howling in mountains

**Design:**
- The LLM can emit `[SFX:door_creak]` tags in the story
- The audio engine maps these to a sound effect library
- Sound effects play at the appropriate moment in the narration
- Volume mixed appropriately with background music

**Sound effect sources:**
- Free libraries: freesound.org, Pixabay sounds
- Procedural generation for sounds not in the library
- The mood derivation system already classifies scenes — extend it to suggest SFX

### 6. Narrator voice personality

**Request:** The narrator should have a configurable voice personality.

**Design:**
- In the foreword (Session Zero), the narrator's personality is established
- Or: a setting in the Settings panel with presets: "Warm storyteller", "Mysterious guide", "Dramatic bard", "Calm companion"
- The personality affects:
  - TTS voice selection (pitch, speed, style)
  - The system prompt's voice instructions
  - Background music style

### 7. Audio export

**Request (from v1.8 commercial):** Export the story as an audio file.

**Design:**
- "Export audio" button in Settings
- Merges all segment audio files into a single audiobook file (MP3/M4B)
- Includes chapter markers
- Includes background music mixed in
- This is a v1.8 feature but the audio architecture should support it from v1.3

### 8. Audio quality settings

**Design:**
- Quality presets: "Fast" (Kokoro, lower quality), "Balanced" (auto), "Expressive" (Qwen3)
- Sample rate options
- The "auto" mode should be smarter — consider segment length, available lead time, and current queue depth

## Implementation order

1. Free-text timing fix (highest priority from feedback)
2. User action narration (core experience)
3. Per-paragraph replay buttons
4. Audio debugging (connects to v1.2)
5. Ambient SFX (new feature)
6. Narrator voice personality
7. Audio export architecture (prepare for v1.8)
