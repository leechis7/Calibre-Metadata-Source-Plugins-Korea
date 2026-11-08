import unittest
import gzip
from lxml.html import fromstring
from support import load_adapter

cleaner = load_adapter('yes24').__dict__
from calibre_plugins.yes24_com.text_cleaner import clean_html, comments, decode_html, isbn_key, parse_date


class CleanerTests(unittest.TestCase):
    def test_duplicate_sections_empty_controls_and_corrupt_text(self):
        result = comments([('책소개', '<p>같은 소개</p>'), ('출판사 리뷰', '<div>같은  소개</div>'),
                           ('저자소개', '<button>더보기</button>'), ('목차', '깨진 \ufffd 본문')])
        self.assertEqual(result.count('<h3>'), 1)
        self.assertNotIn('출판사 리뷰', result)
        self.assertNotIn('\ufffd', result)

    def test_hidden_nodes_and_plain_korean(self):
        result = clean_html('<p>한글 소개</p><p style="display: none">광고</p><script>추적 코드</script>')
        self.assertIn('한글 소개', result)
        self.assertNotIn('광고', result)
        self.assertNotIn('추적 코드', result)
        self.assertEqual(clean_html('깨진 \ufffd 본문'), '')
        for value in ('$undefined', 'null', {'description': 'raw data'}, []):
            self.assertEqual(clean_html(value), '')

    def test_unsafe_html_removed(self):
        html = clean_html('<div onclick="bad()"><script>bad()</script><iframe src="https://example.com"></iframe><a href="javascript:bad()">link</a><img src="//image.yes24.com/a.jpg" onerror="bad()"></div>')
        self.assertNotIn('bad()', html)
        self.assertNotIn('<iframe', html)
        self.assertIn('https://image.yes24.com/a.jpg', html)

    def test_toc_option_and_plain_text(self):
        html = comments([('책소개', '소개\n다음 줄'), ('목차', '목차 내용')], False)
        self.assertNotIn('목차', html)
        self.assertEqual(len(fromstring(html).xpath('.//br')), 1)

    def test_encoding_and_date(self):
        self.assertEqual(decode_html('한국어'.encode('cp949')), '한국어')
        self.assertEqual(decode_html(gzip.compress('한국어'.encode('utf-8'))), '한국어')
        self.assertEqual(parse_date('20240328').day, 28)
        self.assertEqual(parse_date('2024년 03월 28일').year, 2024)
        self.assertIsNone(parse_date('2024-02-30'))

    def test_equivalent_isbn(self):
        self.assertEqual(isbn_key('8936434268'), isbn_key('9788936434267'))
