# Narrator v0 — GUI Feedback

**Date:** 2026-08-19
**App:** `narrator_v0/app.py` (web server at http://localhost:5102)

Please fill in your feedback using `>` prefix on the lines below each question.
Your input will be preserved and shared with all LLMs working on this project.
All LLMs must read `notes/HUMAN-FEEDBACK.md` before starting work.

---

## How to access the GUI

```bash
cd glm-work && source .venv/bin/activate
python -m narrator_v0.app --model gemini-3.5-flash-lite --port 5102
```

Then open http://localhost:5102 in your browser.

---

## Layout

### Overall first impression

> 

### Sidebar (character stats, enemies, inventory, dice roller)

Is the information clear and readable?

> 

Is anything missing from the sidebar that you'd want to see?

> 

### Chat area (narrative, mechanics, suggestions, chronicle)

Is the narrative text readable (font, color, formatting)?

> 

Are the [MECHANICS] tags useful to see, or should they be hidden/collapsible?

> 

Are the [SUGGESTIONS] buttons useful? Do you click them or type your own actions?

> 

Is the [CHRONICLE] log entry useful?

> 

### Audio playback bar

Does the audio player appear in the right place?

> 

Does the "generating..." status indicator work well while waiting?

> 

Is the autoplay toggle useful, or should audio always autoplay?

> 

How long did you wait for audio on average? Was it acceptable?

> 

---

## Interaction

### Input field

Is the input field prominent enough?

> 

Should there be a "quick action" menu (e.g. attack, cast spell, search) or is free text better?

> 

### Dice roller

Is the dice roller in the sidebar useful?

> 

Does the dice result automatically appending to your input work well?

> 

Should the dice roller be in the main chat area instead of the sidebar?

> 

### New Game / Toggle Stats buttons

Are these controls in the right place?

> 

---

## State display

### HP bar

Is the HP bar (color-coded green/yellow/red) clear?

> 

### Enemy list

Is the enemy display (with dead enemies struck through) clear?

> 

Should enemy HP bars be shown too?

> 

### Inventory

Is the inventory list sufficient, or do you want item details/icons?

> 

---

## Missing features

What features are most missing from the GUI?

> 

What would make this feel like a real D&D app rather than a prototype?

> 

---

## Comparison with the GUI mockup

You previously iterated on `notes/gui_v2/` mockups. How does this live GUI compare?

> 

Should any elements from the mockups be brought into this live GUI?

> 

---

## Bugs or issues

Any bugs, layout issues, or unexpected behavior?

> 
