# V2-08 — Commercial Features

**Status:** Planning — no implementation yet
**Priority:** Medium (for commercial viability)
**Estimated effort:** Large
**Feedback:** Add `>` inline notes anywhere.

## Summary

Features that make Narrator commercially viable as a product: user accounts, story export, sharing, freemium model, and the infrastructure to support a live service.

## Core question

Before implementing any of this, the fundamental business model question:

**Is Narrator:**
- A. A local-first app that readers run on their own machine (like a creative writing tool)
- B. A hosted web service that readers access via browser (like a SaaS product)
- C. A hybrid — local app with optional cloud sync and sharing

This document assumes **C (hybrid)** as the most flexible option. The app works fully locally, but cloud features enhance it.

## Features

### 1. User accounts

**Lightweight account system:**
- Email + password, or OAuth (Google, GitHub)
- Accounts are optional — the app works without one
- With an account: cloud sync of library, cross-device resume, sharing
- Without an account: local-only, all data stays on the machine

**Implementation:**
- Backend: a simple auth system (JWT tokens) or use a managed service (Supabase, Clerk)
- The existing app.py server handles auth, or a separate auth service
- Frontend: login/register screen, account settings

### 2. Story export

**Audio export:**
- "Export as audiobook" — merges all segment audio into a single file
- Format: MP3 (universal) or M4B (audiobook format with chapter markers)
- Includes background music mixed in
- Includes chapter markers and metadata (title, author, cover)
- File size: ~50-100MB for a typical story (depends on length)

**Text export:**
- "Export as text" — the full story as a formatted document
- Format: EPUB (e-book), PDF (print-style), or Markdown
- Includes chapter headings, scene settings, dialogue formatting
- No engine internals — pure story text

**Cover image:**
- AI-generated cover art based on the story's mood, genre, and title
- Or: a templated cover with mood-derived colors and typography
- Stored with the export

### 3. Story sharing

**Share as a "story seed":**
- A story seed = the starting conditions (genre, setting, character, tone) without the actual story
- Others can start a new story from the same seed and get a completely different path
- This is like sharing a "recipe" — the ingredients but not the meal

**Share as a "finished book":**
- Export the story (audio or text) and share it publicly
- A shareable link that shows the story in read-only mode
- Others can listen/read but not steer

**Share the world:**
- Share the world view (v1.7) as an interactive visualization
- Others can explore the map, characters, and timeline

### 4. Freemium model

**Free tier:**
- Unlimited stories
- Free AI models (Gemini Flash, Groq)
- Kokoro TTS (good quality)
- Local saves
- Basic world view

**Premium tier ($X/month):**
- Premium AI models (Claude, GPT-4)
- Qwen3 expressive TTS
- Cloud sync across devices
- Audiobook export (MP3/M4B)
- AI-generated cover art
- Advanced world view with art
- Priority generation (faster TTS, no queue)

**One-time purchase option:**
- "Buy Narrator" — $Y one-time for lifetime premium features
- Or: pay-per-story for exports

### 5. Story templates

Pre-configured starting conditions for specific genres:
- "The Haunted Manor" — gothic horror, isolated location, supernatural mystery
- "The Desert Caravan" — adventure, travel, trade and intrigue
- "The Detective's Case" — mystery, urban setting, investigation
- "The Lost Kingdom" — epic fantasy, restoration, political intrigue
- "The Space Station" — sci-fi, isolation, unknown threat

Each template provides:
- Genre, setting, tone, atmosphere
- Suggested character archetypes
- Opening scenario seed
- The foreword can still customize further

Templates make it easy for new readers to start without a long Session Zero.

### 6. Story marketplace (future)

A community-driven library of shared stories and seeds:
- Browse stories others have shared
- Rate and review
- Start from someone's seed
- "Remix" a story — take someone's world and continue differently

This is a v3 feature but the architecture should support it from v2.

### 7. Analytics and feedback

For the author/developer (Arie):
- Anonymous usage analytics (stories created, chapters played, models used, audio generated)
- Error reporting (crashes, API failures, audio issues)
- Feature usage tracking (which settings are used, which views are opened)
- All opt-in, privacy-respecting

## Implementation plan

1. Choose auth approach (Supabase recommended for speed)
2. Implement account system (register, login, logout)
3. Implement cloud sync (upload library, download library)
4. Implement audio export (merge segments + music → MP3/M4B)
5. Implement text export (story → EPUB/PDF)
6. Implement story seed sharing (serialize starting conditions)
7. Implement story templates (pre-configured setups)
8. Implement freemium gating (feature flags based on account tier)
9. Implement cover image generation (templated first, AI later)
10. Set up deployment infrastructure (see v2.0)

## Open questions

1. Which payment provider? (Stripe, Paddle, LemonSqueezy)
2. Which auth provider? (Supabase, Clerk, custom)
3. Should the hosted version use the same Python server, or a separate backend?
4. What's the pricing? (Suggestion: $5/month or $40/year for premium)
5. Should there be a free trial of premium features?
