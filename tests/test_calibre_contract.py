"""Integration contract tests with small doubles; not a Calibre installation test."""
import importlib
import itertools
from io import BytesIO
from queue import Queue
import re
import sys
from threading import Event
import types
import unittest
from unittest.mock import patch

from support import fixture, load_adapter, ROOT
from mechanize import make_response
from source_doubles import Browser, Log, MechanizeBrowser, Response, COVER


def check_isbn(value):
    value = re.sub(r'[^0-9Xx]', '', str(value or '')).upper()
    if len(value) == 13 and value.isdigit():
        return value if sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10 == 0 else None
    if len(value) == 10:
        try:
            return value if sum((10-i) * (10 if c == 'X' else int(c)) for i,c in enumerate(value)) % 11 == 0 else None
        except ValueError:
            pass


class Metadata:
    def __init__(self, title, authors):
        self.title, self.authors, self.identifiers = title, authors, {}
        self.isbn = None
    def set_identifier(self, key, value):
        self.identifiers[key] = value


class Source:
    name = 'Trivial Plugin'
    def __init__(self):
        self.prefs = {o.name: o.default for o in self.options}
        self.ids, self.covers = {}, {}
    def cache_isbn_to_identifier(self, isbn, id_):
        self.ids[isbn] = id_
    def cached_isbn_to_identifier(self, isbn):
        return self.ids.get(isbn)
    def cache_identifier_to_cover_url(self, id_, url):
        self.covers[id_] = url
    def cached_identifier_to_cover_url(self, id_):
        return self.covers.get(id_)
    def clean_downloaded_metadata(self, mi):
        mi.isbn = check_isbn(mi.isbn)
        if mi.isbn:
            mi.identifiers['isbn'] = mi.isbn
    def identify_results_keygen(self, **kwargs):
        return lambda mi: mi.source_relevance


class Option:
    def __init__(self, name, type_, default, label, desc):
        self.name, self.default = name, default


def load_source(store):
    worker = load_adapter(store)
    namespace = worker.__package__
    modules = {}
    for name in ('calibre', 'calibre.ebooks', 'calibre.ebooks.metadata', 'calibre.ebooks.metadata.book',
                 'calibre.ebooks.metadata.book.base', 'calibre.ebooks.metadata.sources',
                 'calibre.ebooks.metadata.sources.base', 'calibre.library', 'calibre.library.comments'):
        modules[name] = types.ModuleType(name)
        modules[name].__path__ = []
    modules['calibre.ebooks.metadata'].check_isbn = check_isbn
    modules['calibre.ebooks.metadata.book.base'].Metadata = Metadata
    modules['calibre.ebooks.metadata.sources.base'].Source = Source
    modules['calibre.ebooks.metadata.sources.base'].Option = Option
    modules['calibre.library.comments'].sanitize_comments_html = lambda html: html
    env = {'__name__': namespace}
    with patch.dict(sys.modules, modules):
        exec((ROOT / 'plugins' / store / '__init__.py').read_text(encoding='utf-8'), env)
    # Match Calibre's class-selection rule (shallowest module wins).
    classes = [v for v in env.values() if isinstance(v, type) and issubclass(v, Source) and v.name != 'Trivial Plugin']
    classes.sort(key=lambda c: c.__module__.count('.'))
    return classes[0]()


