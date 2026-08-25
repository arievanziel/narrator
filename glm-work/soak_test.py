#!/usr/bin/env python3
"""Soak test — 30+ turn session against the running app.

Usage:
  cd glm-work && source .venv/bin/activate
  python -m narrator_v01.app --no-audio --port 5102 &
  python soak_test.py --turns 35
"""
import argparse
import json
import time
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:5102"

# Varied actions to exercise different code paths
ACTIONS = [
    "I look around the room carefully, taking in every detail.",
    "I approach the barkeep and ask about any rumors.",
    "I draw my sword and attack the nearest enemy!",
    "I try to sneak past the guards quietly.",
    "I search the body for anything useful.",
    "I cast a spell to illuminate the dark corridor.",
    "I attempt to pick the lock on the chest.",
    "I negotiate with the merchant for a better price.",
    "I retreat and take cover behind the pillar.",
    "I drink a health potion to heal my wounds.",
    "I investigate the strange symbol on the wall.",
    "I shout a warning to my companions.",
    "I climb the wall to get a better vantage point.",
    "I try to remember if I've seen this place before.",
    "I offer gold to the guard to let us pass.",
    "I brace myself and defend against the incoming attack.",
    "I check my inventory for a torch.",
    "I listen carefully at the door before opening it.",
    "I follow the trail of blood down the hallway.",
    "I pray to the gods for guidance in this dark hour.",
    "I throw a rock to distract the guard.",
    "I examine the ancient tome on the pedestal.",
    "I ready my shield and advance slowly.",
    "I try to convince the prisoner to tell us the truth.",
    "I wade through the shallow stream cautiously.",
    "I set a trap using rope and a heavy branch.",
    "I call out to see if anyone is trapped in the rubble.",
    "I use my rope to descend into the pit.",
    "I heal myself and press on despite the pain.",
    "I charge forward with my shield raised high!",
    "I carefully disarm the trap on the floor.",
    "I ask the old woman about the history of this place.",
    "I take a moment to catch my breath and assess the situation.",
    "I follow the map to the next chamber.",
    "I confront the villain directly, sword drawn.",
]


def api_post(path: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "detail": e.read().decode()[:500]}
    except Exception as e:
        return {"error": str(e)}


