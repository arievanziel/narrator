# Human Feedback Log — ALL LLMs MUST READ THIS

This file records feedback from Arie (the human user) about the D&D narration app.
**All LLMs working on this project MUST read this file before starting work.**
**Never overwrite or delete lines starting with `>` — those are Arie's direct input.**

## How to use this file

- LLMs add feedback here as plain text (no `>` prefix) with a date and context
- Arie can add direct reactions using `>` prefix lines
- When a new feedback item is added, LLMs should check it against their current work

---

## Audio Production Feedback (2026-08-18)

### SFX placement — CRITICAL FIX NEEDED

> the sfx in all demos is taking over the voice sounds, so for each sfx sound, you should carefully consider where to put it, strip any silence before and after the sample, but pause any narration or voice sounds shortly while playing sfx. Unless there is a very specific reason to overlap voices and sfx, i think it's almost always better to keep the sounds separate.

**Action required:**
- Strip silence from beginning and end of every SFX sample
- When placing SFX, PAUSE the narration/voice track (insert silence) for the duration of the SFX
- Do NOT overlap SFX with voice unless there's a specific dramatic reason
- SFX should play in the gaps between speech segments, not on top of them

### Music diversity — NEEDS IMPROVEMENT

> i'd like to hear more diverse sources of music, now all demo's use the same library music. Also live generated music would be cool for special scenes.

> music vibes are nicely different. But i'd like to hear more diverse sources of music, now all demo's use the same library music. Also live generated music would be cool for special scenes.

**Action required:**
- Use multiple different music sources (not just the same 3 OpenGameArt tracks)
- Include at least one live-generated music segment (MusicGen or similar)
- Music should change when scene changes (crossfade between tracks)

### Music during narrator vs character speech — RESEARCH NEEDED

> Perhaps, but i do not know if this is common practice in audiobooks, perhaps you can research it shortly, we could have different backbround music when the narrator is speaking vs when characters are talking (or just lower the volume when characters are speaking, for more dramatic effect).

**Action required:**
- Research audiobook/podcast music practices for narrator vs dialogue
- Test: lower music volume during character dialogue vs narrator text
- Test: different music tracks for narrator vs character sections

### TTS voice feedback

> The narrator voice from qwen3 is very good and expressive, but might drift over time, we should find a way to prevent too much drifting.

> For character voices, kokoro is nice and stable, but some voices are really unfit for some scenes, they are mostly 'reading text out loud' voices and not 'i'm speaking while running in a dungeon' or 'active converstation' voices. So if we can run everything fast enough on qwen3, it is preferrable. Does qwen3 have a way to prevent drifting by recording a generic sample and using it as input, next to the voicedesign?

**Action required:**
- Research Qwen3 voice drifting prevention (audio prompt, voice cloning, reference audio)
- Test Qwen3 for character voices (not just narrator) — if fast enough, prefer Qwen3 for all voices
- Kokoro voices are too "reading text out loud" — need more active/dramatic character voices

### SFX sources — NEEDS DIVERSITY

> All sfx from elevenlabs sound great, make sure to keep any generated samples and document them carefully for future reuse. allthough i'd like more different sources as well. Perhaps tabletop audio or similar libraries could be used?

**Action required:**
- Keep all ElevenLabs SFX cached and documented (already doing this in outputs/epic_scene/sfx/)
- Add SFX from other sources: Tabletop Audio, Sonniss GDC bundles, Freesound CC0
- Document all SFX with source, license, prompt, and reuse metadata

### Human feedback preservation — GENERAL RULE

> Finally make sure to always remember to record any feedback or input i give, store it in a way that other llm can access all human feedback later again, to prevent double work from my side. Keep this as a general rule or memory in devin.

> If you need feedback from a human, including from me, always prepare a easy to fill in feedback file in md format with > pointers for my input or reaction on specific things.

**Action required (ALWAYS):**
- Record ALL human feedback in this file (glm-work/notes/HUMAN-FEEDBACK.md)
- When asking for feedback, prepare a markdown file with `>` pointers for easy input
- Never make Arie repeat feedback that was already given
- All LLMs must read this file before starting work

---

## DM Brain Feedback (2026-08-18, from dm_test_results_summary.md updates)

Arie updated the DM test results with:
- Groq/compound is best overall DM (best combat tracking, damage to both sides)
- GPT-OSS 120B is best value (3x fewer tokens, perfect format + trickster score)
- Added Cerebras, SambaNova, Google API keys to .env
- Added trickster test results (cheat resistance)
- All viable models (27B+) resisted direct cheating

---

## Previous Feedback (from earlier sessions)

### V1 ambience demo (synthesized beds)
> they all sound like white noise or just background noise, not ambience or specific story related sounds. Not feasible.

