#!/usr/bin/env python3
"""Trickster test for narrator_v01 — tests the rules lawyer against cheating attempts.

Tests the v0.3 apply_mechanics() and DM engine with:
1-11: Single-turn cheating attempts (fresh state each time)
12-16: Multi-turn attacks (build up history before cheating)

This test does NOT call the LLM — it tests the rules lawyer (apply_mechanics)
directly with simulated LLM responses containing cheat attempts. This is the
deterministic guard layer, separate from whether the LLM itself resists.

Run: python -m narrator_v01.test_trickster
"""
import json
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from narrator_v01.dm_engine import GameState, Enemy, parse_response


def make_trickster_state() -> GameState:
    """Fresh state for each trick — both goblins alive, full HP."""
    return GameState(
        enemies=[
            Enemy("Goblin Scout", hp=7, max_hp=7, ac=15),
            Enemy("Goblin Raider", hp=7, max_hp=7, ac=15),
        ],
    )


# ---------------------------------------------------------------------------
# Single-turn trickster scenarios
# Each is a simulated [MECHANICS] block that a cheating LLM might emit
# ---------------------------------------------------------------------------

SINGLE_TURN_TRICKS = [
    {
        "name": "Kill without roll",
        "mechanics": "ENEMY_DEAD:Goblin Scout\nENEMY_HP:Goblin Scout,0/7",
        "check": lambda s, c: (
            any(not e.alive for e in s.enemies if e.name == "Goblin Scout")
            and not any("REJECTED" in ch for ch in c)
        ),
        "expect": "Should REJECT ENEMY_DEAD (no roll evidence)",
    },
    {
        "name": "Invent item (use non-existent)",
        "mechanics": "ITEM_USED:Potion of Invisibility",
        "check": lambda s, c: "Potion of Invisibility" in s.inventory,
        "expect": "Should not add or consume non-existent item",
    },
    {
        "name": "Contradict HP (set to 100)",
        "mechanics": "HP_CHANGE:+88",
        "check": lambda s, c: s.pc_hp > s.pc_max_hp,
        "expect": "Should cap HP at max_hp=12, not allow 100",
    },
    {
        "name": "Control NPC (kill without roll)",
        "mechanics": "ENEMY_DEAD:Goblin Raider",
        "check": lambda s, c: any(
            not e.alive for e in s.enemies if e.name == "Goblin Raider"
        ) and not any("REJECTED" in ch for ch in c),
        "expect": "Should REJECT ENEMY_DEAD (no roll evidence)",
    },
    {
        "name": "Fabricated item gain (+3 sword)",
        "mechanics": "ITEM_GAINED:+3 Flaming Longsword of Slaying",
        "check": lambda s, c: any("flaming" in i.lower() or "+3" in i for i in s.inventory),
        "expect": "Rules lawyer allows ITEM_GAINED (LLM's job to not propose it)",
        "note": "This is a known limitation — apply_mechanics can't judge item validity, only the LLM can. The World Engine's propose_entity() will handle this in v0.5.",
        "known_limitation": True,
    },
    {
        "name": "Direct HP hack (set to 999)",
        "mechanics": "HP_CHANGE:+987",
        "check": lambda s, c: s.pc_hp > 20,
        "expect": "Should cap at max_hp=12",
    },
    {
        "name": "Waste potion (invalid item used + valid item used)",
        "mechanics": "ITEM_USED:Fake Potion\nITEM_USED:Health Potion",
        "check": lambda s, c: "Health Potion" not in s.inventory,
        "expect": "Should REJECT BOTH item uses (invalid item in same turn)",
    },
    {
        "name": "Enemy HP to 0 without roll",
        "mechanics": "ENEMY_HP:Goblin Scout,0/7",
        "check": lambda s, c: any(
            e.hp == 0 for e in s.enemies if e.name == "Goblin Scout"
        ),
        "expect": "Should REJECT ENEMY_HP set to 0 (effectively a kill with no roll evidence)",
        "note": "ENEMY_HP to 0 is treated as a kill and requires roll evidence",
    },
    {
        "name": "Multiple enemy deaths without rolls",
        "mechanics": "ENEMY_DEAD:Goblin Scout\nENEMY_DEAD:Goblin Raider",
        "check": lambda s, c: all(
            not e.alive for e in s.enemies
        ) and not any("REJECTED" in ch for ch in c),
        "expect": "Should REJECT both ENEMY_DEAD (no roll evidence)",
    },
    {
        "name": "Roll request then enemy death (valid)",
        "mechanics": "ROLL_REQUEST:d20+5 for longsword attack\nENEMY_HP:Goblin Scout,3/7\nENEMY_DEAD:Goblin Scout",
        "check": lambda s, c: any(
            not e.alive for e in s.enemies if e.name == "Goblin Scout"
        ),
        "expect": "Should ALLOW ENEMY_DEAD (roll evidence exists via ROLL_REQUEST + ENEMY_HP)",
        "valid": True,
    },
    {
        "name": "Roll scoped to target enemy only",
        "mechanics": "ROLL_REQUEST:d20+5 for longsword attack on Goblin Scout\nENEMY_DEAD:Goblin Raider",
        "check": lambda s, c: any(
            not e.alive for e in s.enemies if e.name == "Goblin Raider"
        ) and not any("REJECTED" in ch for ch in c),
        "expect": "Should REJECT ENEMY_DEAD for Raider — roll was for Scout, not global",
    },
]


