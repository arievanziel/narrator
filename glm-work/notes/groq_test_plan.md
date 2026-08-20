# Groq Free-Tier DM Brain Test — Setup Plan

**Prepared by:** GLM-5.2 High, 2026-08-18
**Status: SCRIPT BUILT AND TESTED** — `glm-work/test_api_dm.py` is ready to run.
Arie just needs to add a Groq API key to `glm-work/.env` and run the script.
**For:** Originally for another GLM instance to execute; the script is now complete
so Arie can run it directly or hand it to another instance.
**Goal:** Test open-weight LLMs (GPT-OSS 120B, Qwen3 32B, etc.) as D&D DM brains
via free-tier API providers (Groq, SambaNova, Cerebras, OpenRouter) — no model
downloads, no payment required.

## What's been built

- **`glm-work/test_api_dm.py`** (666 lines) — multi-provider DM brain test script.
  Supports Groq, SambaNova, Cerebras, OpenRouter (all OpenAI-compatible API).
  Features: SoloQuest-style 4-section system prompt, deterministic state engine,
  response parser, 10-turn scripted test scenario, interactive mode, comparison
  mode, automated grading, JSON result output. All internal tests pass.
- **`glm-work/.env.example`** — template for API keys (gitignored).
- **`.gitignore`** — protects `.env` and model weights from being committed.
- **Dependencies installed:** `openai` 3.2.0, `python-dotenv` 1.2.3 in `glm-work/.venv`.

## Quick Start (for Arie)

```bash
# 1. Get a free Groq API key at https://console.groq.com (no credit card)

# 2. Create .env file with your key
cd /Users/arie/CascadeProjects/narrator/glm-work
cp .env.example .env
# Edit .env: replace gsk_your_key_here with your real Groq key

# 3. List available models on Groq (verify the key works)
.venv/bin/python test_api_dm.py --provider groq --list-models

# 4. Run the 10-turn test with GPT-OSS 120B (the strongest model that fits budget)
.venv/bin/python test_api_dm.py --provider groq --model gpt-oss-120b

# 5. Compare GPT-OSS 120B vs Qwen3 32B on the same scenario
.venv/bin/python test_api_dm.py --compare groq:gpt-oss-120b groq:qwen3-32b

# 6. Interactive mode — play yourself, type your own actions
.venv/bin/python test_api_dm.py --provider groq --model gpt-oss-120b --interactive
```

To test other free providers (SambaNova, Cerebras), get keys from the URLs in
`.env.example` and add them to `.env`, then use `--provider sambanova` etc.

## Context

- Research doc: `glm-work/notes/local_llm_dm_research.md` §5a and §4
- Groq offers a **free tier**: 30 req/min, 6K tokens/min, 14,400 req/day, no credit card
- Groq serves open-weight models at 300-800 tok/s on their LPU hardware
- The test scenario is defined in §4 of the research doc (10-turn goblin-tavern combat)

## What Groq gives us for free

| Model | Input $/M | Output $/M | Speed (tok/s) | Context | Why it matters |
|---|---|---|---|---|---|
| **GPT-OSS 120B** | $0.15 | $0.60 | ~500 | 128K | Biggest model that fits €10/mo budget. Strongest test candidate. |
| **Qwen3 32B** | $0.29 | $0.59 | ~662 | 128K | Same model family as the local pick — direct local-vs-cloud comparison |
| Llama 3.3 70B | — | — | — | — | **RETIRED from Groq 2026-08-16** — do not use |
| GPT-OSS 20B | $0.075 | $0.30 | ~1,000 | 128K | Fastest/cheapest — use as a quick sanity check |
| Qwen3 30B-A3B | (check) | (check) | (check) | — | MoE variant — if available, compare vs Qwen3 32B |

Free tier limits: 30 RPM, 6K TPM, 14,400 RPD. For a 10-turn test this is more than enough.

## Step 1: Create a Groq account and get an API key

1. Go to https://console.groq.com
2. Sign up with email or Google account (no credit card required)
3. Navigate to API Keys → Create new key
4. Copy the key (starts with `gsk_...`)
5. **Do NOT commit the key to the repo.** Store it in a `.env` file that's gitignored, or export it as an environment variable.

## Step 2: Install the Groq Python SDK

```bash
# In the narrator project venv
uv pip install groq
# Or: pip install groq
```

The Groq SDK is OpenAI-compatible — you can also use the `openai` SDK with a custom base_url if preferred.

## Step 3: Write the test script

Create `glm-work/test_groq_dm.py`. The script should:

### 3a. System prompt (the "rules contract")

Use the SoloQuest 4-layer pattern from `dm_engine_research.md` §1.8. Specifically:

```python
SYSTEM_PROMPT = """You are an expert D&D 5e Dungeon Master running a solo campaign.

RULES CONTRACT (follow strictly):
1. ROLLS BEFORE OUTCOMES: Never narrate a result before the dice are rolled.
   WRONG: "Your sword strikes true, dealing 8 damage!"
   CORRECT: Ask for the roll, wait for the result, THEN narrate what happened.
2. STATE IS AUTHORITATIVE: The game state provided below is the source of truth.
   Do not contradict it. Do not invent items, HP, or conditions not listed.
3. RESPONSE FORMAT: Every response must have exactly 4 sections:
   [NARRATIVE] - the story beat (2-4 paragraphs, vivid but not purple)
   [MECHANICS] - machine-readable tags only, one per line:
     HP_CHANGE:<amount> (negative = damage to PC, positive = healing)
     ENEMY_HP:<name>,<current>/<max>
     ROLL:<dice> for <skill>
     ITEM_USED:<name>
     SPELL_SLOT_USED:<level>
   [SUGGESTIONS] - 2-3 player options, each tagged roll:true or roll:false
   [CHRONICLE] - one-line campaign log entry (only on significant beats)
4. ENCOUNTER BALANCE: Level 1 enemies max 7 HP, no multiattack. Solo play = no party backup.
5. WARLOCK SLOTS recharge on short rest, not long rest. (Common AI failure mode.)
"""
```

### 3b. State injection (each turn)

```python
def build_state_block(state):
    return f"""
CURRENT GAME STATE (authoritative):
PC: Level 1 Fighter | HP: {state['pc_hp']}/12 | AC: 16
  STR 16 (+3) | DEX 12 (+1) | CON 14 (+2) | INT 10 | WIS 10 | CHA 10
  Inventory: {', '.join(state['inventory'])}
  Equipment: longsword (1d8+3 slashing), shield, chain mail
Enemies: {format_enemies(state['enemies'])}
Scene: {state['location']} | Light: {state['light']} | Time: {state['time']}
Previous turn mechanics: {state['last_mechanics']}
"""
```

### 3c. API call (Groq SDK)

```python
from groq import Groq
import os

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def dm_turn(system_prompt, state_block, history, player_input, model="gpt-oss-120b"):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": state_block + "\nPLAYER ACTION:\n" + player_input},
        ],
        temperature=0.7,  # creative but not chaotic
        max_tokens=800,
    )
    return response.choices[0].message.content
```

### 3d. Response parser

```python
import re

def parse_response(text):
    sections = {}
    for tag in ["NARRATIVE", "MECHANICS", "SUGGESTIONS", "CHRONICLE"]:
        match = re.search(rf'\[{tag}\]\s*(.*?)(?=\[|$)', text, re.DOTALL)
        sections[tag] = match.group(1).strip() if match else ""
    
    # Parse mechanics tags into state changes
    mechanics = {}
    for line in sections["MECHANICS"].split("\n"):
        line = line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
            mechanics[key.strip()] = val.strip()
    
    return sections, mechanics
```

### 3e. State updater (deterministic — the engine, not the LLM)

```python
def apply_mechanics(state, mechanics):
    if "HP_CHANGE" in mechanics:
        state["pc_hp"] = max(0, state["pc_hp"] + int(mechanics["HP_CHANGE"]))
    if "ITEM_USED" in mechanics:
        item = mechanics["ITEM_USED"]
        if item in state["inventory"]:
            state["inventory"].remove(item)
    # ... etc for ENEMY_HP, SPELL_SLOT_USED, etc.
    return state
```

