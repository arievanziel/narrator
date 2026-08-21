# Questions for Arie — v0.2 Build

**Date:** 2026-08-21
**From:** GLM (Instance A)

These are questions and decisions I need your input on. I'm continuing to work
in the meantime — these are for the next iteration (v0.3).

## Audio

1. **TTS engine preference**: Both Qwen3 and Kokoro are now available.
   - Qwen3 VoiceDesign: more expressive, RTF 0.58, supports voice descriptions
   - Kokoro: faster (RTF 0.17 after warmup), simpler voice selection
   Which do you prefer as the default? Should I add an "automatic" mode that
   picks based on text length (Kokoro for short, Qwen3 for long)?

2. **Voice consistency**: The current system assigns voices by gender (male/female
   default). Would you like a voice assignment screen where you can pick/customize
   voices for each character?

3. **Continuous music gap**: When scene mood changes, the background music
   restarts with a brief gap. Would you prefer a crossfade or gapless transition?

## Story

4. **Auto-roll quality**: In auto-roll mode, the DM sometimes skips the roll
   entirely and just narrates the outcome. Should I enforce stricter
   roll-first-then-outcome behavior, or is the current flow acceptable
   for an audiobook-like experience?

5. **Story length**: Currently 3-6 segments per turn (~20-35s of audio). Is this
   the right length, or would you prefer shorter/longer turns?

6. **Encounter balance**: The starting encounter has 2 goblins (7 HP each). In
   testing, the player killed one in 2 turns without taking damage. Should
   enemies be tougher, or is this fine for v0?

## Technical

7. **Anthropic credits**: Your Anthropic account has insufficient credits. The Claude
   provider code is ready but untested. Would you like to add credits so I can
   test Claude as a third provider?

8. **Deployment**: The app runs on localhost. Would you ever want to access it
   from other devices on your network (phone, tablet)? This would need network
   binding and possibly authentication.

## GUI

9. **Mobile**: The GUI is designed for desktop. Would you like mobile support
   (responsive layout, touch controls)?

10. **Opening wizard**: The intro screen asks for basic style input. Would you
    like a more elaborate opening wizard (like the foreword of a book) with
    more options and guidance?
