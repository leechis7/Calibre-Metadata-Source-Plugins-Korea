"""Regression tests execute the existing parser methods without loading Qt."""
import ast
import datetime
from pathlib import Path
import re
from collections import OrderedDict
from types import SimpleNamespace
import sys
import types
import unittest
from unittest.mock import patch

from lxml.html import fromstring, tostring
from support import ROOT

# The parser-only package still resolves shared code from the repository.
if 'calibre_plugins.aladin_co_kr' not in sys.modules:
    package = types.ModuleType('calibre_plugins.aladin_co_kr')
    package.__path__ = [str(ROOT / 'shared')]
    sys.modules[package.__name__] = package


def parser_class():
    tree = ast.parse((ROOT / 'plugins/aladin/worker.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Worker')
    cls.bases = []
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name != '__init__']
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    config = SimpleNamespace(STORE_NAME='Aladin_co_kr', KEY_GET_ALL_AUTHORS='getAllAuthors',
        KEY_APPEND_TOC='appendTOC', KEY_COMMENTS_SUFFIX='commentsSuffix',
        DEFAULT_STORE_VALUES={'getAllAuthors':False, 'appendTOC':True, 'commentsSuffix':''},
        plugin_prefs={'Aladin_co_kr':{}})
    env = dict(re=re, datetime=datetime, OrderedDict=OrderedDict, fromstring=fromstring,
               tostring=tostring, unicode=str, cfg=config, clean_ascii_chars=lambda x:x,
               sanitize_comments_html=lambda x:x)
    exec(compile(module, 'aladin-parser-methods', 'exec'), env)
    return env['Worker']


def source_class():
    tree = ast.parse((ROOT / 'plugins/aladin/__init__.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    cls.bases = []
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef)]
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    env = dict(re=re, OrderedDict=OrderedDict, lower=str.lower, unicode=str)
    exec(compile(module, 'aladin-source-methods', 'exec'), env)
    return env[cls.name]


class AladinTests(unittest.TestCase):
    def test_other_editions_description_is_excluded(self):
        from source_doubles import Log, Response
        worker = self.worker
        worker.isbn, worker.url, worker.timeout = '9788936434267', 'https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=123', 10
        worker.log = Log()
        raw = ('<meta property="books:isbn" content="9781807300814">'
               '<div class="Ere_prod_mconts_box"><div class="Ere_prod_mconts_LS">책소개</div>'
               '<div class="Ere_prod_mconts_R">다른 판본 소개</div></div>').encode()
        worker.browser = SimpleNamespace(addheaders=[], open_novisit=lambda url, timeout: Response(raw))
        result = worker.parse_comments(fromstring('<html><p>빈 상세</p></html>'))
        self.assertEqual(result, '')
        self.assertIn('다른 판본', str(worker.log.errors))

    def test_duplicate_and_cp949_description_blocks(self):
        from source_doubles import Log, Response
        worker = self.worker
        worker.isbn, worker.url, worker.timeout = '9788936434267', 'https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=123', 10
        worker.log = Log()
        raw = ('<div class="Ere_prod_mconts_box"><div class="Ere_prod_mconts_LS">책소개</div>'
               '<div class="Ere_prod_mconts_R">정상 한글 소개<button>더보기</button></div></div>'
               '<div class="Ere_prod_mconts_box"><div class="Ere_prod_mconts_LS">출판사 서평</div>'
               '<div class="Ere_prod_mconts_R">정상 한글 소개</div></div>').encode('cp949')
        worker.browser = SimpleNamespace(addheaders=[], open_novisit=lambda url, timeout: Response(raw))
        result = worker.parse_comments(fromstring('<html><p>상세</p></html>'))
        self.assertEqual(result.count('정상 한글 소개'), 1)
        self.assertNotIn('더보기', result)

    def setUp(self):
        self.worker = parser_class()()
        from threading import Event
        from calibre_plugins.aladin_co_kr.request_budget import RequestBudget
        self.worker.budget = RequestBudget(Event(), 10)

    def test_title_span_and_link(self):
        for tag in ('span', 'a'):
            root = fromstring('<div><%s class="Ere_bo_title">테스트 도서</%s></div>' % (tag,tag))
            self.assertEqual(self.worker.parse_title_series(root), ('테스트 도서',None,None))

    def test_isbn_and_identifier(self):
        root = fromstring('<meta property="books:isbn" content="9788936434267"><meta property="og:url" content="https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=123">')
        self.assertEqual(self.worker.parse_isbn(root), '9788936434267')
        self.assertEqual(self.worker.parse_aladin_id('https://www.aladin.co.kr/shop/wproduct.aspx?ISBN=9788936434267', root), '123')

    def test_unavailable_isbn_has_no_identifier(self):
        url = 'https://www.aladin.co.kr/shop/wproduct.aspx?ISBN=9781807300814'
        self.assertIsNone(self.worker.parse_aladin_id(url, fromstring('<html>상품 없음</html>')))
        self.assertIsNone(self.worker.parse_aladin_id(url, fromstring('<meta property="og:url" content="https://www.aladin.co.kr/">')))

    def test_toc_fallback(self):
        root = fromstring('<div id="div_TOC_Short"><p>1장<br/>2장</p></div>')
        self.assertIn('1장', self.worker._find_toc_html(root))

    def test_description_section_and_sanitization(self):
        root = fromstring('<div><div class="Ere_prod_mconts_box"><div class="Ere_prod_mconts_LS">출판사 제공 책소개</div><div class="Ere_prod_mconts_R">소개<script>bad()</script></div></div></div>')
        node = self.worker._find_aladin_content_node(root, ['출판사 제공 책소개'])
        html = self.worker._content_node_to_comments_html(node)
        self.assertIn('소개', html)
        self.assertNotIn('bad()', html)

    def test_search_logs_keep_korean_unicode(self):
        from test_calibre_contract import Log
        source = source_class()()
        source.get_title_tokens = lambda title: title.split()
        source.get_author_tokens = lambda authors: iter(authors or [])
        config = types.ModuleType('calibre_plugins.aladin_co_kr.config')
        config.STORE_NAME, config.KEY_MAX_DOWNLOADS = 'Aladin_co_kr', 'maxDownloads'
        config.plugin_prefs = {config.STORE_NAME:{config.KEY_MAX_DOWNLOADS:5}}
        package = types.ModuleType('calibre_plugins.aladin_co_kr')
        package.__path__ = [str(ROOT / 'shared')]
        package.config = config
        log = Log()
        messages = []
        log.info = lambda *args: messages.append(args)
        root = fromstring('<div class="ss_book_box"><div class="ss_book_list"><p><a href="https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=401344136">트렌드 코리아 2027</a></p><a href="/search/wsearchresult.aspx?AuthorSearch=test">김난도</a></div></div>')
        with patch.dict(sys.modules, {'calibre_plugins.aladin_co_kr':package, config.__name__:config}):
            matches = []
            source._parse_search_results(log, '트렌드 코리아 2027', None, root, matches, 30)
        self.assertEqual(len(matches), 1)
        args = next(args for args in messages if args[0].startswith('Considering search result'))
        self.assertIn('트렌드 코리아 2027', args)
        self.assertIn('김난도', '|'.join(args))
        self.assertTrue(all(isinstance(value, str) for value in args))
