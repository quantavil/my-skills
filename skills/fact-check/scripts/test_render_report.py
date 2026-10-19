"""Verify report rendering, optional diagrams and handling of source content."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name('render_report.py')
        assert path.exists(), 'HTML renderer has not been implemented'
        spec = importlib.util.spec_from_file_location('report', path)
        cls.report = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.report)

    def test_report_preserves_hindi_and_links_with_navigation(self):
        page = self.report.render('# परीक्षण\n\n## C1 · Claim\n\n✅ **Supported**\n\n[Evidence](https://example.org/source)')
        self.assertIn('परीक्षण', page)
        self.assertIn('href="https://example.org/source"', page)
        self.assertIn('href="#section-1"', page)
        self.assertIn('<strong class="verdict verdict-supported">Supported</strong>', page)

    def test_claims_are_separate_landmarks_without_losing_content(self):
        page = self.report.render('# Report\n\n## Findings\n\nBrief summary.\n\n## C1 · A claim\n\n✅ **Supported**\n\n> The actual quotation.\n\nExplanation with [source](https://example.org).\n\n## Coverage\n\nLimited to one claim.')
        self.assertIn('aria-labelledby="section-2"', page)
        self.assertEqual(page.count('The actual quotation.'), 1)
        self.assertEqual(page.count('Limited to one claim.'), 1)
        self.assertIn('href="https://example.org"', page)

    def test_source_content_cannot_execute_or_load_external_images(self):
        page = self.report.render('# <title>\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n![tracking](https://example.org/track.png)')
        self.assertNotIn('<script>', page)
        self.assertNotIn('href="javascript:', page)
        self.assertNotIn('src="https:', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('Content-Security-Policy', page)

    @unittest.skipUnless(shutil.which('dot'), 'Graphviz is optional')
    def test_optional_dot_map_is_embedded_without_a_network_request(self):
        page = self.report.render('# Argument\n\n```dot\ndigraph { P1 [label="A premise"]; P1 -> C; }\n```')
        self.assertIn('data:image/svg+xml;base64,', page)
        self.assertNotIn('src="http', page)

    @unittest.skipUnless(shutil.which('dot'), 'Graphviz is optional')
    def test_invalid_map_does_not_silently_disappear(self):
        with self.assertRaises(ValueError):
            self.report.render('```dot\nnot a valid graph {\n```')

    def test_code_fences_remain_code_and_empty_report_is_rejected(self):
        page = self.report.render('```python\nprint("<hello>")\n```')
        self.assertIn('&lt;hello&gt;', page)
        with self.assertRaises(ValueError):
            self.report.render('  ')

    def test_cli_preserves_input_and_rejects_overwriting_it(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'report.md'
            target = Path(folder) / 'report.html'
            source.write_text('# A report\n\nEvidence pending.', encoding='utf-8')
            self.assertEqual(self.report.main([str(source), '--output', str(target)]), 0)
            self.assertIn('Evidence pending.', target.read_text())
            self.assertEqual(source.read_text(), '# A report\n\nEvidence pending.')
            with self.assertRaises(ValueError):
                self.report.main([str(source), '--output', str(source)])

    def test_local_identity_paths_are_scrubbed(self):
        page = self.report.render('# Report\n\nPreserved in [transcript](file:///home/secretuser/projects/job/clean_transcript.txt).')
        self.assertNotIn('/home/secretuser', page)
        self.assertIn('clean_transcript.txt', page)

    @mock.patch('urllib.request.urlopen')
    def test_share_html_uploads_and_returns_url(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b'{"url": "https://example.ship.place/", "expires_at": "2026-11-18T00:00:00Z"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        res = self.report.share_html('<h1>Report</h1>')
        self.assertEqual(res['url'], 'https://example.ship.place/')
        self.assertEqual(res['expires_at'], '2026-11-18T00:00:00Z')

    @mock.patch('urllib.request.urlopen')
    def test_cli_share_flag(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b'{"url": "https://example.ship.place/", "expires_at": "2026-11-18T00:00:00Z"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'report.md'
            source.write_text('# A report\n\nEvidence pending.', encoding='utf-8')
            self.assertEqual(self.report.main([str(source), '--share']), 0)


if __name__ == '__main__':
    unittest.main()

