"""Kyobo metadata source for Calibre. GPL-3.0."""
from calibre_plugins.kyobobook_co_kr.source_base import KoreanBookSource
from calibre_plugins.kyobobook_co_kr.config import OPTIONS


class Kyobo(KoreanBookSource):
    name = 'Kyobobook.co.kr'
    description = '교보문고에서 도서 메타데이터와 표지를 가져옵니다.'
    version = (1, 2, 5)
    namespace = 'kyobobook_co_kr'
    identifier = 'kyobobook.co.kr'
    referer = 'https://www.kyobobook.co.kr/'
    detail_url = 'https://product.kyobobook.co.kr/detail/{id}'
    search_url = 'https://search.kyobobook.co.kr/search?keyword={query}'
    options = OPTIONS
    touched_fields = frozenset(('title', 'authors', 'identifier:kyobobook.co.kr', 'identifier:isbn',
                                'comments', 'publisher', 'pubdate', 'tags', 'languages', 'rating'))
