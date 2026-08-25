# V2 Roadmap — Master Plan

**Status:** Planning — no implementation yet
**Date:** 2026-08-24
**Author:** Instance A (backend/planning)
**Feedback:** Add `>` inline notes anywhere. Your input is preserved.

## Vision

Transform Narrator from a working v1 prototype into a commercially viable live-generated audiobook platform — an app where readers steer an AI narrator through procedurally generated stories, experiencing them as audiobooks with full narration, music, and a book-like reading interface.

The core insight: **Narrator is not a game. It is an audiobook you can steer.** Every design decision in v2 should serve that identity.

## What v1 proved

- The book GUI works and feels right
- The World Engine produces consistent, chapter-structured stories
- Segment-by-segment TTS streaming works
- Per-chapter ambience enhances immersion
- The foreword (Session Zero) is a pleasant onboarding
- Storyteller mode is a good concept but needs to be fully implemented
- The architecture is sound but needs debugging tools, polish, and commercial features

## What v2 must solve

From playtest feedback:
1. Storyteller mode leaks mechanics in book mode (rolls, guards, dice)
2. No debug/logging visibility — hard to understand what the engine is doing
3. Save/load is unclear — no multi-book library
4. Book title is hardcoded, not generated
5. Quick start is not fully procedural
6. Model switching is locked when it shouldn't be
7. Free-text audio plays too early (should wait for send)
8. User actions aren't narrated as part of the story
9. No per-paragraph replay
10. "Turn" appears in some places instead of "passage"

New creative directions:
11. Interactive world/campaign view that grows with the story
12. Multi-book library with save slots
13. Export to audio file (real audiobook export)
14. Voice variety and character voice consistency
15. Story branching and memory across sessions
16. Social features (share your story, explore others' stories)
17. Subscription/freemium model for commercial viability
18. Mobile-responsive design for phone/tablet listening

## Subversion plan (v1.1 through v2.0)

| Version | Focus | Document |
|---------|-------|----------|
| v1.1 | Bug fixes from playtest | [V2-01-BUGFIXES.md](V2-01-BUGFIXES.md) |
| v1.2 | Debug & logging system | [V2-02-DEBUG-LOGGING.md](V2-02-DEBUG-LOGGING.md) |
| v1.3 | Audio improvements | [V2-03-AUDIO.md](V2-03-AUDIO.md) |
| v1.4 | Save/load & multi-book library | [V2-04-SAVE-LOAD.md](V2-04-SAVE-LOAD.md) |
| v1.5 | Dynamic titles & metadata | [V2-05-METADATA.md](V2-05-METADATA.md) |
| v1.6 | Model switching & provider resilience | [V2-06-PROVIDERS.md](V2-06-PROVIDERS.md) |
| v1.7 | Interactive world view | [V2-07-WORLD-VIEW.md](V2-07-WORLD-VIEW.md) |
| v1.8 | Commercial features | [V2-08-COMMERCIAL.md](V2-08-COMMERCIAL.md) |
| v1.9 | Voice & narration quality | [V2-09-VOICE.md](V2-09-VOICE.md) |
| v2.0 | Polish & launch readiness | [V2-10-LAUNCH.md](V2-10-LAUNCH.md) |

## Design principles for v2

1. **Book first, engine second.** The reader never sees engine internals unless they explicitly opt in. The default experience is a book.
2. **Minimal GUI.** Panels open only when the user asks. The default view is just text and audio controls.
3. **Everything is logged.** Even when debug mode is off, the engine logs every decision, every API call, every audio generation step. Logs are saved to files and optionally shown in the GUI.
4. **Stories are persistent.** A reader can have multiple books in their library, resume any of them, and export them.
5. **The narrator is a character.** Not a DM, not a system — a narrator. The voice, personality, and style of the narrator is itself a creative element.
6. **Audio is the product.** Text is the source, but audio is what makes this an audiobook. Every text improvement should consider how it sounds aloud.
7. **Procedural everything.** No hardcoded scenarios, names, settings, or characters. Every story is unique.

## Suggested development order

The subversions are ordered by dependency and value:

1. **v1.1 (bugfixes)** — fix what's broken from v1 feedback. Fast, high value.
2. **v1.2 (debug/logging)** — enables effective development of everything else.
3. **v1.3 (audio)** — core product quality. User actions narrated, per-paragraph replay, free-text timing.
4. **v1.4 (save/load)** — readers need to keep their stories. Multi-book library.
5. **v1.5 (metadata)** — dynamic titles, chapter names, "passage" terminology everywhere.
6. **v1.6 (providers)** — model switching, fallback chains, rate-limit handling.
7. **v1.7 (world view)** — the creative centerpiece. An interactive world that grows.
8. **v1.8 (commercial)** — accounts, export, sharing, freemium model.
9. **v1.9 (voice)** — voice quality, character voices, narrator personality.
10. **v2.0 (launch)** — mobile, performance, polish, deployment.

## Open questions for Arie

These are decisions I need your input on before implementation begins. Add `>` inline answers.

1. Should the app require user accounts for v2, or remain local-first with optional cloud sync?

2. For the world view (v1.7), do you prefer a map-based visualization, a relationship graph, or a timeline view — or all three as tabs?

3. For commercial viability (v1.8), do you want a freemium model (free tier with limits, paid tier for premium voices/models), a one-time purchase, or a subscription?

4. Should audiobook export (v1.8) produce a single merged audio file, or a chapter-by-chapter audio bundle?

5. For mobile (v2.0), do you want a responsive web app, a native app (React Native / Flutter), or a PWA?

6. Should the narrator have a configurable personality (warm, mysterious, dramatic, etc.), or should it adapt to the story's tone automatically?

7. How important is multi-player / shared steering for v2? (Multiple readers steering the same story simultaneously.)

8. Should stories be shareable as "seeds" — i.e., a reader can share their story's starting conditions so others can experience a different path through the same world?

9. For the debug world view, should it be a separate full-screen mode, a bottom panel, a side panel, or a toggleable overlay?

10. Should we support "story templates" — pre-configured starting conditions for specific genres (mystery, romance, horror, etc.) that readers can pick from?
