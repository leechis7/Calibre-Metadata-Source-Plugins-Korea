"""Pure parsing helpers shared by independently packaged sources (GPL-3.0)."""
import gzip
import re
import unicodedata
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlsplit

from lxml.html import fragment_fromstring, tostring

from .book_matching import isbn_key


def decode_html(raw):
    if isinstance(raw, str):
        return raw
    if raw.startswith(b'\x1f\x8b'):
        raw = gzip.decompress(raw)
    for encoding in ('utf-8-sig', 'cp949', 'euc-kr'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode('utf-8', errors='replace')


def text(node):
    return ' '.join(node.text_content().split()) if node is not None else ''


def first_text(root, xpath):
    nodes = root.xpath(xpath)
    return text(nodes[0]) if nodes else ''


def meta(root, name):
    values = root.xpath('//meta[@property=$name or @name=$name]/@content', name=name)
    return values[0].strip() if values else ''


def safe_url(url):
    url = str(url or '').strip()
    if url.startswith('//'):
        url = 'https:' + url
    return url if urlsplit(url).scheme in ('http', 'https') else ''


def clean_html(value):
    if not isinstance(value, str) or not value.strip():
        return ''
    if value.strip() in ('$undefined', 'undefined', 'null', 'None'):
        return ''
    if not re.search(r'<[a-zA-Z][^>]*>', value):
        value = '<p>' + escape(value).replace('\n', '<br/>') + '</p>'
    root = fragment_fromstring(value, create_parent='div')
    for bad in root.xpath('.//script|.//style|.//iframe|.//object|.//form|.//button|.//input|.//textarea|.//noscript|.//*[@hidden or @aria-hidden="true"]'):
        bad.drop_tree()
    controls = {'더보기', '접기', '펼치기', '내용 더보기', '책소개 펼치기', '책소개 접기', '이미지 확대보기'}
    for node in list(root.iterdescendants()):
        if node.getparent() is None:
            continue
        style = re.sub(r'\s+', '', node.get('style', '')).lower()
        if 'display:none' in style or 'visibility:hidden' in style or text(node) in controls:
            node.drop_tree()
    for node in root.iter():
        for key in list(node.attrib):
            if key not in ('href', 'src', 'alt', 'title'):
                del node.attrib[key]
            elif key in ('href', 'src'):
                url = safe_url(node.attrib[key])
                if url:
                    node.attrib[key] = url
                else:
                    del node.attrib[key]
    visible = text(root)
    if not visible or '\ufffd' in visible or '占쏙옙' in visible:
        return ''
    return tostring(root, encoding='unicode', method='html')


def content_key(value):
    """Compare visible content, ignoring wrapper tags and whitespace."""
    root = fragment_fromstring(value, create_parent='div')
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text(root))).casefold()


def comments(sections, append_toc=True):
    result = []
    seen = set()
    for heading, value in sections:
        if heading == '목차' and not append_toc:
            continue
        html = clean_html(value)
        key = content_key(html) if html else ''
        if key and key not in seen:
            seen.add(key)
            result.append('<h3>%s</h3>%s' % (escape(heading), html))
    return ''.join(result)


def parse_date(value):
    match = re.search(r'(\d{4})\D*(\d{2})\D*(\d{2})', str(value or ''))
    if match:
        try:
            return datetime(*map(int, match.groups()), tzinfo=timezone.utc)
        except ValueError:
            pass


def normalized(value):
    return re.sub(r'[^\w]', '', str(value or '')).casefold()
