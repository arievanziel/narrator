"""Ensemble story #2 — Qwen3-TTS VoiceDesign version of 'The Descent of Ysolde's Light'.

Same story as run_ensemble2.py (Kokoro), but generated with Qwen3-TTS VoiceDesign
via mlx-audio. Each character gets a natural-language voice description instead of
a preset voice name. This is the key comparison: can VoiceDesign produce distinct,
character-appropriate voices that match or exceed Kokoro's preset voices?

Outputs (all in glm-work/outputs/voice_catalog/):
  ensemble2_the_descent_qwen3.md        — story with VoiceDesign descriptions
  ensemble2_the_descent_qwen3_input.txt — voice-edited input (segments with [voice_desc] tags)
  ensemble2_the_descent_qwen3.wav       — the final audio

Run:  python run_ensemble2_qwen3.py
"""
import time
import numpy as np
import soundfile as sf
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "outputs" / "voice_catalog"
LOG = ROOT / "logs" / "ensemble2_qwen3.log"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG.parent.mkdir(parents=True, exist_ok=True)

# Use local path (manually downloaded via curl) — NOT the HF repo ID.
MODEL = str(ROOT / "models" / "qwen3_voicedesign_8bit")

# ---------------------------------------------------------------------------
# Voice descriptions for VoiceDesign — one per character
# ---------------------------------------------------------------------------
# These natural-language descriptions replace Kokoro's preset voice names.
# Each description captures the character's personality, age, gender, and tone.

VOICE_DESCRIPTIONS = {
    "Narrator": (
        "A mature British male narrator with a deep, resonant voice. He speaks "
        "with the measured cadence of a seasoned storyteller — warm but grave, "
        "with a weight that suggests he has witnessed the events he describes. "
        "Slight rasp, unhurried pace, clear diction."
    ),
    "Kaelen": (
        "A man in his forties, battle-worn but steady. His voice is firm and "
        "authoritative, the voice of someone accustomed to giving orders that "
        "others follow without question. Mid-to-low pitch, clipped military "
        "precision, no wasted words."
    ),
    "Lyra": (
        "A woman in her thirties, a scholar by training. Her voice is calm and "
        "precise, with a thoughtful, bookish quality. She speaks carefully, as "
        "though each word has been weighed. Warm but measured, mid-range pitch, "
        "slightly breathy on emphasized words."
    ),
    "Dax": (
        "A grizzled man in his fifties, skeptical and dry. His voice is rough "
        "and low, with a gravelly texture that comes from years of smoke and "
        "shouted orders. He speaks slowly, with a sardonic edge — every sentence "
        "carries the weight of someone who has seen too much to be surprised."
    ),
    "Sera": (
        "A young woman, quiet and watchful. Her voice is soft and low, almost "
        "a murmur, as if she is accustomed to speaking in places where sound "
        "travels dangerously. Clear but hushed, with a tense alertness "
        "underneath the calm."
    ),
    "Bram": (
        "A young man in his early twenties, restless and hot-headed. His voice "
        "is energetic and bright, with a youthful edge that hasn't yet been "
        "grounded down by experience. He speaks quickly when excited, slower "
        "when afraid. Mid-range pitch, slightly breathless."
    ),
    "Ysolde": (
        "A woman in her thirties, noble-born and resolute. Her voice is clear "
        "and steady, with a quiet authority that doesn't need volume to command "
        "attention. There is warmth in it, but also iron — the voice of someone "
        "who has made a decision and will not unmake it. Mid-range, precise, "
        "with a slight formal quality."
    ),
    "The Hollow": (
        "An inhuman voice that echoes as if from deep stone. It is male-ish but "
        "wrong — too smooth, too knowing, with a hollow resonance that suggests "
        "a vast empty space behind it. Slow, deliberate, almost tender in its "
        "menace. The voice of something that remembers being human but no longer is."
    ),
}

# ---------------------------------------------------------------------------
# The story — same content as run_ensemble2.py, but keyed by speaker label
# instead of Kokoro voice name. Tuple: (speaker_label, text, location)
# ---------------------------------------------------------------------------

