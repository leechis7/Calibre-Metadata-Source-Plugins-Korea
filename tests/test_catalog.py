"""Catalogue cases also run against the real loader via regression_calibre.py."""
from queue import Queue
from threading import Event
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from catalog import BOOKS, responses
from source_doubles import Browser, Log, COVER


def unit_source(store):
    from test_calibre_contract import load_source
    return load_source(store)


class CatalogBrowser(Browser):
    def clone_browser(self):
        return self

    def open_novisit(self, url, timeout):
        if '/middle' in url:
            self.routes[url] = b'{"data":{"middle":{}}}'
        elif 'getContents.aspx?' in url:
            self.routes[url] = b'<html> </html>'
        return super().open_novisit(url, timeout)


class CatalogTests(unittest.TestCase):
    stores = ('yes24', 'kyobo')
    source_factory = staticmethod(unit_source)

    def source(self, store, title, author, isbn, availability='InStock', format_='Hardcover', intro='검증 소개'):
        source = self.source_factory(store)
        url, search, detail = responses(store, title, author, isbn, availability, format_, intro)
        query = source.create_query(Log(), title=title, authors=[author])
        browser = CatalogBrowser({url: detail, query: search})
        if store == 'aladin':
            browser.routes['https://www.aladin.co.kr/shop/wproduct.aspx?ISBN=' + isbn] = detail
        # Real Source.browser is a read-only property which clones _browser.
        if isinstance(getattr(type(source), 'browser', None), property):
            source._browser = browser
        else:
            source.browser = browser
        return source, browser, url, query

    def test_aladin_ajax_search_uses_the_ajax_response(self):
        if 'aladin' not in self.stores:
            self.skipTest('Real Calibre Aladin runtime required')
        source, browser, _, query = self.source('aladin', *BOOKS[0][1:4])
        ajax = source._create_ajax_query_from_search_query(query)
        browser.routes[ajax] = browser.routes[query]
        browser.routes[query] = b'<html>Search requires AJAX</html>'
        queue, log = Queue(), Log()
        source.identify(log, queue, Event(), title='아몬드', authors=['손원평'])
        self.assertEqual(queue.get_nowait().isbn, '9788936434267')
        self.assertIn(ajax, browser.calls)
        self.assertTrue(all(r.stream.closed for r in browser.responses))

    def test_invalid_isbn_does_not_fall_back_to_title(self):
        for store in self.stores:
            with self.subTest(store=store):
                source, browser, _, _ = self.source(store, *BOOKS[0][1:4])
                queue, log = Queue(), Log()
                source.identify(log, queue, Event(), title='아몬드', authors=['손원평'],
                                identifiers={'isbn': '9788936434268'})
                self.assertTrue(queue.empty())
                self.assertFalse(browser.calls)
                self.assertIn('유효하지 않은 ISBN', str(log.errors))

    def test_cancel_during_detail_never_publishes_or_caches(self):
        for store in self.stores:
            with self.subTest(store=store):
                source, browser, url, query = self.source(store, *BOOKS[0][1:4])
                abort, queue, log = Event(), Queue(), Log()
                original = browser.open_novisit
                def cancel_detail(requested, timeout):
                    response = original(requested, timeout)
                    if requested == url or 'wproduct.aspx?' in requested:
                        abort.set()
                    return response
                browser.routes[source.create_query(log, identifiers={'isbn': '9788936434267'})] = browser.routes[query]
                with patch.object(browser, 'open_novisit', side_effect=cancel_detail):
                    source.identify(log, queue, abort, identifiers={'isbn': '9788936434267'})
                self.assertTrue(queue.empty())
                self.assertIsNone(source.cached_isbn_to_identifier('9788936434267'))
                self.assertFalse(any('getContents.aspx' in u for u in browser.calls))
                self.assertTrue(all(r.stream.closed for r in browser.responses))

    def test_domestic_foreign_and_out_of_print_by_title_and_isbn(self):
        for store in self.stores:
            for kind, title, author, isbn, availability in BOOKS:
                for by_isbn in (False, True):
                    with self.subTest(store=store, kind=kind, by_isbn=by_isbn):
                        source, browser, url, _ = self.source(store, title, author, isbn, availability)
                        query = source.create_query(Log(), identifiers={'isbn': isbn})
                        browser.routes[query] = responses(store, title, author, isbn, availability)[1]
                        queue, log = Queue(), Log()
                        source.identify(log, queue, Event(), title=None if by_isbn else title,
                                        authors=None if by_isbn else [author], identifiers={'isbn': isbn} if by_isbn else {})
                        rows = list(queue.queue)
                        self.assertEqual(len(rows), 1, (log.errors, log.exceptions))
                        self.assertEqual(rows[0].isbn, isbn)
                        self.assertEqual(rows[0].authors, [author])
                        self.assertIn('검증 소개', rows[0].comments)
                        self.assertFalse(log.exceptions)

    def test_wrong_edition_does_not_escape_isbn_filter_via_title_fallback(self):
        for store in self.stores:
            with self.subTest(store=store):
                title, author, isbn = BOOKS[0][1:4]
                source, browser, url, query = self.source(store, title, author, isbn)
                wanted = '9781807300814'
                browser.routes[source.create_query(Log(), identifiers={'isbn': wanted})] = browser.routes[query]
                browser.routes['https://www.aladin.co.kr/shop/wproduct.aspx?ISBN=' + wanted] = browser.routes[url]
                queue, log = Queue(), Log()
                source.identify(log, queue, Event(), title=title, authors=[author], identifiers={'isbn': wanted})
                self.assertTrue(queue.empty())
                self.assertTrue(any('ISBN 불일치' in str(m) for m in log.messages))

    def test_stale_store_id_fallback_preserves_isbn_and_does_not_cache_wrong_book(self):
        for store in (s for s in self.stores if s != 'aladin'):
            with self.subTest(store=store):
                title, author, isbn = BOOKS[0][1:4]
                source, browser, _, query = self.source(store, title, author, isbn)
                wanted = '9781807300814'
                isbn_query = source.create_query(Log(), identifiers={'isbn': wanted})
                browser.routes[isbn_query] = browser.routes[query]
                queue, log = Queue(), Log()
                store_id = '125557465' if store == 'yes24' else 'S000000610625'
                source.identify(log, queue, Event(), title=title, authors=[author],
                                identifiers={source.identifier: store_id, 'isbn': wanted})
                self.assertTrue(queue.empty())
                self.assertIn(isbn_query, browser.calls)
                self.assertNotIn(query, browser.calls)
                self.assertIsNone(source.cached_isbn_to_identifier(isbn))

    def test_equivalent_isbn10_is_accepted(self):
        for store in self.stores:
            with self.subTest(store=store):
                source, browser, url, query = self.source(store, *BOOKS[0][1:4])
                browser.routes[source.create_query(Log(), identifiers={'isbn': '8936434268'})] = browser.routes[query]
                browser.routes['https://www.aladin.co.kr/shop/wproduct.aspx?ISBN=8936434268'] = browser.routes[url]
                queue, log = Queue(), Log()
                source.identify(log, queue, Event(), identifiers={'isbn': '8936434268'})
                self.assertEqual(queue.get_nowait().isbn, '9788936434267')

    def test_no_result_and_structure_change_have_different_logs(self):
        for store in self.stores:
            for html, expected in ((b'<html><p>Nothing here</p></html>', '페이지 구조 변경'),
                                   ('<html>검색 결과가 없습니다</html>'.encode(), '책 없음')):
                with self.subTest(store=store, expected=expected):
                    source, browser, _, query = self.source(store, *BOOKS[0][1:4])
                    browser.routes[query] = html
                    if store == 'aladin':
                        browser.routes[source._create_ajax_query_from_search_query(query)] = html
                    queue, log = Queue(), Log()
                    source.identify(log, queue, Event(), title='아몬드', authors=['손원평'])
                    self.assertTrue(queue.empty())
                    self.assertIn(expected, str(log.errors + log.messages + log.exceptions))

    def test_connection_failure_has_diagnostic_and_no_results(self):
        for store in self.stores:
            with self.subTest(store=store):
                source, browser, _, _ = self.source(store, *BOOKS[0][1:4])
                queue, log = Queue(), Log()
                with patch.object(browser, 'open_novisit', side_effect=OSError('connection failed')):
                    source.identify(log, queue, Event(), title='아몬드', authors=['손원평'])
                self.assertTrue(queue.empty())
                self.assertIn('접속 실패', str(log.errors + log.exceptions))

    def test_candidate_exclusion_reasons(self):
        cases = (('아몬드 2', '손원평', '제목 불일치'), ('아몬드 세트', '손원평', '개정판·세트'),
                 ('아몬드 (개정판)', '손원평', '개정판·세트'), ('[eBook] 아몬드', '손원평', '형식 불일치'),
                 ('아몬드', '손원평연구회', '저자 불일치'), ('The Almond', '손원평', '제목 불일치'))
        for store in self.stores:
            for title, author, expected in cases:
                with self.subTest(store=store, title=title, author=author):
                    source, browser, _, query = self.source(store, title, author, '9788936434267')
                    requested = source.create_query(Log(), title='아몬드', authors=['손원평'])
                    browser.routes[requested] = browser.routes[query]
                    if store == 'aladin':
                        browser.routes[source._create_ajax_query_from_search_query(requested)] = browser.routes[query]
                    queue, log = Queue(), Log()
                    source.identify(log, queue, Event(), title='아몬드', authors=['손원평'])
                    self.assertTrue(queue.empty())
                    self.assertIn(expected, str(log.messages))

    def test_missing_product_and_changed_detail_have_distinct_logs(self):
        for store in self.stores:
            for response, expected in ((HTTPError('https://example.test', 404, 'missing', {}, None), '책 없음'),
                                       (b'<html><p>new layout</p></html>', '페이지 구조 변경')):
                with self.subTest(store=store, expected=expected):
                    source, browser, url, _ = self.source(store, *BOOKS[0][1:4])
                    if store != 'aladin':
                        query = source.create_query(Log(), identifiers={'isbn': '9788936434267'})
                        browser.routes[query] = responses(store, *BOOKS[0][1:4])[1]
                    queue, log = Queue(), Log()
                    if isinstance(response, Exception):
                        self.addCleanup(response.close)
                        original = browser.open_novisit
                        def missing(url_, timeout):
                            if 'wproduct.aspx?' in url_ or url_ == url:
                                raise response
                            return original(url_, timeout)
                        with patch.object(browser, 'open_novisit', side_effect=missing):
                            source.identify(log, queue, Event(), identifiers={'isbn': '9788936434267'})
                    else:
                        browser.routes[url] = response
                        if store == 'aladin':
                            browser.routes['https://www.aladin.co.kr/shop/wproduct.aspx?ISBN=9788936434267'] = response
                        source.identify(log, queue, Event(), identifiers={'isbn': '9788936434267'})
                    self.assertTrue(queue.empty())
                    self.assertIn(expected, str(log.messages + log.errors + log.exceptions))

    def test_cover_download_validates_bytes_in_all_sources(self):
        for store in self.stores:
            for raw, accepted in ((COVER, True), (b'<html>error</html>', False), (COVER[:40], False)):
                with self.subTest(store=store, accepted=accepted, size=len(raw)):
                    source, browser, _, _ = self.source(store, *BOOKS[0][1:4])
                    identifier = '123' if store == 'aladin' else ('125557465' if store == 'yes24' else 'S000000610625')
                    cover_url = 'https://example.test/cover.png'
                    source.cache_isbn_to_identifier('9788936434267', identifier)
                    source.cache_identifier_to_cover_url(identifier, cover_url)
                    browser.routes[cover_url] = raw
                    queue, log = Queue(), Log()
                    source.download_cover(log, queue, Event(), identifiers={'isbn': '9788936434267'})
                    if accepted:
                        self.assertEqual(queue.get_nowait()[1], raw)
                    else:
                        self.assertTrue(queue.empty())
                        self.assertIn('표지 제외', str(log.errors))
                    self.assertTrue(all(r.stream.closed for r in browser.responses))

    def test_introduction_controls_hidden_text_and_corruption(self):
        for store in self.stores:
            for intro, expected in (('<p>정상 소개</p><button>더보기</button><p hidden>숨김 광고</p>', '정상 소개'),
                                    ('깨진 \ufffd 소개', '')):
                with self.subTest(store=store, intro=intro):
                    source, _, _, _ = self.source(store, *BOOKS[0][1:4], intro=intro)
                    queue, log = Queue(), Log()
                    source.identify(log, queue, Event(), title='아몬드', authors=['손원평'])
                    comments = queue.get_nowait().comments or ''
                    self.assertNotIn('더보기', comments)
                    self.assertNotIn('숨김 광고', comments)
                    self.assertNotIn('\ufffd', comments)
                    if expected:
                        self.assertIn(expected, comments)
                    else:
                        self.assertEqual(comments, '')

    def test_cover_cancel_after_response_does_not_publish_image(self):
        for store in self.stores:
            with self.subTest(store=store):
                source, browser, _, _ = self.source(store, *BOOKS[0][1:4])
                identifier = '123' if store == 'aladin' else ('125557465' if store == 'yes24' else 'S000000610625')
                source.cache_isbn_to_identifier('9788936434267', identifier)
                source.cache_identifier_to_cover_url(identifier, 'https://example.test/cover.png')
                browser.routes['https://example.test/cover.png'] = COVER
                abort = Event()
                original = browser.open_novisit
                def open_(url, timeout):
                    response = original(url, timeout)
                    read = response.read
                    def cancel(size=-1):
                        raw = read(size)
                        abort.set()
                        return raw
                    response.read = cancel
                    return response
                queue = Queue()
                with patch.object(browser, 'open_novisit', side_effect=open_):
                    source.download_cover(Log(), queue, abort, identifiers={'isbn': '9788936434267'})
                self.assertTrue(queue.empty())
