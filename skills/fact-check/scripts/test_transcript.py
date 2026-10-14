"""Focused regression checks; run with python -m unittest discover -s this_directory."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('transcript.py')


class TranscriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert SCRIPT.exists(), 'Transcript CLI has not been implemented'
        spec = importlib.util.spec_from_file_location('transcript', SCRIPT)
        cls.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cli)

    def test_rolling_captions_preserve_repetition_and_strip_tags(self):
        cues = self.cli.parse_captions('''WEBVTT

00:00:00.000 --> 00:00:02.000
नमस्ते <00:00:01.000><c>भारत</c>

00:00:01.500 --> 00:00:03.000
नमस्ते भारत आज

00:00:10.000 --> 00:00:12.000
नमस्ते भारत आज
''')
        self.assertEqual([c['text'] for c in cues], ['नमस्ते भारत', 'आज', 'नमस्ते भारत आज'])
        self.assertEqual(cues[-1]['start'], 10)

    def test_srt_multiline_and_empty_rejected(self):
        cues = self.cli.parse_captions('1\n00:00:01,250 --> 00:00:03,000\nHello\nworld\n')
        self.assertEqual(cues[0], {'start': 1.25, 'end': 3.0, 'text': 'Hello world'})
        self.assertEqual(self.cli.parse_captions('WEBVTT\n'), [])

    def test_caption_keeps_spoken_numbers(self):
        cues = self.cli.parse_captions('1\n00:00:01,000 --> 00:00:02,000\n104\n\n2\n00:00:02,000 --> 00:00:03,000\npeople\n')
        self.assertEqual([cue['text'] for cue in cues], ['104', 'people'])

    def test_overlapping_asr_chunks_do_not_duplicate_boundary_words(self):
        segments = [{'start': 0, 'end': 11, 'text': 'Ask what you can do for your country.'},
                    {'start': 9, 'end': 20, 'text': 'your country. Next sentence.'}]
        self.assertEqual([x['text'] for x in self.cli.deduplicate_segments(segments)],
                         ['Ask what you can do for your country.', 'Next sentence.'])

    def test_overlap_ignores_sentence_case_and_punctuation(self):
        segments = [{'start': 0, 'end': 11, 'text': 'Ask what you can do for your country.'},
                    {'start': 9, 'end': 11, 'text': 'You can do for your country!'}]
        self.assertEqual(len(self.cli.deduplicate_segments(segments)), 1)

    def test_asr_metadata_and_invalid_response(self):
        self.assertEqual(self.cli.asr_text({'text': 'language Hindi<asr_text>नमस्ते'}), ('नमस्ते', 'Hindi'))
        for data in ({'text': None}, {'text': ''}, {'text': 'language Hindi<asr_text>'}):
            with self.assertRaises(ValueError):
                self.cli.asr_text(data)

    def test_caption_choice_never_defaults_to_english_translation(self):
        info = {'language': 'hi', 'subtitles': {'en': [{}]}, 'automatic_captions': {'hi': [{}], 'en': [{}]}}
        self.assertEqual(self.cli.choose_caption(info, None), ('automatic', 'hi'))
        self.assertEqual(self.cli.choose_caption(info, 'en'), ('manual', 'en'))
        self.assertIsNone(self.cli.choose_caption(info, 'fr'))

    def test_ambiguous_language_requires_selection(self):
        with self.assertRaises(ValueError):
            self.cli.choose_caption({'subtitles': {'hi': [{}], 'en': [{}]}}, None)

    def test_local_transcript_resume_and_source_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            source = base / 'input.txt'
            source.write_text('A supplied transcript.', encoding='utf-8')
            args = self.cli.parser().parse_args(['fetch', str(source), '--output', str(base / 'job')])
            self.cli.fetch(args)
            self.cli.fetch(args)
            self.assertEqual((base / 'job/transcript.txt').read_text().strip(), 'A supplied transcript.')
            source.write_text('Changed input', encoding='utf-8')
            with self.assertRaises(ValueError):
                self.cli.fetch(args)


if __name__ == '__main__':
    unittest.main()
