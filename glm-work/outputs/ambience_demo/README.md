# Ambience-under-narration demo

## v2 — REAL library tracks (the one to listen to)

Arie's feedback on v1 was that the synthesized beds "sound like white noise, not
ambience." Fair — procedural numpy synthesis can't match real composed music. v2
uses **actual royalty-free tracks** from OpenGameArt, layered under the same Kokoro
narration with side-chain ducking.

**Listen in this order:**

1. `narration_dry_reference.wav` — the Kokoro narration with NO ambience (baseline)
2. **`v2_dark_woods.wav`** — "RPG Ambient 4 (The Dark Woods)" by Hitctrl (CC-BY 3.0).
   Tense orchestral strings. **Best match for the narration content** (Mireth at the
   marsh edge, storm coming, vodnik lurking). Start here.
3. `v2_dungeon.wav` — "Loopable Dungeon Ambience" by JaggedStone (CC0). Low-frequency
   wind + water drips. Also matches the marsh/dark mood — more ambient, less musical.
4. `v2_tavern.wav` — "The Old Tower Inn" by RandomMind (CC0). Medieval tavern/inn
   theme with lute. Doesn't match the story (it's a "safe/social" scene type) but
   shows what a different scene would sound like.

**What you're hearing:**
- The narration voice plays at full volume the whole time.
- The real music/ambience track plays at ~15-22% volume underneath.
- When the narrator speaks, the music is automatically ducked (side-chain
  compression) so the voice stays intelligible.
- When the narrator pauses, the music swells back up to fill the space.
- The tracks fade in at the start and fade out at the end (no abrupt cuts).

**Track sources (all in `tracks/`):**
| File | Track | Artist | License | Duration |
|---|---|---|---|---|
| `tavern_old_tower_inn.mp3` | The Old Tower Inn | RandomMind | **CC0** (public domain) | 105.8s |
| `dark_woods.mp3` | RPG Ambient 4 (The Dark Woods) | Hitctrl | **CC-BY 3.0** (credit required) | 144.2s |
| `dungeon_ambient.ogg` | Loopable Dungeon Ambience | JaggedStone | **CC0** (public domain) | 94.3s |

All downloaded from OpenGameArt.org. Total download: ~10 MB (not a model download —
just regular audio files). These are the kind of tracks the v1 library-based
approach would use, just curated and scene-tagged.

**What to evaluate:**
- Does real music under narration add to the experience? (vs. the v1 synthesized noise)
- Is the ducking depth right? (Currently 55-60% duck at full speech, 15-22% base vol)
- Which track fits the narration best?
- Would you want the music louder or quieter relative to the voice?

**Script:** `glm-work/make_ambience_demo_v2.py` — tweak `base_vol` and `duck_depth`
per track in the `BEDS` list, then re-run. Swap in any other audio file by dropping
it in `tracks/` and adding an entry.

---

## v1 — synthesized beds (kept for reference, but Arie said these sound like noise)

`demo_tavern.wav`, `demo_forest.wav`, `demo_marsh.wav` — procedurally synthesized
with numpy/scipy. Arie's feedback: "they all sound like white noise or just
background noise, not ambience or specific story related sounds. Not feasible."
Kept for comparison but skip these — listen to the v2 files above instead.

Script: `glm-work/make_ambience_demo.py`
