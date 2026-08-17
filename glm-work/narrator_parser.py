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
    return clean_text.strip(), total_pause


def parse_speaker_tag(line: str) -> tuple[Optional[str], str]:
    """Check if a line starts with [S1]/[S2] tag.
    
    Returns (speaker_label, remaining_text) or (None, original_line).
    """
    m = re.match(r"^\[S([12])\]\s*(.*)", line)
    if m:
        return f"S{m.group(1)}", m.group(2)
    return None, line


def is_dialogue(text: str) -> bool:
    """Check if text looks like quoted dialogue."""
    stripped = text.strip()
    return (stripped.startswith('"') and stripped.endswith('"')) or \
           (stripped.startswith('"') and stripped.endswith('"')) or \
           (stripped.startswith('"') and stripped.endswith('"'))


def parse_text(text: str) -> list[Segment]:
    """Parse pasted text into a list of TTS-ready segments.
    
    Handles:
    - [S1]/[S2] speaker tags
    - (emotion) cues
    - [beat]/[long beat] pause markers
    - Quoted dialogue (auto-labeled as "character")
    - Unquoted text (labeled as "narrator")
    """
    segments = []
    
    for raw_line in text.strip().splitlines():
        line = raw_line.strip()
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
            lines.append(f"{prefix}{emo} {s.text}")
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
        
        # Show single-speaker adaptation
        single_text = segments_to_text(segments, for_single_speaker=True)
        print(f"\nSingle-speaker adaptation ({len(single_text)} chars):")
        print(f"  {single_text[:100]}...")


if __name__ == "__main__":
    main()
