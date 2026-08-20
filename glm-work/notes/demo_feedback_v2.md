# Demo Feedback — v2 Demos (7, 8, 9)

Please fill in your feedback using `>` prefix on the lines below each question.
Your input will be preserved and shared with all LLMs working on this project.

## Demo 7: Mystery/Exploration (`demo7_mystery.wav`)

**Scene:** Two adventurers discover a hidden archive beneath a ruined tower. A book whispers their names.
**Pipeline:** Groq generates scene → Qwen3 narrates ALL voices → ElevenLabs SFX in gaps → Music transitions (dark_chamber → exploration → dark_chamber)

### SFX placement (no voice overlap)

> perfect, very nice. sometimes quite loud, but no issue.

### Music transitions (does the music change feel natural?)

> very nice, good quality; some volume changes are very abrupt

### Narrator vs character music volume (is dialogue nearly dry?)

> good, but sometimes there are weird short high volume music bursts in between narrator and character voice changes.

### Qwen3 narrator voice (mystery/hushed vibe)

> not really nice for long narrations, but very good quality for this

### Qwen3 character voices (scholar + rogue, active not reading)

> very very nice, i'm impressed

### Overall immersion

> very good

---

## Demo 8: Combat/Action (`demo8_combat.wav`)

**Scene:** Two adventurers ambushed in an alley, fight their way out.
**Pipeline:** Groq generates scene → Qwen3 narrates ALL voices → ElevenLabs SFX in gaps → Music transitions (battle_march → battle_theme → battle_march)

### SFX placement (no voice overlap)

> perfection.

### Music transitions (tension → full combat → aftermath)

> very good, but again sometimes high volume peaks inbetween voice changes

### Qwen3 character voices (fighter shouting + ranger calling warnings)

> very good, impressive.

### Combat energy (does it feel fast and desperate?)

> yes, impressive.

### Overall immersion

> the female narrator voice is terrible for these kind of scenes. good quality, but bad choice for voice design.
> the male narrator voice is better, but still, the narration should be improved.
> overall i'm very impressed and it's really going in the right direction!

---

## Demo 9: Emotional/Dramatic (`demo9_emotional.wav`)

**Scene:** A cleric sacrifices herself to hold a magical barrier so her companion can escape.
**Pipeline:** Groq generates scene → Qwen3 narrates ALL voices → ElevenLabs SFX in gaps → Emotional piano/cello music throughout

### SFX placement (no voice overlap)

> very good, but some sfx is not the best fit for the description and sometimes the volume is very much out of place for the type of scene or emotion.
> some sfx, like the heartbeat, is amazing.
> some sfx is just weird and unfitting.
> the rain sound is waaaay too loud and short. some sounds like that are more fitting for background sounds instead of short effects.

### Music (emotional piano/cello — appropriate for the scene?)

> very very nice, but again sometimes high volume peaks between voice changes. background music should be normalized to a pretty stable volume.

### Qwen3 character voices (paladin breaking with grief + cleric calm/accepting)

> incredible. emotional and dramatic.

### Emotional impact (does the scene move you?)

> yes, well done.

### Overall immersion

> great!

---

## General questions

### Qwen3 for ALL voices (vs Kokoro for characters) — which do you prefer?

> qwen3 for all is great, but we have to keep an eye/ear for drifting voices in the long run. Perhaps research mittigation strategies or test other models?

### Music diversity (5 new tracks from OpenGameArt — noticeable improvement?)

> very good, incredible improvement.

### Live-generated music (would you like to hear MusicGen in a future demo?)

> yes, please! but already the library tracks are very good and well fitting.

### What should I focus on next?

> improve the overall audio blend, double check for weird volume spikes and make sure the final blend is normalized. 