STORY = [
    # === Location 1: The Cliffside at Dawn ===
    ("Narrator",
     "The wind came off the Greywater Sea like a living thing, salt-edged and cold, "
     "and it bent the dead grass of the cliffside around the ruins of the old watchtower. "
     "Dawn was breaking — not the gentle dawn of the lowlands, but a hard, copper light "
     "that clawed its way over the horizon and turned the sea to hammered bronze. "
     "Seven figures stood where the tower had fallen, their cloaks snapping in the gale, "
     "looking down at a wound in the earth: a stair, black and smooth, plunging into the cliff itself.",
     "1. The Cliffside at Dawn"),

    ("Narrator",
     "Kaelen stood at the stair's edge, his hand on the hilt of a sword older than any kingdom "
     "now living. Beside him, Lyra traced a faded map with one finger, her lips moving silently. "
     "Dax squinted into the dark, arms folded, unconvinced. Sera crouched at the rim, listening. "
     "Bram paced, restless as a hound on a leash. And Ysolde — Ysolde held the lantern, "
     "and within it, a flame that had not been lit by any human hand.",
     "1. The Cliffside at Dawn"),

    ("Narrator",
     "They were the Company of the Last Light, and the mountain had been waiting for them "
     "for a very long time.",
     "1. The Cliffside at Dawn"),

    ("Kaelen",
     "Lyra. How far down?",
     "1. The Cliffside at Dawn"),

    ("Lyra",
     "The map says three hundred steps to the river, and then the river takes us under the spine "
     "of the cliff. After that... the map ends. The cartographer drew a circle and wrote one word: "
     "'beneath.'",
     "1. The Cliffside at Dawn"),

    ("Dax",
     "A map that ends with a circle and a riddle. That's not a map, Lyra. That's a warning "
     "someone was too polite to write in blood.",
     "1. The Cliffside at Dawn"),

    ("Sera",
     "Dax is right that it's a warning. He's wrong that it matters. The stair goes down, "
     "and we go down it. That's the whole of it.",
     "1. The Cliffside at Dawn"),

    ("Bram",
     "Sera, if you've seen something down there, now would be the time.",
     "1. The Cliffside at Dawn"),

    ("Sera",
     "I haven't seen it, Bram. I've heard it. Last night, in the wind. A voice, "
     "or something that remembers what a voice was. It said a name. It said Ysolde.",
     "1. The Cliffside at Dawn"),

    ("Ysolde",
     "Then it knows I'm coming. Good. Let it be afraid. "
     "Kaelen — give the order. I'm tired of standing in the wind.",
     "1. The Cliffside at Dawn"),

    ("Kaelen",
     "You heard her. Dax, you have the rear. Sera, point. Bram, with me. "
     "Lyra, stay close to Ysolde and that lantern. If the flame goes out, we are all "
     "buried in the dark. We move. Now.",
     "1. The Cliffside at Dawn"),

    # === Location 2: The Stair ===
    ("Narrator",
     "The stair swallowed them whole. The light of dawn retreated three steps in and gave up, "
     "as if the darkness were a tide and the sun had no claim here. The steps were carved from "
     "the living rock of the cliff — not rough-hewn, but polished, as though the mountain itself "
     "had been taught patience by whatever hands had made this place. The walls wept thin lines "
     "of water that caught the lantern-light and ran like veins of silver. Their footsteps echoed, "
     "and the echoes came back a half-beat too late, as if something below were walking with them, "
     "matching their pace, learning their rhythm.",
     "2. The Stair"),

    ("Narrator",
     "Down and down. The air grew thick and warm, and it tasted of old stone and older water. "
     "Sera moved first, silent as a draft, her hand on the wall. Kaelen followed, then Ysolde "
     "with the lantern held high — and the flame within it burned without flickering, without wind, "
     "a small steady gold that pushed the dark back exactly far enough for the next step, and no further.",
     "2. The Stair"),

    ("Dax",
     "Kaelen. Stop. Listen.",
     "2. The Stair"),

    ("Kaelen",
     "I hear it. Everyone still. Lyra — what is that?",
     "2. The Stair"),

    ("Lyra",
     "It's not an echo. An echo repeats. This... answers. It's using our own voices to speak back to us. "
     "Bram, don't answer it. Whatever it says, don't answer it in your own voice.",
     "2. The Stair"),

    ("The Hollow",
     "Ysolde. You bring a borrowed flame into my house. You always were the brave one. "
     "Come down, little light-bearer. Come down and we will talk as we used to.",
     "2. The Stair"),

    ("Ysolde",
     "That is not my brother. My brother died on the field at Aldermoor. Whatever you are, "
     "you wear his voice the way a thief wears a stolen coat. I am not coming down to talk. "
     "I am coming down to end this.",
     "2. The Stair"),

    ("Bram",
     "Ysolde, it spoke in your brother's voice. Are you sure — ",
     "2. The Stair"),

    ("Ysolde",
     "I am sure, Bram. I buried him myself. Move on.",
     "2. The Stair"),

    ("Narrator",
     "And so they descended, and the stair descended with them, and the dark pressed close, "
     "and the only light in a hundred miles of stone was the one Ysolde carried in her hands.",
     "2. The Stair"),

    # === Location 3: The Under-River ===
    ("Narrator",
     "The stair ended at a shore that should not have existed. A river ran through the heart of the cliff — "
     "broad, black, slow, and utterly silent. No current-sound, no lap of water on stone. It moved "
     "like glass being poured, heavy and patient, and where it touched the walls it left a faint "
     "phosphorescence, a ghost-light the color of drowned moons. A bridge of pale stone arched over it, "
     "but the bridge was broken in the middle, and the two halves hung in the dark like the arms of "
     "someone reaching for a hand they will never hold again.",
     "3. The Under-River"),

    ("Lyra",
     "The Drowned Bridge. The map didn't lie — it just didn't warn us that the bridge would be broken. "
     "Kaelen, the gap is at least ten feet. The stone is wet. A jump is possible, but not safe.",
     "3. The Under-River"),

    ("Dax",
     "Possible and not safe describes this entire journey, Lyra. Bram — you're the youngest, "
     "the lightest, and the most reckless. You first.",
     "3. The Under-River"),

    ("Bram",
     "Dax, when this is over, you and I are going to have a conversation about the way you "
     "volunteer me for things.",
     "3. The Under-River"),

    ("Dax",
     "I look forward to it, boy. Jump.",
     "3. The Under-River"),

    ("Narrator",
     "Bram ran. Three strides, a leap, and the dark swallowed him for one held breath before "
     "his boots struck the far side and he stumbled, caught himself, and turned with a grin "
     "that the lantern-light found from across the void.",
     "3. The Under-River"),

    ("Bram",
     "It holds! Sera, you next. You're lighter than me — you'll barely touch the stone.",
     "3. The Under-River"),

    ("Sera",
     "Bram, stop grinning. You nearly fell. Ysolde — the lantern. Can you make the jump with it? "
     "If the flame drops into that water, I don't know what happens. I don't want to know.",
     "3. The Under-River"),

    ("Ysolde",
     "The flame will not drop, Sera. It has been carried through worse than this. "
     "Kaelen, help me across. Lyra, Dax — follow us.",
     "3. The Under-River"),

    ("Narrator",
     "One by one they crossed, and the river beneath them did not stir, did not ripple, "
     "did not so much as whisper. It simply watched them pass, the way a thing with no eyes "
     "and all the time in the world might watch. And on the far side, the stone opened into a hall "
     "that no living person had stood in for a thousand years.",
     "3. The Under-River"),

    # === Location 4: The Flame Chamber ===
    ("Narrator",
     "The chamber was vast — so vast that the lantern-light could not find its walls, only "
     "the floor: a mirror of black stone so polished that the seven of them walked on their own "
     "reflections. Pillars rose into the dark like the trunks of trees in a drowned forest, and "
     "between the pillars, in alcoves cut with terrible care, stood figures of stone — hundreds of them, "
     "each one different, each one covering its face with its hands. At the far end of the hall, "
     "something burned. Not Ysolde's flame. Something older. Something that had been burning since before "
     "the sea had a name, a cold blue fire that threw no warmth and cast shadows that pointed the wrong way.",
     "4. The Flame Chamber"),

    ("The Hollow",
     "Welcome home, Ysolde. You brought them all. I knew you would. "
     "Kaelen with his old sword. Lyra with her old map. Dax with his old doubts. "
     "Sera with her old ears. And Bram — young Bram, who jumps before he looks. "
     "I have been so very alone. Thank you for coming to keep me company.",
     "4. The Flame Chamber"),

    ("Kaelen",
     "Bram, hold. Lyra, what is that light?",
     "4. The Flame Chamber"),

    ("Lyra",
     "It's the original flame. The one the temple was built to guard. "
     "Kaelen, if Ysolde's lantern touches it — I don't know. The texts say the bearer must choose. "
     "She must give her flame to the greater one, or take the greater one into herself. "
     "Either way, she will not walk out of here unchanged.",
     "4. The Flame Chamber"),

    ("Dax",
     "Ysolde. You knew this. You knew, and you brought us down here anyway.",
     "4. The Flame Chamber"),

    ("Ysolde",
     "Yes, Dax. I knew. I did not bring you here to die. I brought you here to witness. "
     "Someone must remember what happens next, and I cannot carry the story and the flame both. "
     "Lyra — you will carry the story. Promise me.",
     "4. The Flame Chamber"),

    ("Lyra",
     "Ysolde, no. There has to be another way. The texts — there are always gaps in the texts. "
     "Let me read them again. Let me — ",
     "4. The Flame Chamber"),

    ("Ysolde",
     "Lyra. My friend. There is no time, and there is no other way, and I have known that since "
     "the morning I lit this lantern. Promise me you will remember. All of you. Promise me, "
     "and then step back, because what comes next will not be gentle.",
     "4. The Flame Chamber"),

    ("Bram",
     "Ysolde... please. There has to be — ",
     "4. The Flame Chamber"),

    ("Ysolde",
     "Bram. Hush. You jumped the bridge without hesitating. Let me do the same. "
     "Kaelen — get them back. Now.",
     "4. The Flame Chamber"),

    ("Narrator",
     "Kaelen did not argue. He seized Bram by the shoulder and pulled, and Dax was already moving, "
     "and Sera had Lyra by the wrist, and the five of them fell back toward the pillars as Ysolde "
     "walked forward alone, into the blue fire, the small gold flame in her lantern held out before her "
     "like a hand extended to a stranger in the dark.",
     "4. The Flame Chamber"),

    ("Narrator",
     "The two flames met. And the mountain, which had held its breath for a thousand years, "
     "remembered how to breathe.",
     "4. The Flame Chamber"),

    ("Narrator",
     "What came after, Lyra wrote down. She wrote it in the back of the map, in a hand that shook, "
     "by the light of a flame she would not name. She wrote that the blue fire took Ysolde, "
     "and that Ysolde took it in return, and that when the light faded there was a woman standing "
     "where no woman could stand, and she was smiling, and she was not entirely Ysolde anymore, "
     "and she was not entirely anything else either. She wrote that the stone figures uncovered their faces. "
     "She wrote that the river, far behind them, began at last to sing.",
     "4. The Flame Chamber"),

    ("Narrator",
     "And she wrote one line more, in the margin, in a smaller hand, as though she were afraid "
     "even the paper might overhear: 'It was not a sacrifice. It was a bargain. "
     "And I think, in the end, she got the better of it.'",
     "4. The Flame Chamber"),

    ("Narrator",
     "The Company of the Last Light climbed back into the dawn a half-hour later, six instead of seven, "
     "and the sea was the color of new silver, and the wind had died, and the stair behind them "
     "closed like a mouth that had finished speaking. Lyra folded the map. Kaelen did not sheathe his sword "
     "for a long while. And Bram — Bram did not speak at all, all the way home, "
     "which is how those who knew him best knew that something had truly changed.",
     "4. The Flame Chamber"),

    ("Narrator",
     "So ends the Descent of Ysolde's Light. So begins, perhaps, something else.",
     "4. The Flame Chamber"),
]

