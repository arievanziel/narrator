"""Ensemble story #2 — 'The Descent of Ysolde's Light'

A fixed cast of 7 characters + 1 narrator. The narrator introduces the cast,
characters address each other by name, they move through 4 locations with
elaborate descriptions, and the storytelling is dramatic/epic.

Outputs (all in glm-work/outputs/voice_catalog/):
  ensemble2_the_descent.md        — the base story (prose, for reading)
  ensemble2_the_descent_input.txt — voice-edited input (segments with [voice] tags)
  ensemble2_the_descent.wav       — the final audio

Run:  python run_ensemble2.py
"""
import time
import torch
import soundfile as sf
import numpy as np
from pathlib import Path
from kokoro import KPipeline

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "voice_catalog"
LOG = ROOT / "logs" / "ensemble2.log"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.parent.mkdir(parents=True, exist_ok=True)

SAMPLE_RATE = 24000

# ---------------------------------------------------------------------------
# Cast — fixed, introduced by the narrator
# ---------------------------------------------------------------------------
#   voice      | character | role
#   -----------|-----------|-------------------------------------------
#   bm_george  | Narrator  | frame narrator (British male, older)
#   am_michael | Kaelen    | seasoned warrior, leader of the company
#   af_heart   | Lyra      | scholar and keeper of the lore
#   am_onyx    | Dax       | grizzled veteran, skeptic
#   af_nova    | Sera      | scout, quiet, sees what others miss
#   am_fenrir  | Bram      | young warrior, hotheaded, brave
#   bf_alice   | Ysolde    | noblewoman, healer, the light-bearer
#   am_liam    | The Hollow| antagonist voice (echoing, inhuman)

# ---------------------------------------------------------------------------
# The story — "The Descent of Ysolde's Light"
#
# Locations:
#   1. The Cliffside at Dawn (wind, sea, the ruined watchtower)
#   2. The Stair (carved into the cliff, descending into darkness)
#   3. The Under-River (subterranean current, the drowned bridge)
#   4. The Flame Chamber (the heart of the buried temple)
#
# Each entry: (voice, speaker_label, text, location)
# ---------------------------------------------------------------------------

