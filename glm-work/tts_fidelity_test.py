#!/usr/bin/env python3
"""TTS fidelity test: generate the same text with Kokoro and Qwen3,
save both audio files for human comparison.

Also measures timing and audio characteristics.
"""
import os
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv('.env')

from narrator_v01 import audio_engine
import soundfile as sf
import numpy as np

OUTPUT = Path("/Users/arie/CascadeProjects/narrator/glm-work/outputs/tts_comparison")
OUTPUT.mkdir(parents=True, exist_ok=True)

# Test passages from actual game output
test_passages = [
    {
        "id": "combat_short",
        "speaker": "narrator",
        "text": "The goblin lunges at you with a rusty blade, snarling with rage.",
        "voice": "A warm, deep male narrator voice with a measured storytelling tone",
    },
    {
        "id": "dialogue_goblin",
        "speaker": "Goblin Scout",
        "text": "Fresh meat for the kettle!",
        "voice": "A rough, snarling goblin voice with a menacing tone",
    },
    {
        "id": "narration_long",
        "speaker": "narrator",
        "text": "The heavy wooden door of the Rusty Anchor groans open, letting in a bitter gust of mountain air. Inside, the common room is dim and smoky, lit by a few sputtering candles. Two goblin scouts huddle in the corner, their beady eyes glinting in the candlelight as they sharpen crude blades.",
        "voice": "A warm, calm, deep male narrator voice with a measured storytelling tone",
    },
    {
        "id": "dialogue_kael",
        "speaker": "Kael",
        "text": 'Predictable," he growls, pivoting smoothly on his heel.',
        "voice": "A rugged male adventurer's voice, confident and clear",
    },
    {
        "id": "action_climax",
        "speaker": "narrator",
        "text": "Kael drives his longsword forward in a swift, practiced riposte, piercing the scout's chest. The goblin gasps, drops its dagger, and collapses motionless to the tavern floor.",
        "voice": "A warm, deep male narrator voice with a measured storytelling tone",
    },
]

results = []

for passage in test_passages:
    print(f"\n{'='*60}")
    print(f"  Passage: {passage['id']}")
    print(f"  Speaker: {passage['speaker']}")
    print(f"  Text: {passage['text'][:80]}...")
    print(f"  Text length: {len(passage['text'])} chars")

    passage_results = {"id": passage["id"], "text": passage["text"], "engines": {}}

    for engine in ["kokoro", "qwen3"]:
        print(f"\n  [{engine}]")
        out_path = str(OUTPUT / f"{passage['id']}_{engine}.wav")

        try:
            t0 = time.time()
            audio_path = audio_engine.generate_segment_tts(
                text=passage["text"],
                voice_desc=passage["voice"],
                output_path=out_path,
                engine=engine,
            )
            t1 = time.time()

            data, sr = sf.read(audio_path)
            duration = len(data) / sr
            rtf = (t1 - t0) / duration if duration > 0 else 0

            # Estimate expected duration (~15 chars/sec for normal speech)
            est_dur = len(passage["text"]) / 15.0
            fidelity_ratio = duration / est_dur if est_dur > 0 else 0

            print(f"    Duration: {duration:.1f}s (est: {est_dur:.1f}s, ratio: {fidelity_ratio:.2f})")
            print(f"    Gen time: {t1-t0:.1f}s (RTF: {rtf:.2f})")
            print(f"    File: {audio_path}")

            passage_results["engines"][engine] = {
                "duration": duration,
                "gen_time": t1 - t0,
                "rtf": rtf,
                "fidelity_ratio": fidelity_ratio,
                "file": audio_path,
                "error": None,
            }
        except Exception as e:
            print(f"    ERROR: {e}")
            passage_results["engines"][engine] = {"error": str(e)}

    results.append(passage_results)

# Save results
results_path = OUTPUT / "comparison_results.json"
with open(results_path, "w") as f:
    json.dump(results, f, indent=2)

# Summary
print(f"\n\n{'='*60}")
print(f"  FIDELITY COMPARISON SUMMARY")
print(f"{'='*60}")
print(f"{'Passage':<25} {'Kokoro ratio':<15} {'Qwen3 ratio':<15} {'Winner'}")
print(f"{'-'*70}")
for r in results:
    k = r["engines"].get("kokoro", {})
    q = r["engines"].get("qwen3", {})
    k_ratio = k.get("fidelity_ratio", 0)
    q_ratio = q.get("fidelity_ratio", 0)
    # Closer to 1.0 = more faithful
    k_diff = abs(1.0 - k_ratio)
    q_diff = abs(1.0 - q_ratio)
    winner = "Kokoro" if k_diff < q_diff else "Qwen3"
    print(f"{r['id']:<25} {k_ratio:<15.2f} {q_ratio:<15.2f} {winner}")

print(f"\nResults saved: {results_path}")
print(f"Audio files in: {OUTPUT}")
