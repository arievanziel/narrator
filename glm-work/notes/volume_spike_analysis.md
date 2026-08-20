# Volume Spike Root Cause Analysis

## Finding (2026-08-19)

After analyzing demo11_boss.wav around the timestamps Arie flagged (1:50-1:60, 2:13):

### The "spikes" are NOT clipping
- Peak values are 0.4-0.6, well within normal range
- The final mix is normalized to 0.75 peak

### The real cause: SHARP SFX ATTACKS
- SFX clips go from silence to full volume **instantly** (no fade-in)
- SFX are normalized to 0.8 peak, then multiplied by 0.45 volume = 0.36 peak
- But the **RMS jump** from silence (0.02) to SFX (0.15-0.17) is abrupt
- The gap between SFX and voice is only 0.2-0.3 seconds — too short
- This creates the perception of a "spike" even though amplitude is fine

### Secondary cause: SFX + MUSIC overlap
- SFX play in gaps between voice, but music is still playing underneath
- When SFX hits, it adds to the music volume, creating a sudden jump
- Music at 14% + SFX at 36% = 50% combined, vs 14% music alone

## Fixes (v4)

1. **Add 150ms fade-in to every SFX clip** — prevents sharp attacks
2. **Add 150ms fade-out to every SFX clip** — prevents sharp endings
3. **Increase SFX-to-voice gaps** from 0.2/0.3s to 0.4/0.5s
4. **Lower SFX normalization** from 0.8 to 0.6 peak
5. **Duck music during SFX** — reduce music volume by 50% while SFX plays
6. **Apply final limiter** — soft clip at 0.7 to catch any remaining transients
7. **Always fade out music** at end of scene (3-second fade)
