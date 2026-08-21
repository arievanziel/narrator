#!/usr/bin/env python3
"""Second round of playtests with Kokoro default + Qwen3 auto-fallback.
Tests edge cases and verifies the fidelity fix works.
"""
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = "http://localhost:5102"
OUTPUT = Path("/Users/arie/CascadeProjects/narrator/glm-work/outputs/playtests2")
OUTPUT.mkdir(parents=True, exist_ok=True)


def api(path, data=None):
    url = f"{BASE}{path}"
    if data is not None:
        req = urllib.request.Request(
            url, data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"}, method="POST"
        )
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def wait_audio(turn_id, timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        r = api(f"/api/audio_status?turn_id={turn_id}")
        if r.get("status") in ("ready", "error"):
            return r
        time.sleep(2)
    return {"status": "timeout"}


def save_audio(turn_id, dest_path):
    url = f"{BASE}/audio/{turn_id}.wav"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
            with open(dest_path, "wb") as f:
                f.write(data)
            return len(data)
    except:
        return 0


def run_playtest(name, settings, actions):
    print(f"\n{'='*60}")
    print(f"  PLAYTEST: {name}")
    print(f"{'='*60}")

    results = {"name": name, "settings": settings, "turns": [], "errors": []}

    # New game
    print(f"\n[1] Starting new game...")
    r = api("/api/newgame", {
        "name": "Kael",
        "style": "dark fantasy",
        "setting": "a haunted mountain village",
        "persona": "a grizzled veteran",
        "atmosphere": "tense",
        "dicemode": "auto",
    })

    if r.get("error"):
        print(f"  ERROR: {r['error']}")
        results["errors"].append(f"newgame: {r['error']}")
        return results

    print(f"  Segments: {len(r.get('segments', []))}, Scene: {r.get('scene')}")

    turn_data = {
        "turn": r.get("turn"),
        "scene": r.get("scene"),
        "segments": r.get("segments", []),
        "suggestions": r.get("suggestions", []),
        "changes": r.get("changes", []),
        "model": r.get("model"),
    }

    audio_id = r.get("audio_turn_id")
    if audio_id:
        print(f"  Waiting for audio ({audio_id})...")
        audio_status = wait_audio(audio_id)
        turn_data["audio_status"] = audio_status.get("status")
        turn_data["audio_duration"] = audio_status.get("duration")
        if audio_status.get("status") == "ready":
            dest = OUTPUT / f"{name}_turn_{r.get('turn'):03d}.wav"
            size = save_audio(audio_id, dest)
            turn_data["audio_file"] = str(dest)
            print(f"  Audio: {audio_status.get('duration')}s saved")

    total_text = " ".join(s.get("text", "") for s in r.get("segments", []))
    turn_data["total_text"] = total_text
    turn_data["text_length"] = len(total_text)

    # Check fidelity
    if turn_data.get("audio_duration"):
        est = len(total_text) / 15.0
        ratio = turn_data["audio_duration"] / est if est > 0 else 0
        turn_data["fidelity_ratio"] = ratio
        status = "GOOD" if 0.8 <= ratio <= 1.5 else "WARNING" if ratio <= 2.5 else "BAD"
        print(f"  Fidelity: {ratio:.2f} ({status})")

    results["turns"].append(turn_data)

    # Additional turns
    for i, action in enumerate(actions):
        turn_num = i + 2
        print(f"\n[{turn_num}] Action: {action[:60]}...")
        r = api("/api/turn", {"action": action, "settings": settings})

        if r.get("error"):
            print(f"  ERROR: {r['error']}")
            results["errors"].append(f"turn {turn_num}: {r['error']}")
            continue

        print(f"  Segments: {len(r.get('segments', []))}, Scene: {r.get('scene')}")
        print(f"  Changes: {r.get('changes', [])}")

        turn_data = {
            "turn": r.get("turn"),
            "scene": r.get("scene"),
            "segments": r.get("segments", []),
            "suggestions": r.get("suggestions", []),
            "changes": r.get("changes", []),
            "model": r.get("model"),
            "action": action,
        }

        audio_id = r.get("audio_turn_id")
        if audio_id:
            print(f"  Waiting for audio ({audio_id})...")
            audio_status = wait_audio(audio_id)
            turn_data["audio_status"] = audio_status.get("status")
            turn_data["audio_duration"] = audio_status.get("duration")
            if audio_status.get("status") == "ready":
                dest = OUTPUT / f"{name}_turn_{r.get('turn'):03d}.wav"
                size = save_audio(audio_id, dest)
                turn_data["audio_file"] = str(dest)
                print(f"  Audio: {audio_status.get('duration')}s saved")

        total_text = " ".join(s.get("text", "") for s in r.get("segments", []))
        turn_data["total_text"] = total_text
        turn_data["text_length"] = len(total_text)

        if turn_data.get("audio_duration"):
            est = len(total_text) / 15.0
            ratio = turn_data["audio_duration"] / est if est > 0 else 0
            turn_data["fidelity_ratio"] = ratio
            status = "GOOD" if 0.8 <= ratio <= 1.5 else "WARNING" if ratio <= 2.5 else "BAD"
            print(f"  Fidelity: {ratio:.2f} ({status})")

        results["turns"].append(turn_data)
        time.sleep(1)

    results_path = OUTPUT / f"{name}_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved: {results_path}")
    return results


