import sys
from pathlib import Path
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from diagnostics import check_source, failure_kind


class DiagnosticsTests(unittest.TestCase):
    def test_distinct_and_mixed_failures(self):
        for lines, expected in ((['접속 실패'], 'connection_failure'), (['페이지 구조 변경'], 'parser_change'),
                                (['접속 실패', '페이지 구조 변경'], 'mixed_failure'),
                                (['책 없음'], 'not_found'), ([], 'unknown_failure')):
            self.assertEqual(failure_kind(lines), expected)

    def test_failure_does_not_skip_next_search_and_partial_fields_are_reported(self):
        class Source:
            name = 'store'
            def identify(self, log, queue, abort, **kwargs):
                if kwargs['title']:
                    raise OSError('offline')
                queue.put(SimpleNamespace(title='book', isbn='123', identifiers={}, authors=['writer'],
                                          publisher='publisher', comments=None))
            def download_cover(self, log, queue, abort, **kwargs):
                queue.put((self, b'validated image'))
        rows = check_source(Source(), 'book', ['writer'], '123')
        self.assertEqual(len(rows), 2)
        self.assertIn('OSError', rows[0]['error'])
        self.assertEqual(rows[1]['status'], 'partial_metadata')
        self.assertEqual(rows[1]['missing_fields'], ['comments', 'toc'])
