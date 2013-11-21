# Copyright 2013 RACKSPACE HOSTING
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from six.moves import http_client
from six.moves import StringIO

from testtools import testcase

from openstack.common import bufferedhttp

CONTINUE = 100


class FakeSocket:
    def __init__(self, text, fileclass=StringIO):
        self.text = text
        self.fileclass = fileclass
        self.data = ''

    def sendall(self, data):
        self.data += ''.join(data)

    def makefile(self, mode, bufsize=None):
        if mode != 'r' and mode != 'rb':
            raise http_client.UnimplementedFileMode()
        return self.fileclass(self.text)


class TestBufferedHTTP(testcase.TestCase):

    def test_getexpect(self):
        sock = FakeSocket('HTTP/1.1 100 CONTINUE')
        conn = bufferedhttp.BufferedHTTPConnection('example.com')
        conn.sock = sock
        response = conn.getexpect()
        self.assertIsNotNone(response.status)
        self.assertEqual(response.status, 100)

    def test_expect_response_continue(self):
        sock = FakeSocket('HTTP/1.1 100 CONTINUE')
        response = bufferedhttp.BufferedHTTPResponse(sock)
        response.expect_response()
        self.assertEqual(response.status, CONTINUE)

    def test_expect_response_not_continue(self):
        sock = FakeSocket('HTTP/1.1 401 UNAUTHORISED')
        response = bufferedhttp.BufferedHTTPResponse(sock)
        response.expect_response()
        self.assertIsNot(response.status, CONTINUE)