# Qwen3-TTS max_tokens — narrator paragraphs are long, use 2400
MAX_TOKENS = 2400


def log(msg):
    print(msg, flush=True)
    with open(LOG, "a") as f:
        f.write(msg + "\n")


def find_output(output_dir, prefix):
    """Find output file with optional _000 suffix."""
    exact = Path(output_dir) / f"{prefix}.wav"
    if exact.exists():
        return exact
    suffixed = Path(output_dir) / f"{prefix}_000.wav"
    if suffixed.exists():
        return suffixed
    matches = list(Path(output_dir).glob(f"{prefix}*.wav"))
    if matches:
        return matches[0]
    return None


def write_base_story(path):
    """Write the story as readable prose with location headers and voice descriptions."""
    lines = []
    lines.append("# The Descent of Ysolde's Light — Qwen3-TTS VoiceDesign")
    lines.append("")
    lines.append("**Cast (with VoiceDesign descriptions):**")
    for speaker, desc in VOICE_DESCRIPTIONS.items():
        lines.append(f"- **{speaker}** — *{desc[:80]}...*")
    lines.append("")
    lines.append("---")
    lines.append("")
    current_loc = None
    for speaker, text, location in STORY:
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
    """Write the voice-edited input: one segment per line, [speaker] tag prefix."""
    lines = []
    current_loc = None
    for speaker, text, location in STORY:
        if location != current_loc:
            current_loc = location
            lines.append(f"# --- {location} ---")
        lines.append(f"[{speaker}] {text}")
        lines.append("")
    path.write_text("\n".join(lines))