def api_get(path: str) -> dict:
    try:
        with urllib.request.urlopen(f"{BASE}{path}", timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Soak test — 30+ turns")
    parser.add_argument("--turns", type=int, default=35, help="Number of turns")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  SOAK TEST — {args.turns} turns against {BASE}")
    print(f"{'='*60}\n")

    # Check server is up
    health = api_get("/api/providers")
    if "error" in health:
        print(f"FAIL: Server not responding — {health['error']}")
        return 1
    print(f"Server OK: {len(health['providers'])} providers, model={health['current_model']}")

    # Start new game
    print("\nStarting new game...")
    t0 = time.time()
    result = api_post("/api/newgame", {
        "story_style": "dark fantasy",
        "setting": "a crumbling empire on the edge of collapse",
        "persona": "a disgraced cartographer seeking redemption",
        "atmosphere": "ominous and atmospheric",
        "inspiration": "Bloodborne, Dark Souls",
        "auto_roll": True,
    })
    t_newgame = time.time() - t0

    if "error" in result:
        print(f"FAIL: New game failed — {result['error']}")
        print(f"  Detail: {result.get('detail', '')}")
        return 1

    print(f"  New game OK ({t_newgame:.1f}s)")
    print(f"  Story length: {len(result.get('story', ''))} chars")
    print(f"  Suggestions: {len(result.get('suggestions', []))}")

    # Check state
    state = api_get("/api/state")
    if "error" not in state:
        print(f"  PC: {state.get('pc_name', '?')} | HP: {state.get('pc_hp', '?')}/{state.get('pc_max_hp', '?')}")

    # Run turns
    results = []
    errors = []
    crashes = 0
    total_api_time = 0

    for i in range(args.turns):
        action = ACTIONS[i % len(ACTIONS)]
        print(f"\n  Turn {i+1}/{args.turns}: {action[:50]}...")

        t0 = time.time()
        result = api_post("/api/turn", {"action": action})
        elapsed = time.time() - t0
        total_api_time += elapsed

        if "error" in result:
            errors.append({"turn": i+1, "error": result["error"], "detail": result.get("detail", "")})
            print(f"    ERROR: {result['error']} ({elapsed:.1f}s)")
            if "detail" in result:
                print(f"    Detail: {result['detail'][:200]}")
            crashes += 1
            # Try to continue — the server might recover
            time.sleep(2)
            continue

        story_len = len(result.get("story", ""))
        changes = result.get("changes", [])
        suggestions = result.get("suggestions", [])
        scene = result.get("scene", "unknown")

        print(f"    OK ({elapsed:.1f}s) | story={story_len} chars | scene={scene} | changes={len(changes)} | choices={len(suggestions)}")

        results.append({
            "turn": i + 1,
            "action": action,
            "elapsed": round(elapsed, 2),
            "story_len": story_len,
            "scene": scene,
            "changes_count": len(changes),
            "suggestions_count": len(suggestions),
        })

        # Check for state corruption signals
        state = api_get("/api/state")
        if "error" not in state:
            hp = state.get("pc_hp", 0)
            max_hp = state.get("pc_max_hp", 1)
            if hp < 0 or hp > max_hp:
                print(f"    WARNING: HP out of bounds: {hp}/{max_hp}")
                errors.append({"turn": i+1, "error": f"HP out of bounds: {hp}/{max_hp}"})

    # Final state check
    print(f"\n{'='*60}")
    print(f"  SOAK TEST SUMMARY")
    print(f"{'='*60}")
    print(f"  Turns attempted:  {args.turns}")
    print(f"  Turns succeeded:  {len(results)}")
    print(f"  Errors/crashes:   {crashes}")
    print(f"  Total API time:   {total_api_time:.1f}s")
    if results:
        avg_time = total_api_time / len(results)
        print(f"  Avg time/turn:    {avg_time:.1f}s")
        max_time = max(r["elapsed"] for r in results)
        min_time = min(r["elapsed"] for r in results)
        print(f"  Min/Max turn:     {min_time:.1f}s / {max_time:.1f}s")

    # Check final state
    final_state = api_get("/api/state")
    if "error" not in final_state:
        print(f"  Final HP:         {final_state.get('pc_hp', '?')}/{final_state.get('pc_max_hp', '?')}")
        print(f"  Final location:   {final_state.get('location', '?')}")
        print(f"  Inventory items:  {len(final_state.get('inventory', []))}")
        print(f"  Chronicle entries: {len(final_state.get('chronicle', []))}")

    # Check for degradation (are later turns getting slower?)
    if len(results) >= 10:
        first_5 = sum(r["elapsed"] for r in results[:5]) / 5
        last_5 = sum(r["elapsed"] for r in results[-5:]) / 5
        ratio = last_5 / first_5 if first_5 > 0 else 0
        print(f"  Degradation:      first 5 avg={first_5:.1f}s, last 5 avg={last_5:.1f}s (ratio={ratio:.2f}x)")
        if ratio > 2.0:
            print(f"  WARNING: Significant response time degradation detected")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    Turn {e['turn']}: {e['error']}")

    # Save results
    out = {
        "turns_attempted": args.turns,
        "turns_succeeded": len(results),
        "errors": errors,
        "crashes": crashes,
        "total_api_time": round(total_api_time, 2),
        "turn_results": results,
        "final_state": final_state if "error" not in final_state else None,
    }
    with open("outputs/soak_test_results.json", "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n  Results saved: outputs/soak_test_results.json")

    return 0 if crashes == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
