"""Report observable failures without treating every empty result as an outage."""
from queue import Queue
from threading import Event
import time


class DiagnosticLog:
    def __init__(self):
        self.lines = []

    def __call__(self, *args):
        self.lines.append(' '.join(str(arg) for arg in args))

    info = debug = warning = warn = error = exception = __call__


def failure_kind(lines):
    value = '\n'.join(lines)
    # Several candidates can fail differently; retain this ambiguity.
    connection = '접속 실패' in value or 'timed out' in value
    structure = '페이지 구조 변경' in value
    if connection and structure:
        return 'mixed_failure'
    if connection:
        return 'connection_failure'
    if structure:
        return 'parser_change'
    if '조건 불일치' in value:
        return 'candidate_mismatch'
    if '책 없음' in value:
        return 'not_found'
    return 'unknown_failure'


def check_source(source, title, authors, isbn, timeout=30):
    rows = []
    for mode in ('title', 'isbn'):
        log, queue, abort = DiagnosticLog(), Queue(), Event()
        started = time.monotonic()
        row = {'store': source.name, 'mode': mode, 'stage': 'identify', 'status': 'unknown_failure'}
        try:
            source.identify(log, queue, abort, title=title if mode == 'title' else None,
                            authors=authors if mode == 'title' else None,
                            identifiers={'isbn': isbn} if mode == 'isbn' else {}, timeout=timeout)
            metadata = next((item for item in list(queue.queue) if item.isbn == isbn), None)
            if metadata is None:
                row['status'] = failure_kind(log.lines)
                row['candidate_count'] = queue.qsize()
            else:
                row.update(title=metadata.title, isbn=metadata.isbn)
                missing = [field for field in ('authors', 'publisher', 'comments') if not getattr(metadata, field, None)]
                if '목차' not in (metadata.comments or ''):
                    missing.append('toc')
                row['missing_fields'] = missing
                row['stage'] = 'cover'
                covers = Queue()
                source.download_cover(log, covers, abort, identifiers=metadata.identifiers, timeout=timeout)
                if covers.empty():
                    row['status'] = 'cover_failure'
                else:
                    row['cover_bytes'] = len(covers.get_nowait()[1])
                    row['status'] = 'partial_metadata' if missing else 'ok'
                    row['stage'] = 'complete'
        except Exception as error:
            row['error'] = type(error).__name__ + ': ' + str(error)
        finally:
            abort.set()
        row['elapsed_seconds'] = round(time.monotonic() - started, 2)
        row['diagnostics'] = log.lines
        rows.append(row)
    return rows