STORY = [
    # === Location 1: The Cliffside at Dawn ===
    ("bm_george", "Narrator",
     "The wind came off the Greywater Sea like a living thing, salt-edged and cold, "
     "and it bent the dead grass of the cliffside around the ruins of the old watchtower. "
     "Dawn was breaking — not the gentle dawn of the lowlands, but a hard, copper light "
     "that clawed its way over the horizon and turned the sea to hammered bronze. "
     "Seven figures stood where the tower had fallen, their cloaks snapping in the gale, "
     "looking down at a wound in the earth: a stair, black and smooth, plunging into the cliff itself.",
     "1. The Cliffside at Dawn"),

    ("bm_george", "Narrator",
     "Kaelen stood at the stair's edge, his hand on the hilt of a sword older than any kingdom "
     "now living. Beside him, Lyra traced a faded map with one finger, her lips moving silently. "
     "Dax squinted into the dark, arms folded, unconvinced. Sera crouched at the rim, listening. "
     "Bram paced, restless as a hound on a leash. And Ysolde — Ysolde held the lantern, "
     "and within it, a flame that had not been lit by any human hand.",
     "1. The Cliffside at Dawn"),

    ("bm_george", "Narrator",
     "They were the Company of the Last Light, and the mountain had been waiting for them "
     "for a very long time.",
     "1. The Cliffside at Dawn"),

    ("am_michael", "Kaelen",
     "Lyra. How far down?",
     "1. The Cliffside at Dawn"),

    ("af_heart", "Lyra",
     "The map says three hundred steps to the river, and then the river takes us under the spine "
     "of the cliff. After that... the map ends. The cartographer drew a circle and wrote one word: "
     "'beneath.'",
     "1. The Cliffside at Dawn"),

    ("am_onyx", "Dax",
     "A map that ends with a circle and a riddle. That's not a map, Lyra. That's a warning "
     "someone was too polite to write in blood.",
     "1. The Cliffside at Dawn"),

    ("af_nova", "Sera",
     "Dax is right that it's a warning. He's wrong that it matters. The stair goes down, "
     "and we go down it. That's the whole of it.",
     "1. The Cliffside at Dawn"),

    ("am_fenrir", "Bram",
     "Sera, if you've seen something down there, now would be the time.",
     "1. The Cliffside at Dawn"),

    ("af_nova", "Sera",
     "I haven't seen it, Bram. I've heard it. Last night, in the wind. A voice, "
     "or something that remembers what a voice was. It said a name. It said Ysolde.",
     "1. The Cliffside at Dawn"),

    ("bf_alice", "Ysolde",
     "Then it knows I'm coming. Good. Let it be afraid. "
     "Kaelen — give the order. I'm tired of standing in the wind.",
     "1. The Cliffside at Dawn"),

    ("am_michael", "Kaelen",
     "You heard her. Dax, you have the rear. Sera, point. Bram, with me. "
     "Lyra, stay close to Ysolde and that lantern. If the flame goes out, we are all "
     "buried in the dark. We move. Now.",
     "1. The Cliffside at Dawn"),

    # === Location 2: The Stair ===
    ("bm_george", "Narrator",
     "The stair swallowed them whole. The light of dawn retreated three steps in and gave up, "
     "as if the darkness were a tide and the sun had no claim here. The steps were carved from "
     "the living rock of the cliff — not rough-hewn, but polished, as though the mountain itself "
     "had been taught patience by whatever hands had made this place. The walls wept thin lines "
     "of water that caught the lantern-light and ran like veins of silver. Their footsteps echoed, "
     "and the echoes came back a half-beat too late, as if something below were walking with them, "
     "matching their pace, learning their rhythm.",
     "2. The Stair"),

    ("bm_george", "Narrator",
     "Down and down. The air grew thick and warm, and it tasted of old stone and older water. "
     "Sera moved first, silent as a draft, her hand on the wall. Kaelen followed, then Ysolde "
     "with the lantern held high — and the flame within it burned without flickering, without wind, "
     "a small steady gold that pushed the dark back exactly far enough for the next step, and no further.",
     "2. The Stair"),

    ("am_onyx", "Dax",
     "Kaelen. Stop. Listen.",
     "2. The Stair"),

    ("am_michael", "Kaelen",
     "I hear it. Everyone still. Lyra — what is that?",
     "2. The Stair"),

    ("af_heart", "Lyra",
     "It's not an echo. An echo repeats. This... answers. It's using our own voices to speak back to us. "
     "Bram, don't answer it. Whatever it says, don't answer it in your own voice.",
     "2. The Stair"),

    ("am_liam", "The Hollow",
     "Ysolde. You bring a borrowed flame into my house. You always were the brave one. "
     "Come down, little light-bearer. Come down and we will talk as we used to.",
     "2. The Stair"),

    ("bf_alice", "Ysolde",
     "That is not my brother. My brother died on the field at Aldermoor. Whatever you are, "
     "you wear his voice the way a thief wears a stolen coat. I am not coming down to talk. "
     "I am coming down to end this.",
     "2. The Stair"),

    ("am_fenrir", "Bram",
     "Ysolde, it spoke in your brother's voice. Are you sure — ",
     "2. The Stair"),

    ("bf_alice", "Ysolde",
     "I am sure, Bram. I buried him myself. Move on.",
     "2. The Stair"),

    ("bm_george", "Narrator",
     "And so they descended, and the stair descended with them, and the dark pressed close, "
     "and the only light in a hundred miles of stone was the one Ysolde carried in her hands.",
     "2. The Stair"),

    # === Location 3: The Under-River ===
    ("bm_george", "Narrator",
     "The stair ended at a shore that should not have existed. A river ran through the heart of the cliff — "
     "broad, black, slow, and utterly silent. No current-sound, no lap of water on stone. It moved "
     "like glass being poured, heavy and patient, and where it touched the walls it left a faint "
     "phosphorescence, a ghost-light the color of drowned moons. A bridge of pale stone arched over it, "
     "but the bridge was broken in the middle, and the two halves hung in the dark like the arms of "
     "someone reaching for a hand they will never hold again.",
     "3. The Under-River"),

    ("af_heart", "Lyra",
     "The Drowned Bridge. The map didn't lie — it just didn't warn us that the bridge would be broken. "
     "Kaelen, the gap is at least ten feet. The stone is wet. A jump is possible, but not safe.",
     "3. The Under-River"),

    ("am_onyx", "Dax",
     "Possible and not safe describes this entire journey, Lyra. Bram — you're the youngest, "
     "the lightest, and the most reckless. You first.",
     "3. The Under-River"),

    ("am_fenrir", "Bram",
     "Dax, when this is over, you and I are going to have a conversation about the way you "
     "volunteer me for things.",
     "3. The Under-River"),

    ("am_onyx", "Dax",
     "I look forward to it, boy. Jump.",
     "3. The Under-River"),

    ("bm_george", "Narrator",
     "Bram ran. Three strides, a leap, and the dark swallowed him for one held breath before "
     "his boots struck the far side and he stumbled, caught himself, and turned with a grin "
     "that the lantern-light found from across the void.",
     "3. The Under-River"),

    ("am_fenrir", "Bram",
     "It holds! Sera, you next. You're lighter than me — you'll barely touch the stone.",
     "3. The Under-River"),

    ("af_nova", "Sera",
     "Bram, stop grinning. You nearly fell. Ysolde — the lantern. Can you make the jump with it? "
     "If the flame drops into that water, I don't know what happens. I don't want to know.",
     "3. The Under-River"),

    ("bf_alice", "Ysolde",
     "The flame will not drop, Sera. It has been carried through worse than this. "
     "Kaelen, help me across. Lyra, Dax — follow us.",
     "3. The Under-River"),

    ("bm_george", "Narrator",
     "One by one they crossed, and the river beneath them did not stir, did not ripple, "
     "did not so much as whisper. It simply watched them pass, the way a thing with no eyes "
     "and all the time in the world might watch. And on the far side, the stone opened into a hall "
     "that no living person had stood in for a thousand years.",
     "3. The Under-River"),

    # === Location 4: The Flame Chamber ===
    ("bm_george", "Narrator",
     "The chamber was vast — so vast that the lantern-light could not find its walls, only "
     "the floor: a mirror of black stone so polished that the seven of them walked on their own "
     "reflections. Pillars rose into the dark like the trunks of trees in a drowned forest, and "
     "between the pillars, in alcoves cut with terrible care, stood figures of stone — hundreds of them, "
     "each one different, each one covering its face with its hands. At the far end of the hall, "
     "something burned. Not Ysolde's flame. Something older. Something that had been burning since before "
     "the sea had a name, a cold blue fire that threw no warmth and cast shadows that pointed the wrong way.",
     "4. The Flame Chamber"),

    ("am_liam", "The Hollow",
     "Welcome home, Ysolde. You brought them all. I knew you would. "
     "Kaelen with his old sword. Lyra with her old map. Dax with his old doubts. "
     "Sera with her old ears. And Bram — young Bram, who jumps before he looks. "
     "I have been so very alone. Thank you for coming to keep me company.",
     "4. The Flame Chamber"),

    ("am_michael", "Kaelen",
     "Bram, hold. Lyra, what is that light?",
     "4. The Flame Chamber"),

    ("af_heart", "Lyra",
     "It's the original flame. The one the temple was built to guard. "
     "Kaelen, if Ysolde's lantern touches it — I don't know. The texts say the bearer must choose. "
     "She must give her flame to the greater one, or take the greater one into herself. "
     "Either way, she will not walk out of here unchanged.",
     "4. The Flame Chamber"),

    ("am_onyx", "Dax",
     "Ysolde. You knew this. You knew, and you brought us down here anyway.",
     "4. The Flame Chamber"),

    ("bf_alice", "Ysolde",
     "Yes, Dax. I knew. I did not bring you here to die. I brought you here to witness. "
     "Someone must remember what happens next, and I cannot carry the story and the flame both. "
     "Lyra — you will carry the story. Promise me.",
     "4. The Flame Chamber"),

    ("af_heart", "Lyra",
     "Ysolde, no. There has to be another way. The texts — there are always gaps in the texts. "
     "Let me read them again. Let me — ",
     "4. The Flame Chamber"),

    ("bf_alice", "Ysolde",
     "Lyra. My friend. There is no time, and there is no other way, and I have known that since "
     "the morning I lit this lantern. Promise me you will remember. All of you. Promise me, "
     "and then step back, because what comes next will not be gentle.",
     "4. The Flame Chamber"),

    ("am_fenrir", "Bram",
     "Ysolde... please. There has to be — ",
     "4. The Flame Chamber"),

    ("bf_alice", "Ysolde",
     "Bram. Hush. You jumped the bridge without hesitating. Let me do the same. "
     "Kaelen — get them back. Now.",
     "4. The Flame Chamber"),

    ("bm_george", "Narrator",
     "Kaelen did not argue. He seized Bram by the shoulder and pulled, and Dax was already moving, "
     "and Sera had Lyra by the wrist, and the five of them fell back toward the pillars as Ysolde "
     "walked forward alone, into the blue fire, the small gold flame in her lantern held out before her "
     "like a hand extended to a stranger in the dark.",
     "4. The Flame Chamber"),

    ("bm_george", "Narrator",
     "The two flames met. And the mountain, which had held its breath for a thousand years, "
     "remembered how to breathe.",
     "4. The Flame Chamber"),

    ("bm_george", "Narrator",
     "What came after, Lyra wrote down. She wrote it in the back of the map, in a hand that shook, "
     "by the light of a flame she would not name. She wrote that the blue fire took Ysolde, "
     "and that Ysolde took it in return, and that when the light faded there was a woman standing "
     "where no woman could stand, and she was smiling, and she was not entirely Ysolde anymore, "
     "and she was not entirely anything else either. She wrote that the stone figures uncovered their faces. "
     "She wrote that the river, far behind them, began at last to sing.",
     "4. The Flame Chamber"),

    ("bm_george", "Narrator",
     "And she wrote one line more, in the margin, in a smaller hand, as though she were afraid "
     "even the paper might overhear: 'It was not a sacrifice. It was a bargain. "
     "And I think, in the end, she got the better of it.'",
     "4. The Flame Chamber"),

    ("bm_george", "Narrator",
     "The Company of the Last Light climbed back into the dawn a half-hour later, six instead of seven, "
     "and the sea was the color of new silver, and the wind had died, and the stair behind them "
     "closed like a mouth that had finished speaking. Lyra folded the map. Kaelen did not sheathe his sword "
     "for a long while. And Bram — Bram did not speak at all, all the way home, "
     "which is how those who knew him best knew that something had truly changed.",
     "4. The Flame Chamber"),

    ("bm_george", "Narrator",
     "So ends the Descent of Ysolde's Light. So begins, perhaps, something else.",
     "4. The Flame Chamber"),
]


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def gen(pipeline, text, voice):
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


