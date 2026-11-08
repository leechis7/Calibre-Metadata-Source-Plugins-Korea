"""Bound read-only requests by one operation deadline and cancellation event."""
from contextlib import closing
import socket
import time
from urllib.error import HTTPError, URLError


class RequestBudget:
    def __init__(self, abort, timeout, deadline=None):
        self.abort = abort
        self.deadline = time.monotonic() + timeout if deadline is None else deadline

    def remaining(self):
        if self.abort.is_set():
            raise InterruptedError('Metadata download cancelled')
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Metadata download timed out')
        return remaining

    def active(self):
        return not self.abort.is_set() and time.monotonic() < self.deadline

    def read(self, browser, url, limit=8 * 1024 * 1024):
        # Retry only transient GET failures, once; never retry 404 or parse errors.
        for attempt in range(2):
            try:
                with closing(browser.open_novisit(url, timeout=self.remaining())) as response:
                    raw = response.read(limit + 1)
                    final_url = response.geturl() if hasattr(response, 'geturl') else url
                self.remaining()
                if len(raw) > limit:
                    raise ValueError('Response exceeds size limit')
                return raw, final_url
            except HTTPError as error:
                transient = error.code in (429, 502, 503, 504)
                error.close()
                if not transient or attempt:
                    raise
            except (URLError, ConnectionError, socket.timeout):
                if attempt:
                    raise
            delay = min(0.25, self.remaining())
            if self.abort.wait(delay):
                raise InterruptedError('Metadata download cancelled')
