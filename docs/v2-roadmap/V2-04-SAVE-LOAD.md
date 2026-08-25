# V2-04 — Save/Load & Multi-Book Library

**Status:** Planning — no implementation yet
**Priority:** High — readers need to keep their stories
**Estimated effort:** Medium
**Feedback:** Add `>` inline notes anywhere.

## Summary

Overhaul the save/load system from a single opaque save slot to a proper multi-book library. Readers should be able to have multiple stories, see their metadata, resume any of them, and manage their library.

## Issues from v1 feedback

- "Place bookmark" and "Resume reading" are unclear
- No way to load a previous book
- After refresh, there's no "resume" button on the intro screen
- Save metadata is invisible

## Design

### Library architecture

```
saves/
  library.json              — index of all saved stories
  story_{game_id}/
    state.json              — full game state
    world_store.json        — WorldStore snapshot
    session.json            — session metadata (model, settings, turn count)
    chapters.json           — chapter list
    chronicle.json          — chronicle entries
    history.json            — LLM conversation history
    metadata.json           — title, author (reader), created, last_played, cover_mood
    audio/
      turn_001_seg_0.wav    — generated audio (optional, can be cleaned up)
      ...
```

### library.json structure

```json
{
  "stories": [
    {
      "id": "g1692887200",
      "title": "The Sunken Archive",
      "character_name": "Lyra",
      "chapter": 5,
      "passage": 23,
      "created": "2026-08-24T10:00:00Z",
      "last_played": "2026-08-24T14:30:00Z",
      "mood": "mystery",
      "model": "gemini-3.5-flash-lite",
      "cover_color": "#2a4a6a"
    }
  ]
}
```

### Library UI

**On the intro screen:**
- "Read the foreword" (new story, conversational setup)
- "Open the book with defaults" (new story, procedural quick start)
- "Continue reading" (if there's a most-recent save) — shows story title and chapter
- "My library" (opens the full library browser)

**Library browser (modal or full-screen):**
- Grid of story cards, each showing:
  - Title (generated, dynamic)
  - Character name
  - Chapter number / passage count
  - Last played time
  - Cover color derived from story mood
  - Click to resume
  - Long-press or menu button to: rename, delete, export, share

**In Settings panel:**
- "Save story" (manual save, shows timestamp)
- "New story" (starts fresh)
- "My library" (opens library browser)
- Auto-save indicator: "Auto-saved at [time]"

### Auto-save

- Auto-save after every turn (or every N turns)
- Auto-save is silent — no notification unless debug mode is on
- The most recent auto-save is what "Continue reading" loads
- Manual save creates a named checkpoint

### Save/load API

New endpoints:
- `GET /api/library` — list all saved stories
- `POST /api/library/save` — save current story (with optional name)
- `POST /api/library/load` — load a specific story by ID
- `DELETE /api/library/{id}` — delete a saved story
- `PATCH /api/library/{id}` — rename a story
- `GET /api/library/{id}/metadata` — get story metadata

### Migration from v1

- On first v2 launch, check for existing v1 save
- Import it into the new library format
- Show a one-time "Your story has been added to your library" message

### Save metadata display

In the Settings panel, show:
```
Current story: The Sunken Archive
Chapter 5 · Passage 23
Last saved: 2 minutes ago
Character: Lyra
Model: Gemini Flash
```

### Creative direction: story covers

Each story gets a "cover" — a visual representation derived from:
- The story's primary mood (color palette)
- The genre (typography)
- The character name and title

This makes the library feel like a bookshelf. Covers can be:
- Simple: mood-derived color + title text
- Rich: AI-generated cover art (v1.8 commercial feature)

### Creative direction: story summaries

Each story in the library shows a one-paragraph summary that updates as the story progresses. The LLM generates this summary at chapter boundaries:
- "Lyra, a rogue from the slums, discovers a hidden archive beneath the city that threatens to rewrite history..."
- This summary is stored in metadata and updated every few chapters

## Implementation plan

1. Create `narrator_v01/library.py` — manages the saves directory and library index
2. Refactor `handle_save()` and `handle_load()` in `game_loop.py` to use the library system
3. Add library API endpoints to `app.py`
4. Add library browser UI to `index.html` and `app.js`
5. Add "Continue reading" to intro screen
6. Add auto-save logic to turn processing
7. Add story summary generation at chapter boundaries