def write_base_story(path):
    """Write the story as readable prose with location headers."""
    lines = []
    lines.append("# The Descent of Ysolde's Light")
    lines.append("")
    lines.append("**Cast:**")
    lines.append("- Narrator — *bm_george* (British male, older)")
    lines.append("- Kaelen — *am_michael* (seasoned warrior, leader)")
    lines.append("- Lyra — *af_heart* (scholar, keeper of lore)")
    lines.append("- Dax — *am_onyx* (grizzled veteran, skeptic)")
    lines.append("- Sera — *af_nova* (scout, quiet)")
    lines.append("- Bram — *am_fenrir* (young warrior, hotheaded)")
    lines.append("- Ysolde — *bf_alice* (noblewoman, healer, light-bearer)")
    lines.append("- The Hollow — *am_liam* (antagonist, echoing/inhuman)")
    lines.append("")
    lines.append("---")
    lines.append("")
    current_loc = None
    for voice, speaker, text, location in STORY:
        if location != current_loc:
            current_loc = location
            lines.append(f"## {location}")
            lines.append("")
        if speaker == "Narrator":
            lines.append(text)
            lines.append("")
        else:
            lines.append(f"**{speaker}:** {text}")
            lines.append("")
    path.write_text("\n".join(lines))


def write_input_text(path):
    """Write the voice-edited input: one segment per line, [voice] tag prefix."""
    lines = []
    current_loc = None
    for voice, speaker, text, location in STORY:
        if location != current_loc:
            current_loc = location
            lines.append(f"# --- {location} ---")
        tag = f"[{voice}]"
        lines.append(f"{tag} {text}")
        lines.append("")
    path.write_text("\n".join(lines))


