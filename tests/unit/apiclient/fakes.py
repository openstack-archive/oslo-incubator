"""
A fake server that "responds" to API methods with pre-canned responses.

All of these responses come from the spec, so if for some reason the spec's
wrong the tests might raise AssertionError. I've indicated in comments the
places where actual behavior differs from the spec.
"""

import urlparse
import requests

from openstack.common.apiclient import client as base_client


def assert_has_keys(dict, required=[], optional=[]):
    keys = dict.keys()
    for k in required:
        try:
            assert k in keys
        except AssertionError:
            extra_keys = set(keys).difference(set(required + optional))
            raise AssertionError("found unexpected keys: %s" %
                                 list(extra_keys))


class TestResponse(requests.Response):
    """
    Class used to wrap requests.Response and provide some
    convenience to initialize with a dict
    """

    def __init__(self, data):
        self._text = None
        super(TestResponse, self)
        if isinstance(data, dict):
            self.status_code = data.get('status_code', None)
            self.headers = data.get('headers',
                                    {"Content-Type": "application/json"})
            # Fake the text attribute to streamline Response creation
            self._text = data.get('text', None)
        else:
            self.status_code = data

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    @property
    def text(self):
        return self._text


class FakeHttpClient(base_client.HttpClient):

    def __init__(self, *args, **kwargs):
        super(FakeHttpClient, self).__init__(
            username='username',
            password='password',
            tenant_id='tenant_id',
            tenant_name='tenant_name',
            auth_url='auth_url',
            endpoint='endpoint',
            token='token',
            region_name='name')

        self.callstack = []

    def assert_called(self, method, url, body=None, pos=-1):
        """
        Assert than an API method was just called.
        """
        expected = (method, url)
        called = self.callstack[pos][0:2]

        assert self.callstack, \
            "Expected %s %s but no calls were made." % expected

        assert expected == called, 'Expected %s %s; got %s %s' % \
            (expected + called)

        if body is not None:
            if self.callstack[pos][2] != body:
                raise AssertionError('%r != %r' %
                                     (self.callstack[pos][2], body))

    def assert_called_anytime(self, method, url, body=None):
        """
        Assert than an API method was called anytime in the test.
        """
        expected = (method, url)

        assert self.callstack, \
            "Expected %s %s but no calls were made." % expected

        found = False
        for entry in self.callstack:
            if expected == entry[0:2]:
                found = True
                break

        assert found, 'Expected %s %s; got %s' % \
            (expected, self.callstack)
        if body is not None:
            try:
                assert entry[2] == body
            except AssertionError:
                print(entry[2])
                print("!=")
                print(body)
                raise

        self.callstack = []

    def clear_callstack(self):
        self.callstack = []

    def authenticate(self):
        pass

    def cs_request(self, client, method, url, **kwargs):
        # Check that certain things are called correctly
        if method in ['GET', 'DELETE']:
            assert 'body' not in kwargs
        elif method == 'PUT':
            assert 'body' in kwargs

        # Call the method
        args = urlparse.parse_qsl(urlparse.urlparse(url)[4])
        kwargs.update(args)
        munged_url = url.rsplit('?', 1)[0]
        munged_url = munged_url.strip('/').replace('/', '_').replace('.', '_')
        munged_url = munged_url.replace('-', '_')

        callback = "%s_%s" % (method.lower(), munged_url)

        if not hasattr(self, callback):
            raise AssertionError('Called unknown API method: %s %s, '
                                 'expected fakes method name: %s' %
                                 (method, url, callback))

        # Note the call
        self.callstack.append((method, url, kwargs.get('body', None)))

        status, headers, body = getattr(self, callback)(**kwargs)
        r = TestResponse({
            "status_code": status,
            "text": body,
            "headers": headers,
        })
        return r, body
