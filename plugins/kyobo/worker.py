"""Parse Kyobo Next.js Flight data as JSON; never execute site JavaScript."""
import json
import re
from urllib.parse import urljoin, urlsplit

from lxml.html import fromstring

from .text_cleaner import decode_html, meta, safe_url, text
from .book_matching import isbn_key

BASE = 'https://product.kyobobook.co.kr'


def search_is_empty(raw):
    value = text(fromstring(decode_html(raw)))
    return bool(re.search(r'검색\s*결과가?\s*없|검색된\s*(?:상품|도서)가?\s*없|상품을\s*찾을\s*수\s*없', value))


def mapping(value):
    # Flight represents absent optional objects as the string "$undefined".
    return value if isinstance(value, dict) else {}


def valid_id(value):
    return bool(re.fullmatch(r'S\d{12}', value))


def empty_response_recovery_url(url):
    parsed = urlsplit(url)
    match = re.fullmatch(r'/detail/(S\d{12})', parsed.path)
    if parsed.hostname == 'product.kyobobook.co.kr' and match:
        return BASE + '/api/gw/pdt/v2/product/component/' + match[1] + '/top'


def search_results(raw):
    root = fromstring(decode_html(raw))
    results = []
    for href in root.xpath('//a[contains(concat(" ", normalize-space(@class), " "), " prod_info ")]/@href'):
        url = urljoin(BASE, href)
        match = re.fullmatch(r'/detail/(S\d{12})', urlsplit(url).path)
        if urlsplit(url).hostname == 'product.kyobobook.co.kr' and match:
            url = BASE + '/detail/' + match[1]
            if url not in results:
                results.append(url)
    return results


def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


def product_data(root, product_id):
    payloads = []
    chunks = []
    for script in root.xpath('//script'):
        raw = script.text or ''
        if script.get('id') == '__NEXT_DATA__':
            try:
                payloads.append(json.loads(raw))
            except ValueError:
                continue
        match = re.fullmatch(r'\s*self\.__next_f\.push\((\[.*\])\)\s*;?\s*', raw, re.S)
        if match:
            try:
                chunk = json.loads(match[1])
                if chunk[0] == 1 and isinstance(chunk[1], str):
                    chunks.append(chunk[1])
            except (ValueError, IndexError, TypeError):
                continue
    # Flight strings can be split between script tags; concatenate before reading records.
    for record in ''.join(chunks).splitlines():
        _, _, raw = record.partition(':')
        if raw.startswith(('[', '{')):
            try:
                payloads.append(json.loads(raw))
            except ValueError:
                continue
    for payload in payloads:
        for obj in objects(payload):
            if isinstance(obj.get('top'), dict) and obj['top'].get('saleCmdtId') == product_id:
                return obj
    raise ValueError('교보 상품 JSON을 찾을 수 없습니다: ' + product_id)


def parse_details(raw, url):
    root = fromstring(decode_html(raw))
    match = re.search(r'/detail/(S\d{12})', meta(root, 'og:url') or url)
    if not match:
        raise ValueError('교보 상품 ID가 없습니다.')
    requested = re.search(r'/detail/(S\d{12})', url)
    if requested and requested[1] != match[1]:
        raise ValueError('교보 상세 페이지 상품 ID가 요청과 일치하지 않습니다.')
    data = product_data(root, match[1])
    return parse_product(data, match[1], meta(root, 'og:image'))


def recover_details(url, fetch):
    """Use the same product's public API if its HTML remains empty."""
    parsed = urlsplit(url)
    match = re.fullmatch(r'/detail/(S\d{12})', parsed.path)
    if parsed.hostname != 'product.kyobobook.co.kr' or not match:
        raise ValueError('교보 복구 대상 상품 URL이 올바르지 않습니다.')
    product_id = match[1]
    prefix = BASE + '/api/gw/pdt/v2/product/component/' + product_id
    info = component(fetch(prefix + '/info'), 'info')
    api_top = component(fetch(prefix + '/top'), 'top')
    title = mapping(api_top.get('title'))
    main, details = mapping(title.get('main')), mapping(api_top.get('info'))
    if (info.get('saleCmdtId') != product_id or not isbn_key(info.get('cmdtCode'))
            or not any(mapping(link).get('pid') == product_id for link in title.get('link') or [])):
        raise ValueError('교보 복구 API의 상품 ID 또는 ISBN이 일치하지 않습니다.')
    top = {'saleCmdtId': product_id, 'title': main.get('value'),
           'authors': details.get('authors'), 'publisher': details.get('publisher'),
           'reviewScore': details.get('review'), 'cmdtCode': info['cmdtCode'],
           'saleCmdtDvsnCode': info.get('saleCmdtDvsnCode')}
    summary = {'basicInfo': {'isbn': info['cmdtCode']},
               'intro': {'categoriList': [{'bookCategory': main.get('category') or []}]}}
    cover = 'https://contents.kyobobook.co.kr/sih/fit-in/1000x0/pdt/%s.jpg' % info['cmdtCode']
    return parse_product({'top': top, 'summary': summary}, product_id, cover)


