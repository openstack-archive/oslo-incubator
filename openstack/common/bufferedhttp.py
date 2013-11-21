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


class BufferedHTTPResponse(http_client.HTTPResponse):
    """HTTPResponse class that buffers reading of headers
        sock is an eventlet.greenio.GreenSocket.
    """

    def __init__(self, sock, debuglevel=0, strict=0,
                 method=None):          # pragma: no cover
        self.sock = sock
        self.fp = sock.makefile('rb')
        self.debuglevel = debuglevel
        self.strict = strict
        self._method = method

        self.msg = None

        # from the Status-Line of the response
        self.version = http_client._UNKNOWN
        self.status = http_client._UNKNOWN
        self.reason = http_client._UNKNOWN

        self.chunked = http_client._UNKNOWN
        self.chunk_left = http_client._UNKNOWN
        self.length = http_client._UNKNOWN
        self.will_close = http_client._UNKNOWN

    def expect_response(self):
        if self.fp:
            self.fp.close()
            self.fp = None
        self.fp = self.sock.makefile('rb', 0)
        version, status, reason = self._read_status()
        if status != http_client.CONTINUE:
            self._read_status = lambda: (version, status, reason)
            self.begin()
        else:
            self.status = status
            self.reason = reason.strip()
            self.version = 11
            self.msg = http_client.HTTPMessage(self.fp, 0)
            self.msg.fp = None


class BufferedHTTPConnection(http_client.HTTPConnection):
    """HTTPConnection class that uses BufferedHTTPResponse."""
    response_class = BufferedHTTPResponse

    def getexpect(self):
        response = BufferedHTTPResponse(self.sock, strict=self.strict,
                                        method=self._method)
        response.expect_response()
        return response


class BufferedHTTPSConnection(http_client.HTTPSConnection):
    """HTTPSConnection class that uses BufferedHTTPResponse."""
    response_class = BufferedHTTPResponse

    def getexpect(self):
        response = BufferedHTTPResponse(self.sock, strict=self.strict,
                                        method=self._method)
        response.expect_response()
        return response
