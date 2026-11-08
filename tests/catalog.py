"""Synthetic catalogue responses: no claims about current bookstore inventory."""
from html import escape
import json


BOOKS = (
    ('domestic', '아몬드', '손원평', '9788936434267', 'InStock'),
    ('foreign', 'AI Governance in Practice', 'Hemang Doshi', '9781807300814', 'InStock'),
    ('out-of-print', 'The Book of Debugging', 'Johannes Kuhlmann', '9781718504066', 'Discontinued'),
)


def responses(store, title, author, isbn, availability='InStock', format_='Hardcover', intro='검증 소개'):
    """Minimal real parser structures with deterministic synthetic field values."""
    if store == 'yes24':
        url = 'https://www.yes24.com/Product/Goods/125557465'
        data = {'@type': 'Book', 'name': title, 'author': {'name': author}, 'isbn': isbn,
                'publisher': {'name': '검증 출판사'}, 'description': intro,
                'bookFormat': format_, 'offers': {'availability': 'https://schema.org/' + availability}}
        detail = '<html><script type="application/ld+json">%s</script></html>' % json.dumps(data)
        search = '<a class="gd_name" href="%s">%s</a>' % (url, escape(title))
    elif store == 'kyobo':
        url = 'https://product.kyobobook.co.kr/detail/S000000610625'
        data = {'top': {'saleCmdtId': 'S000000610625', 'title': title, 'cmdtCode': isbn,
                        'authors': [{'role': {'roleCode': '001'}, 'info': [{'chrcName': author}]}],
                        'publisher': {'label': {'text': '검증 출판사'}}, 'saleCmdtDvsnCode': format_,
                        'saleState': availability},
                'summary': {'basicInfo': {'isbn': isbn},
                            'intro': {'explanation': [{'content': intro, 'anntDvsnCode': '001'}]}}}
        detail = '<html><script id="__NEXT_DATA__">%s</script></html>' % json.dumps(data)
        search = '<a class="prod_info" href="%s">%s</a>' % (url, escape(title))
    else:
        url = 'https://www.aladin.co.kr/shop/wproduct.aspx?ItemId=123'
        detail = ('<html><head><title>[알라딘] %s</title><meta property="books:isbn" content="%s">'
                  '<meta property="og:url" content="%s"><meta name="Description" content="%s">'
                  '</head><body><div><span class="Ere_bo_title">%s</span></div>'
                  '<div class="tlist"><a href="?AuthorSearch=1">%s</a> (지은이)'
                  '<a href="?PublisherSearch=1">검증 출판사</a></div><p>%s</p></body></html>') % (
                      escape(title), isbn, url, escape(intro, quote=True), escape(title), escape(author), availability)
        search = ('<div class="ss_book_box"><div class="ss_book_list"><p><a href="%s">%s</a></p>'
                  '<a href="?AuthorSearch=1">%s</a></div></div>') % (url, escape(title), escape(author))
    return url, search.encode(), detail.encode()
