"""Tests for narrator_parser.py — run with: python test_parser.py

Two kinds of tests:
1. Unit tests — test individual functions (extract_emotion, is_dialogue, etc.)
2. Integration tests — parse the 3 test scripts and verify segment counts/speakers

These test the PARSER LOGIC only (no audio, no TTS models).
"""
import sys
import unittest
from pathlib import Path

# Add parent dir to path so we can import narrator_parser
sys.path.insert(0, str(Path(__file__).resolve().parent))
from narrator_parser import (
    Segment,
    extract_emotion,
    extract_pause_markers,
    parse_speaker_tag,
    is_dialogue,
    join_wrapped_lines,
    parse_text,
    segments_to_text,
    segments_to_native_multi_speaker,
    _ends_sentence_final,
    OPEN_QUOTES,
    CLOSE_QUOTES,
)


class TestExtractEmotion(unittest.TestCase):
    """Test emotion cue extraction from parentheticals."""

    def test_known_emotion_at_start(self):
        text, emotion = extract_emotion("(whispering) Hello there.")
        self.assertEqual(emotion, "whispering")
        self.assertEqual(text, "Hello there.")

    def test_no_emotion(self):
        text, emotion = extract_emotion("Just normal text.")
        self.assertIsNone(emotion)
        self.assertEqual(text, "Just normal text.")

    def test_partial_emotion_match(self):
        # "whispering urgently" should match "whispering" via partial match
        text, emotion = extract_emotion("(whispering urgently) Don't move.")
        self.assertEqual(emotion, "whispering")
        self.assertEqual(text, "Don't move.")

    def test_unknown_parenthetical_not_emotion(self):
        # A parenthetical that's not a known emotion should not be extracted
        text, emotion = extract_emotion("(to himself) This is bad.")
        self.assertIsNone(emotion)
        # Text should be unchanged (the parenthetical stays)
        self.assertIn("(to himself)", text)


class TestExtractPauseMarkers(unittest.TestCase):
    """Test [beat]/[long beat] pause marker extraction."""

    def test_beat(self):
        text, pause = extract_pause_markers("Hello [beat] world")
        self.assertEqual(text, "Hello world")
        self.assertAlmostEqual(pause, 0.7)

    def test_long_beat(self):
        text, pause = extract_pause_markers("Hello [long beat] world")
        self.assertEqual(text, "Hello world")
        self.assertAlmostEqual(pause, 1.5)

    def test_multiple_markers(self):
        text, pause = extract_pause_markers("A [beat] B [beat] C")
        self.assertEqual(text, "A B C")
        self.assertAlmostEqual(pause, 1.4)

    def test_no_markers(self):
        text, pause = extract_pause_markers("No markers here.")
        self.assertEqual(text, "No markers here.")
        self.assertAlmostEqual(pause, 0.0)


class TestParseSpeakerTag(unittest.TestCase):
    """Test [S1]/[S2] speaker tag parsing."""

    def test_s1(self):
        speaker, text = parse_speaker_tag('[S1] "Hello"')
        self.assertEqual(speaker, "S1")
        self.assertEqual(text, '"Hello"')

    def test_s2(self):
        speaker, text = parse_speaker_tag("[S2] Hi there")
        self.assertEqual(speaker, "S2")
        self.assertEqual(text, "Hi there")

    def test_no_tag(self):
        speaker, text = parse_speaker_tag("Just narration.")
        self.assertIsNone(speaker)
        self.assertEqual(text, "Just narration.")


class TestIsDialogue(unittest.TestCase):
    """Test dialogue detection."""

    def test_pure_dialogue_ascii(self):
        self.assertTrue(is_dialogue('"Wrong how?"'))

    def test_pure_dialogue_curly(self):
        self.assertTrue(is_dialogue('\u201cWrong how?\u201d'))

    def test_mixed_with_attribution(self):
        # Has >2 quotes → contains attribution → not pure dialogue
        self.assertFalse(is_dialogue('"No," she said. "I won\'t again."'))

    def test_narration(self):
        self.assertFalse(is_dialogue("The wind blew cold."))

    def test_starts_quote_ends_nonquote(self):
        self.assertFalse(is_dialogue('"You\'re not from here," he said.'))

    def test_empty(self):
        self.assertFalse(is_dialogue(""))


