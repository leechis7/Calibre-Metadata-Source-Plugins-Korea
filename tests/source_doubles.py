"""Small HTTP and log doubles shared by ordinary and Calibre runtime tests."""
from io import BytesIO
import unittest.mock
from mechanize import make_response
from PIL import Image


def cover_bytes(format_='PNG', size=(100, 150)):
    output = BytesIO()
    Image.new('RGB', size, 'navy').save(output, format_)
    return output.getvalue()


COVER = cover_bytes()


class Browser:
    def __init__(self, routes):
        self.routes, self.calls = routes, []
        self.addheaders = []
        self.responses = []
    def open_novisit(self, url, timeout):
        self.calls.append(url)
        self.last_timeout = timeout
        response = Response(self.routes[url])
        self.responses.append(response)
        return response


class Response:
    """Like mechanize responses: read/close, with no context-manager protocol."""
    def __init__(self, raw):
        self.stream = BytesIO(raw)
    def read(self, size=-1):
        return self.stream.read(size)
    def close(self):
        self.stream.close()


class Log:
    def __init__(self):
        self.exceptions = []
        self.errors, self.messages = [], []
    def error(self, *args):
        self.errors.append(args)
    def info(self, *args):
        self.messages.append(args)
    def exception(self, *args):
        self.exceptions.append(args)


class MechanizeBrowser(Browser):
    def open_novisit(self, url, timeout):
        self.calls.append(url)
        response = make_response(self.routes[url], [('Content-Type', 'text/html; charset=utf-8')], url)
        # Record close() separately from mechanize's cached body semantics.
        response.close = unittest.mock.Mock(wraps=response.close)
        self.responses.append(response)
        return response
