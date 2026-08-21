#!/usr/bin/env python3
"""Round 3: Edge case tests — Qwen3 auto-fallback, long text, empty input, etc."""
import json
import time
import urllib.request
from pathlib import Path

BASE = "http://localhost:5102"
OUTPUT = Path("/Users/arie/CascadeProjects/narrator/glm-work/outputs/playtests3")
OUTPUT.mkdir(parents=True, exist_ok=True)


def api(path, data=None):
    url = f"{BASE}{path}"
    if data is not None:
        req = urllib.request.Request(url, data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
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


def save_audio(turn_id, dest):
    try:
        with urllib.request.urlopen(f"{BASE}/audio/{turn_id}.wav", timeout=30) as resp:
            data = resp.read()
            with open(dest, "wb") as f:
                f.write(data)
            return len(data)
    except:
        return 0


def run_test(name, settings, actions):
    print(f"\n{'='*60}")
    print(f"  TEST: {name}")
    print(f"{'='*60}")
    results = {"name": name, "settings": settings, "turns": [], "errors": []}

    r = api("/api/newgame", {"name": "Kael", "dicemode": "auto"})
    if r.get("error"):
        results["errors"].append(f"newgame: {r['error']}")
        return results

    print(f"  Newgame: {len(r.get('segments',[]))} segs, scene={r.get('scene')}")

    # Process newgame audio
    audio_id = r.get("audio_turn_id")
    if audio_id:
        status = wait_audio(audio_id)
        dur = status.get("duration", 0)
        text = " ".join(s.get("text","") for s in r.get("segments",[]))
        est = len(text) / 15.0
        ratio = dur / est if est > 0 and dur else 0
        print(f"  Audio: {dur}s, ratio={ratio:.2f}")
        if status.get("status") == "ready":
            save_audio(audio_id, OUTPUT / f"{name}_turn_001.wav")

    for i, action in enumerate(actions):
        turn_num = i + 2
        print(f"\n  [{turn_num}] {action[:50]}...")
        r = api("/api/turn", {"action": action, "settings": settings})
        if r.get("error"):
            print(f"    ERROR: {r['error']}")
            results["errors"].append(f"turn {turn_num}: {r['error']}")
            continue

        print(f"    Segments: {len(r.get('segments',[]))}, Changes: {r.get('changes',[])}")
        audio_id = r.get("audio_turn_id")
        if audio_id:
            status = wait_audio(audio_id)
            dur = status.get("duration", 0)
            text = " ".join(s.get("text","") for s in r.get("segments",[]))
            est = len(text) / 15.0
            ratio = dur / est if est > 0 and dur else 0
            print(f"    Audio: {dur}s, ratio={ratio:.2f}")
            if status.get("status") == "ready":
                save_audio(audio_id, OUTPUT / f"{name}_turn_{turn_num:03d}.wav")
        time.sleep(1)

    with open(OUTPUT / f"{name}.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    return results


tests = [
    # Qwen3 with auto-fallback — should detect paraphrasing and switch to Kokoro
    {
        "name": "qwen3_autofallback",
        "settings": {"autoroll": True, "music": True, "tts": "qwen3",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "library",
            "model": "gemini-3.5-flash-lite"},
        "actions": [
            "I tell the goblin a long story about my adventures in the northern mountains.",
            "I recite an ancient elven poem to calm the spirits.",
        ],
    },
    # Very short action
    {
        "name": "short_actions",
        "settings": {"autoroll": True, "music": True, "tts": "kokoro",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "library",
            "model": "gemini-3.5-flash-lite"},
        "actions": ["I attack.", "I run.", "I hide."],
    },
    # Long complex action
    {
        "name": "long_action",
        "settings": {"autoroll": True, "music": True, "tts": "kokoro",
            "speed": 1.0, "musicVol": 0.12, "musicSrc": "library",
            "model": "openai/gpt-oss-120b"},
        "actions": ["I carefully approach the goblin, keeping my shield raised and my sword at the ready. I try to negotiate with it, speaking in a calm but firm voice, offering it gold in exchange for safe passage through the village."],
    },
    # No music
    {
        "name": "no_music",
        "settings": {"autoroll": True, "music": False, "tts": "kokoro",
            "speed": 1.0, "musicVol": 0.0, "musicSrc": "library",
            "model": "gemini-3.5-flash-lite"},
        "actions": ["I listen carefully for any sounds.", "I search the room."],
    },
    # Procedural music
    {
        "name": "procedural_music",
        "settings": {"autoroll": True, "music": True, "tts": "kokoro",
            "speed": 1.0, "musicVol": 0.15, "musicSrc": "procedural",
            "model": "gemini-3.5-flash-lite"},
        "actions": ["I enter the dark dungeon.", "I hear something approaching."],
    },
]

all_results = []
for t in tests:
    r = run_test(t["name"], t["settings"], t["actions"])
    all_results.append(r)
    time.sleep(2)

print(f"\n{'='*60}")
print(f"  ROUND 3 SUMMARY")
print(f"{'='*60}")
for r in all_results:
    errors = len(r.get("errors", []))
    print(f"  {r['name']}: {errors} errors")
