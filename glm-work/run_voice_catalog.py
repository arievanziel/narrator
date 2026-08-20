"""Generate a voice comparison catalog for all 28 English Kokoro voices.

Produces:
  outputs/voice_catalog/{voice}_narration.wav   — narration test line
  outputs/voice_catalog/{voice}_dialogue.wav    — dialogue test line
  outputs/voice_catalog/ensemble_all_voices.wav — short multi-character story
  outputs/voice_catalog/index.html              — clickable preview page

Kokoro 0.9.4 API (same as run_kokoro.py):
  pipeline = KPipeline(lang_code='a')
  ps, tokens = pipeline.g2p(text)
  for result in pipeline.generate_from_tokens(tokens=tokens, voice=VOICE):
      result.audio  # torch.FloatTensor
"""
import html
import time
import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "voice_catalog"
LOG = ROOT / "logs" / "voice_catalog.log"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.parent.mkdir(parents=True, exist_ok=True)

SAMPLE_RATE = 24000

# ---------------------------------------------------------------------------
# Voice catalog — 28 English voices (20 American + 8 British)
#   Prefix: a=American English, b=British English
#   Gender: f=female, m=male
# ---------------------------------------------------------------------------

VOICES = [
    # American female (11)
    ("af_alloy",   "American", "female"),
    ("af_aoede",   "American", "female"),
    ("af_bella",   "American", "female"),
    ("af_heart",   "American", "female"),
    ("af_jessica", "American", "female"),
    ("af_kore",    "American", "female"),
    ("af_nicole",  "American", "female"),
    ("af_nova",    "American", "female"),
    ("af_river",   "American", "female"),
    ("af_sarah",   "American", "female"),
    ("af_sky",     "American", "female"),
    # American male (9)
    ("am_adam",    "American", "male"),
    ("am_echo",    "American", "male"),
    ("am_eric",    "American", "male"),
    ("am_fenrir",  "American", "male"),
    ("am_liam",    "American", "male"),
    ("am_michael", "American", "male"),
    ("am_onyx",    "American", "male"),
    ("am_puck",    "American", "male"),
    ("am_santa",   "American", "male"),
    # British female (4)
    ("bf_alice",   "British",  "female"),
    ("bf_emma",    "British",  "female"),
    ("bf_isabella","British",  "female"),
    ("bf_lily",    "British",  "female"),
    # British male (4)
    ("bm_daniel",  "British",  "male"),
    ("bm_fable",   "British",  "male"),
    ("bm_george",  "British",  "male"),
    ("bm_lewis",   "British",  "male"),
]

VOICE_NAMES = [v[0] for v in VOICES]
VOICE_META = {v[0]: {"accent": v[1], "gender": v[2]} for v in VOICES}

# ---------------------------------------------------------------------------
# Test lines
# ---------------------------------------------------------------------------

NARRATION_LINE = (
    "The dragon's eyes opened slowly, revealing gold-flecked irises "
    "that had not blinked in a thousand years."
)

DIALOGUE_LINE = (
    "You can't be serious. That thing burned half the village to ash, "
    "and you want to walk right back in?"
)

# ---------------------------------------------------------------------------
# Ensemble story — "The Last Lantern"
# All 28 English voices used: 2 narrators + 26 characters.
# Each entry: (voice, speaker_label, text)
# ---------------------------------------------------------------------------