# ============================================================
# Round 2 playtests — focus on Kokoro fidelity + edge cases
# ============================================================

playtests = [
    {
        "name": "kokoro_default_gemini",
        "settings": {
            "autoroll": True, "music": True, "tts": "kokoro",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "library",
            "model": "gemini-3.5-flash-lite",
        },
        "actions": [
            "I attack the Goblin Scout with my longsword!",
            "I swing again at the Goblin Scout!",
            "I use my Health Potion to heal.",
            "I attack the Goblin Raider!",
        ],
    },
    {
        "name": "kokoro_default_groq",
        "settings": {
            "autoroll": True, "music": True, "tts": "kokoro",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "library",
            "model": "openai/gpt-oss-120b",
        },
        "actions": [
            "I sneak through the dark forest, keeping to the shadows.",
            "I attempt to pick the lock on the crypt door.",
            "I enter the crypt with my torch raised high.",
        ],
    },
    {
        "name": "auto_tts_gemini",
        "settings": {
            "autoroll": True, "music": True, "tts": "auto",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "library",
            "model": "gemini-3.5-flash-lite",
        },
        "actions": [
            "I charge into battle, swinging my sword wildly!",
            "I defend myself against the goblin's counterattack.",
        ],
    },
    {
        "name": "qwen3_with_fallback",
        "settings": {
            "autoroll": True, "music": True, "tts": "qwen3",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "library",
            "model": "gemini-3.5-flash-lite",
        },
        "actions": [
            "I carefully examine the ancient runes on the wall.",
            "I recite the incantation I learned as a child.",
        ],
    },
    {
        "name": "kokoro_fast_speed",
        "settings": {
            "autoroll": True, "music": True, "tts": "kokoro",
            "speed": 1.3, "musicVol": 0.10, "musicSrc": "procedural",
            "model": "gemini-3.5-flash-lite",
        },
        "actions": [
            "I race through the dungeon, chasing the goblin!",
            "I leap across the chasm to escape the collapsing bridge!",
        ],
    },
    {
        "name": "kokoro_slow_speed",
        "settings": {
            "autoroll": True, "music": True, "tts": "kokoro",
            "speed": 0.8, "musicVol": 0.15, "musicSrc": "library",
            "model": "openai/gpt-oss-120b",
        },
        "actions": [
            "I slowly approach the ancient altar, examining every detail.",
            "I carefully read the inscription carved into the stone.",
        ],
    },
]

all_results = []
for pt in playtests:
    result = run_playtest(pt["name"], pt["settings"], pt["actions"])
    all_results.append(result)
    time.sleep(2)

# Summary
print(f"\n\n{'='*60}")
print(f"  ROUND 2 SUMMARY")
print(f"{'='*60}")
print(f"{'Playtest':<30} {'Turns':<8} {'Avg Ratio':<12} {'Status'}")
print(f"{'-'*65}")
for r in all_results:
    turns = len(r.get("turns", []))
    ratios = [t.get("fidelity_ratio", 0) for t in r["turns"] if t.get("fidelity_ratio")]
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0
    errors = len(r.get("errors", []))
    status = "PASS" if errors == 0 and avg_ratio <= 1.5 else "CHECK"
    print(f"{r['name']:<30} {turns:<8} {avg_ratio:<12.2f} {status}")

summary_path = OUTPUT / "summary.json"
with open(summary_path, "w") as f:
    json.dump(all_results, f, indent=2, default=str)
print(f"\nSummary saved: {summary_path}")
