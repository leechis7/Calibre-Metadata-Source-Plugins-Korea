"""YES24 metadata source for Calibre. GPL-3.0."""
from calibre_plugins.yes24_com.source_base import KoreanBookSource
from calibre_plugins.yes24_com.config import OPTIONS


class YES24(KoreanBookSource):
    name = 'YES24.com'
    description = 'YES24에서 도서 메타데이터와 표지를 가져옵니다.'
    version = (1, 2, 5)
    namespace = 'yes24_com'
    identifier = 'yes24.com'
    detail_url = 'https://www.yes24.com/Product/Goods/{id}'
    search_url = 'https://www.yes24.com/Product/Search?domain=ALL&query={query}'
    options = OPTIONS
    touched_fields = frozenset(('title', 'authors', 'identifier:yes24.com', 'identifier:isbn',
                                'comments', 'publisher', 'pubdate', 'tags', 'languages', 'rating', 'series'))
