# Narrator GUI — structured feedback

**Mockup:** `glm-work/notes/gui_mockup.html` (open via the browser preview or
`python3 -m http.server 8776` in the `notes/` folder)

**How to use this file:** each section describes one part of the mockup and
asks specific questions. Write your feedback on `>` lines (your convention).
Leave a section blank if you have no opinion on it. Be brutal — wrong guesses
are cheaper to fix now than after code exists.

**After you fill this in:** I'll revise the mockup based on your notes, then
we can iterate again or move toward a real implementation.

---

## A. Overall layout

Current: 440px phone-width column, 4 bottom tabs (Story / Voices / Sessions /
Settings), dark theme, sticky audio player at top of Story tab.

You said "may have a simpler layout." Questions:

1. Are 4 tabs too many? If fewer, which merge or drop?
   (e.g. fold Sessions into Settings? fold Voices into Story?)

2. Is the phone-width column right for Mac testing, or would you rather see a
   wider desktop layout now and worry about phone later?

3. Dark theme — keep, or would you prefer light / a toggle?

4. Anything visually cluttered that should go?

>

>

>

>

---

## B. Story tab — narration display

Current: narration appears in cards per turn, color-coded — NARRATOR (gold
left border), characters (red speaker tag), emotion cues like `(whispering)`
and `[a long beat of silence]` in italic dim text. Turn dividers say
"— TURN N —".

1. Is the per-turn card structure right, or should it read as one continuous
   scroll (like a chat log / book page)?

2. Speaker labels (NARRATOR / MIRETH / THE STRANGER) — useful, or noise once
   you can hear the voice difference?

3. Emotion cues visible in text — helpful for editing, or distracting during
   play?

4. Turn dividers — keep, or let it flow?

>

>

>

>

---

## C. Story tab — streaming player

Current: sticky bar at top of Story tab, play/pause button, "STREAMING" badge
with pulsing green dot, animated scrubber, time display. Simulates playback
advancing.

1. Does "STREAMING" as the default state communicate "audio plays as it
   generates, not generate-then-wait"? Or is the badge unclear?

2. Should the player show what's currently being voiced (e.g. highlight the
   narration card that's playing, word-by-word or sentence-by-sentence)?

3. Is sticky-at-top right, or should the player be a mini-bar at the very
   bottom (above the tab bar / choice panel)?

4. Any controls missing? (seek, skip-turn, replay-turn, volume)

>

>

>

>

---

## D. Story tab — choice panel + text input

Current: "What does Mireth do next?" → 3 multiple-choice buttons (A/B/C) +
a free-text input row at the bottom. Picking a choice or submitting text
triggers a "Generating turn 5…" toast.

**Note:** I've added an interaction simulation to the mockup — picking a
choice or typing now appends a new narration card and scrolls to it, so you
can test the chat flow. Try it.

1. Multiple-choice + free-text both always visible — right, or should free
   text be behind a "type your own" toggle to reduce clutter?

2. Three choices — too few, too many, or right?

3. Should choices show likely consequences / tone hints, or stay bare?

4. After submitting, should the choice panel collapse / hide until the next
   turn is ready, or stay visible?

5. The generating toast — enough feedback, or do you want a fuller
   "story AI thinking → TTS generating → streaming" progress breakdown?

>

>

>

>

>

---

## E. Voices tab

Current: per-character cards, each showing one voice method — Narrator
(preset dropdown), Mireth (natural-language description field), The Stranger
(reference-audio clone with file path). Method pills color-coded. "Add
character" button. "Sound bed" section for ambient layer.

1. Per-character voice assignment — right granularity, or should there be a
   global default voice with per-character overrides only when needed?

2. Three voice methods shown (preset / designed / clone) — for the final app
   you said presets + sound generators are enough. Should the mockup reflect
   that (hide description + clone), or keep them visible since we're still
   testing?

3. The natural-language description field — is a free-text box the right
   input, or would a few sliders (pitch / warmth / pace / roughness) be more
   usable?

4. Sound bed / ambient layer — is this where "sound generators" should live,
   or a separate concept?

>

>

>

>

---

## F. Sessions tab

Current: list of saved sessions (title, date, turn count, audio length),
play/export/more buttons per row. Export options: stitched MP3, per-turn
WAVs zip, private relisten link. "No account or upload required" note.

1. Is this enough for "store audio to relisten or manually send," or do you
   need more (e.g. search, tags, folders, session notes)?

2. Export options — which would you actually use? (The "private link" one
   implies a server; the other two are pure local files.)

3. Should sessions be grouped (by campaign / one-shot / date), or is a flat
   list fine for now?

>

>

>

---

## G. Settings tab

Current: Story AI model picker, choice style, TTS engine picker (with "Auto
— pick per character" option), playback speed, pause handling, storage
location.

1. Is anything here that should be in the main flow instead of buried in
   settings? (e.g. TTS engine choice might be per-session, not global)

2. Anything missing? (API keys, language, content warnings, model download
   management, offline mode)

3. "Auto — pick per character (mixed)" as a TTS option — useful, or too
   clever / confusing?

>

>

>

---

## H. What's missing entirely

Things not in the mockup that you expect in the eventual app:

>

>

>

---

## I. Interaction simulation (new)

I added a basic simulation: picking a choice or typing appends a new
narration card and auto-scrolls to it, with a fake generating delay. The
player scrubber advances. This lets you feel the chat flow.

1. Does the flow feel right? (submit → generating → new narration appears →
   scroll to it → audio plays)

2. Should new narration appear all at once, or stream in word-by-word as the
   story AI generates (typewriter effect)?

3. Should it auto-scroll, or notify you and let you scroll manually?

4. Anything about the flow that feels wrong?

>

>

>

>

---

## J. Priority for next iteration

If I revise the mockup, what should I focus on? (pick top 2-3)

- [ ] Simpler layout (fewer tabs / less clutter)
- [ ] Rework the player (position, controls, now-playing highlight)
- [ ] Rework the choice panel (collapse behavior, # of choices, free-text toggle)
- [ ] Simplify voices tab (hide testing-only methods)
- [ ] Add something missing (specify in section H)
- [ ] Word-by-word narration streaming / typewriter effect
- [ ] Other:

>