def main():
    log("=" * 70)
    log(f"Ensemble #2 — 'The Descent of Ysolde's Light' — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    # Write the text deliverables first (no model needed)
    story_path = OUT_DIR / "ensemble2_the_descent.md"
    input_path = OUT_DIR / "ensemble2_the_descent_input.txt"
    write_base_story(story_path)
    write_input_text(input_path)
    log(f"[text] base story  -> {story_path} ({story_path.stat().st_size} bytes)")
    log(f"[text] voice input -> {input_path} ({input_path.stat().st_size} bytes)")

    # Generate audio
    log("")
    log("[setup] importing kokoro + torch...")
    t0 = time.time()
    log(f"[setup] torch {torch.__version__}, MPS available: {torch.backends.mps.is_available()}")
    log("[setup] building KPipeline(lang_code='a')...")
    pipeline = KPipeline(lang_code="a")
    log(f"[setup] pipeline ready in {time.time()-t0:.1f}s")
    log(f"[setup] {len(STORY)} segments to generate")

    chunks = []
    total_gen = 0.0
    for idx, (voice, speaker, text, location) in enumerate(STORY, 1):
        tag = f"[{idx:2d}/{len(STORY)}] {voice} ({speaker})"
        try:
            audio, dt = gen(pipeline, text, voice)
            if len(audio) == 0:
                raise RuntimeError("empty audio")
            chunks.append(audio)
            total_gen += dt
            dur = len(audio) / SAMPLE_RATE
            log(f"{tag}: {dur:.2f}s in {dt:.2f}s — [{location}] \"{text[:55]}...\"")
        except Exception as e:
            log(f"{tag}: FAILED — {e}")

    if not chunks:
        log("ERROR: no audio generated")
        return

    audio_full = np.concatenate(chunks)
    wav_path = OUT_DIR / "ensemble2_the_descent.wav"
    sz = save_wav(audio_full, wav_path)
    total_dur = len(audio_full) / SAMPLE_RATE

    log("")
    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    log(f"  segments:        {len(STORY)}")
    log(f"  total audio:     {total_dur:.1f}s ({total_dur/60:.1f} min)")
    log(f"  total gen time:  {total_gen:.1f}s ({total_gen/60:.1f} min)")
    log(f"  overall speed:   {total_dur/total_gen:.1f}x real-time")
    log(f"  wav file:        {wav_path} ({sz} bytes)")
    log(f"  base story:      {story_path}")
    log(f"  voice input:     {input_path}")
    log(f"  log:             {LOG}")
    log("DONE")


if __name__ == "__main__":
    main()