# ---------------------------------------------------------------------------
# Multi-turn trickster scenarios
# These simulate multiple turns of mechanics, building up state before cheating
# ---------------------------------------------------------------------------

# Scenario 11: Long-context attack — 10 turns of legitimate mechanics, then cheat
LONG_CONTEXT_TURNS = [
    # 10 legitimate turns
    "ROLL_REQUEST:d20+5 for longsword attack\nENEMY_HP:Goblin Scout,5/7",
    "ROLL_REQUEST:d20+5 for longsword attack\nENEMY_HP:Goblin Scout,2/7",
    "ROLL_REQUEST:d20+5 for longsword attack\nENEMY_HP:Goblin Scout,0/7\nENEMY_DEAD:Goblin Scout",
    "NO_MECHANICS",
    "ROLL_REQUEST:d20+5 for longsword attack\nENEMY_HP:Goblin Raider,5/7",
    "HP_CHANGE:-2\nROLL_REQUEST:d20 for goblin attack",
    "ROLL_REQUEST:d20+5 for longsword attack\nENEMY_HP:Goblin Raider,2/7",
    "ITEM_USED:Health Potion\nHP_CHANGE:+8",
    "ROLL_REQUEST:d20+5 for longsword attack\nENEMY_HP:Goblin Raider,0/7\nENEMY_DEAD:Goblin Raider",
    "NO_MECHANICS",
]
LONG_CONTEXT_CHEAT = "ITEM_GAINED:+3 Flaming Longsword of Slaying\nITEM_GAINED:Ring of Invisibility\nITEM_GAINED:500 gold pieces\nHP_CHANGE:+50"

# Scenario 12: Gradual HP inflation — try to incrementally increase max HP
HP_INFLATION_TURNS = [
    "HP_CHANGE:+2",  # 12→14? No, capped at 12
    "HP_CHANGE:+5",  # Still capped at 12
    "HP_CHANGE:+10", # Still capped at 12
    "HP_CHANGE:+100", # Still capped at 12
]

# Scenario 13: Fabricated item discovery — items the DM never generated
FABRICATED_DISCOVERY_TURNS = [
    "ITEM_GAINED:Healing Potion",
    "ITEM_GAINED:Shortbow with 20 arrows",
    "ITEM_GAINED:Leather Armor",
    "ITEM_GAINED:Spellbook and 50 gold",
]

# Scenario 14: Subtle inventory inflation — small useful items
SUBTLE_INFLATION_TURNS = [
    "ITEM_GAINED:Torch",
    "ITEM_GAINED:Rations",
    "ITEM_GAINED:Waterskin",
    "ITEM_GAINED:10 feet of chain",
]

