#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# Modified by leechis7 beginning 2026-06-02.
# See README.md and CHANGELOG.md for maintenance changes.
from __future__ import (unicode_literals, division, absolute_import, print_function)

import time
import re
# from urllib import quote
from six.moves.urllib.parse import quote
# from Queue import Queue, Empty
from queue import Queue, Empty
from collections import OrderedDict

from lxml.html import fromstring, tostring

from calibre import as_unicode
from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.sources.base import Source
from calibre.utils.icu import lower
from calibre.utils.cleantext import clean_ascii_chars

from six import text_type as unicode


__license__   = 'GPL v3'
__copyright__ = '2014, YongSeok Choi <sseeookk@gmail.com> based on the Goodreads work by Grant Drake <grant.drake@gmail.com>'
__docformat__ = 'restructuredtext en'

try:
    load_translations()
except NameError:
    pass


class Aladin_co_kr(Source):
    """
    This plugin is only for books in the Korean language.
    It allows Calibre to read book information from aladin.co.kr(online book store in korea, http://aladin.co.kr/) when you choose to download/fetch metadata.
    It was based on the 'Goodreads' and the 'Barnes' by 'Grant Drake'.
    """
    name = 'Aladin.co.kr'
    description = _('Downloads metadata and covers from aladin.co.kr')
    author = 'YongSeok Choi'
    version = (1, 2, 5)
    minimum_calibre_version = (5, 0, 0)
    
    
    capabilities = frozenset(['identify', 'cover'])
    touched_fields = frozenset(['title', 'authors', 'identifier:aladin.co.kr',
                                'identifier:isbn', 'rating', 'comments', 'publisher', 'pubdate',
                                'tags', 'series', 'languages'])
    has_html_comments = True
    supports_gzip_transfer_encoding = True
    
    # 201602 aladin url patterns :
    # https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=27942886
    
    # 201403 aladin url patterns :
    # https://www.aladin.co.kr/shop/wproduct.aspx?ISBN=8965744024
    # https://www.aladin.co.kr/search/wsearchresult.aspx?SearchType=3&KeyISBN=9788965744023
    # https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget=All&SearchWord=9788965744023&x=30&y=18
    # https://www.aladin.co.kr/search/wsearchresult.aspx?SearchTarget=Book&SearchFieldEnable=1&KeyTitle=&KeyAuthor=&KeySubject=&KeyPublisher=&KeyTOC=&KeyYearStart=&KeyMonthStart=&KeyYearEnd=&KeyMonthEnd=&SortOrder=11
    # SearchTarget - All, Book, Foreign, EBook, Used, Music, DVD
    # SortOrder 정렬순서(select="SortOrder") -  11 정확도순,  1 상품명순,  2 판매량순,  3 평점순,  4 리뷰순,  5 출간일순,  9 저가격순
    
    BASE_URL = 'https://www.aladin.co.kr'

    def _read_response_html(self, response):
        raw = response.read().strip()
        if not raw:
            return ''
        if isinstance(raw, unicode):
            return raw

        encodings = []
        try:
            charset = response.info().get_content_charset()
            if charset:
                encodings.append(charset)
        except:
            pass

        for encoding in encodings + ['utf-8', 'cp949', 'euc-kr']:
            try:
                return raw.decode(encoding)
            except:
                pass
        return raw.decode('utf-8', errors='replace')

    def _create_ajax_query_from_search_query(self, query):
        match = re.search(r'[?&]SearchWord=([^&]+)', query)
        if not match:
            return None
        search_word = match.group(1)
        return (
            '%s/search/Search3Ajax.aspx?SearchTarget=All&KeyWord=%s'
            '&KeyFullWord=%s&KeyLastWord=%s&CategorySearch='
            '&ViewType=Detail&SortOrder=11&page=1&viewrowcount=25'
            '&ItemViewTypes=Browse&method=search3html2'
        ) % (Aladin_co_kr.BASE_URL, search_word, search_word, search_word)

    def _search_result_nodes(self, root):
        results = root.xpath('//div[@id="Search3_Result"]/div[contains(@class, "ss_book_box")]')
        if not results:
            results = root.xpath('//div[contains(@class, "ss_book_box")]')
        return results
    
    def config_widget(self):
        """
        Overriding the default configuration screen for our own custom configuration
        """
        from calibre_plugins.aladin_co_kr.config import ConfigWidget
        return ConfigWidget(self)
    
    def get_book_url(self, identifiers):
        aladin_id = identifiers.get('aladin.co.kr', None)
        if aladin_id:
            return 'aladin.co.kr', aladin_id, '%s/shop/wproduct.aspx?ItemId=%s' % (Aladin_co_kr.BASE_URL, aladin_id)
    
    def create_query(self, log, title=None, authors=None, identifiers={}):
        
        isbn = check_isbn(identifiers.get('isbn', None))
        q = ''
        if isbn is not None:
            q = '/search/wsearchresult.aspx?SearchType=3&KeyISBN=' + isbn
            # q = '/shop/wproduct.aspx?ISBN=' + isbn
        
        elif title or authors:
            tokens = []
            
            title_tokens = list(self.get_title_tokens(title, strip_joiners=False, strip_subtitle=True))
            tokens += title_tokens
            
            # TODO: No token is returned for korean name.
            # 한글이름일 경우 token 이 반환 안된다.
            # by sseeookk ,  20140315 
            author_tokens = self.get_author_tokens(authors, only_first_author=True)
            # authors_encode = None
            # if authors:
            #     # authors_encode = list(a.encode('utf-8') for a in authors)
            #     authors_encode = list(quote(a.encode('utf-8') if isinstance(a, unicode) else a) for a in authors)
            #     # authors_encode = list(a for a in authors)
            # author_tokens = self.get_author_tokens(authors_encode, only_first_author=True)
            tokens += author_tokens

            tokens = [quote(t.encode('utf-8') if isinstance(t, unicode) else t) for t in tokens]
            # tokens = [(t.encode('utf-8') if isinstance(t, unicode) else t) for t in tokens]  # by sseeookk
            q = '+'.join(tokens)
            
            # TODO: why? \ or %
            # by sseeookk
            # change : \ --> % 
            q = "%r" % q
            q = re.sub("\\\\", "%", q)
            q = re.sub("'", "", q)
            # q = q[1:]
            
            q = '/search/wsearchresult.aspx?SearchTarget=All&SearchWord=' + q
   
        if not q:
            return None
        # by sseeookk
        # if isinstance(q, unicode):
        # q = q.encode('utf-8')
        return Aladin_co_kr.BASE_URL + '' + q
    
    # 세글자 이상만을 두글자이상으로 override 함
    def get_author_tokens(self, authors, only_first_author=True):
        """
        Take a list of authors and return a list of tokens useful for an
        AND search query. This function tries to return tokens in
        first name middle names last name order, by assuming that if a comma is
        in the author name, the name is in lastname, other names form.
        """

        if authors:
            # Leave ' in there for Irish names
            remove_pat = re.compile(r'[!@#$%^&*()（）「」{}`~"\s\[\]/]')
            replace_pat = re.compile(r'[-+.:;,，。；：]')
            if only_first_author:
                authors = authors[:1]
            for au in authors:
                has_comma = ',' in str(au)
                au = replace_pat.sub(' ', au)
                parts = au.split()
                if has_comma:
                    # au probably in ln, fn form
                    parts = parts[1:] + parts[:1]
                for tok in parts:
                    tok = remove_pat.sub('', tok).strip()
                    if len(tok) > 1 and tok.lower() not in ('von', 'van', _('Unknown').lower()):
                        yield tok
                        
    def get_cached_cover_url(self, identifiers):
        url = None
        aladin_id = identifiers.get('aladin.co.kr', None)
        if aladin_id is None:
            isbn = identifiers.get('isbn', None)
            if isbn is not None:
                aladin_id = self.cached_isbn_to_identifier(isbn)
        if aladin_id is not None:
            url = self.cached_identifier_to_cover_url(aladin_id)
        
        return url
    
    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        """
        Identify candidates while keeping the requested ISBN edition constraint.
        """
        if abort.is_set() or timeout <= 0:
            return
        from calibre_plugins.aladin_co_kr.request_budget import RequestBudget
        from calibre_plugins.aladin_co_kr.text_cleaner import decode_html
        budget = RequestBudget(abort, timeout)
        identifiers = identifiers or {}
        if identifiers.get('isbn') and not check_isbn(identifiers['isbn']):
            log.error('조건 불일치: 유효하지 않은 ISBN입니다.')
            return
        query = ''
        matches = []
        # Unlike the other metadata sources, if we have a aladin id then we
        # do not need to fire a "search" at Aladin.com. Instead we will be
        # able to go straight to the URL for that book.
        aladin_id = identifiers.get('aladin.co.kr', None)
        isbn = check_isbn(identifiers.get('isbn', None))
        br = self.browser
        if isbn:
            matches.append('%s/shop/wproduct.aspx?ISBN=%s' % (Aladin_co_kr.BASE_URL, isbn))
        elif aladin_id:
            matches.append('%s/shop/wproduct.aspx?ItemId=%s' % (Aladin_co_kr.BASE_URL, aladin_id))
        else:
            query = self.create_query(log, title=title, authors=authors, identifiers=identifiers)
            if query is None:
                log.error('Insufficient metadata to construct query')
                return
            try:
                log.info('Querying: %s' % query)
                raw, _ = budget.read(br, query)
                
                try:
                    raw = decode_html(raw)
                    # open('E:\\t11.html', 'wb').write(raw) # XXXX
                    if not raw:
                        log.error('접속 실패: 빈 검색 응답: %r' % query)
                        return
                    root = fromstring(clean_ascii_chars(raw))
                except:
                    msg = '페이지 구조 변경: 검색 응답 파싱 실패: %r' % query
                    log.exception(msg)
                    return msg
                
                if isbn:
                    self._parse_search_isbn_results(log, isbn, root, matches, timeout)
                
                # For ISBN based searches we have already done everything we need to
                # So anything from this point below is for title/author based searches.
                if not isbn:
                    # open('E:\\t12.html', 'wb').write(raw) # XXXXXX
                    # log.info('identify: raw = %s' % raw)
                    
                    # Now grab the first value from the search results, provided the
                    # title and authors appear to be for the same book
                    self._parse_search_results(log, title, authors, root, matches, timeout)
                    if not matches:
                        ajax_query = self._create_ajax_query_from_search_query(query)
                        if ajax_query:
                            log.info('No results in search page, querying AJAX search: %s' % ajax_query)
                            try:
                                raw, _ = budget.read(br, ajax_query)
                                raw = decode_html(raw)
                                if raw:
                                    root = fromstring(clean_ascii_chars(raw))
                                    self._parse_search_results(log, title, authors, root, matches, timeout)
                            except:
                                log.exception('접속 또는 페이지 구조 확인: AJAX 검색 실패: %r' % ajax_query)
            
            except Exception as e:
                err = '접속 실패: 검색 요청 실패: %r' % query
                log.exception(err)
                return as_unicode(e)
        
        if abort.is_set():
            return
        
        if not matches:
            if identifiers and title and authors and not isbn:
                log.info('No matches found with identifiers, retrying using only title and authors')
                return self.identify(log, result_queue, abort, title=title, authors=authors, timeout=max(0, budget.deadline - time.monotonic()))
            log.info('책 없음 또는 조건 불일치: 허용할 검색 후보가 없습니다: %r' % query)
            return
        
        from calibre_plugins.aladin_co_kr.worker import Worker
        workers = [Worker(url, result_queue, br, log, i, self, timeout=timeout,
                          requested_title=title, requested_authors=authors, requested_isbn=isbn, budget=budget)
                   for i, url in enumerate(dict.fromkeys(matches))]
        
        for w in workers:
            if not budget.active():
                return
            w.start()
            # Don't send all requests at the same time
            abort.wait(min(0.1, max(0, budget.deadline - time.monotonic())))
        
        while budget.active():
            a_worker_is_alive = False
            for w in workers:
                w.join(min(0.2, max(0, budget.deadline - time.monotonic())))
                if abort.is_set():
                    break
                if w.is_alive():
                    a_worker_is_alive = True
            if not a_worker_is_alive:
                break
        
        return None
    
    def _parse_search_isbn_results(self, log, orig_isbn, root, matches, timeout):
        UNSUPPORTED_FORMATS = ['audiobook', 'other format', 'cd', 'item', 'see all formats & editions']
        results = self._search_result_nodes(root)
        if not results:
            # log.info('FOUND NO RESULTS:')
            return
        
        import calibre_plugins.aladin_co_kr.config as cfg
        max_results = cfg.plugin_prefs[cfg.STORE_NAME][cfg.KEY_MAX_DOWNLOADS]
        title_url_map = OrderedDict()
        num = 1
        for result in results:
            log.info('Looking at result:')
            title_nodes = result.xpath(
                './/div[contains(@class, "ss_book_list")]//a[@class="bo3" and contains(@href,"wproduct.aspx?ISBN=")]')
            
            title = ''
            if title_nodes:
                title = re.sub(r"\s{2,}", " ", title_nodes[0].text_content().strip())
            if not title:
                log.info('Could not find titlexxxxxxx')
                continue
            # Strip off any series information from the title
            log.info('FOUND TITLE:', title)
            if '(' in title:
                # log.info('Stripping off series(')
                title = title.rpartition('(')[0].strip()
            
            result_url = title_nodes[0].get('href')
            
            # if result_url and title not in title_url_map:
            # title_url_map[title] = Aladin_co_kr.BASE_URL + result_url
            if result_url:
                title_url_map["[%d] %s" % (num, title)] = result_url
                num = num + 1
                if len(title_url_map) >= max_results:
                    break
        
        for title in title_url_map.keys():
            matches.append(title_url_map[title])
            if len(matches) >= max_results:
                break
    
    def _parse_search_results(self, log, orig_title, orig_authors, root, matches, timeout):
        from calibre_plugins.aladin_co_kr.book_matching import mismatch
        # UNSUPPORTED_FORMATS = ['audiobook', 'other format', 'cd', 'item', 'see all formats & editions']
        # [국내도서], [외국도서], '[eBook]', '[알라딘굿즈]', '[커피]', '[음반]', '[DVD]', '[블루레이]'
        UNSUPPORTED_FORMATS = ['[ebook]', '[알라딘굿즈]', '[커피]', '[음반]', '[dvd]', '[블루레이]']
        
        results = self._search_result_nodes(root)
        if not results:
            value = root.text_content()
            if re.search(r'검색\s*결과가?\s*없|검색된\s*(?:상품|도서)가?\s*없', value):
                log.info('책 없음: 검색 결과가 없습니다.')
            else:
                log.error('페이지 구조 변경: 검색 결과 영역을 확인할 수 없습니다.')
            return
        
        import calibre_plugins.aladin_co_kr.config as cfg
        max_results = cfg.plugin_prefs[cfg.STORE_NAME][cfg.KEY_MAX_DOWNLOADS]
        title_url_map = OrderedDict()
        num = 1
        for result in results:
            log.info('Looking at result:')
            title_nodes = result.xpath(
                './/div[contains(@class, "ss_book_list")]//a[contains(@href,"wproduct.aspx")]/..')
            
            title = ''
            if title_nodes:
                title = re.sub(r"\s{2,}", " ", title_nodes[0].text_content().strip())
            if not title:
                log.error('페이지 구조 변경: 검색 후보 제목을 찾을 수 없습니다.')
                continue
            
            contributors = result.xpath('.//div[contains(@class, "ss_book_list")]//a[contains(@href,"AuthorSearch")]')
            authors = []
            for c in contributors:
                author = c.text_content()
                # log.info('Found author:',author)
                if author:
                    authors.append(author.strip())
            
            # log.info('Looking at tokens:',author)
            log.info('Considering search result: ', title, ",", '|'.join(authors))
            reason = mismatch(orig_title, orig_authors, None, {'title': title, 'authors': authors})
            if any(value in title.lower() for value in UNSUPPORTED_FORMATS):
                reason = reason or '지원하지 않는 상품 형식'
            if reason:
                log.info('조건 불일치: 후보 제외: %s: %s' % (reason, title))
                continue
            
            result_url = result.xpath('.//div[contains(@class, "ss_book_list")]//a/@href[contains(.,"wproduct.aspx?")]')
            
            # if result_url and title not in title_url_map:
            # title_url_map[title] = Aladin_co_kr.BASE_URL + result_url
            if result_url:
                title_url_map["[%d] %s" % (num, title)] = result_url[0]
                num = num + 1
                if len(title_url_map) >= max_results:
                    break
        
        for title in title_url_map.keys():
            matches.append(title_url_map[title])
            if len(matches) >= max_results:
                break
    
    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        from calibre_plugins.aladin_co_kr.request_budget import RequestBudget
        from calibre_plugins.aladin_co_kr.cover_validation import MAX_BYTES, validate_cover
        if abort.is_set() or timeout <= 0:
            return
        deadline = time.monotonic() + timeout
        cached_url = self.get_cached_cover_url(identifiers)
        if cached_url is None:
            log.info('No cached cover found, running identify')
            rq = Queue()
            self.identify(log, rq, abort, title=title, authors=authors, identifiers=identifiers, timeout=timeout)
            if abort.is_set():
                return
            results = []
            while True:
                try:
                    results.append(rq.get_nowait())
                except Empty:
                    break
            results.sort(key=self.identify_results_keygen(title=title, authors=authors, identifiers=identifiers))
            for mi in results:
                cached_url = self.get_cached_cover_url(mi.identifiers)
                if cached_url is not None:
                    break
        if cached_url is None:
            log.info('No cover found')
            return
        
        remaining = deadline - time.monotonic()
        if abort.is_set() or remaining <= 0:
            return
        br = self.browser
        log.info('Downloading cover from:', cached_url)
        try:
            cdata, _ = RequestBudget(abort, timeout, deadline=deadline).read(br, cached_url, limit=MAX_BYTES)
            validate_cover(cdata)
            if not abort.is_set() and time.monotonic() < deadline:
                result_queue.put((self, cdata))
        except ValueError as error:
            log.error('표지 제외: %s: %s' % (error, cached_url))
        except:
            log.exception('Failed to download cover from:', cached_url)


