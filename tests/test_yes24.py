import unittest
from support import fixture, load_adapter

worker = load_adapter('yes24')


class YES24Tests(unittest.TestCase):
    def test_recommended_book_json_does_not_supply_the_main_introduction(self):
        raw = '''<html><script type="application/ld+json">[
          {"@type":"Book","sku":"999","name":"다른 책","description":"다른 책 소개"},
          {"@type":"Book","sku":"125557465","name":"요청한 책","description":"올바른 소개"}
        ]</script></html>'''
        book = worker.parse_details(raw, 'https://www.yes24.com/Product/Goods/125557465')
        self.assertEqual(dict(book['sections'])['책소개'], '올바른 소개')
        self.assertEqual(book['title'], '요청한 책')

    def test_canonical_product_mismatch_is_rejected(self):
        raw = '<meta property="og:url" content="https://www.yes24.com/Product/Goods/999">'
        with self.assertRaises(ValueError):
            worker.parse_details(raw, 'https://www.yes24.com/Product/Goods/125557465')

    def test_real_structure_search(self):
        self.assertEqual(worker.search_results(fixture('yes24_search.html')), ['https://www.yes24.com/Product/Goods/125557465'])

    def test_real_structure_details(self):
        book = worker.parse_details(fixture('yes24_detail.html'), 'https://www.yes24.com/Product/Goods/125557465')
        self.assertEqual(book['title'], '하루 한 장 나의 어휘력을 위한 필사 노트')
        self.assertEqual(book['authors'], ['유선경'])
        self.assertEqual(book['isbn'], '9791171711673')
        self.assertEqual(book['publisher'], '위즈덤하우스')
        self.assertEqual(book['pubdate'], '2024-03-28')
        self.assertEqual(book['rating'], 4.75)
        self.assertTrue(book['cover'].lower().endswith('/xl'))
        self.assertTrue(dict(book['sections'])['목차'])
        self.assertTrue(dict(book['sections'])['출판사 리뷰'])

    def test_search_rejects_external_links_and_duplicates(self):
        raw = '<a class="gd_name" href="https://evil.example/product/goods/1">bad</a><a class="gd_name" href="/product/goods/2">ok</a><a class="gd_name" href="/Product/Goods/2">ok</a>'
        self.assertEqual(worker.search_results(raw), ['https://www.yes24.com/Product/Goods/2'])

    def test_html_fallback_without_json(self):
        raw = '<meta property="books:isbn" content="9791171711673"><meta property="og:url" content="https://www.yes24.com/Product/Goods/1"><h2 class="gd_name">제목</h2><span class="gd_auth"><a>저자</a></span>'
        book = worker.parse_details(raw, '')
        self.assertEqual(book['title'], '제목')
        self.assertEqual(book['authors'], ['저자'])

    def test_missing_result(self):
        self.assertEqual(worker.search_results('<html>검색 결과 없음</html>'), [])

    def test_foreign_book_plain_author_overrides_truncated_json(self):
        raw = '<script type="application/ld+json">{"@type":"Book","name":"The Book of Debugging","author":{"name":"Kuhlmann"},"isbn":"9781718504066"}</script><h2 class="gd_name">The Book of Debugging</h2><span class="gd_auth">Kuhlmann, Johannes</span>'
        book = worker.parse_details(raw, 'https://www.yes24.com/Product/Goods/141546817')
        self.assertEqual(book['authors'], ['Johannes Kuhlmann'])
        self.assertEqual(book['isbn'], '9781718504066')
        self.assertEqual(book['id'], '141546817')

    def test_session_redirect_only_matches_yes24_home(self):
        query = 'https://www.yes24.com/Product/Search?query=test'
        self.assertTrue(worker.is_session_redirect(query, 'https://www.yes24.com/Main/default.aspx'))
        self.assertTrue(worker.is_session_redirect('https://www.yes24.com/Product/Goods/1', 'https://www.yes24.com/'))
        self.assertFalse(worker.is_session_redirect(query, query))
        self.assertFalse(worker.is_session_redirect(query, 'https://evil.example/Main/default.aspx'))
