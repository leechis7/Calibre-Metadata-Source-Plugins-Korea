import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image
from support import load_adapter
from source_doubles import cover_bytes

load_adapter('yes24')
from calibre_plugins.yes24_com.cover_validation import validate_cover


class CoverValidationTests(unittest.TestCase):
    def test_supported_formats_and_dimensions(self):
        for format_ in ('PNG', 'JPEG', 'GIF', 'WEBP'):
            with self.subTest(format=format_):
                self.assertEqual(validate_cover(cover_bytes(format_)), (format_, 100, 150))

    def test_html_empty_truncated_and_tiny_images(self):
        for raw in (b'', b'<html>Service unavailable</html>', b'\xff\xd8not a jpeg',
                    cover_bytes()[:40], cover_bytes('JPEG')[:-40], cover_bytes(size=(1, 1))):
            with self.subTest(length=len(raw)):
                with self.assertRaises(ValueError):
                    validate_cover(raw)

    def test_unsupported_format(self):
        output = BytesIO()
        Image.new('RGB', (100, 150)).save(output, 'BMP')
        with self.assertRaises(ValueError):
            validate_cover(output.getvalue())

    def test_pixel_limit_prevents_decoding(self):
        with patch('calibre_plugins.yes24_com.cover_validation.MAX_PIXELS', 10_000):
            with self.assertRaises(ValueError):
                validate_cover(cover_bytes())

    def test_byte_limit_prevents_decoding(self):
        with patch('calibre_plugins.yes24_com.cover_validation.MAX_BYTES', 20):
            with self.assertRaises(ValueError):
                validate_cover(cover_bytes())
