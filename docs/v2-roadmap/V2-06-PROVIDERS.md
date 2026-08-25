# V2-06 — Model Switching & Provider Resilience

**Status:** Planning — no implementation yet
**Priority:** Medium-High
**Estimated effort:** Medium
**Feedback:** Add `>` inline notes anywhere.

## Summary

Make model switching seamless and resilient. The reader should be able to change models at any time, and the app should handle rate limits, outages, and quality differences gracefully.

## Issues from v1 feedback

- "Model changes should always be possible, but only take effect after a user input is sent"
- "A model change should not be an issue because the campaign state and all world details are saved programmatically"
- "Display rate limit info on screen in debug mode"

## Design

### Model switching

**Rules:**
1. The model selector is always enabled (never locked)
2. A model change takes effect on the NEXT turn (after the user sends their next input)
3. The current turn finishes with the current model
4. The session state, world store, and history are model-agnostic — they work with any model

**Implementation:**
- Frontend: remove `szModel.disabled = true` from Session Zero
- Frontend: the Settings panel model selector is already always enabled
- Backend: at the start of `handle_turn()` and `handle_session_zero_turn()`, check if `data.get("model")` differs from `session.model`
- If different: call `session.model = new_model; session.init_client()`
- The conversation history continues with the new model — no context is lost

**Model selection in Session Zero:**
- The model picker in the foreword is always available
- Changing it mid-foreword takes effect on the next exchange
- The foreword conversation history carries over to the new model

### Provider fallback chain

When a provider fails (rate limit, outage, timeout), automatically fall back to another provider:

```python
FALLBACK_CHAIN = [
    "gemini-3.5-flash-lite",      # primary (free, fast)
    "openai/gpt-oss-120b",        # secondary (free, Groq)
    "groq/compound-mini",          # tertiary (free, Groq)
    "claude-haiku-4-5",           # paid (if credits available)
]
```

**Fallback logic:**
1. Try the user's selected model
2. If 429 (rate limit): wait and retry up to 3 times with exponential backoff
3. If still failing: fall back to next model in chain
4. If all models fail: return an error to the frontend with a clear message
5. Log every fallback decision (for debug mode)

**Frontend notification:**
- In debug mode: show "Falling back from Gemini to GPT-OSS due to rate limit"
- In normal mode: silent fallback (the reader doesn't need to know)
- If all models fail: show a gentle "The narrator is gathering their thoughts... please try again in a moment"

### Rate limit handling

**Per-provider rate limit tracking:**
- Track requests per minute per provider
- If approaching the limit, proactively slow down or switch providers
- Show rate limit status in debug mode:
  - "Gemini: 12/15 requests this minute"
  - "Groq: 3/30 requests this minute"

**Rate limit display (debug mode):**
```
Provider status:
  Gemini Flash: 12/15 rpm (80%) — yellow
  GPT-OSS 120B: 3/30 rpm (10%) — green
  Claude Haiku: ready — green
```

### Model quality indicators

In the model selector, show quality indicators:
- ⚡ Fast (Gemini Flash, Groq)
- 🧠 Smart (Claude, GPT-OSS)
- 🎭 Expressive (Qwen3 for TTS)
- 💰 Paid (Claude)

Help the reader understand the tradeoffs without exposing API details.

### Provider health check

A new `/api/providers` endpoint enhancement:
- Real-time availability check
- Rate limit status
- Estimated latency
- Cost per 1K tokens

### Creative direction: model as "narrator voice"

In the final product, the model choice could be framed as choosing the narrator's "voice" or "style":
- "Gemini Flash" → "The Quick Storyteller" (fast, light)
- "GPT-OSS 120B" → "The Thoughtful Narrator" (balanced, deep)
- "Claude Haiku" → "The Literary Voice" (premium, nuanced)

This abstracts away the AI model names and makes it feel like choosing a narrator personality.

## Implementation plan

1. Remove model dropdown lock from Session Zero (v1.1 bugfix)
2. Add model change detection in `handle_turn()` and `handle_session_zero_turn()`
3. Implement fallback chain in `dm_turn()` or a new `dm_turn_with_fallback()`
4. Add rate limit tracking per provider
5. Enhance `/api/providers` endpoint with health and rate limit info
6. Add debug mode display for provider status
7. Add user-facing model descriptions (abstracted names)