ENSEMBLE_SCRIPT = [
    # --- Frame narrator (British male, older) ---
    ("bm_george", "Narrator",
     "They gathered in the last lantern-lit tavern still standing, "
     "while the ashes drifted past the windows like grey snow."),

    # --- Main narrator (American female, warm) ---
    ("af_heart", "Narrator",
     "The Dragon's Rest, they called it now — a joke none of them laughed at."),

    ("af_alloy", "Mara (innkeeper)",
     "Drink up. The first round's on the house. Might be the last round any of us gets."),

    ("am_adam", "Brom (blacksmith)",
     "My forge is gone. Twenty years of work, melted to slag in a single breath."),

    ("af_bella", "Lira (survivor)",
     "I was in the market square when it came. I just ran. I didn't even look back."),

    ("am_echo", "Wren (scout)",
     "It flew east after the attack. I tracked it to the ridge, then lost it in the clouds."),

    ("bf_alice", "Lady Cordelia (noblewoman)",
     "My family has held these lands for six generations. We do not flee from beasts."),

    ("am_eric", "Elder Tomas",
     "Cordelia, your family has held these lands because they knew when to fight and when to shelter."),

    ("af_jessica", "Helena (merchant)",
     "I've sent word to three cities. No one will trade with us while a dragon nests nearby."),

    ("am_fenrir", "Grom (warrior)",
     "Then we stop trading and start fighting. Who's with me?"),

    ("af_kore", "Sister Wynn (healer)",
     "Fighting costs lives. I've stitched fourteen people today who'd disagree with you, Grom."),

    ("am_liam", "Sir Aldric (young knight)",
     "There must be a way. The old chronicles say dragons can be reasoned with."),

    ("af_nicole", "Captain Voss (guard)",
     "The old chronicles also say they can be killed. I'd rather try that first."),

    ("am_michael", "Magus Theln (wizard)",
     "Both are true, and neither is simple. This dragon spoke, before it burned. I heard it."),

    ("af_nova", "The Stranger",
     "You heard it because it wanted to be heard. That is not the same as being willing to talk."),

    ("am_onyx", "Sergeant Bray (veteran)",
     "I've fought monsters before. Talked to none of them. Dead is dead."),

    ("af_river", "Tomasa (farmer)",
     "My children are hiding in the root cellar. I can't fight a dragon, but I can't just wait either."),

    ("am_puck", "Fenn the Bard",
     "Oh, what a tale this will make! The Last Lantern, where heroes were born — or burned."),

    ("af_sarah", "Della (barmaid)",
     "Fenn, if you write a song about this before we survive it, I'll drown you in the ale barrel."),

    ("am_santa", "Father Aldous (priest)",
     "Pray, all of you. Not for rescue — for courage. The gods help those who help themselves."),

    ("bf_emma", "Mistress Nettle (apothecary)",
     "Courage won't stop dragonfire. I've mixed a salve that may resist the burn, but I need sulfur."),

    ("af_sky", "Young Pell",
     "There's sulfur in the old mines. I know the way. I can guide someone there."),

    ("bf_isabella", "Envoy Sabine (diplomat)",
     "If it truly spoke, then perhaps the Crown should send an emissary, not a regiment."),

    ("bm_daniel", "Captain Hale (ship captain)",
     "The Crown is three weeks away by sea. We don't have three weeks."),

    ("bf_lily", "Rose (seamstress)",
     "We have each other. Isn't that what the stories always say, before the end?"),

    ("bm_fable", "Cass (apprentice storyteller)",
     "The stories say the lantern always burns brightest before the dawn."),

    ("bm_lewis", "Old Drumm (drunk philosopher)",
     "The stories also say the lantern burns brightest right before it goes out. Cheers."),

    ("af_aoede", "Saela (elven scholar)",
     "There is a fourth option. The old maps mark a place beneath the mountain — a binding circle."),

    # --- Closing narration ---
    ("af_heart", "Narrator",
     "They argued until the lantern guttered, and then they argued in the dark. "
     "But no one left. And in the morning, they went to find the dragon together."),

    ("bm_george", "Narrator",
     "Whether they found courage or fire, the stories do not agree. "
     "But the lantern was still burning when they went."),
]


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------

def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def gen(pipeline, text, voice):
    """g2p + generate_from_tokens, return (audio_np, wall_clock_seconds)."""
    t0 = time.time()
    ps, tokens = pipeline.g2p(text)
    chunks = []
    for result in pipeline.generate_from_tokens(tokens=tokens, voice=voice):
        chunks.append(result.audio)
    dt = time.time() - t0
    audio = torch.cat(chunks).cpu().numpy() if chunks else np.array([])
    return audio, dt


def save_wav(audio, path):
    sf.write(str(path), audio, SAMPLE_RATE)
    return path.stat().st_size


# ---------------------------------------------------------------------------
# HTML preview page
# ---------------------------------------------------------------------------

