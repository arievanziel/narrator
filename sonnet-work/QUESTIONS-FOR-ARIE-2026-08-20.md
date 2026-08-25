# Questions for Arie — 2026-08-20

Concise, with context. Answer inline with `>` lines like your other feedback files, or
just tell me in chat. GLM doesn't need to see this file unless you want it to.

## 1. GUI direction — pick one to move forward with

There are now 14 GUI mockups in `glm-work/notes/gui_v2/` (the original 6 style
explorations, plus 8 new variants — `v1-bookmark.html` through `v8-margin-marks.html` —
built specifically to solve the bar/tab visibility problem from your round-3 feedback).
Nobody has picked a winner yet, and GLM will keep iterating indefinitely without one.

> Which variant (or which elements from which variants) should become the real GUI?
> (Open `glm-work/notes/gui_v2/index_v3.html` to compare them side by side if you
> haven't already.)

> Sonnet or another visual model needs to check the details of the gui of v9 and create improved instructions for glm to make it modern and profesionally coded with best practices for interface design. So far i like v9 the most, but it needs some polishing in the details, like the tabs for the side panels are not properly aligned with the panel tops.
> we also need to figure out a better layout for the audio bar and the bottom bar. a tab toggle on these double bottom bars doesn't work well, so perhaps we need another solution altogether.
> but for now, the v9 or any of the v3 variants are fine to use as a baseline for the visual model to improve. And for a v0.1 app we can already start using the current gui.

## 2. Rules-lawyer hardening — OK to start now?

Two known cheat vulnerabilities exist ("waste potion" trick, "control NPC" trick) with
clear, well-specified fixes already proposed by GLM. This doesn't depend on any of your
other feedback.

> OK for GLM to start this now, in parallel with whatever else you're reviewing?
> (My recommendation: yes — no reason to wait.)
> totally OK.

## 3. DM brain: play a real session before deciding the model

Two candidates tested well: **GPT-OSS 120B** (best rule/cheat enforcement, but Groq's
200K tokens/day quota is tight) vs **Gemini 3.5 Flash-Lite** (your current default,
best value, more generous quota). Numbers alone don't tell us which *feels* better to
actually play with.

> Can you play a real 10+ turn session (not scripted) with each and say which you prefer? This also doubles as testing the actual app, not just the test harness.
> I'm going to try both and see which one i prefer. I need to see if it actually works already, technically on my macbook it was still very buggy the last time glm ran it.

## 4. Claude baseline — still waiting on you specifically

`glm-work/notes/claude_dm_test_prompt.md` has the full script ready — paste the system
prompt into a Devin/Claude session (Opus, Sonnet, or Fable) and play the same 10
scripted turns used for the other models. This is the one test only you can run (it
needs a real Claude conversation, not an API call GLM can script).

> Any chance to run this soon? It's the missing data point for "is a paid API worth it at all," which affects several other decisions downstream.
> I ran it and had a lovely session, great quality from Sonnet free. But I didn't follow the scripted turns. We should do that directly through api use, but i need help to set it up and a cost estimate.

## 5. Feedback forms still empty

`notes/v0_gui_feedback.md`, `notes/v0_audio_feedback.md`, `notes/v0_playtesting_feedback.md`
are all prepared but empty, and `notes/demo_feedback_v4.md` has a few empty sections left
(interactive demo, general questions).

> No rush on all of these — but if you have 10 minutes, even partial answers help GLM avoid guessing at your preferences.
> I've filled out what i think is usefull, if i haven't given feedback assume i have no opinion on it or at least not any ideas myself for improvement.

## 6. Campaign config draft — still needs your input

`sonnet-work/CAMPAIGN-CONFIG-DRAFT.md` (my draft from a few days ago) — tracking
granularity, dice visibility, NPC management, etc. — hasn't been answered yet. Not
urgent (nothing is blocked on it right now), but it'll matter once the rules-lawyer
and GUI work settle down.

> When you have a moment — no specific deadline.
> thanks for the reminder, I will think about these, but mainly i think the final app should have a sort of opening wizard that guides the user through the setup process. Like the introduction or foreword to a book.
> I think i mainly want the app to stay simple, like an audiobook with some user choices for the main character, but in the base version all DM activity, like dice rolling and character management, should be handled by the app itself. It should be visible to the user though, so they can see what's happening. But for the start it's about narration and user choices, the DM engine and all world building and stat tracking is only to support that in the background. Later we could maybe develop a more full game experience, but that's not the focus right now.

---

## Addendum (2026-08-20, after reading your answers) — one new decision: Claude API tier

You asked me to help set up the Claude API for direct testing and give a cost estimate.
Good news: Anthropic has an OpenAI-SDK-compatible endpoint, so this slots into the
existing multi-provider test harness (`test_api_dm.py`) with a small addition — no
architecture change needed. I've asked GLM to add it.

**Cost estimate** (using GPT-OSS 120B's token profile as the proxy — ~1,800 input +
~700 output tokens/turn — scaled to ~50 turns/day, 30 days/month). The SoloQuest
architecture only sends current state + last turn, not full history, so per-turn cost
should stay roughly flat over a session rather than growing — good for predictability:

| Model | Input/Output $ per MTok | Estimated $/month at 50 turns/day |
|---|---|---|
| Claude Haiku 4.5 | $1 / $5 | **~$8/month** |
| Claude Sonnet 5 | $2 / $10 | **~$16/month** |
| Claude Opus 5 | $5 / $25 | **~$40/month** |

These are rough (Claude's actual verbosity/tokenization will differ somewhat from
GPT-OSS's), but directionally solid. Haiku fits your original ~€10/month budget
comfortably; Sonnet is close but over; Opus is well over unless you're fine treating it
as an occasional/quality-check model rather than the daily driver.

> Which Claude tier(s) should GLM wire up and test — just Haiku (stays in budget), or
> Haiku + Sonnet (to see if the quality jump is worth ~$8 more), or all three for a
> complete picture regardless of budget for now (it's just a test, not a commitment)?

---

## What I do NOT need from GLM right now

Everything GLM would need to act on the above is already in its own files/handoff —
no additional GLM output required before you answer these. If you want GLM to keep
working in parallel while you think about #1/#3/#4, tell it to start on #2 (rules-lawyer
hardening) — that one's unblocked regardless of your answers above.
