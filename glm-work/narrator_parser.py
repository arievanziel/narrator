"""Narrator text parser — splits pasted text into TTS-ready segments.

This is a model-agnostic preprocessing layer. It takes text pasted from a Claude
chat and produces a list of Segment objects that any TTS engine can consume.

Supported patterns:
- [S1]/[S2] speaker tags → segment with speaker label
- "quoted dialogue" → character speech (detected even without speaker tags)
- (whispering), (shouting), etc. → emotion cues
- [beat]/[long beat] → pause markers
- Unquoted text between dialogue → narrator segment

The emotion mappings are adapted from the multivoice project (wcharliebrown).
See glm-work/notes/pipeline_design_reference.md for the full reference.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Segment:
    """A single segment of narration or dialogue, ready for TTS generation."""
    speaker: str  # "narrator", "S1", "S2", or a character name
    text: str
    emotion: Optional[str] = None  # "whispering", "shouting", etc.
    pause_after: float = 0.0  # seconds of silence to insert after this segment

    def __repr__(self):
        emo = f" emotion={self.emotion}" if self.emotion else ""
        pause = f" pause={self.pause_after}s" if self.pause_after > 0 else ""
        return f"Segment(speaker={self.speaker!r}, text={self.text[:50]!r}...{emo}{pause})"


# Emotion/delivery cue mappings (adapted from multivoice project)
# Maps stage direction keywords to TTS instruction text
EMOTION_MAPPINGS = {
    # Loudness
    "whispering": "Speak in a soft, hushed whisper.",
    "whispered": "Speak in a soft, hushed whisper.",
    "quietly": "Speak softly and quietly.",
    "muttering": "Speak in a low, mumbled tone under your breath.",
    "murmuring": "Speak softly in a low, gentle murmur.",
    "hissing": "Speak in a sharp, forceful whisper with sibilant emphasis.",
    "shouting": "Speak loudly and forcefully, almost yelling.",
    "yelling": "Speak very loudly, yelling with intensity.",
    "loudly": "Speak in a loud, raised voice.",
    "calling": "Speak loudly as if calling out to someone.",
    "calling out": "Speak loudly, calling out to someone in the distance.",

    # Emotions - Positive
    "laughing": "Speak while laughing, with joy and amusement in the voice.",
    "chuckling": "Speak with a warm, amused chuckle.",
    "smiling": "Speak with a warm smile evident in the voice.",
    "happily": "Speak with happiness and joy.",
    "excitedly": "Speak with excitement and enthusiasm.",
    "cheerfully": "Speak in a cheerful, upbeat manner.",

    # Emotions - Negative
    "angry": "Speak with anger and frustration in the voice.",
    "angrily": "Speak with intense anger.",
    "furious": "Speak with explosive fury and rage.",
    "frustrated": "Speak with evident frustration and annoyance.",
    "annoyed": "Speak with irritation and annoyance.",
    "growling": "Speak with a low, threatening growl.",

    # Emotions - Fear/Anxiety
    "scared": "Speak with fear and trembling in the voice.",
    "frightened": "Speak with fear, voice shaking slightly.",
    "terrified": "Speak with extreme terror, voice trembling.",
    "nervous": "Speak nervously, with slight hesitation.",
    "anxious": "Speak with anxiety and worry.",
    "panicking": "Speak in a panicked, breathless rush.",
    "worried": "Speak with concern and worry.",

    # Emotions - Sad
    "sad": "Speak with sadness and melancholy.",
    "sadly": "Speak with deep sadness in the voice.",
    "crying": "Speak while crying, voice choked with tears.",
    "sobbing": "Speak through sobs, voice breaking.",
    "mournfully": "Speak with grief and mourning.",
    "sighing": "Speak with a weary, resigned sigh.",

    # Emotions - Surprise
    "surprised": "Speak with surprise and astonishment.",
    "shocked": "Speak with shock and disbelief.",
    "amazed": "Speak with wonder and amazement.",
    "incredulous": "Speak with disbelief and incredulity.",

    # Delivery Style
    "sarcastically": "Speak with heavy sarcasm and irony.",
    "mockingly": "Speak in a mocking, derisive tone.",
    "seriously": "Speak in a serious, earnest tone.",
    "firmly": "Speak firmly and decisively.",
    "sternly": "Speak in a stern, authoritative manner.",
    "gently": "Speak gently and softly.",
    "tenderly": "Speak with tenderness and affection.",
    "hesitantly": "Speak with hesitation and uncertainty.",
    "confused": "Speak with confusion, as if puzzled.",
    "quickly": "Speak rapidly and hurriedly.",
    "slowly": "Speak slowly and deliberately.",
    "urgently": "Speak with urgency and importance.",
    "breathlessly": "Speak breathlessly, as if out of breath.",
    "thoughtfully": "Speak thoughtfully, as if considering carefully.",
    "dreamily": "Speak in a dreamy, distant manner.",
    "wistfully": "Speak with wistful longing.",
    "dramatically": "Speak with theatrical drama.",
    "deadpan": "Speak in a flat, emotionless deadpan.",
    "dryly": "Speak in a dry, understated manner.",
    "pleading": "Speak pleadingly, begging.",
    "begging": "Speak desperately, begging.",
    "threatening": "Speak with menace and threat.",
    "teasing": "Speak in a playful, teasing manner.",
    "impatient": "Speak with impatience.",
    "exasperated": "Speak with exasperation.",
    "resigned": "Speak with weary resignation.",
    "defeated": "Speak as if defeated, voice low.",
    "triumphant": "Speak triumphantly, with victory.",
    "proud": "Speak with pride.",
    "embarrassed": "Speak with embarrassment.",
    "apologetic": "Speak apologetically.",
}

# Pause marker mappings
PAUSE_MARKERS = {
    "[beat]": 0.7,
    "[long beat]": 1.5,
    "[pause]": 1.0,
}

# Default pause between sentences in a multi-sentence segment
SENTENCE_PAUSE = 0.3
# Default pause after narrator segments
NARRATOR_PAUSE = 0.5
# Default pause after dialogue segments
DIALOGUE_PAUSE = 0.4


def extract_emotion(text: str) -> tuple[str, Optional[str]]:
    """Extract emotion cue from parenthetical at start of text.
    
    Returns (text_without_emotion, emotion_key) or (original_text, None).
    """
    # Match (emotion) at start of line, optionally after whitespace
    m = re.match(r"^\s*\(([^)]+)\)\s*(.*)", text, re.DOTALL)
    if m:
        cue = m.group(1).strip().lower()
        rest = m.group(2).strip()
        if cue in EMOTION_MAPPINGS:
            return rest, cue
        # Try partial match (e.g. "whispering" in "whispering urgently")
        for key in EMOTION_MAPPINGS:
            if key in cue:
                return rest, key
    return text, None


def extract_pause_markers(text: str) -> tuple[str, float]:
    """Extract [beat]/[long beat] markers from text.
    
    Returns (text_without_markers, total_pause_seconds).
    """
    total_pause = 0.0
    clean_text = text
    for marker, seconds in PAUSE_MARKERS.items():
        count = clean_text.count(marker)
        if count > 0:
            total_pause += count * seconds
            clean_text = clean_text.replace(marker, "")
    # Collapse multiple spaces left by removed markers
    clean_text = re.sub(r" {2,}", " ", clean_text).strip()
    return clean_text, total_pause


def parse_speaker_tag(line: str) -> tuple[Optional[str], str]:
    """Check if a line starts with [S1]/[S2] tag.
    
    Returns (speaker_label, remaining_text) or (None, original_line).
    """
    m = re.match(r"^\[S([12])\]\s*(.*)", line)
    if m:
        return f"S{m.group(1)}", m.group(2)
    return None, line


# Quote characters: ASCII straight + Unicode curly
OPEN_QUOTES = '"\u201c\u00ab'  # " " «
CLOSE_QUOTES = '"\u201d\u00bb'  # " " »
ALL_QUOTES = OPEN_QUOTES + CLOSE_QUOTES

# Characters that end a sentence (optionally followed by a closing quote/bracket)
_SENTENCE_FINAL = set('.!?')
_SENTENCE_FINAL_SUFFIX = set('"\'\u201d\u2019\u00bb)]')  # closing quotes/brackets


def _ends_sentence_final(text: str) -> bool:
    """Check if text ends with sentence-final punctuation (., !, ?) optionally
    followed by a closing quote or bracket."""
    stripped = text.rstrip()
    if not stripped:
        return False
    last = stripped[-1]
    if last in _SENTENCE_FINAL:
        return True
    if last in _SENTENCE_FINAL_SUFFIX and len(stripped) >= 2:
        return stripped[-2] in _SENTENCE_FINAL
    return False


def join_wrapped_lines(text: str) -> list[str]:
    """Join hard-wrapped lines into logical lines.

    A line is a continuation of the previous if:
    - It's not blank
    - It doesn't start with [S1]/[S2] tag
    - The previous logical line doesn't end with sentence-final punctuation
      (., !, ? optionally followed by a closing quote/bracket)

    Blank lines are preserved as paragraph separators.
    """
    logical_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            # Blank line — paragraph break
            logical_lines.append("")
            continue
        # Check if this line starts a new segment
        starts_new = (
            line.startswith(("[S1]", "[S2]"))
            or not logical_lines
            or logical_lines[-1] == ""
            or _ends_sentence_final(logical_lines[-1])
        )
        if starts_new:
            logical_lines.append(line)
        else:
            # Continuation — join with space
            logical_lines[-1] = logical_lines[-1] + " " + line
    return logical_lines


def is_dialogue(text: str) -> bool:
    """Check if text looks like quoted dialogue (starts and ends with quotes).

    Lines with more than 2 quotes likely contain narrator attribution
    (e.g. '"No," she said. "I won't again."') and are classified as
    narrator, not pure dialogue.
    """
    stripped = text.strip()
    if len(stripped) < 2:
        return False
    first = stripped[0]
    last = stripped[-1]
    if first not in OPEN_QUOTES or last not in CLOSE_QUOTES:
        return False
    # Count quote characters — >2 means mixed dialogue + attribution
    quote_count = sum(1 for ch in stripped if ch in ALL_QUOTES)
    return quote_count <= 2


def parse_text(text: str) -> list[Segment]:
    """Parse pasted text into a list of TTS-ready segments.

    Handles:
    - [S1]/[S2] speaker tags
    - (emotion) cues
    - [beat]/[long beat] pause markers
    - Quoted dialogue (auto-labeled as "character")
    - Unquoted text (labeled as "narrator")
    - Hard line-wrapping (joined into logical lines before parsing)
    """
    segments = []

    for line in join_wrapped_lines(text):
        if not line:
            continue
        
        # Check for pause-only lines
        clean, pause = extract_pause_markers(line)
        if not clean and pause > 0:
            # This line is only a pause marker — add to previous segment
            if segments:
                segments[-1].pause_after += pause
            continue
        
        # Check for speaker tag
        speaker, remaining = parse_speaker_tag(clean)
        
        if speaker:
            # This is a tagged dialogue line
            remaining, emotion = extract_emotion(remaining)
            remaining, line_pause = extract_pause_markers(remaining)
            segments.append(Segment(
                speaker=speaker,
                text=remaining,
                emotion=emotion,
                pause_after=line_pause + DIALOGUE_PAUSE,
            ))
        elif is_dialogue(clean):
            # Quoted dialogue without speaker tag
            inner, emotion = extract_emotion(clean)
            inner, line_pause = extract_pause_markers(inner)
            # Strip quotes
            inner = inner.strip('""""')
            segments.append(Segment(
                speaker="character",
                text=inner,
                emotion=emotion,
                pause_after=line_pause + DIALOGUE_PAUSE,
            ))
        else:
            # Narrator text
            inner, emotion = extract_emotion(clean)
            inner, line_pause = extract_pause_markers(inner)
            segments.append(Segment(
                speaker="narrator",
                text=inner,
                emotion=emotion,
                pause_after=line_pause + NARRATOR_PAUSE,
            ))
    
    return segments


def segments_to_text(segments: list[Segment], for_single_speaker: bool = False) -> str:
    """Convert segments back to plain text (for single-speaker TTS models).

    If for_single_speaker=True, strips speaker labels and emotion cues,
    producing one continuous text block.
    """
    if for_single_speaker:
        return " ".join(s.text for s in segments if s.text)
    else:
        lines = []
        for s in segments:
            prefix = f"[{s.speaker}]" if s.speaker != "narrator" else ""
            emo = f" ({s.emotion})" if s.emotion else ""
            # Build line, avoiding leading space when prefix is empty
            line = f"{prefix}{emo} {s.text}".strip()
            lines.append(line)
        return "\n".join(lines)


def segments_to_native_multi_speaker(segments: list[Segment]) -> str:
    """Convert segments to text with inline [S1]/[S2] tags for models that
    support native multi-speaker (e.g. Dia-1.6B).

    Narrator segments are emitted without a tag (Dia treats untagged text as
    a default narrator voice). Character segments use [character] since Dia
    only supports [S1]/[S2] — the caller should map character→S1/S2 before
    sending to Dia if needed.

    Emotion cues are emitted as parentheticals before the text, which Dia
    may interpret as stage directions.
    """
    lines = []
    for s in segments:
        if s.speaker in ("S1", "S2"):
            prefix = f"[{s.speaker}] "
        elif s.speaker == "narrator":
            prefix = ""
        else:
            # character or custom — use as-is if it looks like a tag,
            # otherwise wrap in brackets
            prefix = f"[{s.speaker}] " if not s.speaker.startswith("[") else f"{s.speaker} "
        emo = f"({s.emotion}) " if s.emotion else ""
        lines.append(f"{prefix}{emo}{s.text}")
    return "\n".join(lines)


def main():
    """Demo: parse the test scripts and show the segment structure."""
    from pathlib import Path

    scripts_dir = Path(__file__).resolve().parent / "test_scripts"

    for script_file in sorted(scripts_dir.glob("*.txt")):
        print(f"\n{'='*60}")
        print(f"Parsing: {script_file.name}")
        print(f"{'='*60}")

        text = script_file.read_text()
        segments = parse_text(text)

        print(f"Found {len(segments)} segments:\n")
        for i, seg in enumerate(segments):
            print(f"  [{i:2d}] {seg}")

        # Show all three output modes
        single_text = segments_to_text(segments, for_single_speaker=True)
        print(f"\nSingle-speaker mode ({len(single_text)} chars):")
        print(f"  {single_text[:120]}...")

        native_text = segments_to_native_multi_speaker(segments)
        print(f"\nNative multi-speaker mode (Dia-style, {len(native_text)} chars):")
        for line in native_text.splitlines()[:5]:
            print(f"  {line}")
        if native_text.count("\n") > 5:
            print(f"  ... ({native_text.count(chr(10)) + 1} lines total)")


if __name__ == "__main__":
    main()
