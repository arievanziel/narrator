# Questions for Arie — v0.1 Build

**Date:** 2026-08-21
**From:** GLM (Instance A)

These are questions and decisions I need your input on. I'm continuing to work
in the meantime — these are for the next iteration (v0.2).

## Audio

1. **Qwen3 model reload overhead**: Each TTS call reloads the model (~4s). Should I
   invest time in keeping the model persistently loaded, or is the current speed
   acceptable? (Total audio gen time for 4 segments: ~15-20s)

2. **Kokoro TTS**: Kokoro is installed but not downloaded (needs HuggingFace auth).
   Should I download it as a second TTS option? It's faster but less expressive
   than Qwen3 VoiceDesign.

3. **Continuous music**: Currently music is embedded in each turn's narration audio.
   Would you prefer a separate continuous music stream that plays between turns?
   This would require a second audio player in the browser.

4. **Voice consistency**: The current system assigns voices by gender (male/female
   default). Would you like a voice assignment screen where you can pick/customize
   voices for each character?

## Story

5. **Auto-roll quality**: In auto-roll mode, the DM generates roll results. Sometimes
   it skips the roll entirely and just narrates the outcome. Should I enforce
   stricter roll-first-then-outcome behavior, or is the current flow acceptable
   for an audiobook-like experience?

6. **Story length**: Currently 4-8 segments per turn (~30s of audio). Is this the
   right length, or would you prefer shorter/longer turns?

7. **Encounter balance**: The starting encounter has 2 goblins (7 HP each). In
   testing, the player killed one in 2 turns without taking damage. Should
   enemies be tougher, or is this fine for v0?

## Technical

8. **Anthropic credits**: Your Anthropic account has insufficient credits. The Claude
   provider code is ready but untested. Would you like to add credits so I can
   test Claude as a third provider?

9. **Save/load**: Would you like save/load functionality in v0.2? (JSON file or
   SQLite database)

10. **Deployment**: The app runs on localhost. Would you ever want to access it
    from other devices on your network (phone, tablet)? This would need network
    binding and possibly authentication.

## GUI

11. **Theme**: The current theme is light/paper. Would you like a dark mode option?
    The v9 mockup had light/dark/sepia swatches but I only implemented light.

12. **Mobile**: The GUI is designed for desktop. Would you like mobile support
    (responsive layout, touch controls)?