def component(raw, name):
    response = json.loads(raw)
    data = mapping(mapping(response).get('data')).get(name)
    if mapping(response).get('error') or not isinstance(data, dict):
        raise ValueError('교보 %s API 응답 형식이 올바르지 않습니다.' % name)
    return data


def parse_product(data, product_id, cover):
    top, summary = data['top'], mapping(data.get('summary'))
    basic = mapping(summary.get('basicInfo'))
    intro = mapping(summary.get('intro'))
    authors = []
    for group in top.get('authors') or []:
        # Keep writers, exclude translator/illustrator roles from the authors field.
        if mapping(group.get('role')).get('roleCode') == '001':
            authors.extend(a.get('chrcName', '') for a in group.get('info') or [])
    authors = [a.strip() for a in authors if a and a.strip()]
    for i, author in enumerate(authors):
        parts = [p.strip() for p in author.split(',')]
        if len(parts) == 2 and all(parts) and not re.search(r'[가-힣]', author):
            authors[i] = parts[1] + ' ' + parts[0]
    publisher = mapping(top.get('publisher'))
    tags = []
    for group in intro.get('categoriList') or []:
        tags.extend(c['label'] for c in (group.get('bookCategory') or [])[1:] if c.get('label'))
    langs = {'한국어': 'kor', '영어': 'eng', '일본어': 'jpn', '중국어': 'zho', '독일어': 'deu', '프랑스어': 'fra'}
    language = basic.get('language')
    if not language and top.get('saleCmdtDvsnCode') == 'KOR':
        language = '한국어'
    cover = safe_url(cover)
    if 'contents.kyobobook.co.kr/sih/fit-in/' in cover:
        cover = re.sub(r'/fit-in/\d+x\d+/', '/fit-in/1000x0/', cover)
    score = mapping(top.get('reviewScore')).get('score')
    isbn_match = re.search(r'(?<!\d)(?:97[89]\d{10}|\d{9}[\dXx])(?!\d)', str(basic.get('isbn') or top.get('cmdtCode') or ''))
    return {
        'id': product_id, 'title': top.get('title', ''),
        'format': top.get('saleCmdtDvsnCode', ''),
        'authors': list(dict.fromkeys(a for a in authors if a)),
        # Foreign editions can display both ISBN-13 and ISBN-10 in one field.
        'isbn': isbn_match.group(0) if isbn_match else None,
        'publisher': mapping(publisher.get('label')).get('text', ''), 'pubdate': publisher.get('pubDate'),
        'cover': cover, 'languages': [langs[language]] if language in langs else [],
        'rating': max(0, min(5, float(score) / 2)) if score is not None else None,
        'tags': list(dict.fromkeys(tags)),
        'sections': [('책소개', '\n\n'.join(x['content'] for x in intro.get('explanation') or [] if x.get('content') and x.get('anntDvsnCode') in ('001', '002')))],
    }


def enrich(book, fetch):
    url = BASE + '/api/gw/pdt/v2/product/component/' + book['id'] + '/middle'
    middle = component(fetch(url), 'middle')
    if middle.get('saleCmdtId') not in (None, book['id']):
        raise ValueError('교보 추가 도서정보의 상품 ID가 일치하지 않습니다.')
    authors = '\n\n'.join(a['name'] + '\n' + a['intro'] for a in middle.get('authorInfoList') or [] if a.get('name') and a.get('intro'))
    book['sections'].extend([('저자소개', authors), ('출판사 리뷰', middle.get('pubReview')),
                             ('목차', middle.get('contentTableList'))])