class TestEndsSentenceFinal(unittest.TestCase):
    """Test sentence-final punctuation detection."""

    def test_period(self):
        self.assertTrue(_ends_sentence_final("Hello."))
        self.assertTrue(_ends_sentence_final("Hello. "))

    def test_question_mark(self):
        self.assertTrue(_ends_sentence_final("What?"))

    def test_exclamation(self):
        self.assertTrue(_ends_sentence_final("Go!"))

    def test_period_then_quote(self):
        self.assertTrue(_ends_sentence_final('she said.'))
        self.assertTrue(_ends_sentence_final('"Not yet."'))
        self.assertTrue(_ends_sentence_final('\u201cNot yet.\u201d'))

    def test_no_sentence_final(self):
        self.assertFalse(_ends_sentence_final("and then"))
        self.assertFalse(_ends_sentence_final("cold, unnervingly"))
        self.assertFalse(_ends_sentence_final(""))

    def test_comma_not_final(self):
        self.assertFalse(_ends_sentence_final("nothing,"))


class TestJoinWrappedLines(unittest.TestCase):
    """Test hard line-wrap joining."""

    def test_join_continuation(self):
        text = "First line that continues\nonto the next line."
        lines = join_wrapped_lines(text)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0], "First line that continues onto the next line.")

    def test_blank_line_separates(self):
        text = "First paragraph.\n\nSecond paragraph."
        lines = join_wrapped_lines(text)
        self.assertEqual(len(lines), 3)  # includes the blank line
        self.assertEqual(lines[0], "First paragraph.")
        self.assertEqual(lines[1], "")
        self.assertEqual(lines[2], "Second paragraph.")

    def test_speaker_tag_starts_new(self):
        text = '[S1] "Hello."\n[S2] "Hi."'
        lines = join_wrapped_lines(text)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], '[S1] "Hello."')
        self.assertEqual(lines[1], '[S2] "Hi."')

    def test_continuation_after_nonfinal(self):
        text = '[S1] "It\'s not moving. Not even the reeds." She dipped a finger in — cold, unnervingly\ncold — and pulled back sharp.'
        lines = join_wrapped_lines(text)
        self.assertEqual(len(lines), 1)
        self.assertIn("cold — and pulled back sharp.", lines[0])

    def test_new_line_after_sentence_final(self):
        text = '[S1] "Don\'t. Not yet."\nSomewhere behind them, branches cracked.'
        lines = join_wrapped_lines(text)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], '[S1] "Don\'t. Not yet."')
        self.assertEqual(lines[1], "Somewhere behind them, branches cracked.")


class TestParseText(unittest.TestCase):
    """Test full text parsing."""

    def test_speaker_tag_with_emotion(self):
        segments = parse_text('[S2] (whispering) "That\'s not exactly comforting."')
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].speaker, "S2")
        self.assertEqual(segments[0].emotion, "whispering")
        self.assertIn("comforting", segments[0].text)

    def test_narrator_segment(self):
        segments = parse_text("The wind blew cold across the marsh.")
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].speaker, "narrator")
        self.assertIsNone(segments[0].emotion)

    def test_pure_dialogue_segment(self):
        segments = parse_text('"Wrong how?"')
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].speaker, "character")

    def test_mixed_dialogue_narration_is_narrator(self):
        segments = parse_text('"No," she said. "I won\'t again."')
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].speaker, "narrator")

    def test_pause_marker_only_line(self):
        segments = parse_text('First line.\n[beat]')
        self.assertEqual(len(segments), 1)
        self.assertGreater(segments[0].pause_after, 0.5)  # beat adds 0.7

    def test_empty_text(self):
        self.assertEqual(parse_text(""), [])
        self.assertEqual(parse_text("\n\n\n"), [])


