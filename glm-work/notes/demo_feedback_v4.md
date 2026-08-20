# Demo Feedback — v4 Demos (13, 14, 15) + Interactive Demo

Please fill in your feedback using `>` prefix on the lines below each question.
Your input will be preserved and shared with all LLMs working on this project.

## Demo 13: Forest Mystery (`demo13_forest.wav`)

**Scene:** Tracker + druid follow strange markings on ancient trees, discover a hidden grove with glowing flowers.
**Pipeline:** Groq → Qwen3 ALL voices (calmer narrator) → ElevenLabs SFX with fade in/out → Forest ambience → Dark woods music
**Fixes:** SFX fade in/out (150ms), music ducking during SFX, calmer narrator voice, limiter

### Volume spike fix (SFX fade in/out — better?)

> seems to be working well now, all good.

### SFX transitions (fade in/out — smoother now?)

> very smooth, good sfx

### Calmer narrator voice (less shouty than v3?)

> perfect, narrator is much better now, only sometimes a change in voice tone or type of voice.
> at the start of the scene, the first word is hard to hear, because the narrator voice start so directly that you are not aware that the scene already started. perhaps the music and background sound should start directly, but the narator voice should wait a bit before starting.

### Background forest ambience (recognizable? no white noise?)

> very recognizable, good ambience. no white noise, and very nice combination of music and forest ambiance with bird sounds and such.

### Qwen3 character voices (tracker + druid)

> very good.

### Overall immersion

> very immersive, good job. 
> although from about 2:38there is some artifacts at the end of the recording spoken out loud that are meta texts.

---

## Demo 14: City Chase (`demo14_chase.wav`)

**Scene:** Rogue + acrobat chased across rooftops through a medieval city at night.
**Pipeline:** Groq → Qwen3 ALL voices (fast but NOT shouty narrator) → ElevenLabs SFX → Battle march music
**Fixes:** SFX fade in/out, music ducking during SFX, fast-but-controlled narrator

### Volume spike fix (SFX fade in/out — better?)

> nice, no more volume spikes.

### Fast narrator voice (urgent but not shouty?)

> nice, dramatic and fast, but not shouty. The narrator voice seems to switch between different voices, could it be that there are multiple voices in the narration? Or is it just drifting?

### Qwen3 character voices (rogue whispering + acrobat exhilarated)

> nice, good voices. acrobat is very dramatic, but that fits the character.
> some character lines are mixed with narrator lines, which is a bit confusing because they are sometimes narrated in the character voice.
> we need to look into the scripting of the recording and how each part is generated, is the whole piece generated as one whole recording with different voices, or are the different parts generated separately and then combined?
> we should really record/generate narrator text in one go and then mix it with separate recordings/generations for character voices.

### Chase energy (fast and thrilling?)

> very good, but not too much drama and shouting, still clear and easy to follow. but also thrilling and showing a nice energy overall.

### Overall immersion

> very good, immersive and thrilling.

---

## Demo 15: Campfire Rest (`demo15_campfire.wav`)

**Scene:** Fighter + wizard rest by a campfire. He shares a story about his brother's death. A quiet laugh. The fire dies.
**Pipeline:** Groq (qwen3.6-27b) → Qwen3 ALL voices (warm, gentle narrator) → ElevenLabs SFX → Campfire + crickets ambience → Emotional music
**Fixes:** SFX fade in/out, campfire + crickets as long background ambience, intimate narrator, music at 2% during dialogue

### Volume spike fix (SFX fade in/out — better?)

> perfect, no issues at all.

### Warm narrator voice (gentle, intimate — better for this scene?)

> very nice, a bit slow, but that's fine for this scene. very intimate, the voice is very warm and gentle. a bit leaning towards erotic at some points.

### Background ambience (campfire + crickets — recognizable?)

> very very good. not too much, not too little.

### Music during intimate dialogue (nearly silent — good?)

> very good! intimate and emotional, but there is a very sudden stop of the music near the end.
> in general backgroudn sounds and music should fade out more smoothly or be extended to the full scene duration.
> perhaps first generate all spoken lines, both character voices and narrator voice, then check the total length of the audio and then generate the music and background sounds to match the full duration.
> in general, if music/background sounds are longer than the spoken audio, it's not really a problem because they can just fade in and out at the beginning and end.
> in the real implementation, we will probably keep music running throughout the whole story, also when a user makes choices and there is no narration, so it will be more smooth.

### Qwen3 character voices (fighter vulnerable + wizard reflective)

> some character lines are mixed with narrator lines, which is a bit confusing because they are sometimes narrated in the narrator voice. while it should be a spoken out loud sentence by a character.
> same issue as demo14.

### Emotional impact

> perfect, good dialogue, good music, good ambience, good narrator voice.

---

## Interactive Demo (`interactive_audio_demo.py`)

**What it is:** A terminal-based interactive D&D story. You type choices, Groq generates each scene turn, Qwen3 generates TTS live, SFX are assembled from cached clips, music is selected by mood.

**To run:** `.venv/bin/python interactive_audio_demo.py`

### Live TTS speed (acceptable wait time per turn?)

> 

### Music mood matching (does the music fit each scene?)

> 

### SFX selection (do the SFX fit the generated scenes?)

> 

### Story responsiveness (do your choices feel impactful?)

> 

### Voice consistency across turns (does the narrator stay consistent?)

> 

### Overall experience

> 

---

## General questions

### Volume spike root cause fix (fade in/out + music ducking + limiter — improvement?)

> 

### SFX fade in/out (150ms — natural or too slow?)

> 

### Music always fading out (no sudden stops — fixed?)

> 

### What should I focus on next?

> 
