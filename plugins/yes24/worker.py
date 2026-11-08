"""YES24 HTML/JSON-LD adapter; no GUI or Calibre dependencies."""
import json
import re
from urllib.parse import urljoin, urlsplit

from lxml.html import fromstring, tostring

from .text_cleaner import decode_html, first_text, meta, safe_url, text

BASE = 'https://www.yes24.com'


def search_is_empty(raw):
    value = text(fromstring(decode_html(raw)))
    return bool(re.search(r'검색\s*결과가?\s*없|검색된\s*(?:상품|도서)가?\s*없|상품을\s*찾을\s*수\s*없', value))


def valid_id(value):
    return bool(re.fullmatch(r'\d+', value))


def is_session_redirect(requested_url, response_url):
    """YES24 sets a validation cookie and sends a fresh session to its home page."""
    requested, response = urlsplit(requested_url), urlsplit(response_url)
    return (requested.hostname == response.hostname == 'www.yes24.com'
            and requested.path.lower().startswith('/product/')
            and response.path.lower() in ('/', '/main/default.aspx'))


def search_results(raw):
    root = fromstring(decode_html(raw))
    result = []
    for href in root.xpath('//a[contains(concat(" ", normalize-space(@class), " "), " gd_name ")]/@href'):
        url = urljoin(BASE, href)
        match = re.fullmatch(r'/product/goods/(\d+)', urlsplit(url).path, re.I)
        if urlsplit(url).hostname == 'www.yes24.com' and match:
            url = BASE + '/Product/Goods/' + match[1]
            if url not in result:
                result.append(url)
    return result


def book_json(root, product_id=None):
    unbound = []
    for raw in root.xpath('//script[@type="application/ld+json"]/text()'):
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(value, (dict, list)):
            continue
        values = value if isinstance(value, list) else value.get('@graph', [value])
        for item in values:
            if not isinstance(item, dict):
                continue
            types = item.get('@type', [])
            if 'Book' in (types if isinstance(types, list) else [types]):
                item_id = str(item.get('sku') or '')
                match = re.search(r'/product/goods/(\d+)', str(item.get('url') or ''), re.I)
                ids = {item_id} if item_id else set()
                if match:
                    ids.add(match[1])
                if not product_id or ids == {product_id}:
                    return item
                if not ids:
                    unbound.append(item)
    return unbound[0] if len(unbound) == 1 else {}


def section(root, id_):
    nodes = root.xpath('//*[@id=$id]', id=id_)
    if not nodes:
        return ''
    node = nodes[0]
    # Some YES24 descriptions are escaped HTML in a textarea, rendered by JS.
    values = node.xpath('.//textarea[contains(@class,"txtContentText")]/text()')
    if values:
        return '\n'.join(v.strip() for v in values)
    nodes = node.xpath('.//*[contains(concat(" ", normalize-space(@class), " "), " txtContentText ")]')
    return tostring(nodes[0], encoding='unicode') if nodes else ''


def parse_details(raw, url):
    root = fromstring(decode_html(raw))
    canonical = meta(root, 'og:url') or url
    match = re.search(r'/product/goods/(\d+)', canonical, re.I)
    requested = re.search(r'/product/goods/(\d+)', url, re.I)
    if requested and match and requested[1] != match[1]:
        raise ValueError('YES24 상세 페이지 상품 ID가 요청과 일치하지 않습니다.')
    data = book_json(root, match[1] if match else None)
    title = first_text(root, '//h2[contains(@class,"gd_name")]') or data.get('name', '')
    author = data.get('author', [])
    if isinstance(author, dict):
        author = [author]
    elif isinstance(author, str):
        author = [author]
    authors = [a.get('name', '') if isinstance(a, dict) else str(a) for a in author]
    # Foreign-book JSON-LD sometimes contains only the surname. The visible
    # author field has the full name as plain text rather than linked authors.
    author_nodes = root.xpath('//span[contains(@class,"gd_auth")]')
    if author_nodes and not author_nodes[0].xpath('.//a'):
        visible = text(author_nodes[0])
        if visible:
            authors = []
            for name in re.split(r'\s*[;/]\s*', visible):
                parts = [part.strip() for part in name.split(',')]
                if len(parts) == 2 and all(parts) and not re.search(r'[가-힣]', name):
                    name = parts[1] + ' ' + parts[0]
                authors.append(name)
    if not authors:
        authors = [text(n) for n in root.xpath('//span[contains(@class,"gd_auth")]//a')]
    publisher = data.get('publisher', {})
    publisher = publisher.get('name', '') if isinstance(publisher, dict) else publisher
    date = data.get('datePublished') or first_text(root, '//span[contains(@class,"gd_date")]')
    rating = data.get('aggregateRating') or {}
    try:
        score = float(rating.get('ratingValue', meta(root, 'books:rating:value'))) * 5 / float(rating.get('bestRating', 10))
        score = max(0, min(5, score))
    except (TypeError, ValueError, ZeroDivisionError):
        score = None
    series = data.get('isPartOf') or {}
    intro = section(root, 'infoset_introduce') or data.get('description') or meta(root, 'description')
    language = str(data.get('inLanguage', '')).lower()
    langs = {'ko': 'kor', 'en': 'eng', 'ja': 'jpn', 'zh': 'zho', 'de': 'deu', 'fr': 'fra'}
    return {
        'id': match[1] if match else None, 'title': title,
        'format': data.get('bookFormat', ''),
        'authors': list(dict.fromkeys(a.strip() for a in authors if a.strip())),
        'isbn': data.get('isbn') or meta(root, 'books:isbn'),
        'publisher': publisher or first_text(root, '//span[contains(@class,"gd_pub")]/a'),
        'pubdate': date, 'rating': score,
        'cover': safe_url(meta(root, 'og:image')),
        'series': series.get('name') if isinstance(series, dict) else None,
        'tags': data.get('genre', []) if isinstance(data.get('genre', []), list) else [data['genre']],
        'languages': [langs[language.split('-')[0]]] if language.split('-')[0] in langs else [],
        'sections': [('책소개', intro), ('저자소개', '\n\n'.join(text(n) for n in root.xpath('//*[@id="infoset_authorGrp"]//*[contains(@class,"info_origin")]'))),
                     ('출판사 리뷰', section(root, 'infoset_pubReivew')), ('목차', section(root, 'infoset_toc'))],
    }