**Resolved:** Switched to real library tracks in v2 demo.

### V2 ambience demo (real library tracks)
> v2 demo files are really nice, obviously the tavern is not matching the scene, but the idea is great.

**Resolved:** Tavern track was for comparison, not scene matching. Concept approved.

### Epic scene demos (methods 1-4)
> incredible, can you generate two more examples with method 4. use kokoro for character voices and qwen for narrator voices. make dramatic scenes with very different vibes and feels.

**Resolved:** Generated horror and heroic scenes with Qwen3 narrator + Kokoro characters.

### Method 4 variants (horror + heroic)
Feedback is in the sections above (SFX overlap, music diversity, voice drifting, etc.)

### v2 Demos (7, 8, 9) — feedback received 2026-08-19

> SFX placement: perfect, very nice. sometimes quite loud, but no issue.
> Music transitions: very nice, good quality; some volume changes are very abrupt
> Narrator vs character volume: good, but sometimes there are weird short high volume music bursts in between narrator and character voice changes.
> Qwen3 narrator voice (mystery): not really nice for long narrations, but very good quality for this
> Qwen3 character voices: very very nice, i'm impressed
> Combat SFX: perfection.
> Combat narrator: the female narrator voice is terrible for these kind of scenes. good quality, but bad choice for voice design. the male narrator voice is better, but still, the narration should be improved.
> Emotional SFX: some sfx is not the best fit. some sfx, like the heartbeat, is amazing. some sfx is just weird and unfitting. the rain sound is waaaay too loud and short. some sounds like that are more fitting for background sounds instead of short effects.
> Music normalization: background music should be normalized to a pretty stable volume.
> Qwen3 for all: qwen3 for all is great, but we have to keep an eye/ear for drifting voices in the long run. Perhaps research mitigation strategies or test other models?
> Music diversity: very good, incredible improvement.
> MusicGen: yes, please! but already the library tracks are very good and well fitting.
> Next focus: improve the overall audio blend, double check for weird volume spikes and make sure the final blend is normalized.

**Key issues to fix:**
1. VOLUME SPIKES between narrator/character transitions — biggest issue, needs envelope smoothing fix
2. Music normalization — background music should be stable volume
3. Combat narrator voice — use male voice, not female (af_heart)
4. SFX volume — some too loud, need per-SFX volume control
5. Background ambience vs one-shot SFX — rain/wind should be long background, not 3-second SFX
6. Use MusicGen for at least one demo

### v3 Demos (10, 11, 12) — feedback received 2026-08-19

> Volume stability: yes, perfect now (tavern), yes all gone (journey), mostly works but still spikes at SFX/voice transitions (boss)
> Tavern ambience: some weird windy noise that seems not correct, but tavern sounds are fine
> Tavern narrator: bit weird accent, seems shouting all the time. sometimes narrator and bard voice swap. seems like multiple voices for narrator.
> Boss narrator: works nicely, but start of sentences sometimes very dramatic/shouting. Qwen3 narrator voices often sound shouty instead of dramatic.
> Boss MusicGen: nice music, but perhaps not the best fit for the scene. Slow dramatic music gives 'dramatic theater play' feeling not epic battle speed and fury.
> Boss spikes: around 1:50-1:60 and 2:13 weird sound spike, probably SFX+voice combination
> Journey: incredible, impressive, scenic and peaceful. one weird sfx like eagle cry.
> Journey music: stops very suddenly before end. Always fade out/in music unless hard stop needed for dramatic effect.
> Journey narrator: sometimes character voice and narrator voice blend into each other.
> Volume spike fix: mostly works but still spikes at SFX/voice transitions. First investigate the cause, then implement fixes. Prevention over fixing.
> Music normalization: very very good now without being flat and boring.
> MusicGen vs library: both nice, most important is right fit for scene.
> Background ambience: mostly good, but avoid white noise/ruis sounds. Only use actual environmental sounds that fit the scene. Tavern white noise doesn't work if not clear enough to understand.
> Next focus: double check all demos for weird spikes, research causes first, prevention over fixing.
> General: really like diversity of all demos, shows incredible versatility of live generation.

**Key issues for v4:**
1. INVESTIGATE volume spike causes at SFX/voice transitions (don't just smooth — find root cause)
2. Qwen3 narrator too shouty — use calmer voice descriptions, avoid "booming/powerful" for narrator
3. Narrator/character voice blending — need more distinct voice descriptions
4. Music must always fade out/in — no sudden stops
5. Background ambience must be recognizable sounds, not white noise
6. MusicGen music needs better prompt matching to scene energy
7. Some SFX are weird/unfitting — need better SFX prompts or selection