def main():
    log("=" * 70)
    log(f"Ensemble #2 Qwen3 VoiceDesign — 'The Descent of Ysolde's Light'")
    log(f"{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    # Write text deliverables first
    story_path = OUT_DIR / "ensemble2_the_descent_qwen3.md"
    input_path = OUT_DIR / "ensemble2_the_descent_qwen3_input.txt"
    write_base_story(story_path)
    write_input_text(input_path)
    log(f"[text] base story  -> {story_path} ({story_path.stat().st_size} bytes)")
    log(f"[text] voice input -> {input_path} ({input_path.stat().st_size} bytes)")

    # Generate audio
    log("")
    log("[setup] importing mlx-audio...")
    t0 = time.time()
    from mlx_audio.tts import load_model
    from mlx_audio.tts.generate import generate_audio
    log(f"[setup] imports done in {time.time()-t0:.1f}s")

    log("[setup] loading model...")
    t0 = time.time()
    model = load_model(MODEL)
    log(f"[setup] model loaded in {time.time()-t0:.1f}s")
    log(f"[setup] {len(STORY)} segments to generate")

    # Temp dir for per-segment audio
    temp_dir = OUT_DIR / "_qwen3_temp"
    temp_dir.mkdir(exist_ok=True)

    chunks = []
    total_gen = 0.0
    sr = None

    for idx, (speaker, text, location) in enumerate(STORY, 1):
        voice_desc = VOICE_DESCRIPTIONS[speaker]
        tag = f"[{idx:2d}/{len(STORY)}] {speaker}"
        log(f"{tag}: generating... [{location}] \"{text[:55]}...\"")

        t0 = time.time()
        temp_prefix = f"seg_{idx:02d}_{speaker}"
        try:
            generate_audio(
                text=text,
                model=model,
                instruct=voice_desc,
                lang_code="en",
                max_tokens=MAX_TOKENS,
                output_path=str(temp_dir),
                file_prefix=temp_prefix,
                audio_format="wav",
                verbose=False,
            )
            dt = time.time() - t0
            total_gen += dt

            temp_file = find_output(temp_dir, temp_prefix)
            if temp_file and temp_file.exists():
                audio, sr = sf.read(str(temp_file))
                dur = len(audio) / sr
                chunks.append(audio)
                log(f"{tag}: {dur:.2f}s in {dt:.2f}s")
                temp_file.unlink()
            else:
                log(f"{tag}: ERROR — output file not found")
        except Exception as e:
            log(f"{tag}: FAILED — {e}")

    # Clean up temp dir
    try:
        temp_dir.rmdir()
    except OSError:
        pass  # dir not empty, leave it

    if not chunks:
        log("ERROR: no audio generated")
        return

    audio_full = np.concatenate(chunks)
    wav_path = OUT_DIR / "ensemble2_the_descent_qwen3.wav"
    sf.write(str(wav_path), audio_full, sr)
    total_dur = len(audio_full) / sr
    sz = wav_path.stat().st_size

    log("")
    log("=" * 70)
    log("SUMMARY")
    log("=" * 70)
    log(f"  segments:        {len(STORY)}")
    log(f"  generated:       {len(chunks)}/{len(STORY)}")
    log(f"  total audio:     {total_dur:.2f}s ({total_dur/60:.1f} min)")
    log(f"  total gen time:  {total_gen:.2f}s ({total_gen/60:.1f} min)")
    log(f"  real-time factor: {total_dur/total_gen:.2f}x" if total_gen > 0 else "")
    log(f"  output file:     {wav_path} ({sz} bytes, {sz/1048576:.1f} MB)")
    log(f"  log file:        {LOG}")
    log("DONE")


if __name__ == "__main__":
    main()
