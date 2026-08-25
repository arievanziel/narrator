# Narrator V1 — Playtest Feedback

**Date:** 2026-08-24
**Server:** http://localhost:5199
**Build:** v1.0 (backend book layer + Book GUI + UX fixes)

## How to playtest

1. Open http://localhost:5199/ in your browser
2. You'll see a book cover with "Read the foreword" or "Open the book"
3. "Read the foreword" = Session Zero (conversation with the Narrator to set up your story)
4. "Open the book" = Quick Start (pick style/setting/name and jump in)

## What's new in v1

### Book experience
- The UI is now a book, not a D&D character sheet
> great!
- Intro screen is a book cover with "Read the foreword" / "Open the book"
> the left side panel opens automatically at the start of chapter one, this is not needed. Always keep the gui as minimal as possible, unless there is a specific user instruction to open panels or make background information visible.
- Top bar shows: book title (left), chapter name (center), controls (right)
> the book title is now hard coded as "[name]'s tale" but should be generated, it's fine to start the story as it is now, but after each chapter the title should be updated to reflect the current 'full book title'. Just like each chapter gets a live generated name.
- Story feed renders as book pages: chapter headings in small caps, scene-setting with drop caps, justified narration, indented dialogue
> perfect!
- No roman-numeral turn marks
> perfect, but there should be a setting to turn them back on if the user wants to see them
- Left panel: "Your character", "Carried", "Belongings", "The story so far" (chapter TOC)
> perfect! it updates nicely and reflects the story correctly as far as i have tested it.
- Save/Load = "Place bookmark" / "Resume reading"
> interesting take on save/load, but in the settings panel it can have meta information, so no need to have in 'book style'.
> Also it is totally unclear to me now what "Place bookmark" and "Resume reading" actually do. How and where is it saved? How can i load a previous book?
- New game = "New book"
> i would prefer a "New story" button instead of "New book"

### Storyteller's notes toggle
- In Settings, there's a "Show storyteller's notes" toggle
> perfect, but it should work in the whole gui, now when it's 'off' i still see: 
> "Storyteller’s notes
> Roll requested: 1d20 for Perception DC 12
> [Guard: response regenerated due to a consistency violation]"
> and also dice rolls are shown on the main screen/page.
- OFF (default): hides all D&D mechanics (dice, AC, HP numbers, roll results, raw engine logs)
> perfect!
- ON: shows everything like the old game UI
> perfect!
- This is the single switch between "book mode" and "game mode"
> perfect!
> we should also add an extra switch for now to 'show logs' in the gui, so that we can see the logs in the gui when we are in 'book mode' or 'game mode', what i would like to see is inline notes about what is happening in the background technically. like notes about which ai is used and for what, which model, which provider, etc. in what order decisions are made programmatically, which audio is used for each text, how the text is generated, which pre-generation is used. It should reflect any programmatic actions that are happening in the background.
> the main goal for this setting is to be able to see what is happening in the background technically, so that we can debug and understand what is happening exactly while playtesting.
> even if the setting is off, the logs should still be made and saved somewhere.

### Audio
- Narration is generated as you play (segment-by-segment streaming)
> nice! it mostly works smoothly, but we will need some trouble shooting for later versions, but we first need to add full debug logging so we can see what is happening in the background.
- Chapter openings speak the scene-setting paragraph first, then the story
> yes very nice.
- Per-chapter ambience: mood is derived from the scene and drives background music
> very nice and good choices so far (with only a few tests), both for the ambience choice and where a chapter ends/starts.
- Audio progress bar is now display-only (seeking was broken for multi-segment passages)
> good
- Play/pause and replay still work
> good
> perhaps a small improvement would be to add a replay button next to each paragraph to restart narration from that point in the text.

> user actions should also be narrated, but rephrased by the narrator as part of the ongoing story.
> now only the free text input is narrated, and directly live as soon as it's typed. This is a great method and approach for 'pre-generating' the audio, but it should only be played once the user has finished typing and send the free text input.

### UX fixes applied
1. Dice roller: d20 results are now sent as `manual_roll` when auto-roll is off (only visible in storyteller mode)
> they are still always visible, needs to be fixed
2. Seek bar: removed (was broken for multi-segment — now a progress indicator only)
> ok
3. Session Zero model dropdown: locks after first exchange (changing it mid-conversation did nothing)
> model changes should always be possible, but only take effect after a user input is send.
4. Free-text TTS: now polls for status and plays back when ready (shows "voicing..." indicator)
> good
5. Narration volume: verified — slider persists across segments
> good

## What to test

### First impressions
- [ ] Does it feel like a book, not a game?
> yes
- [ ] Is the foreword/intro pleasant to read?
> yes, works very nicely now
- [ ] Do chapter openings feel like turning a page?
> yes, perfection!

