# Demo Feedback — v3 Demos (10, 11, 12)

Please fill in your feedback using `>` prefix on the lines below each question.
Your input will be preserved and shared with all LLMs working on this project.

## Demo 10: Tavern/Social (`demo10_tavern.wav`)

**Scene:** A bard and warrior drinking in a tavern. A mysterious stranger approaches with a map.
**Pipeline:** Groq generates scene → Qwen3 ALL voices → ElevenLabs SFX in gaps + background tavern ambience → Tavern music (stable volume)
**Fixes applied:** Smooth 2s volume transitions, normalized music, background ambience as long track, per-SFX volume

### Volume stability (are the spikes gone?)

> yes, perfect now

### Background ambience (tavern noise as continuous bed — good addition?)

> some weird windy noise that seems not correct, but tavern sounds are fine and music fits.

### SFX volume (appropriate levels?)

> perfect. 

### Qwen3 narrator voice (warm tavern storyteller)

> bit weird accent, seems shouting all the time
> sometimes the narrator and bard voice are used for the wrong line. the bard voice sometimes also is used for narration. I could check it in more detail with the exact script next to it.
> it seems like there are multiple voices for the narrator.

### Qwen3 character voices (bard theatrical + warrior dry humor)

> very very good. the bard also sounds like he is shouting sometimes, but that seems fitting, whereas with the narrator voice it seems weird.

### Overall immersion

> very good.

---

## Demo 11: Boss Battle (`demo11_boss.wav`) — WITH MUSICGEN

**Scene:** Barbarian + wizard face an ancient dragon. Epic battle with near-defeat and climactic spell.
**Pipeline:** Groq generates scene → Qwen3 ALL voices (MALE narrator for combat) → ElevenLabs SFX → **MusicGen-generated music** (dark tension → heroic victory)
**Fixes applied:** Male narrator voice, MusicGen live-generated music, per-SFX volume, smooth volume

### MusicGen music (live-generated — how does it compare to library tracks?)

> nice music, but perhaps not the best fit for the scene.

### Male narrator voice (better for combat than female?)

> this one works nicely, but the start of the sentences is sometimes very very drammatic. Some parts are really like shouting, too loud.
> it is often with qwen3 narrator voices that it sounds very shouty instead of a dramatic narrator.

### SFX volume (dragon roar, explosions — appropriate levels?)

> incredible, but some sounds are weird. volume is perfect.

### Volume stability (are the spikes gone?)

> yes, and without flattening the sound. It's still dramatic and lively.
> around 1.50-1.60 and 2:13 there is a weird sound spike. I think because of combination with sfx.

### Qwen3 character voices (barbarian roar + wizard chanting)

> nice, but a bit overly dramatic ;) but good to try out.

### Epic battle feel

> yes, but the slow dramatic music does more give a 'dramatic theater play' feeling than a epic battle with speed and fury. But good effort.

---

## Demo 12: Journey/Travel (`demo12_journey.wav`)

**Scene:** Ranger + druid cross a mountain pass at dawn. Storm building in the distance.
**Pipeline:** Groq generates scene → Qwen3 ALL voices → ElevenLabs SFX + background mountain wind → Exploration music
**Fixes applied:** Background wind ambience, per-SFX volume, smooth volume, peaceful narrator

### Background wind ambience (continuous — good for scenic scenes?)

> good and creates dramatic feeling. very nice.

### Volume stability (are the spikes gone?)

> yes, all gone.
> music stops very suddenly before the end of the scene. Make sure to always fade out and fade in music, unless a hard stop is needed for dramatic effect.

### Qwen3 narrator voice (gentle, contemplative for travel)

> nice, but sometimes the character voice and narrator voice blends into eachother. 


### Qwen3 character voices (ranger calm + druid reverent)

> very nice again, no remarks.

### Peaceful/scenic feel

> incredible. impressive. scenic and peaceful.
> one weird sfx, like an eagles cry at some point.

---

## General questions

> in general i really like the diversity of all demo's, it really shows the incredible versatility of live generation. 

### Volume spike fix (2-second smoothing — improvement from v2?)

> mostly works, but i think at some transitions between sfx and voices it still spikes sometimes, needs more improvement and checks
> perhaps first investigate the cause of the spikes and then implement fixes

### Music normalization (stable background music volume?)

> yes, very good now, without making it flat and boring, it is very very good

### MusicGen vs library music (which do you prefer? when should we use each?)

> both are very nice, most important is to find the right fit for each scene

### Background ambience (separate from one-shot SFX — good direction?)

> yes, mostly good, try to prevent white noise or ruis (NL) sounds, they are a bit distracting and do not add anything, try to only put in actual environmental sounds that fit the scene or music that fits the scene.
> the demo 12 rain and thunder sounds are fine, because they are actual environmental sounds fitting the scene, but the tavern with the white noise is not fitting the scene. I understand the idea is to have some rumbling sounds of wind or hushed talking in the background of the tavern, but it doesn't work if it's not clear enough to actually be understandable to the listener what the sound is.

### What should I focus on next?

> double check all demo's for weird spikes in sound or unexpected sounds and find ways to prevent them
> first research and then try to explain the cause and try to prevent the issues instead of fixing it afterwards. prevention should always be the aim instead of fixing it afterwards.