if __name__ == '__main__':  # tests
    # To run these test use:
    # calibre-debug -e __init__.py
    from calibre.ebooks.metadata.sources.test import (test_identify_plugin, title_test, authors_test, series_test)
    
    test_identify_plugin(
        Aladin_co_kr.name,
        [
            # # 원제 꼭지가 붙어 있다.
            # # 장 코르미에 (지은이) | 김미선 (옮긴이) | 실천문학사 | 2005-05-25 | 원제 Che Guevara (2002년)
            # (  # A book with an ISBN
            #     {'identifiers': {'isbn': '9788939205109'},
            #      'title': '체 게바라',
            #      'authors': ['장 코르미에']},
            #     [title_test('체 게바라 평전', exact=True),
            #      authors_test(['장 코르미에', '김미선']),
            #      series_test('역사 인물 찾기', 10.0)]
            # ),
            #
            # (  # A book with an aladin id
            #     {'identifiers': {'aladin.co.kr': '8932008485'}},
            #     [title_test('광장', exact=False),
            #      authors_test(['최인훈']),
            #      ]
            # ),
            #
            # (  # A book with title and author
            #     {'title': '나의 문화유산답사기 1',
            #      'authors': ['유홍준']},
            #     [title_test('나의 문화유산답사기 1', exact=False),
            #      authors_test(['유홍준'])]
            # ),
            #
            # (  # A book with an ISBN
            #     {'identifiers': {'isbn': '9788993824698'},
            #      'title': '61시간',
            #      'authors': ['리 차일드']},
            #     [title_test('61시간', exact=True),
            #      authors_test(['리 차일드', '박슬라']),
            #      series_test('잭 리처 시리즈', 0.0)]
            # ),
            
            # TODO: Books that hasn't isbn.
            
            # # rating 이 0 인 도서들( 외국도서 등)에서는 테스트할 때 멈춘다.
            # (  # A book with a Aladin id
            #     {'identifiers': {'aladin.co.kr': '0440243696'},
            #      'title': '61 Hours',
            #      'authors': ['Lee Child']},
            #     [title_test('61 Hours (Paperback, Reprint) - A Reacher Novel', exact=True),
            #      authors_test(['Lee Child']),
            #      # series_test('Jack Reacher', 14.0)
            #      ]
            # ),
            # (  # A book with an ISBN
            #     {'identifiers': {'isbn': '9780385340588'},
            #      'title': '61 Hours',
            #      'authors': ['Lee Child']},
            #     [title_test('61 Hours', exact=True),
            #      authors_test(['Lee Child']),
            #      series_test('Jack Reacher', 14.0)]
            # ),
            #
            # (  # A book with an ISBN
            #     {'identifiers': {'isbn': '9780385340588'},
            #      'title': '61 Hours',
            #      'authors': ['Lee Child']},
            #     [title_test('61 Hours (Hardcover)', exact=True),
            #      authors_test(['Lee Child'])]
            # ),  # ,series_test('A Reacher Novel', 14.0)
            #
            # (  # A book with an ISBN
            #     {'identifiers': {'isbn': '780804194587'},
            #      'title': 'Personal',
            #      'authors': ['Lee Child']},
            #     [title_test('Personal', exact=True),
            #      authors_test(['Lee Child']),
            #      series_test('Jack Reacher', 14.0)]
            # ),
            #
            # (  # A book throwing an index error
            #     {'title': 'The Girl Hunters',
            #      'authors': ['Mickey Spillane']},
            #     [title_test('The Girl Hunters', exact=True),
            #      authors_test(['Mickey Spillane']),
            #      series_test('Mike Hammer', 7.0)]
            # ),
            # (  # A book with no ISBN specified
            #     {'title': "Playing with Fire", 'authors': ['Derek Landy']},
            #     [title_test("Playing with Fire", exact=True),
            #      authors_test(['Derek Landy']),
            #      series_test('Skulduggery Pleasant', 2.0)]
            # ),
            
            # TODO: Testing code error when rating value is 0.0
            (  # A book with an ISBN
                # resutlt : Failed to find rating
                # rating 값이 0인 예.
                {'identifiers': {'isbn': '9788978011136'},
                 'title': '금강삼매경론',
                 'authors': ['원효']},
                [title_test('금강삼매경론 -상', exact=True),
                 authors_test(['원효', '조용길']),
                 # series_test('', 0.0)
                 ]
            ),
        
        ])
