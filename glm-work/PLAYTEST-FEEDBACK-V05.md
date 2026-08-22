# Playtest & Feedback — v0.5c (2026-08-22)

**For:** Arie
**From:** GLM Instance A (Rules & World Engine)
**App version:** v0.5c + v0.4a (audio streaming)
**Server:** http://localhost:5102

This file is for you to playtest the latest version and write your feedback.
Lines starting with `>` are reserved for your input — I won't modify them.

---

## How to start

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v01.app --port 5102
```

Then open http://localhost:5102 in your browser.

---

## What's new since you last tested

### 1. Procedural opening — no more hardcoded goblins

The app no longer starts with the same two goblins every time. The LLM now
generates a unique opening location, NPCs, and situation based on your
story style and setting choices. Each game should feel different.

**Try it:** Start a new game with different settings (e.g. "dark fantasy"
vs "classic fantasy") and see if the opening feels unique.

### 2. Audio segment queue — live streaming

Audio now generates in segments and starts playing as soon as the first
segment is ready, while later segments continue generating in the
background. This should make narration feel faster and more responsive.

**Try it:** Start a game and notice that audio starts playing before the
full narration is generated. The progress bar shows which segments are
ready vs generating.

### 3. Pre-generated choice audio

When you see choices after a turn, the audio for those choices is being
pre-generated in the background. When you click a choice, its audio should
be ready almost immediately.

### 4. Free-text audio (debounced)

When you type a custom action, the app starts generating TTS for what
you're typing after a short debounce. If you keep typing, it cancels and
restarts. This is experimental — let me know if it feels natural or
distracting.

### 5. File restructuring (invisible to you)

The app's code has been split into separate files (HTTP server, game loop,
world store, audio queue, etc.) to allow multiple developers/instances to
work simultaneously. This shouldn't affect your experience, but if anything
feels different or broken, please note it.

---

## What to test

### Basic flow
- [ ] Intro screen works (name, style, setting, persona, atmosphere, dice mode)
- [ ] Game starts with a unique opening (not the same goblins every time)
- [ ] Story text displays correctly
- [ ] Audio plays (segment by segment, not all at once)
- [ ] Choices appear and are clickable
- [ ] Free-text input works
- [ ] Save/load works

### Settings
- [ ] Model switching works (Gemini, Groq, Claude if credits available)
- [ ] TTS engine switching (Kokoro vs Qwen3)
- [ ] Theme switching (light, dark, sepia — all should look distinct)
- [ ] Music toggle and volume
- [ ] Auto-roll toggle
- [ ] Budget tracker shows spending

### Rules lawyer (should be visible in the mechanics log)
- [ ] HP changes show in the log
- [ ] Enemy deaths require a roll (rejected without one)
- [ ] Invalid item use is rejected
- [ ] Rejected actions show [REJECTED — ...] in the story feed

### Audio quality
- [ ] Narration audio matches the displayed text exactly
- [ ] Background music plays and ducks during narration
- [ ] No audio crashes or silent turns

---

## Known limitations (not bugs)

1. **World Engine not fully wired in** — the entity store, context
   assembler, and consistency guards exist and pass all tests, but aren't
   connected to the live turn flow yet. The app still uses the simpler
   flat-state system. This means:
   - Entity dedup (recognizing the same NPC by different names) isn't active
   - The context assembler (smarter memory) isn't active
   - The presence guard (catching dead NPCs speaking) isn't active

2. **DC-then-roll not in live flow** — the two-call dice flow exists but
   isn't wired into the app yet. Dice rolls still work the old way.

3. **Claude/Anthropic** — the integration is in place but may fail if your
   Anthropic account has insufficient credits. This is an API issue, not
   a bug. The app will fall back to a free provider if the budget is
   exhausted.

4. **Session Zero wizard** — exists in the code but Instance C hasn't
   built the full UI yet. The intro form is still the way to start a game.

5. **Long sessions (30+ turns)** — haven't been stress-tested yet. The app
   is about to change substantially, so this is deferred.

---

## Your feedback

> (Write your feedback here. Lines starting with > are yours — I won't touch them.)

> Procedural opening:

> Audio segment queue:

> Pre-generated choice audio:

> Free-text audio:

> Rules lawyer visibility:

> Anything else:
