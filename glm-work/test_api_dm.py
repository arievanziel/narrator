#!/usr/bin/env python3
"""Test open-weight LLMs as D&D DM brains via free-tier API providers.

Supports: Groq, SambaNova, Cerebras, OpenRouter (all OpenAI-compatible).
Tests the "LLM narrates, code adjudicates" architecture from dm_engine_research.md
using the SoloQuest 4-section response format and a deterministic state engine.

Usage:
  # List available models on a provider
  python test_api_dm.py --provider groq --list-models

  # Run the 10-turn scripted test scenario
  python test_api_dm.py --provider groq --model gpt-oss-120b
  python test_api_dm.py --provider groq --model qwen3-32b
  python test_api_dm.py --provider sambanova --model Meta-Llama-3.3-70B-Instruct

  # Interactive mode (type your own actions)
  python test_api_dm.py --provider groq --model gpt-oss-120b --interactive

  # Compare two models on the same scenario
  python test_api_dm.py --compare groq:gpt-oss-120b groq:qwen3-32b

Requires: .env file with API keys (see .env.example). No model downloads.
"""
import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


# ---------------------------------------------------------------------------
# Cost tracker — for paid API providers (Anthropic)
# ---------------------------------------------------------------------------

class CostTracker:
    """Tracks cumulative API cost in USD. Raises BudgetExceeded when limit hit."""
    def __init__(self, budget_usd: float = 5.0):
        self.budget_usd = budget_usd
        self.total_cost = 0.0
        self.calls = []

    def add_call(self, provider: str, model: str, prompt_tokens: int, completion_tokens: int):
        """Record a call and add its cost. Returns the cost of this call."""
        pricing = PRICING_PER_MTOK.get(provider, {}).get(model)
        if not pricing:
            # Free provider or unknown model — no cost
            self.calls.append({
                "provider": provider, "model": model,
                "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                "cost": 0.0,
            })
            return 0.0

        input_per_tok = pricing[0] / 1_000_000
        output_per_tok = pricing[1] / 1_000_000
        cost = (prompt_tokens * input_per_tok) + (completion_tokens * output_per_tok)
        self.total_cost += cost
        self.calls.append({
            "provider": provider, "model": model,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "cost": cost,
        })
        return cost

    def check_budget(self) -> bool:
        """Returns True if under budget, False if exceeded."""
        return self.total_cost < self.budget_usd

    def summary(self) -> str:
        return f"${self.total_cost:.4f} / ${self.budget_usd:.2f} budget"


# Global cost tracker (set by main() when using paid providers)
_cost_tracker: CostTracker | None = None


def get_cost_tracker() -> CostTracker | None:
    return _cost_tracker


class BudgetExceeded(Exception):
    """Raised when the API cost budget is exceeded."""
    pass

# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_var": "GROQ_API_KEY",
        "label": "Groq (LPU, 300-800 tok/s)",
    },
    "sambanova": {
        "base_url": "https://api.sambanova.ai/v1",
        "env_var": "SAMBANOVA_API_KEY",
        "label": "SambaNova (RDU, free 200K tok/day, needs card)",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "env_var": "CEREBRAS_API_KEY",
        "label": "Cerebras (WSE, ~3000 tok/s, needs card)",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_var": "OPENROUTER_API_KEY",
        "label": "OpenRouter (aggregator)",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_var": "GOOGLE_API_KEY",
        "label": "Google AI Studio (Gemini, free, no card)",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1/",
        "env_var": "ANTHROPIC_API_KEY",
        "label": "Anthropic (Claude, paid, OpenAI-compatible endpoint)",
    },
}

# Recommended models per provider (verified from provider docs, Aug 2026)
RECOMMENDED_MODELS = {
    "groq": ["openai/gpt-oss-120b", "groq/compound-mini", "qwen/qwen3.6-27b", "openai/gpt-oss-20b"],
    "sambanova": ["DeepSeek-V3.1", "DeepSeek-V3.2", "gemma-4-31b-it", "MiniMax-M2.7"],
    "cerebras": ["gpt-oss-120b", "gemma-4-31b"],
    "openrouter": [],  # varies, check --list-models
    "gemini": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
    "anthropic": ["claude-haiku-4-5", "claude-sonnet-5", "claude-opus-5"],
}

# Pricing per million tokens (input, output) in USD — for cost tracking
# Only paid providers need entries; free providers default to $0
PRICING_PER_MTOK = {
    "anthropic": {
        "claude-haiku-4-5": (1.0, 5.0),
        "claude-haiku-4-5-20251001": (1.0, 5.0),
        "claude-sonnet-5": (2.0, 10.0),
        "claude-opus-5": (5.0, 25.0),
    },
    # groq, gemini, sambanova, cerebras: free tier, no cost tracking needed
}

# ---------------------------------------------------------------------------
# System prompt — the "rules contract" (SoloQuest pattern, dm_engine_research §1.8)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert D&D 5e Dungeon Master running a solo campaign for one player.

## RULES CONTRACT (follow strictly)

1. ROLLS BEFORE OUTCOMES. Never narrate a combat result before the dice are rolled.
   WRONG: "Your sword strikes true, dealing 8 damage!"
   CORRECT: Ask the player to roll, wait for the number, THEN narrate the outcome.
   If the player has not provided a roll for an action that needs one, ask for it.

2. STATE IS AUTHORITATIVE. The game state provided in each turn is the source of
   truth. Do not contradict it. Do not invent items, HP, conditions, or NPCs not
   listed in the state. If the player claims something not in the state, rule
   based on what is actually there.

3. RESPONSE FORMAT. Every response MUST contain exactly 4 sections, each on a new
   line with the section tag in brackets:

   [NARRATIVE]
   The story beat — 2 to 4 paragraphs. Vivid but not purple prose. Show the
   scene, NPC reactions, and consequences of the player's action.

   [MECHANICS]
   Machine-readable tags only, one per line. Use ONLY these tags:
     HP_CHANGE:<signed_int>          (negative = damage to PC, positive = healing)
     ENEMY_HP:<name>,<current>/<max>  (update an enemy's HP)
     ENEMY_DEAD:<name>                (mark an enemy as dead)
     ROLL_REQUEST:<dice> for <skill>  (ask the player to roll — when you need a roll)
     ITEM_USED:<name>                 (consume an item from inventory)
     ITEM_GAINED:<name>               (add an item to inventory)
     SPELL_SLOT_USED:<level>          (consume a spell slot)
     CONDITION:<target>,<condition>   (apply a condition: poisoned, stunned, etc.)
     NO_MECHANICS                     (use when no mechanical change this turn)

   [SUGGESTIONS]
   2-3 player options for the next action, each on its own line, tagged:
     roll:true — this option requires a dice roll before it can resolve
     roll:false — this option is narrative/social, no roll needed
   Format: "- <option text> [roll:true]" or "- <option text> [roll:false]"

   [CHRONICLE]
   One-line campaign log entry. Only include on significant beats (combat start,
   enemy death, item gained, scene change). Use "NO_ENTRY" for uneventful turns.

4. ENCOUNTER BALANCE. This is solo play — no party backup. Level 1 enemies: max
   7 HP, no multiattack. A single bad roll should not end the run.

5. BE THE DM, NOT A PLAYER. You control NPCs, monsters, and the world. The player
   controls only their character. Never act for the player.

6. WARLOCK SPELL SLOTS recharge on a short rest, not a long rest. (Common AI error.)
"""


# ---------------------------------------------------------------------------
# Game state — the deterministic engine (dm_engine_research §1.8 Layer 3)
# ---------------------------------------------------------------------------

@dataclass
class Enemy:
    name: str
    hp: int
    max_hp: int
    ac: int

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def __repr__(self):
        status = f"{self.hp}/{self.max_hp} HP, AC {self.ac}"
        if not self.alive:
            status += " [DEAD]"
        return f"{self.name} ({status})"


@dataclass
class GameState:
    pc_name: str = "Kael"
    pc_class: str = "Fighter"
    pc_level: int = 1
    pc_hp: int = 12
    pc_max_hp: int = 12
    pc_ac: int = 16
    pc_str: int = 16
    pc_dex: int = 12
    pc_con: int = 14
    pc_int: int = 10
    pc_wis: int = 10
    pc_cha: int = 10
    inventory: list = field(default_factory=lambda: [
        "Health Potion", "Torch", "Waterskin", "50 feet of rope",
    ])
    equipment: str = "longsword (1d8+3 slashing), shield, chain mail"
    enemies: list = field(default_factory=list)
    location: str = "The Rusty Anchor tavern"
    light: str = "dim (candlelit)"
    time: str = "evening"
    last_mechanics: str = "(start of encounter)"
    chronicle: list = field(default_factory=list)

    @property
    def str_mod(self):
        return (self.pc_str - 10) // 2

    @property
    def dex_mod(self):
        return (self.pc_dex - 10) // 2

    def to_prompt_block(self) -> str:
        enemies_str = "\n  ".join(str(e) for e in self.enemies) if self.enemies else "None"
        inv_str = ", ".join(self.inventory) if self.inventory else "Empty"
        return f"""\
CURRENT GAME STATE (authoritative — do not contradict):
  PC: {self.pc_name}, Level {self.pc_level} {self.pc_class} | HP: {self.pc_hp}/{self.pc_max_hp} | AC: {self.pc_ac}
  STR {self.pc_str} ({'+' if self.str_mod >= 0 else ''}{self.str_mod}) | DEX {self.pc_dex} ({'+' if self.dex_mod >= 0 else ''}{self.dex_mod}) | CON {self.pc_con} | INT {self.pc_int} | WIS {self.pc_wis} | CHA {self.pc_cha}
  Inventory: {inv_str}
  Equipment: {self.equipment}
  Enemies:
  {enemies_str}
  Scene: {self.location} | Light: {self.light} | Time: {self.time}
  Previous turn mechanics: {self.last_mechanics}"""

    def apply_mechanics(self, mechanics_text: str) -> list:
        """Parse [MECHANICS] tags and apply them deterministically. Returns log of changes.

        Includes two anti-cheat safeguards (trickster hardening, 2026-08-20):
        - Waste-potion guard: if any ITEM_USED names an item NOT in inventory, skip ALL
          ITEM_USED tags that turn (prevents a different valid item being silently consumed).
        - Control-NPC guard: ENEMY_DEAD is only applied if the same turn's mechanics
          include roll evidence for that enemy (an ENEMY_HP change or a ROLL_REQUEST).
        """
        changes = []
        lines = [l.strip() for l in mechanics_text.strip().split("\n")
                 if l.strip() and l.strip() != "NO_MECHANICS"]

        # --- Pre-scan: collect ITEM_USED items and roll-evidence enemies ---
        item_used_tags = []  # list of (line_index, item_name)
        item_used_invalid = False  # any named item not in inventory?
        enemies_with_roll_evidence = set()  # enemy names lowercased

        for line in lines:
            if ":" not in line:
                continue
            tag, val = line.split(":", 1)
            tag = tag.strip().upper()
            val = val.strip()

            if tag == "ITEM_USED":
                item = val.strip()
                item_used_tags.append(item)
                if item not in self.inventory:
                    item_used_invalid = True

            elif tag == "ENEMY_HP":
                # format: <name>,<current>/<max> — damage was dealt (roll evidence)
                parts = val.split(",")
                if len(parts) == 2:
                    enemies_with_roll_evidence.add(parts[0].strip().lower())

            elif tag == "ROLL_REQUEST":
                # A roll was requested this turn — counts as roll evidence for ALL enemies
                # (the DM wouldn't request a roll unless an action targeting an enemy happened)
                for e in self.enemies:
                    enemies_with_roll_evidence.add(e.name.lower())

        # --- Apply tags, using pre-scan results to guard against cheats ---
        for line in lines:
            if ":" not in line:
                changes.append(f"  [unparseable] {line}")
                continue
            tag, val = line.split(":", 1)
            tag = tag.strip().upper()
            val = val.strip()

            if tag == "HP_CHANGE":
                try:
                    amt = int(val)
                    old_hp = self.pc_hp
                    self.pc_hp = max(0, min(self.pc_max_hp, self.pc_hp + amt))
                    changes.append(f"  PC HP: {old_hp} -> {self.pc_hp} ({'+' if amt >= 0 else ''}{amt})")
                except ValueError:
                    changes.append(f"  [bad HP_CHANGE value] {val}")

            elif tag == "ENEMY_HP":
                # format: <name>,<current>/<max>
                parts = val.split(",")
                if len(parts) == 2:
                    name = parts[0].strip()
                    hp_parts = parts[1].strip().split("/")
                    if len(hp_parts) == 2:
                        for e in self.enemies:
                            if e.name.lower() == name.lower():
                                try:
                                    e.hp = max(0, int(hp_parts[0]))
                                    changes.append(f"  {e.name} HP -> {e.hp}/{e.max_hp}")
                                except ValueError:
                                    changes.append(f"  [bad ENEMY_HP] {val}")
                                break

            elif tag == "ENEMY_DEAD":
                name = val.strip()
                # Control-NPC guard: only apply if there's roll evidence for this enemy
                if name.lower() not in enemies_with_roll_evidence:
                    changes.append(f"  [REJECTED ENEMY_DEAD — no roll evidence] {name}")
                    continue
                for e in self.enemies:
                    if e.name.lower() == name.lower() and e.alive:
                        e.hp = 0
                        changes.append(f"  {e.name} marked DEAD")
                        break

            elif tag == "ITEM_USED":
                item = val.strip()
                # Waste-potion guard: if ANY item used this turn was invalid, reject ALL
                if item_used_invalid:
                    if item in self.inventory:
                        changes.append(f"  [REJECTED ITEM_USED — invalid item in same turn] {item}")
                    else:
                        changes.append(f"  [ITEM_USED but not in inventory] {item}")
                elif item in self.inventory:
                    self.inventory.remove(item)
                    changes.append(f"  Used: {item}")
                else:
                    changes.append(f"  [ITEM_USED but not in inventory] {item}")

            elif tag == "ITEM_GAINED":
                item = val.strip()
                self.inventory.append(item)
                changes.append(f"  Gained: {item}")

            elif tag == "SPELL_SLOT_USED":
                changes.append(f"  Spell slot used: {val}")

            elif tag == "CONDITION":
                changes.append(f"  Condition: {val}")

            elif tag == "ROLL_REQUEST":
                changes.append(f"  [Roll requested] {val}")

            else:
                changes.append(f"  [unknown tag] {tag}:{val}")

        self.last_mechanics = mechanics_text.strip()[:200] if mechanics_text.strip() else "NO_MECHANICS"
        return changes


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def parse_response(text: str) -> dict:
    """Extract the 4 sections from the LLM response.
    Handles markdown bold (**[TAG]**), plain [TAG], and thinking blocks."""
    sections = {"NARRATIVE": "", "MECHANICS": "", "SUGGESTIONS": "", "CHRONICLE": ""}

    # Strip thinking/reasoning blocks if present (some models emit these)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    for tag in sections:
        # Match [TAG] or **[TAG]** with optional markdown formatting
        pattern = rf"\*{{0,2}}\[{tag}\]\*{{0,2}}\s*(.*?)(?=\*{{0,2}}\[(?:NARRATIVE|MECHANICS|SUGGESTIONS|CHRONICLE)\]|$)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            sections[tag] = match.group(1).strip()
    return sections


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

def make_client(provider: str) -> OpenAI:
    cfg = PROVIDERS[provider]
    api_key = os.environ.get(cfg["env_var"])
    if not api_key or api_key.startswith("your_") or api_key.endswith("_here"):
        print(f"ERROR: {cfg['env_var']} not set. Copy glm-work/.env.example to "
              f"glm-work/.env and fill in your key.", file=sys.stderr)
        print(f"Get a free key at:", file=sys.stderr)
        if provider == "groq":
            print(f"  https://console.groq.com", file=sys.stderr)
        elif provider == "sambanova":
            print(f"  https://cloud.sambanova.ai", file=sys.stderr)
        elif provider == "cerebras":
            print(f"  https://cloud.cerebras.ai", file=sys.stderr)
        elif provider == "openrouter":
            print(f"  https://openrouter.ai", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=api_key, base_url=cfg["base_url"])


def dm_turn(client: OpenAI, model: str, system_prompt: str,
            state_block: str, history: list, player_input: str,
            temperature: float = 0.7, max_tokens: int = 2000,
            max_retries: int = 3, provider: str = "",
            cost_tracker: CostTracker | None = None) -> tuple:
    """Call the LLM for one DM turn. Returns (response_text, elapsed_seconds, token_usage).
    Retries on rate-limit errors with exponential backoff.
    If cost_tracker is provided, records the call cost and checks budget."""
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": f"{state_block}\n\nPLAYER ACTION:\n{player_input}",
    })

    for attempt in range(max_retries + 1):
        try:
            t0 = time.time()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed = time.time() - t0
            text = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
            # Track cost if a tracker is provided
            if cost_tracker:
                call_cost = cost_tracker.add_call(
                    provider, model,
                    usage["prompt_tokens"], usage["completion_tokens"]
                )
                usage["cost_usd"] = round(call_cost, 6)
                if not cost_tracker.check_budget():
                    print(f"  [BUDGET EXCEEDED] {cost_tracker.summary()} — stopping after this call")
                    raise BudgetExceeded(f"Budget limit reached: {cost_tracker.summary()}")
            return text, elapsed, usage
        except BudgetExceeded:
            raise
        except Exception as e:
            if attempt < max_retries and "429" in str(e):
                wait = (attempt + 1) * 5
                print(f"  Rate limited, waiting {wait}s before retry ({attempt+1}/{max_retries})...")
                time.sleep(wait)
                continue
            raise


# ---------------------------------------------------------------------------
# Test scenario
# ---------------------------------------------------------------------------

def make_initial_state() -> GameState:
    return GameState(
        enemies=[
            Enemy("Goblin Scout", hp=7, max_hp=7, ac=15),
            Enemy("Goblin Raider", hp=7, max_hp=7, ac=15),
        ],
    )


# 10 scripted player actions for reproducible testing
SCRIPTED_ACTIONS = [
    "I push open the tavern door and step inside, hand on my sword hilt.",
    "I draw my longsword and attack the nearest goblin. I rolled a 14 on my attack roll.",
    "I use my bonus action to look around for other threats. I rolled a 12 for Perception.",
    "The goblin scout swings at me — go ahead and roll for it, then I'll respond.",
    "I attack the goblin raider. I rolled a 19 on my attack roll.",
    "I roll damage for my longsword: 1d8+3 = I got a 5, so 8 damage total.",
    "I'm hurt. I drink my Health Potion as my action this turn.",
    "I try to intimidate the surviving goblin into surrendering. I rolled a 10 on Intimidation.",
    "If the goblin surrenders, I tie it up with my rope and question it about why it attacked.",
    "I search the bodies of the dead goblins for anything useful.",
]


def grade_turn(turn_num: int, sections: dict, state: GameState, player_input: str) -> list:
    """Check for common failure modes. Returns list of issues found."""
    issues = []

    # Check all 4 sections present
    missing = [t for t in ["NARRATIVE", "MECHANICS", "SUGGESTIONS", "CHRONICLE"]
               if not sections[t]]
    if missing:
        issues.append(f"Missing sections: {missing}")

    # Check roll-before-outcome: did the narrative mention damage/HP before a roll was provided?
    narrative = sections["NARRATIVE"].lower()
    mechanics = sections["MECHANICS"]
    if "damage" in narrative and "HP_CHANGE" in mechanics:
        # Check if the player provided a roll this turn
        roll_provided = any(w in player_input.lower() for w in
                            ["rolled", "roll", "i got a", "natural", "d20"])
        if not roll_provided and "ROLL_REQUEST" not in mechanics:
            issues.append("Narrative mentions damage but no roll was provided or requested")

    # Check NO_MECHANICS vs actual mechanics
    if sections["MECHANICS"].strip() == "NO_MECHANICS" and turn_num > 1:
        # Some turns legitimately have no mechanics, but flag for review
        pass

    return issues


def run_scripted_test(client: OpenAI, model: str, provider: str,
                      verbose: bool = True,
                      cost_tracker: CostTracker | None = None) -> dict:
    """Run the 10-turn scripted test. Returns results dict."""
    state = make_initial_state()
    history = []
    results = {
        "model": model,
        "provider": provider,
        "turns": [],
        "final_state": {},
        "issues": [],
        "total_tokens": 0,
        "total_time": 0,
        "total_cost_usd": 0.0,
    }

    print(f"\n{'='*70}")
    print(f"  DM BRAIN TEST: {model} on {PROVIDERS[provider]['label']}")
    if cost_tracker:
        print(f"  Budget: {cost_tracker.summary()}")
    print(f"{'='*70}\n")

    for i, action in enumerate(SCRIPTED_ACTIONS, 1):
        state_block = state.to_prompt_block()
        print(f"--- Turn {i}/10 ---")
        print(f"Player: {action}\n")

        try:
            text, elapsed, usage = dm_turn(
                client, model, SYSTEM_PROMPT, state_block, history, action,
                provider=provider, cost_tracker=cost_tracker
            )
        except Exception as e:
            err = f"Turn {i} API error: {e}"
            print(f"  ERROR: {e}\n")
            results["turns"].append({"turn": i, "error": str(e)})
            results["issues"].append(err)
            break

        sections = parse_response(text)
        changes = state.apply_mechanics(sections["MECHANICS"])
        issues = grade_turn(i, sections, state, action)

        results["turns"].append({
            "turn": i,
            "player_input": action,
            "narrative": sections["NARRATIVE"][:500],
            "mechanics": sections["MECHANICS"],
            "suggestions": sections["SUGGESTIONS"],
            "chronicle": sections["CHRONICLE"],
            "state_changes": changes,
            "issues": issues,
            "elapsed": round(elapsed, 2),
            "tokens": usage,
        })
        results["total_tokens"] += usage.get("total_tokens", 0)
        results["total_time"] += elapsed
        results["issues"].extend(f"Turn {i}: {iss}" for iss in issues)

        if verbose:
            print(f"[NARRATIVE]\n{sections['NARRATIVE']}\n")
            if sections["MECHANICS"]:
                print(f"[MECHANICS]\n{sections['MECHANICS']}\n")
            if sections["SUGGESTIONS"]:
                print(f"[SUGGESTIONS]\n{sections['SUGGESTIONS']}\n")
            if changes:
                print(f"[STATE CHANGES]")
                for c in changes:
                    print(c)
            print(f"[Time: {elapsed:.1f}s | Tokens: {usage.get('total_tokens', '?')}]\n")

        history.append({"role": "user", "content": action})
        history.append({"role": "assistant", "content": text})

        # Small delay to respect rate limits (free tiers have low TPM)
        time.sleep(5)

    # Final state
    results["final_state"] = {
        "pc_hp": f"{state.pc_hp}/{state.pc_max_hp}",
        "inventory": list(state.inventory),
        "enemies": [str(e) for e in state.enemies],
        "chronicle": state.chronicle,
    }

    print(f"\n{'='*70}")
    print(f"  TEST COMPLETE: {model}")
    print(f"{'='*70}")
    print(f"\nFINAL STATE:")
    print(f"  PC HP: {state.pc_hp}/{state.pc_max_hp}")
    print(f"  Inventory: {', '.join(state.inventory)}")
    for e in state.enemies:
        print(f"  Enemy: {e}")
    print(f"\nTotal time: {results['total_time']:.1f}s")
    print(f"Total tokens: {results['total_tokens']}")
    if results["issues"]:
        print(f"\nISSUES FOUND ({len(results['issues'])}):")
        for iss in results["issues"]:
            print(f"  - {iss}")
    else:
        print(f"\nNo issues detected by automated grading.")
    print()

    return results


def run_interactive(client: OpenAI, model: str, provider: str):
    """Interactive mode — player types actions."""
    state = make_initial_state()
    history = []
    turn = 0

    print(f"\n{'='*70}")
    print(f"  INTERACTIVE DM SESSION: {model} on {PROVIDERS[provider]['label']}")
    print(f"  Type 'quit' to exit, 'state' to see current state.")
    print(f"{'='*70}\n")

    # Opening narration
    opening_input = "I enter the tavern and look around."
    state_block = state.to_prompt_block()
    text, elapsed, usage = dm_turn(
        client, model, SYSTEM_PROMPT, state_block, history, opening_input
    )
    sections = parse_response(text)
    state.apply_mechanics(sections["MECHANICS"])
    print(f"[NARRATIVE]\n{sections['NARRATIVE']}\n")
    if sections["SUGGESTIONS"]:
        print(f"[SUGGESTIONS]\n{sections['SUGGESTIONS']}\n")
    history.append({"role": "user", "content": opening_input})
    history.append({"role": "assistant", "content": text})
    turn = 1

    while True:
        try:
            action = input(f"\n[Turn {turn+1}] What do you do? > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break
        if action.lower() in ("quit", "exit", "q"):
            break
        if action.lower() == "state":
            print(state.to_prompt_block())
            continue
        if not action:
            continue

        state_block = state.to_prompt_block()
        try:
            text, elapsed, usage = dm_turn(
                client, model, SYSTEM_PROMPT, state_block, history, action
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        sections = parse_response(text)
        changes = state.apply_mechanics(sections["MECHANICS"])
        print(f"\n[NARRATIVE]\n{sections['NARRATIVE']}\n")
        if sections["MECHANICS"] and sections["MECHANICS"] != "NO_MECHANICS":
            print(f"[MECHANICS]\n{sections['MECHANICS']}\n")
        if sections["SUGGESTIONS"]:
            print(f"[SUGGESTIONS]\n{sections['SUGGESTIONS']}\n")
        if changes:
            print(f"[STATE CHANGES]")
            for c in changes:
                print(c)
        print(f"[{elapsed:.1f}s | {usage.get('total_tokens', '?')} tokens]")

        history.append({"role": "user", "content": action})
        history.append({"role": "assistant", "content": text})
        turn += 1
        time.sleep(1)


def run_comparison(specs: list, verbose: bool = True):
    """Run the same test scenario on multiple model specs and compare."""
    all_results = {}
    for spec in specs:
        provider, model = spec.split(":", 1)
        if provider not in PROVIDERS:
            print(f"Unknown provider: {provider}")
            continue
        client = make_client(provider)
        results = run_scripted_test(client, model, provider, verbose=verbose)
        all_results[spec] = results

        # Save results to file
        out_path = Path(__file__).parent / "outputs" / f"dm_test_{provider}_{model.replace('/', '_')}.json"
        out_path.parent.mkdir(exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"  Results saved to {out_path}\n")

    # Summary comparison
    if len(all_results) > 1:
        print(f"\n{'='*70}")
        print(f"  COMPARISON SUMMARY")
        print(f"{'='*70}")
        print(f"{'Model':<35} {'Time':>8} {'Tokens':>10} {'Issues':>8} {'Final HP':>10}")
        print(f"{'-'*35} {'-'*8} {'-'*10} {'-'*8} {'-'*10}")
        for spec, r in all_results.items():
            hp = r["final_state"].get("pc_hp", "?")
            print(f"{spec:<35} {r['total_time']:>7.1f}s {r['total_tokens']:>10} "
                  f"{len(r['issues']):>8} {hp:>10}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_list_models(client: OpenAI, provider: str):
    """List available models on a provider."""
    print(f"\nModels available on {PROVIDERS[provider]['label']}:\n")
    try:
        models = client.models.list()
        for m in sorted(models.data, key=lambda x: x.id):
            print(f"  {m.id}")
    except Exception as e:
        print(f"  Error listing models: {e}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Test open-weight LLMs as D&D DM brains via free-tier API providers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python test_api_dm.py --provider groq --list-models
  python test_api_dm.py --provider groq --model gpt-oss-120b
  python test_api_dm.py --provider groq --model qwen3-32b --interactive
  python test_api_dm.py --compare groq:gpt-oss-120b groq:qwen3-32b
""",
    )
    parser.add_argument("--provider", choices=list(PROVIDERS.keys()),
                        help="API provider to use")
    parser.add_argument("--model", help="Model name on the provider")
    parser.add_argument("--list-models", action="store_true",
                        help="List available models on the provider, then exit")
    parser.add_argument("--interactive", action="store_true",
                        help="Interactive mode (type your own actions)")
    parser.add_argument("--compare", nargs="+", metavar="PROVIDER:MODEL",
                        help="Compare multiple provider:model specs on the same scenario")
    parser.add_argument("--quiet", action="store_true",
                        help="Less verbose output (summary only)")
    args = parser.parse_args()

    # Load .env from glm-work/ directory
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    if args.compare:
        run_comparison(args.compare, verbose=not args.quiet)
        return

    if not args.provider:
        parser.error("--provider is required (unless using --compare)")

    client = make_client(args.provider)

    if args.list_models:
        cmd_list_models(client, args.provider)
        return

    if not args.model:
        parser.error("--model is required (or use --list-models to see options)")

    if args.interactive:
        run_interactive(client, args.model, args.provider)
    else:
        results = run_scripted_test(client, args.model, args.provider,
                                    verbose=not args.quiet)
        # Save results
        out_path = Path(__file__).parent / "outputs" / f"dm_test_{args.provider}_{args.model.replace('/', '_')}.json"
        out_path.parent.mkdir(exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
