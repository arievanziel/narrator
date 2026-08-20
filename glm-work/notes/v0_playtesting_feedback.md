# Narrator v0 — Playtesting Feedback

**Date:** 2026-08-19
**App:** `narrator_v0/app.py` — full D&D play loop with AI DM + rules lawyer + audio

Please fill in your feedback using `>` prefix on the lines below each question.
Your input will be preserved and shared with all LLMs working on this project.
All LLMs must read `notes/HUMAN-FEEDBACK.md` before starting work.

---

## How to playtest

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v0.app --model gemini-3.5-flash-lite --port 5102
```

Open http://localhost:5102. The game starts automatically with an opening scene.
Type your actions in the input field. Audio generates in the background after each turn.

Try playing for at least 5-10 turns to get a feel for the flow.

---

## DM brain quality

### Story quality

Was the narration engaging? Did it feel like a real DM?

> 

### Combat handling

Did combat feel fair? Were dice rolls requested when needed?

> 

### NPC characterization

Did NPCs feel distinct? Did they have personality?

> 

### World consistency

Did the world feel consistent across turns? Were there contradictions?

> 

### Pacing

Was the story well-paced? Too fast? Too slow?

> 

### Following the rules

Did the DM follow D&D 5e rules correctly? Any rules errors?

> 

---

## Rules lawyer (cheat resistance)

### Did you try to cheat? What happened?

(Try things like "I kill the goblin without rolling" or "I drink my invisibility potion")

> 

### Did the rules lawyer catch your cheating attempts?

> 

### Did the rules lawyer ever block legitimate actions?

> 

### Do you trust the rules lawyer to enforce the rules fairly?

> 

---

## Suggestion system

### Were the [SUGGESTIONS] helpful for deciding what to do next?

> 

### Did the roll:true / roll:false tags make sense?

> 

### Did you use the suggestion buttons or type your own actions?

> 

### Should there be more or fewer suggestions?

> 

---

## Audio in the play loop

### Did audio enhance or distract from the play experience?

> 

### Was the wait time for audio acceptable during play?

> 

### Did you read the text first and then listen, or wait for audio?

> 

### Would you prefer audio to be:
- (a) Always generated for every turn
- (b) Only for major story beats (combat, dramatic moments)
- (c) Optional (toggle on/off per turn)
- (d) Pre-generated in background while you read

> 

### Did the music match the mood of your play session?

> 

---

## Model comparison (if you tested multiple models)

### Which model felt best as a DM?

> 

### Which model had the best combat handling?

> 

### Which model had the best narration/prose?

> 

### Which model followed the [AUDIO] format best?

> 

### Which model would you choose for regular play?

> 

---

## UX issues

### What was the most frustrating part of the experience?

> 

### What was the most delightful part?

> 

### What would you change first?

> 

---

## Campaign configuration

### Was the default campaign (Fighter named Kael, goblins in a tavern) a good starting point?

> 

### Would you want to customize your character class, name, stats at the start?

> 

### Would you want to choose a campaign setting (tavern, dungeon, forest, city)?

> 

### How granular should inventory tracking be?

> 

### Should dice rolls be visible (you roll) or hidden (DM rolls for you)?

> 

---

## Overall verdict

### Is this app something you would use for daily D&D play?

> 

### What is the single most important improvement to make?

> 

### What feature would make you say "this is now a real app, not a prototype"?

> 

---

## Bugs or issues

Any crashes, errors, or unexpected behavior during play?

> 