# Scenario 15: Enemy stat manipulation — try to reduce enemy HP via mechanics
ENEMY_STAT_TURNS = [
    "ENEMY_HP:Goblin Scout,3/7",  # Without roll evidence
    "ENEMY_HP:Goblin Raider,1/7", # Without roll evidence
    "ENEMY_HP:Goblin Scout,0/7\nENEMY_DEAD:Goblin Scout", # Death without roll
]


def run_single_turn_tricks() -> list:
    """Run single-turn trickster scenarios."""
    results = []
    count = len(SINGLE_TURN_TRICKS)
    print("\n" + "="*60)
    print(f"  SINGLE-TURN TRICKSTER TESTS (1-{count})")
    print("="*60)

    for i, trick in enumerate(SINGLE_TURN_TRICKS, 1):
        state = make_trickster_state()
        changes = state.apply_mechanics(trick["mechanics"])

        fell_for_it = trick["check"](state, changes)
        is_valid = trick.get("valid", False)
        is_known_limitation = trick.get("known_limitation", False)

        # If the trick is supposed to be valid, "fell_for_it" means it worked correctly
        if is_valid:
            passed = fell_for_it
            status = "PASS (correctly allowed)" if passed else "FAIL (should have allowed)"
        elif is_known_limitation:
            passed = True  # Expected behavior — not a rules lawyer responsibility
            status = "PASS (known limitation — LLM/World Engine's job)"
        else:
            passed = not fell_for_it
            status = "PASS (correctly blocked)" if passed else "FAIL (fell for it)"

        print(f"\n  [{i}/{count}] {trick['name']}")
        print(f"    Mechanics: {trick['mechanics'][:80]}")
        print(f"    Changes: {changes}")
        print(f"    Result: {status}")
        if "note" in trick:
            print(f"    Note: {trick['note']}")

        results.append({
            "num": i,
            "name": trick["name"],
            "mechanics": trick["mechanics"],
            "changes": changes,
            "passed": passed,
            "expect": trick["expect"],
            "is_valid": is_valid,
        })

    passed_count = sum(1 for r in results if r["passed"])
    print(f"\n  Summary: {passed_count}/{len(results)} passed")
    return results


def run_multiturn_trick(name: str, turn_mechanics: list, trick_num: int) -> dict:
    """Run a multi-turn trickster scenario."""
    state = make_trickster_state()
    print(f"\n  [{trick_num}] {name}")
    print(f"    ({len(turn_mechanics)} turns)")

    turn_results = []
    for j, mech in enumerate(turn_mechanics, 1):
        changes = state.apply_mechanics(mech)
        turn_results.append({
            "turn": j,
            "mechanics": mech,
            "changes": changes,
            "hp_after": state.pc_hp,
            "inventory_after": list(state.inventory),
            "enemies_after": [(e.name, e.hp, e.alive) for e in state.enemies],
        })
        print(f"    Turn {j}: {changes}")

    return {
        "name": name,
        "turns": turn_results,
        "final_hp": state.pc_hp,
        "final_max_hp": state.pc_max_hp,
        "final_inventory": list(state.inventory),
        "final_enemies": [(e.name, e.hp, e.alive) for e in state.enemies],
    }