### 3f. Main loop

```python
def run_test_scenario(model="gpt-oss-120b"):
    state = {
        "pc_hp": 12,
        "inventory": ["Health Potion", "Torch", "Waterskin"],
        "enemies": [
            {"name": "Goblin Scout", "hp": 7, "max_hp": 7, "ac": 15},
            {"name": "Goblin Raider", "hp": 7, "max_hp": 7, "ac": 15},
        ],
        "location": "The Rusty Anchor tavern",
        "light": "dim (candlelit)",
        "time": "evening",
        "last_mechanics": "(start of encounter)",
    }
    history = []
    
    # Opening scene
    opening = dm_turn(SYSTEM_PROMPT, build_state_block(state), history,
                      "I push open the tavern door and step inside.", model)
    sections, mechanics = parse_response(opening)
    print(f"\n{'='*60}\n[NARRATIVE]\n{sections['NARRATIVE']}\n")
    print(f"[SUGGESTIONS]\n{sections['SUGGESTIONS']}\n{'='*60}")
    history.append({"role": "assistant", "content": opening})
    state = apply_mechanics(state, mechanics)
    state["last_mechanics"] = sections["MECHANICS"]
    
    # Run 10 turns with scripted player actions (for reproducibility)
    player_actions = [
        "I draw my longsword and attack the nearest goblin.",
        "I roll a 14 on my attack roll.",
        "I use my bonus action to check for other threats (Perception).",
        "I roll a 12 on Perception.",
        "I attack the goblin raider.",
        "I rolled a 19.",
        "The goblin hit me — how much damage do I take? I rolled nothing, you tell me.",
        "I drink my Health Potion as an action.",
        "I try to intimidate the surviving goblin into surrendering.",
        "I roll a 10 on Intimidation (with my +0 Charisma).",
    ]
    
    for i, action in enumerate(player_actions, 1):
        print(f"\n--- Turn {i} ---")
        print(f"Player: {action}")
        response = dm_turn(SYSTEM_PROMPT, build_state_block(state), history, action, model)
        sections, mechanics = parse_response(response)
        print(f"\n[NARRATIVE]\n{sections['NARRATIVE']}")
        print(f"\n[MECHANICS]\n{sections['MECHANICS']}")
        print(f"\n[SUGGESTIONS]\n{sections['SUGGESTIONS']}")
        history.append({"role": "user", "content": action})
        history.append({"role": "assistant", "content": response})
        state = apply_mechanics(state, mechanics)
        state["last_mechanics"] = sections["MECHANICS"]
        
        # Grade roll-before-outcome
        # (manual review — check if NARRATIVE contains damage numbers before a ROLL tag)
    
    # Final state report
    print(f"\n{'='*60}")
    print(f"FINAL STATE:")
    print(f"  PC HP: {state['pc_hp']}/12")
    print(f"  Inventory: {state['inventory']}")
    print(f"  Enemies: {format_enemies(state['enemies'])}")
    print(f"  Turns completed: {len(player_actions)}")
```

### 3g. CLI interface

```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gpt-oss-120b",
                        choices=["gpt-oss-120b", "qwen3-32b", "gpt-oss-20b"],
                        help="Groq model to test")
    parser.add_argument("--interactive", action="store_true",
                        help="Interactive mode (type your own actions)")
    args = parser.parse_args()
    
    if args.interactive:
        run_interactive(args.model)
    else:
        run_test_scenario(args.model)
```

## Step 4: Create a .env file (gitignored)

```bash
# .env (DO NOT COMMIT)
GROQ_API_KEY=gsk_your_key_here
```

Add `.env` to `.gitignore` if not already there.

## Step 5: Verify it works

```bash
# Quick smoke test — 1 turn, cheapest model
python glm-work/test_groq_dm.py --model gpt-oss-20b

# The real test — GPT-OSS 120B
python glm-work/test_groq_dm.py --model gpt-oss-120b

# Comparison test — Qwen3 32B
python glm-work/test_groq_dm.py --model qwen3-32b
```