class CalibreContractTests(unittest.TestCase):
    def test_kyobo_empty_detail_recovers_after_product_api_session(self):
        source = load_source('kyobo')
        detail = source.detail_url.format(id='S000000610625')
        top = 'https://product.kyobobook.co.kr/api/gw/pdt/v2/product/component/S000000610625/top'
        middle = 'https://product.kyobobook.co.kr/api/gw/pdt/v2/product/component/S000000610625/middle'
        class RecoveringBrowser(MechanizeBrowser):
            def open_novisit(self, url, timeout):
                if url.split('?_calibre=')[0] == detail and len(self.calls) < 2:
                    self.calls.append(url)
                    response = make_response(b'', [], url)
                    response.close = unittest.mock.Mock(wraps=response.close)
                    self.responses.append(response)
                    return response
                return super().open_novisit(url.split('?_calibre=')[0], timeout)
        browser = RecoveringBrowser({detail:fixture('kyobo_detail.html').encode(), top:b'{"data":{}}', middle:fixture('kyobo_middle.json').encode()})
        source.browser = browser
        q, log = Queue(), Log()
        source.identify(log, q, Event(), identifiers={'kyobobook.co.kr':'S000000610625'})
        self.assertEqual(q.get_nowait().isbn, '9788936434267')
        self.assertEqual(browser.calls[2:4], [top, detail])
        self.assertFalse(log.exceptions)
        self.assertTrue(all(r.close.called for r in browser.responses))

    def test_kyobo_persistently_empty_detail_stops_after_recovery(self):
        source = load_source('kyobo')
        detail = source.detail_url.format(id='S000000610625')
        class EmptyBrowser(MechanizeBrowser):
            def open_novisit(self, url, timeout):
                self.calls.append(url)
                return make_response(b'{}' if '/api/' in url else b'', [], url)
        browser = EmptyBrowser({})
        source.browser = browser
        q, log = Queue(), Log()
        source.identify(log, q, Event(), identifiers={'kyobobook.co.kr':'S000000610625'})
        self.assertTrue(q.empty())
        self.assertEqual(len(browser.calls), 5)
        self.assertTrue(log.exceptions)

    def test_yes24_title_and_isbn_queries_include_foreign_books(self):
        source = load_source('yes24')
        self.assertIn('domain=ALL&query=The%20Book%20of%20Debugging', source.create_query(Log(), title='The Book of Debugging'))
        self.assertIn('domain=ALL&query=9781718504066', source.create_query(Log(), identifiers={'isbn': '9781718504066'}))

    def test_yes24_cookie_validation_redirect_retries_search_and_details(self):
        for direct in (False, True):
            with self.subTest(direct=direct):
                source = self.yes24()
                first = source.detail_url.format(id='125557465') if direct else source.search_url.format(query='9791171711673')
                class RedirectBrowser(MechanizeBrowser):
                    def open_novisit(self, url, timeout):
                        if not self.calls:
                            self.calls.append(url)
                            self.last_timeout = timeout
                            # A nonempty YES24 home page after setting its session cookie.
                            response = make_response(b'<html>Home, no search results</html>', [], 'https://www.yes24.com/Main/default.aspx')
                            response.close = unittest.mock.Mock(wraps=response.close)
                            self.responses.append(response)
                            return response
                        self.retry_timeout = timeout
                        return super().open_novisit(url, timeout)
                browser = RedirectBrowser(source.browser.routes)
                source.browser = browser
                q, log = Queue(), Log()
                ids = {'yes24.com': '125557465'} if direct else {'isbn': '9791171711673'}
                with patch(source.__class__.__mro__[1].__module__ + '.time.monotonic', side_effect=itertools.count(0, 0.1)):
                    source.identify(log, q, Event(), identifiers=ids)
                self.assertEqual(q.get_nowait().isbn, '9791171711673')
                self.assertEqual(browser.calls[:2], [first, first])
                self.assertLess(browser.retry_timeout, browser.last_timeout)
                self.assertFalse(log.exceptions)
                self.assertTrue(all(r.close.called for r in browser.responses))

    def test_yes24_repeated_session_redirect_is_bounded_and_logged(self):
        source = self.yes24()
        class RedirectBrowser(MechanizeBrowser):
            def open_novisit(self, url, timeout):
                self.calls.append(url)
                return make_response(b'<html>Home</html>', [], 'https://www.yes24.com/Main/default.aspx')
        browser = RedirectBrowser({})
        source.browser = browser
        q, log = Queue(), Log()
        source.identify(log, q, Event(), identifiers={'isbn': '9791171711673'})
        self.assertTrue(q.empty())
        self.assertEqual(len(browser.calls), 2)
        self.assertTrue(log.exceptions)

    def yes24(self):
        source = load_source('yes24')
        source.browser = Browser({
            source.search_url.format(query='9791171711673'): fixture('yes24_search.html').encode(),
            source.detail_url.format(id='125557465'): fixture('yes24_detail.html').encode(),
            'https://image.yes24.com/goods/125557465/xl': COVER,
        })
        return source

    def test_identify_and_cover_cache(self):
        source, queue, log = self.yes24(), Queue(), Log()
        source.identify(log, queue, Event(), identifiers={'isbn': '9791171711673'})
        self.assertEqual(queue.qsize(), 1)
        mi = queue.get()
        self.assertEqual(mi.identifiers['yes24.com'], '125557465')
        self.assertEqual(mi.languages, ['kor'])
        self.assertIn('목차', mi.comments)
        covers = Queue()
        source.download_cover(log, covers, Event(), identifiers={'isbn': '9791171711673'})
        self.assertEqual(covers.get_nowait(), (source, COVER))
        self.assertEqual(len(source.browser.calls), 3)
        self.assertFalse(log.exceptions)
        self.assertTrue(all(r.stream.closed for r in source.browser.responses))

    def test_real_mechanize_search_details_and_cover(self):
        source, queue, log = self.yes24(), Queue(), Log()
        source.browser = MechanizeBrowser(source.browser.routes)
        source.identify(log, queue, Event(), identifiers={'isbn': '9791171711673'})
        self.assertEqual(queue.get_nowait().title, '하루 한 장 나의 어휘력을 위한 필사 노트')
        covers = Queue()
        source.download_cover(log, covers, Event(), identifiers={'isbn': '9791171711673'})
        self.assertEqual(covers.get_nowait()[1], COVER)
        self.assertFalse(log.exceptions)
        for response in source.browser.responses:
            self.assertEqual(response.__class__.__name__, 'response_seek_wrapper')
            response.close.assert_called_once()

    def test_real_mechanize_empty_response_retry(self):
        source, queue, log = self.yes24(), Queue(), Log()
        browser = MechanizeBrowser(source.browser.routes)
        original = browser.open_novisit
        empty = make_response(b'', [], source.detail_url.format(id='125557465'))
        empty.close = unittest.mock.Mock(wraps=empty.close)
        calls = []
        def open_(url, timeout):
            calls.append(url)
            return empty if len(calls) == 1 else original(url.split('?_calibre=')[0], timeout)
        browser.open_novisit = open_
        source.browser = browser
        source.identify(log, queue, Event(), identifiers={'yes24.com': '125557465'})
        self.assertEqual(queue.qsize(), 1)
        self.assertFalse(log.exceptions)
        empty.close.assert_called_once()
        browser.responses[0].close.assert_called_once()

    def test_read_failure_closes_response(self):
        source, queue, log = self.yes24(), Queue(), Log()
        response = Response(b'')
        response.read = unittest.mock.Mock(side_effect=OSError('Read failed'))
        source.browser.open_novisit = lambda url, timeout: response
        source.identify(log, queue, Event(), identifiers={'yes24.com': '125557465'})
        self.assertTrue(queue.empty())
        self.assertTrue(response.stream.closed)
        self.assertEqual(len(log.exceptions), 1)

    def test_uncached_cover_identifies(self):
        source, queue, log = self.yes24(), Queue(), Log()
        source.download_cover(log, queue, Event(), identifiers={'yes24.com': '125557465'})
        self.assertEqual(queue.get_nowait(), (source, COVER))
        self.assertFalse(log.exceptions)

    def test_abort_before_request(self):
        source, queue, abort = self.yes24(), Queue(), Event()
        abort.set()
        source.identify(Log(), queue, abort, title='제목')
        source.download_cover(Log(), queue, abort, title='제목')
        self.assertTrue(queue.empty())
        self.assertFalse(source.browser.calls)

    def test_expired_timeout(self):
        source, queue = self.yes24(), Queue()
        source.identify(Log(), queue, Event(), identifiers={'yes24.com':'125557465'}, timeout=0)
        self.assertTrue(queue.empty())
        self.assertFalse(source.browser.calls)

    def test_empty_response_retry(self):
        source, queue, log = self.yes24(), Queue(), Log()
        original = source.browser.open_novisit
        calls = []
        def open_(url, timeout):
            calls.append(url)
            if len(calls) == 1:
                return BytesIO(b'')
            return original(url.split('?_calibre=')[0], timeout)
        source.browser.open_novisit = open_
        source.identify(log, queue, Event(), identifiers={'yes24.com':'125557465'})
        self.assertEqual(queue.qsize(), 1)
        self.assertEqual(len(calls), 2)
        self.assertIn('?_calibre=', calls[1])
        self.assertFalse(log.exceptions)

    def test_abort_after_http_response(self):
        source, queue, abort = self.yes24(), Queue(), Event()
        original = source.browser.open_novisit
        def open_(url, timeout):
            result = original(url, timeout)
            abort.set()
            return result
        source.browser.open_novisit = open_
        source.identify(Log(), queue, abort, identifiers={'yes24.com':'125557465'})
        self.assertTrue(queue.empty())
        self.assertFalse(source.covers)

    def test_optional_api_failure_keeps_metadata(self):
        source = load_source('kyobo')
        source.browser = Browser({source.detail_url.format(id='S000000610625'): fixture('kyobo_detail.html').encode()})
        queue, log = Queue(), Log()
        source.identify(log, queue, Event(), identifiers={'kyobobook.co.kr':'S000000610625'})
        self.assertEqual(queue.get_nowait().title, '아몬드')
        self.assertEqual(len(log.exceptions), 1)

    def test_wrong_isbn_rejected(self):
        source, queue = self.yes24(), Queue()
        source.browser.routes[source.search_url.format(query='9788936434267')] = fixture('yes24_search.html').encode()
        source.identify(Log(), queue, Event(), identifiers={'isbn':'9788936434267'})
        self.assertTrue(queue.empty())

    def test_options(self):
        source, queue = self.yes24(), Queue()
        source.prefs.update(append_toc=False, get_tags=False)
        source.identify(Log(), queue, Event(), identifiers={'yes24.com':'125557465'})
        mi = queue.get_nowait()
        self.assertNotIn('<h3>목차</h3>', mi.comments)
        self.assertEqual(mi.tags, [])

    def test_independent_namespaces_and_kyobo_api(self):
        source = load_source('kyobo')
        source.browser = Browser({source.detail_url.format(id='S000000610625'): fixture('kyobo_detail.html').encode(),
            'https://product.kyobobook.co.kr/api/gw/pdt/v2/product/component/S000000610625/middle': fixture('kyobo_middle.json').encode()})
        queue, log = Queue(), Log()
        source.identify(log, queue, Event(), identifiers={'kyobobook.co.kr':'S000000610625'})
        mi = queue.get_nowait()
        self.assertIn('프롤로그', mi.comments)
        self.assertEqual(mi.identifiers['kyobobook.co.kr'], 'S000000610625')
        self.assertNotIn('yes24.com', mi.identifiers)
        self.assertFalse(log.exceptions)