class TestOutputModes(unittest.TestCase):
    """Test the three output format modes."""

    def setUp(self):
        self.segments = [
            Segment(speaker="narrator", text="The wind blew."),
            Segment(speaker="S1", text="Hello there."),
            Segment(speaker="S2", text="Hi.", emotion="whispering"),
        ]

    def test_single_speaker_mode(self):
        text = segments_to_text(self.segments, for_single_speaker=True)
        self.assertNotIn("[S1]", text)
        self.assertNotIn("[S2]", text)
        self.assertIn("The wind blew.", text)
        self.assertIn("Hello there.", text)

    def test_tagged_mode(self):
        text = segments_to_text(self.segments, for_single_speaker=False)
        self.assertIn("[S1]", text)
        self.assertIn("[S2]", text)
        self.assertIn("(whispering)", text)
        # Narrator lines have no prefix
        first_line = text.splitlines()[0]
        self.assertTrue(first_line.startswith("The wind blew."))

    def test_native_multi_speaker_mode(self):
        text = segments_to_native_multi_speaker(self.segments)
        lines = text.splitlines()
        # Narrator has no tag
        self.assertFalse(lines[0].startswith("["))
        # S1 has [S1] tag
        self.assertTrue(lines[1].startswith("[S1]"))
        # S2 has [S2] tag with emotion
        self.assertTrue(lines[2].startswith("[S2]"))
        self.assertIn("(whispering)", lines[2])


class TestIntegrationTestScripts(unittest.TestCase):
    """Integration tests against the 3 test scripts."""

    @property
    def scripts_dir(self) -> Path:
        return Path(__file__).resolve().parent / "test_scripts"

    def test_script1_single_speaker(self):
        """Test 1: single speaker — all segments should be narrator."""
        text = (self.scripts_dir / "1_single_speaker.txt").read_text()
        segments = parse_text(text)
        self.assertEqual(len(segments), 4)
        for seg in segments:
            self.assertEqual(seg.speaker, "narrator",
                f"Segment '{seg.text[:40]}...' should be narrator, got {seg.speaker}")

    def test_script2_multi_speaker(self):
        """Test 2: multi-speaker — should have S1, S2, and narrator segments."""
        text = (self.scripts_dir / "2_multi_speaker.txt").read_text()
        segments = parse_text(text)
        self.assertEqual(len(segments), 10)

        # Check speaker sequence
        speakers = [s.speaker for s in segments]
        self.assertEqual(speakers, [
            "S1", "S2", "S1", "S2", "S1",
            "narrator",  # "Somewhere behind them..."
            "S2", "S1", "S2", "S1"
        ])

        # Check emotion on the whispering line (segment 8)
        self.assertEqual(segments[8].emotion, "whispering")

        # Check that the wrapped S1 line was joined
        self.assertIn("cold — and pulled back sharp.", segments[2].text)

        # Check narrator segment is "Somewhere behind them..."
        self.assertIn("Somewhere behind them", segments[5].text)

    def test_script3_long_form(self):
        """Test 3: long form — 12 narrator segments (one per paragraph)."""
        text = (self.scripts_dir / "3_long_form.txt").read_text()
        segments = parse_text(text)
        self.assertEqual(len(segments), 12)
        for seg in segments:
            self.assertEqual(seg.speaker, "narrator",
                f"Segment '{seg.text[:40]}...' should be narrator, got {seg.speaker}")

    def test_script3_first_segment_is_full_paragraph(self):
        """Verify line-wrapping was joined — first segment should be a full paragraph."""
        text = (self.scripts_dir / "3_long_form.txt").read_text()
        segments = parse_text(text)
        first = segments[0].text
        # The first paragraph should contain text from multiple wrapped lines
        self.assertIn("The marsh had a memory", first)
        self.assertIn("did not laugh back", first)
        self.assertGreater(len(first), 200)  # Should be a substantial paragraph


if __name__ == "__main__":
    unittest.main(verbosity=2)
