# Kokoro Voice Catalog — 28 English Voices

**Generated:** 2026-08-17
**Script:** `glm-work/run_voice_catalog.py`
**Outputs:** `glm-work/outputs/voice_catalog/`
**Preview:** `http://127.0.0.1:8766/index.html` (while server runs) or open `index.html` directly

## Test lines

- **Narration:** "The dragon's eyes opened slowly, revealing gold-flecked irises that had not blinked in a thousand years."
- **Dialogue:** "You can't be serious. That thing burned half the village to ash, and you want to walk right back in?"
- **Ensemble:** "The Last Lantern" — 30-segment short story, 2 narrators + 26 characters, all 28 voices used.

## Generation stats

- 57 files written (56 individual + 1 ensemble), 0 failures
- Total audio: 525.5s (8.8 min)
- Total generation time: 272.2s (4.5 min)
- First sample per voice was slow (voice file download ~512 KB each); subsequent samples 5-6x real-time

## Voice table

Objective metadata (accent, gender) is derived from Kokoro's voice naming convention:
prefix `a`=American English, `b`=British English; second letter `f`=female, `m`=male.
Subjective descriptions are for Arie to fill in after listening. Lines starting with `>`
are reserved for Arie's notes — GLM will not modify them.

### American English — Female (11)

| Voice | Accent | Gender | Ensemble role | Arie's notes |
|-------|--------|--------|---------------|--------------|
| af_alloy | American | female | Mara (innkeeper) | |
| af_aoede | American | female | Saela (elven scholar) | |
| af_bella | American | female | Lira (survivor) | |
| af_heart | American | female | Narrator (main) | |
| af_jessica | American | female | Helena (merchant) | |
| af_kore | American | female | Sister Wynn (healer) | |
| af_nicole | American | female | Captain Voss (guard) | |
| af_nova | American | female | The Stranger | |
| af_river | American | female | Tomasa (farmer) | |
| af_sarah | American | female | Della (barmaid) | |
| af_sky | American | female | Young Pell | |

### American English — Male (9)

| Voice | Accent | Gender | Ensemble role | Arie's notes |
|-------|--------|--------|---------------|--------------|
| am_adam | American | male | Brom (blacksmith) | |
| am_echo | American | male | Wren (scout) | |
| am_eric | American | male | Elder Tomas | |
| am_fenrir | American | male | Grom (warrior) | |
| am_liam | American | male | Sir Aldric (young knight) | |
| am_michael | American | male | Magus Theln (wizard) | |
| am_onyx | American | male | Sergeant Bray (veteran) | |
| am_puck | American | male | Fenn the Bard | |
| am_santa | American | male | Father Aldous (priest) | |

### British English — Female (4)

| Voice | Accent | Gender | Ensemble role | Arie's notes |
|-------|--------|--------|---------------|--------------|
| bf_alice | British | female | Lady Cordelia (noblewoman) | |
| bf_emma | British | female | Mistress Nettle (apothecary) | |
| bf_isabella | British | female | Envoy Sabine (diplomat) | |
| bf_lily | British | female | Rose (seamstress) | |

### British English — Male (4)

| Voice | Accent | Gender | Ensemble role | Arie's notes |
|-------|--------|--------|---------------|--------------|
| bm_daniel | British | male | Captain Hale (ship captain) | |
| bm_fable | British | male | Cass (apprentice storyteller) | |
| bm_george | British | male | Narrator (frame) | |
| bm_lewis | British | male | Old Drumm (drunk philosopher) | |

## Ensemble cast — "The Last Lantern"

A tavern scene after a dragon attack. 30 segments, ~2:46 of audio.

| # | Voice | Speaker | Line (first 60 chars) |
|---|-------|---------|----------------------|
| 1 | bm_george | Narrator | They gathered in the last lantern-lit tavern still standing... |
| 2 | af_heart | Narrator | The Dragon's Rest, they called it now — a joke none of them... |
| 3 | af_alloy | Mara (innkeeper) | Drink up. The first round's on the house. Might be the last... |
| 4 | am_adam | Brom (blacksmith) | My forge is gone. Twenty years of work, melted to slag in a... |
| 5 | af_bella | Lira (survivor) | I was in the market square when it came. I just ran. I didn't... |
| 6 | am_echo | Wren (scout) | It flew east after the attack. I tracked it to the ridge... |
| 7 | bf_alice | Lady Cordelia | My family has held these lands for six generations. We do not... |
| 8 | am_eric | Elder Tomas | Cordelia, your family has held these lands because they knew... |
| 9 | af_jessica | Helena (merchant) | I've sent word to three cities. No one will trade with us... |
| 10 | am_fenrir | Grom (warrior) | Then we stop trading and start fighting. Who's with me? |
| 11 | af_kore | Sister Wynn (healer) | Fighting costs lives. I've stitched fourteen people today... |
| 12 | am_liam | Sir Aldric (knight) | There must be a way. The old chronicles say dragons can be... |
| 13 | af_nicole | Captain Voss (guard) | The old chronicles also say they can be killed. I'd rather... |
| 14 | am_michael | Magus Theln (wizard) | Both are true, and neither is simple. This dragon spoke... |
| 15 | af_nova | The Stranger | You heard it because it wanted to be heard. That is not the... |
| 16 | am_onyx | Sgt. Bray (veteran) | I've fought monsters before. Talked to none of them. Dead is... |
| 17 | af_river | Tomasa (farmer) | My children are hiding in the root cellar. I can't fight a... |
| 18 | am_puck | Fenn the Bard | Oh, what a tale this will make! The Last Lantern, where... |
| 19 | af_sarah | Della (barmaid) | Fenn, if you write a song about this before we survive it... |
| 20 | am_santa | Father Aldous (priest) | Pray, all of you. Not for rescue — for courage. The gods... |
| 21 | bf_emma | Mistress Nettle | Courage won't stop dragonfire. I've mixed a salve that may... |
| 22 | af_sky | Young Pell | There's sulfur in the old mines. I know the way. I can guide... |
| 23 | bf_isabella | Envoy Sabine | If it truly spoke, then perhaps the Crown should send an... |
| 24 | bm_daniel | Captain Hale | The Crown is three weeks away by sea. We don't have three... |
| 25 | bf_lily | Rose (seamstress) | We have each other. Isn't that what the stories always say... |
| 26 | bm_fable | Cass (apprentice) | The stories say the lantern always burns brightest before... |
| 27 | bm_lewis | Old Drumm | The stories also say the lantern burns brightest right before... |
| 28 | af_aoede | Saela (elven scholar) | There is a fourth option. The old maps mark a place beneath... |
| 29 | af_heart | Narrator | They argued until the lantern guttered, and then they argued... |
| 30 | bm_george | Narrator | Whether they found courage or fire, the stories do not agree... |

## Arie's overall notes

> (Add your feedback here — which voices work for narrator, which for NPCs, any that stand out as unusable, etc. GLM will not modify lines starting with `>`.)
