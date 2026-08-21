#!/usr/bin/env python3
"""Comprehensive playtest script for Narrator v0.3.

Runs multiple game combinations with different settings,
saves audio recordings, and logs text/audio comparison data.
"""
import json
import os
import time
import shutil
import urllib.request
import urllib.error
from pathlib import Path

BASE = "http://localhost:5102"
OUTPUT = Path("/Users/arie/CascadeProjects/narrator/glm-work/outputs/playtests")
OUTPUT.mkdir(parents=True, exist_ok=True)


def api(path, data=None):
    """Call API endpoint."""
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
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"error": str(e)}


def wait_audio(turn_id, timeout=180):
    """Wait for audio generation to complete."""
    start = time.time()
    while time.time() - start < timeout:
        r = api(f"/api/audio_status?turn_id={turn_id}")
        if r.get("status") == "ready":
            return r
        if r.get("status") == "error":
            return r
        time.sleep(2)
    return {"status": "timeout"}


def save_audio(turn_id, dest_path):
    """Download audio file from server."""
    url = f"{BASE}/audio/{turn_id}.wav"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
            with open(dest_path, "wb") as f:
                f.write(data)
            return len(data)
    except Exception as e:
        return 0


def run_playtest(name, settings, actions):
    """Run a full playtest with given settings and actions."""
    print(f"\n{'='*60}")
    print(f"  PLAYTEST: {name}")
    print(f"{'='*60}")

    results = {
        "name": name,
        "settings": settings,
        "turns": [],
        "errors": [],
    }

    # Start new game
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

    print(f"  Segments: {len(r.get('segments', []))}")
    print(f"  Scene: {r.get('scene')}")
    print(f"  Model: {r.get('model')}")
    print(f"  Suggestions: {len(r.get('suggestions', []))}")

    turn_data = {
        "turn": r.get("turn"),
        "scene": r.get("scene"),
        "segments": r.get("segments", []),
        "suggestions": r.get("suggestions", []),
        "changes": r.get("changes", []),
        "model": r.get("model"),
    }

    # Wait for audio
    audio_id = r.get("audio_turn_id")
    if audio_id:
        print(f"  Waiting for audio ({audio_id})...")
        audio_status = wait_audio(audio_id)
        turn_data["audio_status"] = audio_status.get("status")
        turn_data["audio_duration"] = audio_status.get("duration")
        if audio_status.get("status") == "ready":
            # Save audio
            dest = OUTPUT / f"{name}_turn_{r.get('turn'):03d}.wav"
            size = save_audio(audio_id, dest)
            turn_data["audio_file"] = str(dest)
            turn_data["audio_size"] = size
            print(f"  Audio: {audio_status.get('duration')}s saved to {dest.name}")

    # Calculate total text length vs audio duration
    total_text = " ".join(s.get("text", "") for s in r.get("segments", []))
    turn_data["total_text"] = total_text
    turn_data["text_length"] = len(total_text)

    results["turns"].append(turn_data)

    # Play additional turns
    for i, action in enumerate(actions):
        turn_num = i + 2
        print(f"\n[{turn_num}] Action: {action[:60]}...")
        r = api("/api/turn", {
            "action": action,
            "settings": settings,
        })

        if r.get("error"):
            print(f"  ERROR: {r['error']}")
            results["errors"].append(f"turn {turn_num}: {r['error']}")
            continue

        print(f"  Segments: {len(r.get('segments', []))}")
        print(f"  Scene: {r.get('scene')}")
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

        # Wait for audio
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
                turn_data["audio_size"] = size
                print(f"  Audio: {audio_status.get('duration')}s saved to {dest.name}")

        total_text = " ".join(s.get("text", "") for s in r.get("segments", []))
        turn_data["total_text"] = total_text
        turn_data["text_length"] = len(total_text)

        results["turns"].append(turn_data)
        time.sleep(1)

    # Save results JSON
    results_path = OUTPUT / f"{name}_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved: {results_path}")

    return results


# ============================================================
# Playtest combinations
# ============================================================

playtests = [
    {
        "name": "gemini_qwen3_library",
        "settings": {
            "autoroll": True, "music": True, "tts": "qwen3",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "library",
            "model": "gemini-3.5-flash-lite",
        },
        "actions": [
            "I draw my sword and attack the Goblin Scout!",
            "I swing again at the Goblin Scout!",
            "I use my Health Potion to heal my wounds.",
        ],
    },
    {
        "name": "gemini_kokoro_procedural",
        "settings": {
            "autoroll": True, "music": True, "tts": "kokoro",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "procedural",
            "model": "gemini-3.5-flash-lite",
        },
        "actions": [
            "I carefully examine the tavern for any other threats.",
            "I approach the barkeep and ask about the village.",
            "I decide to rest and recover my strength.",
        ],
    },
    {
        "name": "groq_auto_library",
        "settings": {
            "autoroll": True, "music": True, "tts": "auto",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "library",
            "model": "openai/gpt-oss-120b",
        },
        "actions": [
            "I search the goblin's body for anything useful.",
            "I head outside to investigate the haunted village.",
            "I draw my weapon as I hear strange noises from the woods.",
        ],
    },
    {
        "name": "groq_kokoro_nomusic",
        "settings": {
            "autoroll": True, "music": False, "tts": "kokoro",
            "speed": 1.0, "musicVol": 0.0, "musicSrc": "library",
            "model": "openai/gpt-oss-120b",
        },
        "actions": [
            "I sneak carefully through the dark forest.",
            "I attempt to pick the lock on the old crypt door.",
            "I cast my torch forward and enter the crypt.",
        ],
    },
    {
        "name": "gemini_qwen3_fast",
        "settings": {
            "autoroll": True, "music": True, "tts": "qwen3",
            "speed": 1.3, "musicVol": 0.10, "musicSrc": "library",
            "model": "gemini-3.5-flash-lite",
        },
        "actions": [
            "I charge boldly into the goblin camp, sword raised!",
            "I parry the goblin's attack and riposte!",
        ],
    },
]

# Run all playtests
all_results = []
for pt in playtests:
    result = run_playtest(pt["name"], pt["settings"], pt["actions"])
    all_results.append(result)
    time.sleep(2)  # Brief pause between tests

# Summary
print(f"\n\n{'='*60}")
print(f"  PLAYTEST SUMMARY")
print(f"{'='*60}")
for r in all_results:
    errors = len(r.get("errors", []))
    turns = len(r.get("turns", []))
    audio_turns = sum(1 for t in r["turns"] if t.get("audio_status") == "ready")
    total_dur = sum(t.get("audio_duration", 0) for t in r["turns"])
    print(f"  {r['name']}: {turns} turns, {audio_turns} audio, {total_dur:.0f}s total, {errors} errors")

# Save summary
summary_path = OUTPUT / "summary.json"
with open(summary_path, "w") as f:
    json.dump(all_results, f, indent=2, default=str)
print(f"\nSummary saved: {summary_path}")
