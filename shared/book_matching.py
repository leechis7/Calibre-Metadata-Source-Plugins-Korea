"""Conservative edition matching shared by the three independent plugins."""
import re
import unicodedata


def normalized(value):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', str(value or ''))).casefold()


def isbn_key(value):
    value = re.sub(r'[^\dXx]', '', str(value or '')).upper()
    if len(value) == 10:
        if not re.fullmatch(r'\d{9}[\dX]', value):
            return ''
        if sum((10-i) * (10 if c == 'X' else int(c)) for i, c in enumerate(value)) % 11:
            return ''
        value = '978' + value[:9]
        value += str((-sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value))) % 10)
    if not re.fullmatch(r'97[89]\d{10}', value):
        return ''
    return value if sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10 == 0 else ''


def book_format(title, format_=''):
    value = (str(title or '') + ' ' + str(format_ or '')).casefold()
    if re.search(r'ebook|e-book|전자책', value):
        return 'ebook'
    if re.search(r'audiobook|audio.?cd|오디오북', value):
        return 'audio'
    return 'print'


def edition(title):
    value = str(title or '').casefold()
    revised = re.findall(r'\d+\s*판|개정\s*\d*\s*판|증보판|revised\s+edition|(?:\d+(?:st|nd|rd|th)|first|second|third)\s+edition', value)
    set_ = bool(re.search(r'세트|전집|합본|\bbox(?:ed)?\s+set\b|\bomnibus\b', value))
    return tuple(normalized(v) for v in revised), set_


def title_key(title):
    value = re.sub(r'\[(?:e-?book|전자책|종이책|국내도서|외국도서)\]', '', str(title or ''), flags=re.I)
    return normalized(re.split(r'\s+-\s+|\s*[:：]\s*', value, maxsplit=1)[0])


def volume_key(title):
    """Keep volume markers even when a storefront appends them as a subtitle."""
    value = unicodedata.normalize('NFKC', str(title or '')).casefold()
    numbers = re.findall(r'(?:제\s*)?(\d+)\s*(?:권|부|집)(?![가-힣])|\b(?:vol(?:ume)?\.?|book|part)\s*(\d+)\b', value)
    parts = re.findall(r'(?:^|[\s:：()\[\]-])([상중하])(?:\s*권)?(?=$|[\s)\]:：-])', value)
    return tuple(int(a or b) for a, b in numbers), tuple(parts)


def author_key(author):
    value = re.sub(r'\s+(?:저|지음|글)$', '', str(author or '').strip())
    parts = [p.strip() for p in value.split(',')]
    if len(parts) == 2 and all(parts) and not re.search(r'[가-힣]', value):
        value = parts[1] + ' ' + parts[0]
    return normalized(value)


def mismatch(title, authors, isbn, book):
    """Return a diagnostic reason, or None. A valid ISBN identifies an edition."""
    if isbn:
        wanted, actual = isbn_key(isbn), isbn_key(book.get('isbn'))
        if not wanted or wanted != actual:
            return 'ISBN 불일치 (요청 %s / 후보 %s)' % (isbn, book.get('isbn'))
        return None
    candidate = book.get('title', '')
    if book_format(title) != book_format(candidate, book.get('format', '')):
        return '도서 형식 불일치'
    if title:
        if volume_key(title) != volume_key(candidate):
            return '권수 불일치'
        if edition(title) != edition(candidate):
            return '개정판·세트 조건 불일치'
        if not title_key(title) or title_key(title) != title_key(candidate):
            return '제목 불일치 (요청 %s / 후보 %s)' % (title, candidate)
    if authors:
        wanted = {author_key(a) for a in authors} - {''}
        actual = {author_key(a) for a in book.get('authors', [])} - {''}
        if not wanted.intersection(actual):
            return '저자 불일치 (요청 %s / 후보 %s)' % (', '.join(authors), ', '.join(book.get('authors', [])))
    return None
