import socket
from threading import Event
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from support import load_adapter
from source_doubles import Browser, Response

load_adapter('yes24')
from calibre_plugins.yes24_com.request_budget import RequestBudget


class RequestBudgetTests(unittest.TestCase):
    def test_retry_transient_error_only_once(self):
        browser = Browser({})
        response = Response(b'ok')
        budget = RequestBudget(Event(), 3)
        with patch.object(browser, 'open_novisit', side_effect=[socket.timeout(), response]) as request:
            self.assertEqual(budget.read(browser, 'url')[0], b'ok')
        self.assertEqual(request.call_count, 2)
        self.assertLess(request.call_args_list[1].kwargs['timeout'], request.call_args_list[0].kwargs['timeout'])
        self.assertTrue(response.stream.closed)

    def test_permanent_http_error_does_not_retry(self):
        browser = Browser({})
        with patch.object(browser, 'open_novisit', side_effect=HTTPError('url', 404, 'missing', {}, None)) as request:
            with self.assertRaises(HTTPError):
                RequestBudget(Event(), 3).read(browser, 'url')
        self.assertEqual(request.call_count, 1)

    def test_cancellation_after_read_discards_response_and_closes_it(self):
        abort = Event()
        response = Response(b'ok')
        original = response.read
        def cancel(size):
            abort.set()
            return original(size)
        response.read = cancel
        with self.assertRaises(InterruptedError):
            RequestBudget(abort, 3).read(type('Browser', (), {'open_novisit': lambda *a, **k: response})(), 'url')
        self.assertTrue(response.stream.closed)

    def test_expired_budget_starts_no_requests(self):
        browser = Browser({})
        with self.assertRaises(TimeoutError):
            RequestBudget(Event(), 0).read(browser, 'url')
        self.assertFalse(browser.calls)

    def test_response_size_is_bounded(self):
        browser = Browser({'url': b'12345'})
        with self.assertRaises(ValueError):
            RequestBudget(Event(), 3).read(browser, 'url', limit=4)
        self.assertTrue(browser.responses[0].stream.closed)
