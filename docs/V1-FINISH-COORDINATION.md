# V1 Finish — Instance Coordination

**Created by:** Instance A (main programmer), 2026-08-24
**Source docs:** `docs/GLM-V1-FINISH-INSTRUCTIONS.md`, `docs/V1-PLAN.md`, `docs/V1-BOOK-EXPERIENCE-PLAN.md`

## Task Division

| Instance | Role | Handoff doc | Tasks | Files | Status |
|---|---|---|---|---|---|
| **A** (main programmer) | Backend | (this session) | TASK 3 + TASK 4 | `game_loop.py`, `world_store.py`, `audio_engine.py` | **DONE** — 77/77 tests pass |
| **B** | GUI | `docs/INSTANCE-B-GUI-HANDOFF.md` | TASK 1 (Book GUI) | `app.js`, `index.html`, `style.css` | Ready to start |
| **C** | UX | `docs/INSTANCE-C-UX-HANDOFF.md` | TASK 2 (audit fixes) | `app.js` (after B) | Blocked on B |
| **D** | Testing | `docs/INSTANCE-D-TESTING-HANDOFF.md` | Verify + soak test | Test files | Blocked on A+B+C |

## Dependency graph

```
A (backend) ──────────────────────────────┐
                                          ├──→ D (testing)
B (GUI: Book GUI) ──→ C (UX: audit fixes) ─┘
```

- A and B run in parallel (no file conflicts)
- C starts after B finishes (both need `app.js`)
- D starts after A, B, and C all finish

## File ownership (no overlap)

| File | Owner |
|---|---|
| `game_loop.py` | A |
| `world_store.py` | A |
| `audio_engine.py` | A |
| `audio_queue.py` | A |
| `app.py` | A |
| `dm_engine.py` | A (read-only for B/C) |
| `templates/index.html` | B (C: one line removal) |
| `static/app.js` | B first, then C |
| `static/style.css` | B (C: one cursor change) |

## What Arie needs to do

1. Point Instance B at `docs/INSTANCE-B-GUI-HANDOFF.md` — **can start immediately**
2. Point Instance C at `docs/INSTANCE-C-UX-HANDOFF.md` — starts with audit doc, codes after B finishes
3. Point Instance D at `docs/INSTANCE-D-TESTING-HANDOFF.md` — starts after A+B+C finish
4. Tell B when done so C can start coding
5. Tell D when A+B+C are all done
