# V2-07 — Interactive World View

**Status:** Planning — no implementation yet
**Priority:** Medium (creative centerpiece)
**Estimated effort:** Large
**Feedback:** Add `>` inline notes anywhere.

## Summary

An interactive visualization of the story's world that grows as the story develops. This evolves from the debug/logging system (v1.2) into a feature that readers can explore — a living map of their story's people, places, and events.

This is the creative centerpiece of v2. It transforms Narrator from "an audiobook you can steer" into "an audiobook you can steer AND explore."

## Arie's feedback

> "Perhaps we should add an extra sidebar or large (like 40% screenheight) bottombar which can show the current World Engine info, as a sort of separate debug screen or detailled info screen."
> "Give me some proposals for how to do this in the preparation for developing v2. It could be more than just a debug screen, but a sort of interactive campaign/world view, that grows as the story develops."

## Three visualization modes

### Mode A: Map View (spatial)

A stylized map showing locations the reader has visited:
- Nodes = locations (tavern, forest, dungeon, city)
- Edges = travel paths between locations
- Current location is highlighted
- Unexplored areas are dim or hidden
- Clicking a location shows: when visited, what happened there, who was present

**Visual style:** Not a literal fantasy map — a minimalist, artistic node graph. Think of it as a "story map" rather than a "world map." Locations are circles with labels, connected by lines. The aesthetic matches the book theme (sepia ink on parchment).

**Data source:** WorldStore's scene/location entities + travel history

### Mode B: Relationship Graph (social)

A force-directed graph showing characters and their relationships:
- Nodes = characters (PC, NPCs)
- Node size = importance (more appearances = larger)
- Node color = disposition (ally=green, neutral=gray, enemy=red)
- Edges = relationships ("knows", "fought", "helped", "related to")
- Clicking a character shows: description, first appearance, last appearance, current status

**Data source:** WorldStore's entity records + relationship mechanics

### Mode C: Timeline View (chronological)

A vertical timeline showing the story's events:
- Each passage is a point on the timeline
- Chapters are larger markers
- Color-coded by mood (combat=red, mystery=purple, calm=blue)
- Clicking an event shows: passage text summary, state changes, audio replay
- The timeline can be scrolled and zoomed

**Data source:** Turn records + chronicle entries

## UI integration

### Option 1: Bottom panel (40% screen height)

- Collapsible panel at the bottom of the screen
- Tabs: "Map" | "Characters" | "Timeline" | "Engine" (debug)
- Can be resized by dragging the top edge
- When collapsed, shows just a thin bar with a toggle button
- When expanded, shows the selected view in 40% of the screen height

**Pros:** Doesn't interfere with the book reading area. Can be toggled quickly.
**Cons:** Takes vertical space, which is at a premium on laptops.

### Option 2: Full-screen overlay

- A "World" button in the top bar opens a full-screen overlay
- Shows the selected view in full screen
- Close button returns to the book
- Like the current voice assignment overlay but for world exploration

**Pros:** Maximum space for visualization. Clean separation.
**Cons:** Takes the reader out of the book. Less "always available."

### Option 3: Side panel (left, wider)

- Expand the left panel to include world view tabs
- "Character" tab shows the relationship graph
- "Map" tab shows the location map
- "Timeline" tab shows the chronicle timeline
- Panel can be widened to 400-500px when in world view mode

**Pros:** Always visible alongside the story. Natural extension of existing UI.
**Cons:** Limited space. Graphs may be cramped.

### Option 4: Toggleable split view

- A "World view" button splits the screen: 60% book, 40% world view
- The world view shows on the right side (replacing or alongside settings)
- Can be toggled on/off instantly
- In mobile, becomes a full-screen overlay

**Pros:** Best of both worlds — story and world view side by side.
**Cons:** More complex to implement. May feel cluttered on small screens.

**Recommendation:** Option 1 (bottom panel) for development, with Option 4 (split view) as the final design. The bottom panel is easier to build and can evolve into the split view.

## Data requirements

The WorldStore already tracks:
- Entities (NPCs, locations, items) with descriptions and status
- Scenes (location + mood + who's present)
- Chapters (number, title, mood, scene setting)
- Turn records (action, story, changes)

What's missing:
- **Relationships between entities** — needs a new `relationships` field in WorldStore
- **Travel history** — which locations were visited in what order
- **Entity appearance count** — how many times each entity has appeared
- **Event timeline** — structured events extracted from chronicle entries

### Relationship extraction

The LLM can emit relationship tags:
```
RELATIONSHIP:NPC:Elara|NPC:Marcus|type:ally|since:chapter_3
RELATIONSHIP:PC:Lyra|NPC:Marcus|type:enemy|since:chapter_5
```

Or, simpler: the backend post-processes the story text to infer relationships based on:
- Characters mentioned together in the same passage
- Combat mechanics (ENTITY_NEW with hostile type)
- Dialogue patterns (who talks to whom)

### Travel history

Already tracked via `ENTITY_NEW:location` mechanics. The WorldStore knows which locations exist and which is current. We need to add an ordered visit log.

## Implementation plan

1. Extend WorldStore with relationships, travel history, appearance counts
2. Add relationship extraction (LLM tags or post-processing)
3. Create `/api/world` endpoint returning the full world state for visualization
4. Build the bottom panel UI with tabs
5. Implement Map View (D3.js or custom canvas)
6. Implement Relationship Graph (D3.js force-directed)
7. Implement Timeline View (custom or D3.js)
8. Add click interactions (click entity/location/event for details)
9. Connect to debug logging (v1.2) for the "Engine" tab

## Creative direction: the world view as a feature

In the commercial product, the world view is a key differentiator:
- Readers can explore their story's world between sessions
- The world view serves as a "previously on..." recap when resuming
- The world view can be shared (v1.8) — "look at the world my story created"
- The world view could eventually show AI-generated art for locations and characters

## Creative direction: "The Cartographer's Desk"

Frame the world view as an in-fiction element: the reader's character keeps a map and journal. The world view IS that map and journal. This maintains the book metaphor:
- Map View = the character's hand-drawn map
- Relationship Graph = the character's notes on people they've met
- Timeline View = the character's journal entries

This turns a technical visualization into a narrative artifact.