## Step 6: Grading rubric (for Arie to review the output)

After running, check these criteria (from the research doc §4):

1. **Roll-before-outcome (10 checks):** Does the model ever narrate "you hit for X damage" BEFORE the player provides a roll? Count violations. Pass = ≤1 violation in 10 turns.
2. **State consistency at turn 10:** Is PC HP correct? Are dead goblins marked dead? Is the Health Potion removed from inventory? Pass = all 3 correct.
3. **Response format adherence:** Does every response have all 4 sections ([NARRATIVE], [MECHANICS], [SUGGESTIONS], [CHRONICLE])? Pass = ≥8/10 turns have all 4.
4. **Prose quality (subjective):** Is the narration flat/repetitive, or does it have scene texture? Compare to what Claude produces for the same scenario.
5. **Speed:** Note wall-clock time per turn. Groq should be <2s per turn (500 tok/s).

## Other free-tier providers to test (optional, same script structure)

The script uses the OpenAI-compatible API format, so it works with these too — just change the base_url and API key:

### SambaNova (free tier — strongest alternative to Groq)
- **Free tier:** 200,000 tokens/day, 20 req/min, no credit card
- **Models:** DeepSeek-V3.1/V3.2, Llama-3.3-70B, gpt-oss-120b, gemma-4-31B, MiniMax
- **Why test:** Has Llama 3.3 70B (which Groq retired) + DeepSeek V3 (671B MoE, competitive with frontier)
- **Setup:** `pip install openai`, set `base_url="https://api.sambanova.ai/v1"`
- **Signup:** https://cloud.sambanova.ai

### Cerebras (free tier — fastest inference)
- **Free tier:** 5 RPM, 30K TPM, 1M tokens/day, no credit card
- **Models:** gpt-oss-120b, zai-glm-4.7, Llama 4 Scout
- **Why test:** Fastest inference available (~2,100 tok/s) — if speed matters for real-time DMing
- **Setup:** `pip install cerebras_cloud_sdk` or use OpenAI-compatible endpoint
- **Signup:** https://cloud.cerebras.ai

### Google AI Studio (free tier — frontier model access)
- **Free tier:** 1,500 req/day, 10 RPM, no credit card
- **Models:** Gemini 2.5 Flash, Gemini 3.5 Flash (GA as of May 2026)
- **Why test:** Gemini is a frontier model — compare open-weight quality against a frontier baseline for free
- **Setup:** `pip install google-generativeai` (different API format, not OpenAI-compatible without wrapper)
- **Signup:** https://aistudio.google.com

### OpenRouter (aggregator — free models available)
- **Free tier:** Some models are free (look for `:free` suffix in model names)
- **Why test:** Single API, routes to cheapest provider. Good for production fallback strategy.
- **Setup:** `pip install openai`, set `base_url="https://openrouter.ai/api/v1"`
- **Signup:** https://openrouter.ai

## Priority order for testing

1. **Groq GPT-OSS 120B** — biggest model that fits budget, free tier, 500 tok/s
2. **Groq Qwen3 32B** — direct comparison vs local Qwen3 32B (if Arie also tests local)
3. **SambaNova DeepSeek V3.2** — 671B MoE, competitive with frontier, free tier
4. **Cerebras GPT-OSS 120B** — same model as Groq but 4x faster (2,100 tok/s)
5. **Google Gemini 3.5 Flash** — frontier baseline for quality comparison

All of these are free. Arie can test all 5 without spending anything.

## Notes for the GLM instance setting this up

- Do NOT download any models — this is all API-based, no local weights needed
- Do NOT commit API keys to the repo — use `.env` + `.gitignore`
- The script should be self-contained and runnable with `python glm-work/test_groq_dm.py`
- If Groq's free tier rate-limits during testing, wait 60 seconds and retry (30 RPM = 1 req per 2 seconds)
- The `gpt-oss-120b` model name may have a suffix (e.g., `gpt-oss-120b` or `openai/gpt-oss-120b`) — check Groq's models endpoint: `client.models.list()`
- Print the model's actual name and token counts per turn so Arie can see real costs
