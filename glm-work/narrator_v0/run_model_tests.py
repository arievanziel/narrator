#!/usr/bin/env python3
"""Comprehensive model comparison test for Narrator v0.

For each model:
1. Runs the 10-scenario trickster adversarial test (cheat resistance)
2. Runs a 3-turn scripted play scenario (narration quality + format adherence)
3. Generates audio for the scripted scenario (Qwen3 TTS + SFX + music)
4. Saves all results to JSON + WAV files

Output structure:
  outputs/narrator_v0/model_comparison/
    {model_id}/
      trickster_results.json
      scripted_results.json
      scripted_audio/
        turn_001.wav
        turn_002.wav
        turn_003.wav
      scripted_responses.txt   (human-readable transcript)

Usage:
  python -m narrator_v0.run_model_tests
  python -m narrator_v0.run_model_tests --models gemini-3.5-flash-lite openai/gpt-oss-120b
  python -m narrator_v0.run_model_tests --no-audio  # skip audio generation
  python -m narrator_v0.run_model_tests --skip-trickster  # skip trickster test
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
    make_initial_state,
    SYSTEM_PROMPT_V0,
)

# Import trickster components
from test_trickster import (
    TRICKSTER_ACTIONS,
    make_trickster_state,
    grade_trick,
)

# ---------------------------------------------------------------------------
# Models to test
# ---------------------------------------------------------------------------

MODELS_TO_TEST = [
    {
        "id": "gemini-flash-lite",
        "model": "gemini-3.5-flash-lite",
        "provider": "gemini",
        "label": "Gemini 3.5 Flash-Lite (best value)",
    },
    {
        "id": "gpt-oss-120b",
        "model": "openai/gpt-oss-120b",
        "provider": "groq",
        "label": "GPT-OSS 120B via Groq (best rule enforcement)",
    },
    {
        "id": "groq-compound",
        "model": "groq/compound",
        "provider": "groq",
        "label": "Groq/compound (best combat tracking)",
    },
    {
        "id": "gemini-flash",
        "model": "gemini-3.5-flash",
        "provider": "gemini",
        "label": "Gemini 3.5 Flash (best prose)",
    },
]

# ---------------------------------------------------------------------------
# Scripted play scenario — 3 turns for narration quality testing
# ---------------------------------------------------------------------------

SCRIPTED_ACTIONS = [
    "I push open the tavern door and step inside, hand on my sword hilt. The air smells of stale ale and smoke.",
    "I draw my longsword and challenge the goblins. 'Stand and fight, creatures!' I roll a 15 for my attack on the goblin scout.",
    "The goblin raider swings at me — go ahead and roll for it. Then I want to use my Health Potion if I'm hurt.",
]


# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

OUT_BASE = config.OUTPUT_DIR / "model_comparison"


def get_model_dir(model_id: str) -> Path:
    d = OUT_BASE / model_id
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Trickster test
# ---------------------------------------------------------------------------

def run_trickster_for_model(client, model: str, provider: str, model_dir: Path,
                            verbose: bool = True) -> dict:
    """Run the 10-scenario trickster test for one model."""
    results = {
        "model": model,
        "provider": provider,
        "tricks": [],
        "total_resisted": 0,
        "total_score": 0,
        "max_score": 30,
        "errors": [],
    }

    print(f"\n{'='*60}")
    print(f"  TRICKSTER TEST: {model}")
    print(f"{'='*60}")

    for i, (trick_name, player_input) in enumerate(TRICKSTER_ACTIONS, 1):
        state = make_trickster_state()
        state_before_hp = state.pc_hp
        state_before_inv = list(state.inventory)
        state_before_enemies = [(e.name, e.hp, e.alive) for e in state.enemies]

        print(f"  [{i}/10] {trick_name}...", end=" ", flush=True)

        try:
            text, elapsed, usage = dm_turn_v0(
                client=client, model=model, state=state,
                history=[], player_input=player_input,
            )
        except Exception as e:
            print(f"ERROR: {e}")
            results["tricks"].append({
                "trick": trick_name, "error": str(e), "fell_for_it": None
            })
            results["errors"].append(f"Trick {i}: {e}")
            time.sleep(3)
            continue

        sections = parse_response_v0(text)
        changes = state.apply_mechanics(sections["MECHANICS"])

        grade = grade_trick(
            trick_name, player_input, sections,
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

        status = "RESISTED" if not grade["fell_for_it"] else "FELL FOR IT"
        print(f"{status} (q={grade['resistance_quality']}/3)")

        time.sleep(3)  # respect rate limits

    print(f"  Result: {results['total_resisted']}/10 resisted, "
          f"score {results['total_score']}/30")

    # Save
    with open(model_dir / "trickster_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results


# ---------------------------------------------------------------------------
# Scripted play scenario
# ---------------------------------------------------------------------------

def run_scripted_for_model(client, model: str, provider: str, model_dir: Path,
                           generate_audio: bool = True, verbose: bool = True) -> dict:
    """Run the 3-turn scripted play scenario for one model."""
    results = {
        "model": model,
        "provider": provider,
        "turns": [],
        "total_tokens": 0,
        "total_time": 0,
        "final_state": {},
    }

    print(f"\n{'='*60}")
    print(f"  SCRIPTED SCENARIO: {model}")
    print(f"{'='*60}")

    state = make_initial_state()
    history = []
    audio_dir = model_dir / "scripted_audio"
    audio_dir.mkdir(exist_ok=True)

    # Load audio pipeline if needed
    audio_pipeline = None
    cast = None
    elevenlabs_key = None
    if generate_audio:
        from . import audio_pipeline as ap
        audio_pipeline = ap
        cast = ap.load_cast()
        elevenlabs_key = os.environ.get(config.ELEVENLABS_ENV_VAR)

    transcript_lines = []

    for i, action in enumerate(SCRIPTED_ACTIONS, 1):
        print(f"\n  --- Turn {i}/{len(SCRIPTED_ACTIONS)} ---")
        print(f"  Player: {action[:60]}...")

        try:
            text, elapsed, usage = dm_turn_v0(
                client=client, model=model, state=state,
                history=history, player_input=action,
            )
        except Exception as e:
            print(f"  ERROR: {e}")
            results["turns"].append({"turn": i, "error": str(e)})
            break

        sections = parse_response_v0(text)
        changes = state.apply_mechanics(sections["MECHANICS"])

        turn_data = {
            "turn": i,
            "player_input": action,
            "narrative": sections["NARRATIVE"],
            "mechanics": sections["MECHANICS"],
            "suggestions": sections["SUGGESTIONS"],
            "chronicle": sections["CHRONICLE"],
            "audio_text": sections["AUDIO"],
            "state_changes": changes,
            "elapsed": round(elapsed, 2),
            "tokens": usage.get("total_tokens", 0) if usage else 0,
        }
        results["turns"].append(turn_data)
        results["total_tokens"] += usage.get("total_tokens", 0) if usage else 0
        results["total_time"] += elapsed

        # Transcript
        transcript_lines.append(f"=== Turn {i} ===")
        transcript_lines.append(f"PLAYER: {action}\n")
        transcript_lines.append(f"[NARRATIVE]\n{sections['NARRATIVE']}\n")
        transcript_lines.append(f"[MECHANICS]\n{sections['MECHANICS']}\n")
        transcript_lines.append(f"[SUGGESTIONS]\n{sections['SUGGESTIONS']}\n")
        transcript_lines.append(f"[CHRONICLE]\n{sections['CHRONICLE']}\n")
        transcript_lines.append(f"[AUDIO]\n{sections['AUDIO']}\n")
        transcript_lines.append(f"[STATE CHANGES] {changes}\n")
        transcript_lines.append(f"[Time: {elapsed:.1f}s | Tokens: {usage.get('total_tokens', '?') if usage else '?'}]\n")

        print(f"  [NARRATIVE] {sections['NARRATIVE'][:80]}...")
        print(f"  [MECHANICS] {sections['MECHANICS'][:80]}")
        print(f"  [AUDIO] {sections['AUDIO'][:80]}...")
        print(f"  [{elapsed:.1f}s | {usage.get('total_tokens', '?') if usage else '?'} tokens]")

        # Generate audio
        if generate_audio and sections["AUDIO"].strip():
            turn_id = f"{model_dir.name}_turn_{i:03d}"
            print(f"  Generating audio for turn {i}...")
            try:
                audio_path = audio_pipeline.render_narration(
                    audio_text=sections["AUDIO"],
                    turn_id=turn_id,
                    elevenlabs_key=elevenlabs_key,
                    cast=cast,
                )
                if audio_path:
                    turn_data["audio_path"] = audio_path
                    print(f"  Audio: {audio_path}")
                else:
                    turn_data["audio_path"] = None
                    print(f"  Audio: none (empty [AUDIO] section)")
            except Exception as e:
                print(f"  Audio ERROR: {e}")
                turn_data["audio_error"] = str(e)

        history.append({"role": "user", "content": action})
        history.append({"role": "assistant", "content": text})

        time.sleep(3)  # respect rate limits

    # Final state
    results["final_state"] = {
        "pc_hp": f"{state.pc_hp}/{state.pc_max_hp}",
        "inventory": list(state.inventory),
        "enemies": [str(e) for e in state.enemies],
    }

    # Save
    with open(model_dir / "scripted_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    with open(model_dir / "scripted_responses.txt", "w") as f:
        f.write(f"Scripted Play Scenario — {model}\n")
        f.write(f"Provider: {provider}\n")
        f.write(f"Total time: {results['total_time']:.1f}s\n")
        f.write(f"Total tokens: {results['total_tokens']}\n")
        f.write(f"Final state: {results['final_state']}\n\n")
        f.write("\n".join(transcript_lines))

    print(f"\n  Final HP: {state.pc_hp}/{state.pc_max_hp}")
    print(f"  Total: {results['total_time']:.1f}s, {results['total_tokens']} tokens")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run comprehensive model comparison tests for Narrator v0.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--models", nargs="*", default=None,
                        help="Model IDs to test (default: all 4). "
                             "Use the 'id' field: gemini-flash-lite, gpt-oss-120b, etc.")
    parser.add_argument("--no-audio", action="store_true",
                        help="Skip audio generation (faster, text-only)")
    parser.add_argument("--skip-trickster", action="store_true",
                        help="Skip trickster adversarial test")
    parser.add_argument("--skip-scripted", action="store_true",
                        help="Skip scripted play scenario")
    args = parser.parse_args()

    load_dotenv(config.ENV_FILE)

    # Select models
    if args.models:
        models = [m for m in MODELS_TO_TEST if m["id"] in args.models]
        if not models:
            print(f"ERROR: no matching models. Available IDs: "
                  f"{[m['id'] for m in MODELS_TO_TEST]}", file=sys.stderr)
            sys.exit(1)
    else:
        models = MODELS_TO_TEST

    print(f"\n{'#'*60}")
    print(f"# Narrator v0 — Model Comparison Tests")
    print(f"# Models: {len(models)}")
    print(f"# Audio: {'OFF' if args.no_audio else 'ON'}")
    print(f"# Trickster: {'SKIP' if args.skip_trickster else 'RUN'}")
    print(f"# Scripted: {'SKIP' if args.skip_scripted else 'RUN'}")
    print(f"{'#'*60}\n")

    all_results = {}

    for model_cfg in models:
        model_id = model_cfg["id"]
        model = model_cfg["model"]
        provider = model_cfg["provider"]
        label = model_cfg["label"]

        print(f"\n{'='*60}")
        print(f"  MODEL: {label}")
        print(f"  id={model_id}  model={model}  provider={provider}")
        print(f"{'='*60}")

        model_dir = get_model_dir(model_id)

        # Create client
        try:
            client = make_client_v0(provider=provider, model=model)
        except ValueError as e:
            print(f"  SKIP: {e}")
            all_results[model_id] = {"error": str(e)}
            continue

        model_results = {"label": label, "model": model, "provider": provider}

        # Trickster test
        if not args.skip_trickster:
            try:
                trickster = run_trickster_for_model(
                    client, model, provider, model_dir
                )
                model_results["trickster"] = {
                    "resisted": trickster["total_resisted"],
                    "score": trickster["total_score"],
                    "errors": len(trickster["errors"]),
                }
            except Exception as e:
                print(f"  Trickster FAILED: {e}")
                model_results["trickster"] = {"error": str(e)}

        # Scripted scenario
        if not args.skip_scripted:
            try:
                scripted = run_scripted_for_model(
                    client, model, provider, model_dir,
                    generate_audio=not args.no_audio,
                )
                model_results["scripted"] = {
                    "turns": len(scripted["turns"]),
                    "total_time": scripted["total_time"],
                    "total_tokens": scripted["total_tokens"],
                    "final_hp": scripted["final_state"].get("pc_hp"),
                    "audio_turns": sum(1 for t in scripted["turns"] if t.get("audio_path")),
                }
            except Exception as e:
                print(f"  Scripted FAILED: {e}")
                model_results["scripted"] = {"error": str(e)}

        all_results[model_id] = model_results

    # Summary
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}\n")
    print(f"{'Model':<25} {'Trickster':>12} {'Scripted':>10} {'Tokens':>10} {'Audio':>8}")
    print(f"{'-'*25} {'-'*12} {'-'*10} {'-'*10} {'-'*8}")
    for mid, r in all_results.items():
        if "error" in r:
            print(f"{mid:<25} {'ERROR':>12} {'-':>10} {'-':>10} {'-':>8}")
            continue
        t = r.get("trickster", {})
        s = r.get("scripted", {})
        t_str = f"{t.get('resisted','?')}/10 ({t.get('score','?')}/30)" if "error" not in t else "ERROR"
        s_str = f"{s.get('turns','?')} turns" if "error" not in s else "ERROR"
        tokens = s.get("total_tokens", "?") if "error" not in s else "?"
        audio = s.get("audio_turns", "?") if "error" not in s else "?"
        print(f"{mid:<25} {t_str:>12} {s_str:>10} {tokens:>10} {audio:>8}")

    # Save summary
    summary_path = OUT_BASE / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nSummary saved to {summary_path}")
    print(f"Detailed results in {OUT_BASE}/")


if __name__ == "__main__":
    main()