### Core flow
- [ ] Start a new book via "Read the foreword" (Session Zero)
> works!
- [ ] Start a new book via "Open the book" (Quick Start)
> yes, but seems to be hard-coded still, it should just fully generate a new story with new characters and a new style, all 'settings' or 'campaign' details should be auto-generated.
- [ ] Play 5+ passages and verify the story flows
> works!
- [ ] Verify chapter headings appear when the location changes
> works! and good choice for using location changes as chapter changes.
- [ ] Verify the scene-setting paragraph is spoken (audio on)
> works!

### Audio
- [ ] Turn on audio (Settings → TTS engine → kokoro)
> works
- [ ] Verify narration plays segment-by-segment
> works
- [ ] Verify the chapter opening speaks the scene-setting first
> ok
- [ ] Verify background music changes with mood
> ok
- [ ] Verify the progress bar moves but is not clickable
> ok
- [ ] Verify play/pause and replay work
> ok > but add little buttons to restart playback at each paragraph

### Storyteller mode
- [ ] Toggle "Show storyteller's notes" in Settings
> works partially
- [ ] Verify dice roller appears/disappears
> not tested yet
- [ ] Verify AC/ability scores appear/disappear
> works
- [ ] Verify roll results appear/disappear
> works partially, needs further checking
- [ ] Verify raw mechanics logs appear/disappear
> always visible, should disappear in 'book mode' 

### Panels
- [ ] Open left panel — verify "Your character", "Carried", "Belongings"
> works
- [ ] Verify "The story so far" shows chapter list
> perfect, nice scrollable list
- [ ] Click a chapter in the TOC — does it scroll to that chapter?
> yes, works very nicely!
- [ ] Verify chronicle entries use "passage" not "Turn"
> yes, but in the bottom bar it's still called 'turn' > change it everywhere to 'passage'.

### Save/Load
- [ ] "Place bookmark" — verify it saves
> seems to work, hard to really check
- [ ] Refresh the page
> works
- [ ] "Resume reading" — verify it restores
> after refresh there is no 'resume reading' button, the start screen doesn't have the side panels visible.

### Edge cases
- [ ] What happens if you play very fast on free tier? (429 rate limits)
> no problems so far, but seems hard to test
- [ ] Does the model dropdown lock after the first Session Zero exchange?
> no, and it shouldn't. A model change should not be an issue because the campgaign state and all world details are saved programmatically. After every user input a model change should take effect.
- [ ] Does the free-text "voicing..." indicator appear when you type in the input?
> yes, but it should only generate as soon as the user starts/stops typing, only play the audio when the user sends the input (or presses enter)

## Known limitations (not bugs)

1. **Gemini free-tier rate limits:** If you play fast, you'll hit 15 req/min limits. The app retries 3 times with backoff. Groq models (`openai/gpt-oss-120b`) are an alternative free option.
> display this kind of info on screen in debug mode
2. **Audio generation speed:** Kokoro TTS runs at ~0.18 RTF (faster than realtime). Qwen3 is higher quality but slower (~0.55 RTF). The auto mode picks based on lead time.
> all are fine when they are faster then realtime. so far it works nicely and smoothly.
3. **No cross-segment seeking:** The progress bar is display-only for v1. This is a deliberate scope decision.
> correct, keep it like this
4. **`reader_notes` may be sparse:** The literary translation of engine logs is conservative — it drops anything that leaks engine internals rather than prettifying it.
> good.

## Feedback format

Please add your notes below using `>` prefix (your input is preserved):

> see inline

## Test results (automated)

- 93/93 unit tests pass
- All Python files compile clean
- JS syntax valid
- 35-turn soak test: 0 crashes, no state corruption, no degradation
- Playwright smoke test: 0 console errors, all 3 themes work

## Architecture summary

- **Backend:** World Engine (deterministic chapters, entities, scenes, consistency guards, DC-then-roll flow, procedural character generation)
> in debug mode, give exactly which output is stored and what is send by World Engine to the llm for each turn and in which order
> perhaps we should add an extra sidebar or large (like 40% screenheight) bottombar which can show the current World Engine info, as a sort of separate debug screen or detailled info screen.
> Give me some proposals for how to do this in the preparation for developing v2. It could be more than just a debug screen, but a sort of interactive campaign/world view, that grows as the story develops.
- **Frontend:** Book GUI (LEXICON layer, storyteller mode gating, chapter rendering, TOC, drop caps)
> works very very nicely now.
> i'm not sure about the drop caps, but fine for now.
- **Audio:** Segment queue with background generation, per-chapter ambience, Kokoro/Qwen3 TTS
- **API:** HTTP server with REST endpoints for turns, chapters, state, audio, save/load
