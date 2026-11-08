"""Calibre integration; each archive gets its own copy and cache namespace."""
import importlib
import time
from queue import Queue
from urllib.parse import quote
from lxml.etree import LxmlError

from calibre.ebooks.metadata import check_isbn
from calibre.ebooks.metadata.book.base import Metadata
from calibre.ebooks.metadata.sources.base import Source
from calibre.library.comments import sanitize_comments_html

from .request_budget import RequestBudget
from .book_matching import mismatch
from .cover_validation import MAX_BYTES, validate_cover


class StoreResponseError(ValueError):
    """An unusable server response, distinct from a changed book page."""


class KoreanBookSource(Source):
    author = 'leechis7'
    minimum_calibre_version = (5, 0, 0)
    capabilities = frozenset(('identify', 'cover'))
    has_html_comments = True
    supports_gzip_transfer_encoding = True
    namespace = identifier = detail_url = search_url = ''
    referer = ''

    def adapter(self):
        return importlib.import_module('calibre_plugins.' + self.namespace + '.worker')

    def get_book_url(self, identifiers):
        value = identifiers.get(self.identifier)
        if value and self.adapter().valid_id(str(value)):
            return self.identifier, str(value), self.detail_url.format(id=value)

    def get_cached_cover_url(self, identifiers):
        value = identifiers.get(self.identifier)
        if not value:
            isbn = check_isbn(identifiers.get('isbn'))
            if isbn:
                value = self.cached_isbn_to_identifier(isbn)
        return self.cached_identifier_to_cover_url(value) if value else None

    def create_query(self, log, title=None, authors=None, identifiers=None):
        identifiers = identifiers or {}
        isbn = check_isbn(identifiers.get('isbn'))
        keyword = isbn or ' '.join([title or ''] + list((authors or [])[:1])).strip()
        return self.search_url.format(query=quote(keyword)) if keyword else None

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers=None, timeout=30):
        if abort.is_set():
            return
        identifiers = identifiers or {}
        if identifiers.get('isbn') and not check_isbn(identifiers['isbn']):
            log.error('조건 불일치: 유효하지 않은 ISBN입니다.')
            return
        adapter = self.adapter()
        cleaner = importlib.import_module('calibre_plugins.' + self.namespace + '.text_cleaner')
        budget = RequestBudget(abort, timeout)
        deadline = budget.deadline
        cache = {}
        browser = self.browser
        if self.referer:
            browser.addheaders = [(k,v) for k,v in browser.addheaders if k.lower() != 'referer'] + [('Referer', self.referer)]

        def fetch(url):
            budget.remaining()
            if url in cache:
                return cache[url]
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Metadata download timed out')
            raw, response_url = budget.read(browser, url)
            redirected = getattr(adapter, 'is_session_redirect', lambda requested, actual: False)(url, response_url)
            if (redirected or not raw.strip()) and not abort.is_set():
                # Some CDN entries return a cached empty 200 response. Retry once
                # with a distinct cache key, under the original request deadline.
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('Metadata download timed out')
                # YES24's first request can set a validation cookie and redirect
                # to its home page. Reuse this browser's cookies for the original
                # request; the home page is not an empty search result.
                if redirected:
                    log.info('서점 세션 확인 후 원래 요청을 다시 시도합니다: %s' % url)
                retry = url if redirected else url + ('&' if '?' in url else '?') + '_calibre=' + str(time.time_ns())
                raw, response_url = budget.read(browser, retry)
                if getattr(adapter, 'is_session_redirect', lambda requested, actual: False)(url, response_url):
                    raise StoreResponseError('Store session redirect persisted: ' + url)
            if not raw.strip():
                recovery_url = getattr(adapter, 'empty_response_recovery_url', lambda requested: None)(url)
                if recovery_url and not abort.is_set():
                    # An uncached product API request can establish the Kyobo
                    # product session before one final HTML request. Never invent
                    # metadata from the search query or another bookstore.
                    log.info('빈 상세 응답: 상품 API 세션 확인 후 다시 요청합니다: %s' % url)
                    fetch(recovery_url)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError('Metadata download timed out')
                    if abort.is_set():
                        raise InterruptedError('Metadata download cancelled')
                    retry = url + ('&' if '?' in url else '?') + '_calibre=' + str(time.time_ns())
                    raw, _ = budget.read(browser, retry)
            if not raw.strip():
                raise StoreResponseError('Empty HTTP response: ' + url)
            cache[url] = cleaner.decode_html(raw)
            return cache[url]

        book_url = self.get_book_url(identifiers)
        isbn = check_isbn(identifiers.get('isbn'))
        try:
            if book_url:
                candidates = [book_url[2]]
            else:
                query = self.create_query(log, title, authors, identifiers)
                if not query:
                    log.error('검색에 필요한 제목, 저자 또는 ISBN이 없습니다.')
                    return
                search_html = fetch(query)
                candidates = adapter.search_results(search_html)
                if not candidates:
                    if adapter.search_is_empty(search_html):
                        log.info('책 없음: 검색 결과가 없습니다.')
                    else:
                        log.error('페이지 구조 변경: 검색 결과 영역을 확인할 수 없습니다.')
                    return
            found = 0
            max_results = max(1, min(20, int(self.prefs['max_results'])))
            # Bound detail requests independently of the number of accepted books.
            for url in list(dict.fromkeys(candidates))[:max_results * 3]:
                if abort.is_set():
                    return
                if time.monotonic() >= deadline:
                    log.error('접속 실패: 검색 제한 시간을 초과했습니다.')
                    break
                try:
                    try:
                        detail_html = fetch(url)
                    except StoreResponseError:
                        if not hasattr(adapter, 'recover_details'):
                            raise
                        log.info('빈 상세 HTML: 같은 상품의 API로 메타데이터를 복구합니다: %s' % url)
                        book = adapter.recover_details(url, fetch)
                    else:
                        if adapter.search_is_empty(detail_html):
                            log.info('책 없음: 상품을 찾을 수 없습니다: %s' % url)
                            continue
                        book = adapter.parse_details(detail_html, url)
                    if not book.get('title') or not book.get('authors') or not book.get('id'):
                        log.error('페이지 구조 변경: 도서 필수 정보를 찾을 수 없습니다: %s' % url)
                        continue
                    reason = mismatch(title, authors, isbn, book)
                    if reason:
                        log.info('조건 불일치: 후보 제외: %s: %s' % (reason, url))
                        continue
                    if hasattr(adapter, 'enrich'):
                        try:
                            adapter.enrich(book, fetch)
                        except (InterruptedError, TimeoutError):
                            raise
                        except Exception:
                            log.exception('추가 도서정보 실패 (접속 또는 응답 형식 확인): %s' % url)
                    mi = Metadata(book['title'], book['authors'])
                    mi.set_identifier(self.identifier, book['id'])
                    mi.isbn = check_isbn(book.get('isbn'))
                    mi.publisher = book.get('publisher') or None
                    mi.pubdate = cleaner.parse_date(book.get('pubdate'))
                    mi.languages = book.get('languages') or []
                    mi.tags = book.get('tags', []) if self.prefs['get_tags'] else []
                    mi.rating = book.get('rating')
                    if book.get('series'):
                        mi.series = book['series']
                    mi.comments = sanitize_comments_html(cleaner.comments(book.get('sections', []), self.prefs['append_toc']))
                    cover = book.get('cover')
                    mi.has_cover = bool(cover)
                    mi.source_relevance = found
                    self.clean_downloaded_metadata(mi)
                    if abort.is_set() or time.monotonic() >= deadline:
                        return
                    if mi.isbn:
                        self.cache_isbn_to_identifier(mi.isbn, book['id'])
                    if cover:
                        self.cache_identifier_to_cover_url(book['id'], cover)
                    result_queue.put(mi)
                    found += 1
                    if found >= max_results:
                        break
                except InterruptedError:
                    return
                except TimeoutError:
                    log.error('접속 실패: 검색 제한 시간을 초과했습니다: %s' % url)
                    break
                except (OSError, StoreResponseError) as error:
                    if getattr(error, 'code', None) == 404:
                        log.info('책 없음: 상품 페이지가 없습니다: %s' % url)
                    else:
                        log.exception('접속 실패: 도서 상세정보 요청 실패: %s' % url)
                except (ValueError, TypeError, AttributeError, LxmlError):
                    log.exception('페이지 구조 변경: 도서 상세정보 파싱 실패: %s' % url)
                except Exception:
                    log.exception('도서 상세정보 처리 실패: %s' % url)
            if not found and book_url and title and not abort.is_set():
                remaining = deadline - time.monotonic()
                if remaining > 0:
                    # Drop only the stale store ID. Keep the requested edition's ISBN.
                    log.info('상품 ID 재검색: ISBN·제목·저자 조건을 유지합니다.')
                    retry_ids = {'isbn': isbn} if isbn else {}
                    self.identify(log, result_queue, abort, title, authors, retry_ids, timeout=remaining)
        except InterruptedError:
            return
        except (OSError, StoreResponseError):
            log.exception('접속 실패: 메타데이터 검색 요청 실패')
        except (ValueError, TypeError, AttributeError, LxmlError):
            log.exception('페이지 구조 변경: 검색 결과 파싱 실패')
        except Exception:
            log.exception('메타데이터 검색 실패')

    def download_cover(self, log, result_queue, abort, title=None, authors=None, identifiers=None, timeout=30, get_best_cover=False):
        if abort.is_set():
            return
        identifiers = identifiers or {}
        deadline = time.monotonic() + timeout
        url = self.get_cached_cover_url(identifiers)
        if not url:
            matches = Queue()
            self.identify(log, matches, abort, title, authors, identifiers, timeout)
            results = []
            while not matches.empty():
                results.append(matches.get_nowait())
            results.sort(key=self.identify_results_keygen(title=title, authors=authors, identifiers=identifiers))
            for mi in results:
                url = self.get_cached_cover_url(mi.identifiers)
                if url:
                    break
        remaining = deadline - time.monotonic()
        if not url or abort.is_set() or remaining <= 0:
            return
        try:
            raw, _ = RequestBudget(abort, timeout, deadline=deadline).read(self.browser, url, limit=MAX_BYTES)
            validate_cover(raw)
            if not abort.is_set() and time.monotonic() < deadline:
                result_queue.put((self, raw))
        except ValueError as error:
            log.error('표지 제외: %s: %s' % (error, url))
        except Exception:
            log.exception('표지 다운로드 실패: %s' % url)