def build_html(individual_results, ensemble_path, ensemble_dur):
    """Generate index.html with play buttons for every sample."""
    rows = []
    for voice, accent, gender in VOICES:
        narr_info = individual_results.get((voice, "narration"), {})
        dial_info = individual_results.get((voice, "dialogue"), {})
        narr_file = f"{voice}_narration.wav"
        dial_file = f"{voice}_dialogue.wav"
        narr_dur = narr_info.get("dur", 0)
        dial_dur = dial_info.get("dur", 0)
        narr_err = narr_info.get("error")
        dial_err = dial_info.get("error")

        narr_cell = (
            f'<span class="err">FAILED: {html.escape(narr_err)}</span>'
            if narr_err else
            f'<audio controls preload="none" src="{narr_file}"></audio>'
            f'<span class="dur">{narr_dur:.1f}s</span>'
        )
        dial_cell = (
            f'<span class="err">FAILED: {html.escape(dial_err)}</span>'
            if dial_err else
            f'<audio controls preload="none" src="{dial_file}"></audio>'
            f'<span class="dur">{dial_dur:.1f}s</span>'
        )

        rows.append(
            f"<tr>"
            f'<td class="voice">{voice}</td>'
            f'<td class="meta">{accent}</td>'
            f'<td class="meta">{gender}</td>'
            f"<td>{narr_cell}</td>"
            f"<td>{dial_cell}</td>"
            f"</tr>"
        )

    ensemble_file = "ensemble_all_voices.wav"
    ensemble_html = (
        f'<span class="err">FAILED: {html.escape(str(ensemble_path))}</span>'
        if not ensemble_path or not ensemble_path.exists() else
        f'<audio controls preload="none" src="{ensemble_file}"></audio>'
        f'<span class="dur">{ensemble_dur:.1f}s</span>'
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kokoro Voice Catalog — 28 English Voices</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         margin: 2rem auto; max-width: 980px; color: #1a1a1a; background: #fafafa; }}
  h1 {{ font-size: 1.6rem; }}
  h2 {{ font-size: 1.2rem; margin-top: 2.5rem; border-bottom: 2px solid #ddd; padding-bottom: .3rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
  th, td {{ padding: .5rem .6rem; text-align: left; border-bottom: 1px solid #e0e0e0; }}
  th {{ background: #f0f0f0; font-size: .85rem; text-transform: uppercase; letter-spacing: .03em; }}
  tr:hover {{ background: #f5f5ff; }}
  .voice {{ font-family: "SF Mono", "Fira Code", monospace; font-weight: 600; white-space: nowrap; }}
  .meta {{ color: #666; font-size: .85rem; white-space: nowrap; }}
  .dur {{ color: #888; font-size: .75rem; margin-left: .4rem; }}
  .err {{ color: #c00; font-size: .8rem; }}
  audio {{ height: 28px; }}
  .line {{ font-style: italic; color: #555; margin: .3rem 0 1.5rem; font-size: .9rem; }}
  .ensemble {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 1.2rem; margin-top: 1rem; }}
  .ensemble audio {{ height: 40px; }}
  .legend {{ font-size: .8rem; color: #777; margin-top: -.5rem; margin-bottom: 2rem; }}
</style>
</head>
<body>
<h1>Kokoro Voice Catalog</h1>
<p class="line">28 English voices (20 American + 8 British) &middot; narration + dialogue sample each &middot; one ensemble story</p>

<h2>Individual voice samples</h2>
<p class="legend">
  <strong>Narration line:</strong> &ldquo;{html.escape(NARRATION_LINE)}&rdquo;<br>
  <strong>Dialogue line:</strong> &ldquo;{html.escape(DIALOGUE_LINE)}&rdquo;
</p>
<table>
<thead><tr>
  <th>Voice</th><th>Accent</th><th>Gender</th>
  <th>Narration sample</th><th>Dialogue sample</th>
</tr></thead>
<tbody>
{chr(10).join(rows)}
</tbody>
</table>

<h2>Ensemble story &mdash; &ldquo;The Last Lantern&rdquo;</h2>
<p class="line">All 28 voices in one short scene: 2 narrators + 26 characters in a tavern after a dragon attack.</p>
<div class="ensemble">
{ensemble_html}
</div>

</body>
</html>
"""
    (OUT_DIR / "index.html").write_text(html_doc)
    log(f"[html] wrote index.html ({len(html_doc)} bytes)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log("=" * 70)
    log(f"Voice catalog run — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    log("[setup] importing kokoro + torch...")
    t0 = time.time()
    log(f"[setup] torch {torch.__version__}, MPS available: {torch.backends.mps.is_available()}")
    log("[setup] building KPipeline(lang_code='a')...")
    pipeline = KPipeline(lang_code="a")
    log(f"[setup] pipeline ready in {time.time()-t0:.1f}s")
    log(f"[setup] {len(VOICES)} voices to generate (2 samples each + 1 ensemble)")

    individual_results = {}
    total_files = 0
    total_audio_s = 0.0
    total_gen_s = 0.0
    failures = []

    # --- Individual samples ---
    for i, (voice, accent, gender) in enumerate(VOICES, 1):
        for kind, text in [("narration", NARRATION_LINE), ("dialogue", DIALOGUE_LINE)]:
            tag = f"[{i:2d}/{len(VOICES)}] {voice}_{kind}"
            out_path = OUT_DIR / f"{voice}_{kind}.wav"
            try:
                audio, dt = gen(pipeline, text, voice)
                if len(audio) == 0:
                    raise RuntimeError("empty audio")
                sz = save_wav(audio, out_path)
                dur = len(audio) / SAMPLE_RATE
                individual_results[(voice, kind)] = {"dur": dur, "gen": dt, "size": sz}
                total_files += 1
                total_audio_s += dur
                total_gen_s += dt
                log(f"{tag}: {dur:.2f}s audio in {dt:.2f}s -> {dur/dt:.1f}x RT, {sz} bytes")
            except Exception as e:
                individual_results[(voice, kind)] = {"error": str(e)}
                failures.append(f"{voice}_{kind}: {e}")
                log(f"{tag}: FAILED — {e}")

    # --- Ensemble story ---
    log("")
    log(f"[ensemble] generating 'The Last Lantern' — {len(ENSEMBLE_SCRIPT)} segments")
    ensemble_chunks = []
    ensemble_gen_s = 0.0
    for idx, (voice, speaker, text) in enumerate(ENSEMBLE_SCRIPT, 1):
        tag = f"[ensemble {idx:2d}/{len(ENSEMBLE_SCRIPT)}] {voice} ({speaker})"
        try:
            audio, dt = gen(pipeline, text, voice)
            if len(audio) == 0:
                raise RuntimeError("empty audio")
            ensemble_chunks.append(audio)
            ensemble_gen_s += dt
            dur = len(audio) / SAMPLE_RATE
            log(f"{tag}: {dur:.2f}s in {dt:.2f}s — \"{text[:60]}...\"")
        except Exception as e:
            failures.append(f"ensemble[{idx}] {voice}: {e}")
            log(f"{tag}: FAILED — {e}")

    ensemble_path = None
    ensemble_dur = 0.0
    if ensemble_chunks:
        audio_full = np.concatenate(ensemble_chunks)
        ensemble_path = OUT_DIR / "ensemble_all_voices.wav"
        save_wav(audio_full, ensemble_path)
        ensemble_dur = len(audio_full) / SAMPLE_RATE
        total_files += 1
        total_audio_s += ensemble_dur
        total_gen_s += ensemble_gen_s
        log(f"[ensemble] total: {ensemble_dur:.2f}s audio in {ensemble_gen_s:.2f}s "
            f"-> {ensemble_dur/ensemble_gen_s:.1f}x RT")

    # --- HTML preview ---
    log("")
    log("[html] building preview page...")
    build_html(individual_results, ensemble_path, ensemble_dur)

    # --- Summary ---
    log("")
    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    log(f"  voices processed:  {len(VOICES)}")
    log(f"  files written:     {total_files}")
    log(f"  total audio:       {total_audio_s:.1f}s ({total_audio_s/60:.1f} min)")
    log(f"  total gen time:    {total_gen_s:.1f}s ({total_gen_s/60:.1f} min)")
    log(f"  overall speed:     {total_audio_s/total_gen_s:.1f}x real-time" if total_gen_s > 0 else "  overall speed:     n/a")
    log(f"  failures:          {len(failures)}")
    for f in failures:
        log(f"    - {f}")
    log(f"  output dir:        {OUT_DIR}")
    log(f"  preview page:      {OUT_DIR / 'index.html'}")
    log(f"  log file:          {LOG}")
    log("DONE")


if __name__ == "__main__":
    main()
