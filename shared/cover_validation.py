"""Validate actual cover bytes before returning them to Calibre."""
from io import BytesIO
import warnings

from PIL import Image

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
MIN_EDGE = 64


def validate_cover(raw):
    """Return (format, width, height), or raise ValueError for unusable covers."""
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError('표지가 비어 있거나 20 MiB 제한을 초과했습니다.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                format_, (width, height) = image.format, image.size
                if format_ not in ('JPEG', 'PNG', 'GIF', 'WEBP'):
                    raise ValueError('지원하지 않는 표지 형식입니다: %s' % format_)
                if min(width, height) < MIN_EDGE or width * height > MAX_PIXELS:
                    raise ValueError('표지 크기가 허용 범위를 벗어났습니다: %dx%d' % (width, height))
                image.verify()
            # verify checks structure; load also catches truncated JPEG data.
            with Image.open(BytesIO(raw)) as image:
                image.load()
    except (OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError('손상되었거나 이미지가 아닌 표지 응답입니다.') from error
    return format_, width, height