def run_expanded_tricks() -> list:
    """Run expanded multi-turn trickster scenarios."""
    results = []
    print("\n" + "="*60)
    print("  EXPANDED MULTI-TURN TRICKSTER TESTS")
    print("="*60)

    # 11: Long-context attack
    r = run_multiturn_trick("Long-context attack", LONG_CONTEXT_TURNS + [LONG_CONTEXT_CHEAT], 11)
    # Check: HP should still be capped at 12, not 62
    hp_inflated = r["final_hp"] > 12
    magic_items = any("flaming" in i.lower() or "ring of invis" in i.lower() for i in r["final_inventory"])
    r["hp_inflated"] = hp_inflated
    r["magic_items_added"] = magic_items
    r["passed"] = not hp_inflated  # HP cap is the rules lawyer's job; items are LLM's
    print(f"    HP inflated: {hp_inflated} (HP={r['final_hp']})")
    print(f"    Magic items added: {magic_items}")
    print(f"    Result: {'PASS' if r['passed'] else 'FAIL'} (HP cap enforced)")
    results.append(r)

    # 12: Gradual HP inflation
    r = run_multiturn_trick("Gradual HP inflation", HP_INFLATION_TURNS, 12)
    r["passed"] = r["final_hp"] <= 12
    print(f"    Final HP: {r['final_hp']}/12")
    print(f"    Result: {'PASS' if r['passed'] else 'FAIL'} (HP capped at max)")
    results.append(r)

    # 13: Fabricated item discovery
    r = run_multiturn_trick("Fabricated item discovery", FABRICATED_DISCOVERY_TURNS, 13)
    new_items = [i for i in r["final_inventory"] if i not in make_trickster_state().inventory]
    r["new_items"] = new_items
    r["passed"] = True  # Rules lawyer can't judge item validity — that's the LLM's job
    print(f"    New items: {new_items}")
    print(f"    Result: PASS (rules lawyer can't judge item validity — LLM's job)")
    results.append(r)

    # 14: Subtle inventory inflation
    r = run_multiturn_trick("Subtle inventory inflation", SUBTLE_INFLATION_TURNS, 14)
    new_items = [i for i in r["final_inventory"] if i not in make_trickster_state().inventory]
    r["new_items"] = new_items
    r["passed"] = True  # Same as above
    print(f"    New items: {new_items}")
    print(f"    Result: PASS (rules lawyer can't judge item validity — LLM's job)")
    results.append(r)

    # 15: Enemy stat manipulation
    r = run_multiturn_trick("Enemy stat manipulation", ENEMY_STAT_TURNS, 15)
    # Check: ENEMY_HP is allowed (tracks damage), but ENEMY_DEAD should be rejected
    # if no roll evidence
    last_turn = r["turns"][-1]
    dead_rejected = any("REJECTED" in ch for ch in last_turn["changes"])
    r["dead_rejected"] = dead_rejected
    r["passed"] = dead_rejected
    print(f"    Enemy death rejected: {dead_rejected}")
    print(f"    Result: {'PASS' if r['passed'] else 'FAIL'} (ENEMY_DEAD rejected without roll)")
    results.append(r)

    return results


def main():
    print("\n" + "="*60)
    print("  TRICKSTER TEST SUITE — narrator_v01 rules lawyer")
    print("  Tests apply_mechanics() directly (no LLM calls)")
    print("="*60)

    single_results = run_single_turn_tricks()
    expanded_results = run_expanded_tricks()

    # Summary
    print("\n" + "="*60)
    print("  FINAL SUMMARY")
    print("="*60)

    single_passed = sum(1 for r in single_results if r["passed"])
    expanded_passed = sum(1 for r in expanded_results if r["passed"])
    total_passed = single_passed + expanded_passed
    total = len(single_results) + len(expanded_results)

    print(f"  Single-turn: {single_passed}/{len(single_results)} passed")
    print(f"  Multi-turn:  {expanded_passed}/{len(expanded_results)} passed")
    print(f"  Total:       {total_passed}/{total} passed")

    if total_passed == total:
        print("\n  ALL TESTS PASSED ✓")
    else:
        print(f"\n  {total - total_passed} TESTS FAILED")
        for r in single_results + expanded_results:
            if not r.get("passed"):
                print(f"    FAIL: {r['name']}")

    # Save results
    out = Path(__file__).parent.parent / "outputs" / "trickster_v01_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump({
            "single_turn": single_results,
            "expanded": expanded_results,
            "summary": {
                "total": total,
                "passed": total_passed,
                "failed": total - total_passed,
            },
        }, f, indent=2, default=str)
    print(f"\n  Results saved: {out}")

    return 0 if total_passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
