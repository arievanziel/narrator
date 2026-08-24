# Narrator v0 — Full App Plan

**Maintained by:** Sonnet, alongside `docs/PROJECT-ROADMAP.md`. This doc is the
architecture + build plan for the first real version of the app: AI DM + programmatic
rules lawyer + audio narration with SFX + user input every turn.

---

## Scope philosophy (Arie, 2026-08-20 — important, simplifies a lot)

> I think i mainly want the app to stay simple, like an audiobook with some user choices
> for the main character, but in the base version all DM activity, like dice rolling and
> character management, should be handled by the app itself. It should be visible to the
> user though, so they can see what's happening. But for the start it's about narration
> and user choices, the DM engine and all world building and stat tracking is only to
> support that in the background. Later we could maybe develop a more full game
> experience, but that's not the focus right now.
>
> the final app should have a sort of opening wizard that guides the user through the
> setup process. Like the introduction or foreword to a book.

**This changes v0's target shape:** it's an audiobook-with-choices experience first, a
game second. Concretely:
- Dice rolling, HP tracking, inventory management: **fully automatic, app-driven** — the
  rules lawyer handles it silently. The player never rolls dice or manages a sheet.
- **But visible, not hidden:** the state (HP, inventory, turn log) should be shown
  somewhere (the v9 GUI's topbar + side panel already does roughly this) so the player
  can see what the DM engine is doing, even though they don't interact with it directly.
- Player's actual interaction surface: narration + occasional meaningful choices for
  their character (matches the `[SUGGESTIONS]` section already in the DM response format
  — this was already the right shape, just confirms it).
- **Onboarding wizard** — a guided setup flow (like a book's foreword) instead of a
  settings panel the player has to figure out alone. Not yet designed; follows from the
  campaign-config work once the GUI settles.
- A deeper interactive RPG experience (manual dice, detailed character sheets, etc.) is
  explicitly a **later phase**, not v0/v0.1. Don't build toward that now.

## v0 architecture (based on what's already been proven out)

```
┌─────────────────────────────────────────────────────────────────┐
│  Player types an action                                          │
└───────────────────────────┬───────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  DM BRAIN (LLM) — narrates + proposes state changes only          │
│  Model: GPT-OSS 120B via Groq free tier (tested, works)           │
│  Output format: [NARRATIVE] [MECHANICS] [SUGGESTIONS] [CHRONICLE] │
└───────────────────────────┬───────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  RULES LAWYER (deterministic Python, not an LLM)                  │
│  - Parses [MECHANICS] tags                                        │
│  - Validates against authoritative game state (HP, inventory,     │
│    enemies, conditions) — rejects anything not grounded in state  │
│  - This is what catches cheating/hallucination — proven in the    │
│    10-scenario "trickster" adversarial test                       │
│  - Applies only validated changes; state is the source of truth   │
└───────────────────────────┬───────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  NARRATION PIPELINE                                                │
│  - narrator_parser.py splits [NARRATIVE] into narrator/dialogue   │
│    segments, detects emotion cues, pause markers                  │
│  - TTS: Kokoro (fast) or Qwen3-TTS VoiceDesign (better voices) —   │
│    both tested and scored; assign one voice per tracked character │
│  - Ambient audio: library-based music/SFX layered under narration │
│    (proven in the 4-method demo; ElevenLabs SFX optional upgrade, │
│    not required — see cost decision below)                        │
└───────────────────────────┬───────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Player hears the turn, sees [SUGGESTIONS], types next action     │
└─────────────────────────────────────────────────────────────────┘
```

**Why this is the right shape:** it's not a new idea — it's exactly what GLM's testing
this week already validated piece by piece. The "SoloQuest pattern" (LLM narrates, code
adjudicates) is what makes this work with a cheap/free model instead of needing a
frontier API for every turn, and it's what makes the rules lawyer a real component
instead of "ask the LLM to be careful and hope."

## Open decisions before building v0 for real

1. **ElevenLabs SFX — keep as optional upgrade or cut for strict no-paid-API v0?**
   Library-based SFX (Method 1, fully local/free) already works and was the research's
   own recommendation. ElevenLabs SFX (Methods 2-4) sound better but cost money per new
   sound and require network. Recommend: **ship v0 with library/local SFX only,
   revisit ElevenLabs as a paid "quality" tier later if Arie wants it** — but this is
   your call, not mine to decide unilaterally.
2. **DM brain: GPT-OSS 120B via Groq (tested, works) vs. wait for Claude baseline?**
   The Claude Opus/Sonnet/Fable comparison test is prepared but not run — recommend
   running it (manually, per `notes/claude_dm_test_prompt.md`) before locking in GPT-OSS
   120B, just to know what's being traded away in quality, even if the answer stays
   "GPT-OSS 120B, because it's free and good enough."
3. **Campaign config (world/character tracking, dice visibility, etc.):** my draft in
   `sonnet-work/CAMPAIGN-CONFIG-DRAFT.md` still needs your input — the system prompt/
   state schema GLM already built (`SYSTEM_PROMPT`, `GameState` in `test_api_dm.py`) is
   a good starting concrete implementation of some of this (HP, inventory, enemies,
   conditions) — worth checking it against your draft answers once you give them.
4. **Voice assignment automation:** who/what decides which TTS voice a new NPC gets —
   manual (Arie assigns), or automatic (e.g. LLM picks based on the character
   description it just wrote)? Not decided yet.

## Task split for building v0

### GLM (free, does the implementation legwork)
1. Run the Claude baseline test manually is NOT a GLM task (needs Arie) — but GLM
   should be ready to fold results into `dm_test_results_summary.md` once available.
2. **Merge the proven pieces into one coherent app**, not four separate demo scripts:
   - `test_api_dm.py`'s DM brain + state engine
   - `narrator_parser.py`'s segment parsing
   - TTS generation (Kokoro or Qwen3-TTS, per Arie's pick)
   - Library-based ambient audio from `make_ambience_demo_v2.py`
   - A basic loop: player input → DM brain → rules lawyer validates → narration
     pipeline → audio out → wait for next input
3. Wire the "trickster" adversarial tests into an ongoing regression check — run them
   against whatever model is chosen before considering the rules lawyer trustworthy.
4. Once merged, run a **real multi-turn play session** (not scripted, Arie actually
   playing) to surface UX issues the scripted tests can't catch.
5. Continue iterating on `notes/gui_feedback.md` / `notes/voice_catalog.md` once Arie
   fills in his `>` notes.

### Sonnet (me)
- Keep `PROJECT-ROADMAP.md` and this doc current as things are decided/built.
- Review the merged v0 app's state-schema and system-prompt design once GLM has a
  working draft — this is exactly the kind of "did we get the architecture right"
  check worth doing before too much code is built on top of it.
- Cost/budget tracking as usage patterns become clearer (Groq free-tier limits, any
  paid-API creep).

### Opus/Fable — recommended now, for one specific thing
**Worth a focused session once GLM's merged v0 draft exists:** have Opus (or Fable)
review the **state schema + rules-lawyer validation logic** specifically for
edge cases and exploits the trickster test didn't think of, and sanity-check the
system prompt design against real D&D 5e rules knowledge (spell slots, action economy,
conditions) — GLM is not a strong source of truth on subtle 5e rules correctness, and
this is a "get it right once, expensively, rather than debug exploits for months
cheaply" situation. Not worth doing yet — wait until there's a real merged app to
review rather than reviewing scattered scripts.

**Not recommended:** using Opus/Fable as the actual DM brain in production — GPT-OSS
120B via Groq free tier already tests well and costs ~$0-3/month; there's no quality
gap large enough yet demonstrated to justify a much more expensive model for routine
play, pending the Claude baseline comparison (open decision #2 above).
