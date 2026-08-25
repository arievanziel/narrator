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

   > perhaps the user choice or user free text could be narrated out loud too, by kokoro if there is no qwen3 version ready, or by qwen3 if it is already generated.
   > for pre-set choices, the naration audio could be generated already for all options, before the user makes a choice.
   > free text input by the user can be generated as soon as the user starts typing (ie. after a few words), naturally the user might change the input and then audio generation should restart. 
   > In any case, the audio generated should always be exactly the same as the written text.
   > this would give time to generate all other audio voice tracks for further narration in the background while the user choice audio is playing.
   > if time allows, always use the best quality audio, but if generation is taking too long, revert back to quicker less quality models.

2. **Voice consistency**: The current system assigns voices by gender (male/female
   default). Would you like a voice assignment screen where you can pick/customize
   voices for each character?

   > yes, please add a voice assignment screen where I can pick/customize voices for each character. Make sure the voices are consistent throughout the story. Always pre-pick a voice or create a voice description for each npc or pc, but add a dialogue for changing it manually for each character.

3. **Continuous music gap**: When scene mood changes, the background music
   restarts with a brief gap. Would you prefer a crossfade or gapless transition?

   > yes, crossfade would be great! Also the volume of all music should be normalized. Fine to have volume rise and fall slightly if it fits the mood, but it should never be too extreme.
   > also, the current volume drop when narration or npc voices start playing is quite big, this can be more subtle and should also adjust based on the volume of the voice (ie. whispering voices should have lower volume background music).
   > in the settings panel, now the volume music and other volume sliders are either not available or not working, double check all settings sliders for all types of audio and make sure they are working.

## Story

4. **Auto-roll quality**: In auto-roll mode, the DM sometimes skips the roll
   entirely and just narrates the outcome. Should I enforce stricter
   roll-first-then-outcome behavior, or is the current flow acceptable
   for an audiobook-like experience?

   > always enforce full rolls, never assume the LLM DM is fair or remebers world info. The LLM DM sets a DC first and the roll determines the random result and story direction. Never give the llm DM freedom to decide the story direction, every choice should always be deterministic and traceable.

5. **Story length**: Currently 3-6 segments per turn (~20-35s of audio). Is this
   the right length, or would you prefer shorter/longer turns?

   > seems ok for now, but depending on the scene it could be shorter or longer. Keep in mind that the goal is to always have live direct narration. So sometimes it's good to start with a quick and short segment to 'buy' time to generate audio for longer follow up segments.
   > this part will take a lot of research and playtesting, so try to differentiate for now, so we can see what works and what not.

6. **Encounter balance**: The starting encounter has 2 goblins (7 HP each). In
   testing, the player killed one in 2 turns without taking damage. Should
   enemies be tougher, or is this fine for v0?

   > NO pre-scripted or hard-coded story points or encounters. Every encounter should be dynamically generated based on the player's actions and the current state of the game.

   > the start of the game (or in later parts of the story, the start of each 'chapter') could have a longer 'introduction' narrated, to set the scene and provide context.

   > never hard-code anything about the story or plot.
   > never hard-code anything about the world or setting.
   > never hard-code anything about the characters or NPCs.

## Technical

7. **Anthropic credits**: Your Anthropic account has insufficient credits. The Claude
   provider code is ready but untested. Would you like to add credits so I can
   test Claude as a third provider?

   > yes, i will add credits, but try it anyway and keep the api included in the app.

8. **Deployment**: The app runs on localhost. Would you ever want to access it
   from other devices on your network (phone, tablet)? This would need network
   binding and possibly authentication.

   > yes, but for now localhost is fine.

## GUI

9. **Mobile**: The GUI is designed for desktop. Would you like mobile support
   (responsive layout, touch controls)?

   > yes, but for now desktop is fine.

10. **Opening wizard**: The intro screen asks for basic style input. Would you
    like a more elaborate opening wizard (like the foreword of a book) with
    more options and guidance?

    > yes, i would like it to be more elaborate and guided. Also the questions should be written out like the normal gui. So the result is a written AND narrated 'introduction' chapter to the 'book'.
    > all should be live generated and lively asking for user input, like a real person would do.
    > imagine it like a session 0, a written out conversation from the DM with the player. The DM asks questions, the player answers, and the DM writes it all down. The goal of the DM is to create a world/campaign/story that is the best experience and the most fun for the player as possible.
