import unittest

from support import load_adapter

load_adapter('yes24')
from calibre_plugins.yes24_com.book_matching import isbn_key, mismatch


class EditionMatchingTests(unittest.TestCase):
    def reason(self, requested_title='아몬드', requested_authors=('손원평',), requested_isbn=None, **book):
        candidate = dict(title='아몬드', authors=['손원평'], isbn='9788936434267')
        candidate.update(book)
        return mismatch(requested_title, requested_authors, requested_isbn, candidate)

    def test_same_edition_isbn10_13_and_bad_checksums(self):
        self.assertIsNone(self.reason(requested_isbn='8936434268'))
        self.assertIn('ISBN', self.reason(requested_isbn='9788936434267', **{'isbn': '9788936434268'}))

    def test_invalid_isbn_and_short_values_do_not_match(self):
        for value in ('', '1234', 'abcdefghij', '9788936434268', 'X936434268', '1234567890123'):
            with self.subTest(value=value):
                self.assertEqual(isbn_key(value), '')

    def test_related_titles_volumes_and_authors_are_not_substring_matches(self):
        for book in ({'title': '아몬드 요리'}, {'title': '아몬드 2'}, {'authors': ['손원평연구회']},
                     {'authors': ['다른 작가']}, {'title': 'The Almond'}):
            with self.subTest(book=book):
                self.assertIsNotNone(self.reason(**book))

    def test_formats_revisions_and_sets(self):
        for book in ({'title': '[eBook] 아몬드'}, {'format': 'https://schema.org/EBook'},
                     {'title': '아몬드 오디오북'}, {'title': '아몬드 (개정판)'},
                     {'title': '아몬드 세트'}, {'title': '아몬드 전집'}):
            with self.subTest(book=book):
                self.assertIsNotNone(self.reason(**book))

    def test_volume_markers_survive_subtitle_removal(self):
        for first, second in (('삼국지: 1권', '삼국지: 2권'), ('삼국지 - 1권', '삼국지 - 2권'),
                              ('삼국지: 상', '삼국지: 하'), ('삼국지 (상권)', '삼국지 (하권)'),
                              ('Saga: Volume 1', 'Saga: Volume 2'), ('삼국지', '삼국지: 1권')):
            with self.subTest(first=first, second=second):
                self.assertIsNotNone(self.reason(requested_title=first, title=second))
        self.assertIsNone(self.reason(requested_title='삼국지: 1권', title='삼국지 - 제1권'))

    def test_explicit_edition_and_subtitle_can_match(self):
        self.assertIsNone(self.reason(requested_title='아몬드 (개정판)', **{'title': '아몬드 (개정판)'}))
        self.assertIsNone(self.reason(**{'title': '아몬드 - 성장 이야기'}))
        self.assertIsNone(self.reason(requested_title='[eBook] 아몬드', **{'title': '아몬드', 'format': 'EBook'}))

    def test_foreign_author_order_and_unicode(self):
        self.assertIsNone(mismatch('AI Governance in Practice', ['Hemang Doshi'], None,
                                  {'title': 'AI Governance in Practice', 'authors': ['Doshi, Hemang']}))
        self.assertIsNone(self.reason(requested_title='ＡＩ', requested_authors=['Lee'], **{'title': 'AI', 'authors': ['Lee']}))
        self.assertIsNotNone(mismatch('AI', ['Hemang Doshi'], None, {'title': 'AI', 'authors': ['Doshi']}))

    def test_valid_isbn_has_priority_over_translated_title_and_author_spelling(self):
        self.assertIsNone(self.reason(requested_title='The Almond', requested_authors=['Sohn Won-pyung'], requested_isbn='9788936434267'))
