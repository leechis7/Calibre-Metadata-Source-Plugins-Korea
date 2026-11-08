import itertools
import json
from queue import Queue
from threading import Event
import unittest
from unittest.mock import patch

from support import fixture
from test_calibre_contract import load_source
from source_doubles import Log, MechanizeBrowser


class EmptyDetailBrowser(MechanizeBrowser):
    def __init__(self, routes):
        super().__init__(routes)
        self.timeouts = []

    def open_novisit(self, url, timeout):
        self.timeouts.append(timeout)
        if '/detail/' in url:
            self.routes[url] = b''
        return super().open_novisit(url, timeout)


class KyoboRecoveryTests(unittest.TestCase):
    def source(self):
        source = load_source('kyobo')
        prefix = 'https://product.kyobobook.co.kr/api/gw/pdt/v2/product/component/S000221151022/'
        source.browser = EmptyDetailBrowser({prefix + 'top': fixture('kyobo_api_top.json').encode(),
                                            prefix + 'info': fixture('kyobo_api_info.json').encode(),
                                            prefix + 'middle': b'{"data":{"middle":{}}}'})
        return source, prefix

    def identify(self, source, abort=None):
        queue, log = Queue(), Log()
        source.identify(log, queue, abort or Event(), identifiers={'kyobobook.co.kr': 'S000221151022', 'isbn': '9791124073483'})
        return queue, log

    def test_persistently_empty_html_recovers_verified_api_metadata(self):
        source, _ = self.source()
        with patch('calibre_plugins.kyobobook_co_kr.source_base.time.monotonic', side_effect=itertools.count(0, 0.1)):
            queue, log = self.identify(source)
        mi = queue.get_nowait()
        self.assertEqual(mi.title, '트렌드 코리아 2027')
        self.assertEqual(mi.authors, ['김난도'])
        self.assertEqual(mi.isbn, '9791124073483')
        self.assertEqual(mi.publisher, '미래의창')
        self.assertFalse(mi.comments)  # APIs did not provide the main introduction.
        self.assertTrue(mi.has_cover)
        self.assertTrue(all(r.close.called for r in source.browser.responses))
        self.assertTrue(all(a >= b for a, b in zip(source.browser.timeouts, source.browser.timeouts[1:])))
        self.assertLessEqual(len(source.browser.calls), 7)
        self.assertFalse(log.exceptions)

    def test_wrong_product_id_isbn_and_api_error_are_rejected(self):
        for case in ('product', 'isbn', 'top', 'error'):
            with self.subTest(case=case):
                source, prefix = self.source()
                info = json.loads(source.browser.routes[prefix + 'info'])
                if case == 'product':
                    info['data']['info']['saleCmdtId'] = 'S000000610625'
                elif case == 'isbn':
                    info['data']['info']['cmdtCode'] = '9788936434267'
                elif case == 'error':
                    info['error'] = {'message': 'unavailable'}
                else:
                    top = json.loads(source.browser.routes[prefix + 'top'])
                    top['data']['top']['title']['link'] = [{'pid': 'S000000610625'}]
                    source.browser.routes[prefix + 'top'] = json.dumps(top).encode()
                source.browser.routes[prefix + 'info'] = json.dumps(info).encode()
                queue, _ = self.identify(source)
                self.assertTrue(queue.empty())
                self.assertFalse(source.ids)

    def test_cancel_during_api_recovery_stops_followup_requests(self):
        source, prefix = self.source()
        abort = Event()
        original = source.browser.open_novisit
        def open_(url, timeout):
            response = original(url, timeout)
            if url == prefix + 'info':
                abort.set()
            return response
        source.browser.open_novisit = open_
        queue, _ = self.identify(source, abort)
        self.assertTrue(queue.empty())
        self.assertEqual(source.browser.calls[-1], prefix + 'info')

    def test_foreign_host_is_not_a_recovery_target(self):
        source, _ = self.source()
        with self.assertRaises(ValueError):
            source.adapter().recover_details('https://evil.example/detail/S000221151022', lambda url: self.fail('Unexpected request'))
