#!/usr/bin/env python3
"""Standing adversarial test for Narrator v0's rules lawyer.

Runs the 10 "trickster" cheating attempts from test_trickster.py against
the configured DM model, using the v0 system prompt (which includes the
[AUDIO] section). The rules lawyer (deterministic Python state engine)
should catch and reject all invalid state changes regardless of what the
LLM says.

Usage:
  python -m narrator_v0.run_trickster --model gemini-3.5-flash-lite
  python -m narrator_v0.run_trickster --model openai/gpt-oss-120b --provider groq
  python -m narrator_v0.run_trickster --model gemini-3.5-flash-lite --verbose

Run this before a real play session to verify the rules lawyer is trustworthy.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

# Ensure glm-work/ is on the path
GLM_WORK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GLM_WORK))

from dotenv import load_dotenv

from . import config
from .dm_engine import (
    GameState,
    Enemy,
    parse_response_v0,
    make_client_v0,
    dm_turn_v0,
    SYSTEM_PROMPT_V0,
)

# Import the proven trickster scenarios and grading from test_trickster.py
from test_trickster import (
    TRICKSTER_ACTIONS,
    make_trickster_state,
    grade_trick,
)


def run_trickster_test(client, model: str, provider: str, verbose: bool = True) -> dict:
    """Run all 10 trickster scenarios against the model + rules lawyer.

    Returns results dict with per-trick breakdown and summary.
    """
    results = {
        "model": model,
        "provider": provider,
        "tricks": [],
        "total_resisted": 0,
        "total_score": 0,
        "max_score": 30,
        "errors": [],
    }

    print(f"\n{'='*70}")
    print(f"  TRICKSTER TEST: {model} on {config.PROVIDERS[provider]['label']}")
    print(f"  Using v0 system prompt (with [AUDIO] section)")
    print(f"{'='*70}\n")

    for i, (trick_name, player_input) in enumerate(TRICKSTER_ACTIONS, 1):
        state = make_trickster_state()
        state_before_hp = state.pc_hp
        state_before_inv = list(state.inventory)
        state_before_enemies = [(e.name, e.hp, e.alive) for e in state.enemies]

        print(f"--- Trick {i}/10: {trick_name} ---")
        if verbose:
            print(f"  Player: {player_input}\n")

        try:
            # Single turn, no history (each trick is a fresh attempt)
            text, elapsed, usage = dm_turn_v0(
                client=client,
                model=model,
                state=state,
                history=[],
                player_input=player_input,
            )
        except Exception as e:
            err = f"Trick {i} ({trick_name}) API error: {e}"
            print(f"  ERROR: {e}\n")
            results["tricks"].append({
                "trick": trick_name, "error": str(e), "fell_for_it": None
            })
            results["errors"].append(err)
            continue

        sections = parse_response_v0(text)
        state_after_hp = state.pc_hp
        state_after_inv = list(state.inventory)
        state_after_enemies = [(e.name, e.hp, e.alive) for e in state.enemies]

        # Apply mechanics through the rules lawyer
        changes = state.apply_mechanics(sections["MECHANICS"])

        # Grade: did the rules lawyer catch the cheat?
        grade = grade_trick(
            trick_name, player_input, sections,
            # Reconstruct a "before" state for grading
            type("S", (), {
                "pc_hp": state_before_hp,
                "pc_max_hp": state.pc_max_hp,
                "inventory": state_before_inv,
                "enemies": [type("E", (), {"name": n, "hp": h, "alive": a})()
                           for n, h, a in state_before_enemies],
            })(),
            state,
        )

        results["tricks"].append({
            "trick": trick_name,
            "player_input": player_input,
            "narrative": sections["NARRATIVE"][:300],
            "mechanics": sections["MECHANICS"],
            "state_changes": changes,
            "fell_for_it": grade["fell_for_it"],
            "resistance_quality": grade["resistance_quality"],
            "how": grade["how"],
            "elapsed": round(elapsed, 2),
            "tokens": usage.get("total_tokens", 0) if usage else 0,
        })

        if not grade["fell_for_it"]:
            results["total_resisted"] += 1
        results["total_score"] += grade["resistance_quality"]

        if verbose:
            print(f"  [NARRATIVE] {sections['NARRATIVE'][:200]}...")
            print(f"  [MECHANICS] {sections['MECHANICS']}")
            print(f"  [STATE CHANGES] {changes}")
            print(f"  Result: {'RESISTED' if not grade['fell_for_it'] else 'FELL FOR IT'} "
                  f"(quality: {grade['resistance_quality']}/3)")
            if grade["how"]:
                print(f"  How: {grade['how']}")
            print(f"  [{elapsed:.1f}s | {usage.get('total_tokens', '?') if usage else '?'} tokens]\n")

        # Respect rate limits
        time.sleep(3)

    # Summary
    print(f"\n{'='*70}")
    print(f"  TRICKSTER TEST COMPLETE: {model}")
    print(f"{'='*70}")
    print(f"\n  Resisted: {results['total_resisted']}/10")
    print(f"  Score: {results['total_score']}/30")
    if results["total_resisted"] == 10:
        print(f"  Rating: EXCELLENT — all tricks resisted")
    elif results["total_resisted"] >= 8:
        print(f"  Rating: GOOD — {10 - results['total_resisted']} trick(s) slipped through")
    else:
        print(f"  Rating: POOR — rules lawyer needs review")
    if results["errors"]:
        print(f"\n  Errors: {len(results['errors'])}")
        for e in results["errors"]:
            print(f"    - {e}")
    print()

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Run the trickster adversarial test against the DM brain + rules lawyer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", default=config.DEFAULT_MODEL,
                        help=f"Model name (default: {config.DEFAULT_MODEL})")
    parser.add_argument("--provider", default=None,
                        help="API provider (auto-detected from model name if omitted)")
    parser.add_argument("--verbose", action="store_true", default=True,
                        help="Verbose output (default: on)")
    parser.add_argument("--quiet", action="store_true",
                        help="Less verbose output (summary only)")
    parser.add_argument("--save", action="store_true",
                        help="Save results to outputs/narrator_v0/trickster_results.json")
    args = parser.parse_args()

    load_dotenv(config.ENV_FILE)

    provider = args.provider or config.detect_provider(args.model)
    print(f"Provider: {provider}")

    try:
        client = make_client_v0(provider=provider, model=args.model)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    results = run_trickster_test(
        client=client,
        model=args.model,
        provider=provider,
        verbose=not args.quiet,
    )

    if args.save:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = config.OUTPUT_DIR / "trickster_results.json"
        with open(out_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
