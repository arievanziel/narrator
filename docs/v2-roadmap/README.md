# V2 Roadmap — Document Index

**Start here.** Read [V2-MASTER-PLAN.md](V2-MASTER-PLAN.md) first for the overview and open questions.

## Documents

| # | Document | Focus | Key Feedback Addressed |
|---|----------|-------|----------------------|
| 0 | [V2-MASTER-PLAN.md](V2-MASTER-PLAN.md) | Vision, principles, subversion overview, open questions | All |
| 1 | [V2-01-BUGFIXES.md](V2-01-BUGFIXES.md) | Fix all v1 playtest bugs | Storyteller mode leaks, dice always visible, "turn" vs "passage", panel auto-open, quick start, model lock, free-text timing, resume after refresh, "New story" |
| 2 | [V2-02-DEBUG-LOGGING.md](V2-02-DEBUG-LOGGING.md) | Full logging system + debug display | "Show logs" toggle, engine internals visibility, World Engine inspector |
| 3 | [V2-03-AUDIO.md](V2-03-AUDIO.md) | Audio improvements | Per-paragraph replay, user action narration, free-text timing, ambient SFX, narrator voice personality |
| 4 | [V2-04-SAVE-LOAD.md](V2-04-SAVE-LOAD.md) | Multi-book library | Save/load clarity, multiple stories, library browser, auto-save, story covers |
| 5 | [V2-05-METADATA.md](V2-05-METADATA.md) | Dynamic titles & metadata | Generated book title, passage terminology, passage number toggle, word count, listening time |
| 6 | [V2-06-PROVIDERS.md](V2-06-PROVIDERS.md) | Model switching & resilience | Always-available model switching, fallback chain, rate limit display, model as "narrator voice" |
| 7 | [V2-07-WORLD-VIEW.md](V2-07-WORLD-VIEW.md) | Interactive world visualization | World Engine inspector, map/relationship/timeline views, "The Cartographer's Desk" concept |
| 8 | [V2-08-COMMERCIAL.md](V2-08-COMMERCIAL.md) | Commercial viability | Accounts, export, sharing, freemium, story templates, marketplace |
| 9 | [V2-09-VOICE.md](V2-09-VOICE.md) | Voice & narration quality | Character voice consistency, narrator personality, emotional inflection, natural pacing, multi-voice dialogue |
| 10 | [V2-10-LAUNCH.md](V2-10-LAUNCH.md) | Polish & launch | Performance, mobile, PWA, deployment, CI/CD, monitoring, launch checklist |

## How to give feedback

1. Open any document in this folder
2. Add `>` at the start of a line to write your feedback inline
3. Your feedback is preserved — never overwritten
4. Reference specific sections or line numbers if needed

## Suggested reading order

1. **V2-MASTER-PLAN.md** — read first, answer the 10 open questions
2. **V2-01-BUGFIXES.md** — these are the most urgent fixes
3. **V2-07-WORLD-VIEW.md** — this is the creative centerpiece, needs your design input
4. **V2-08-COMMERCIAL.md** — needs your business model decisions
5. The rest in any order

## Dependency graph

```
v1.1 (bugfixes) ──┬──> v1.2 (debug/logging) ──> v1.7 (world view)
                  │
                  ├──> v1.3 (audio) ──> v1.9 (voice quality)
                  │
                  ├──> v1.4 (save/load) ──> v1.8 (commercial)
                  │
                  ├──> v1.5 (metadata)
                  │
                  └──> v1.6 (providers)
                                              ──> v2.0 (launch)
```

v1.1 is the foundation. v1.2 enables v1.7. v1.3 enables v1.9. v1.4 enables v1.8. v2.0 depends on everything.
