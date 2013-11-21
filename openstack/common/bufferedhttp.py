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

from httplib import CONTINUE, HTTPConnection, \
    HTTPSConnection, HTTPMessage, HTTPResponse, _UNKNOWN


class BufferedHTTPResponse(HTTPResponse):
    """HTTPResponse class that buffers reading of headers"""

    def __init__(self, sock, debuglevel=0, strict=0,
                 method=None):          # pragma: no cover
        self.sock = sock
        # sock is an eventlet.greenio.GreenSocket
        # sock.fd is a socket._socketobject
        # sock.fd._sock is a socket._socket object, which is what we want.
        self.fp = sock.makefile('rb')
        self.debuglevel = debuglevel
        self.strict = strict
        self._method = method

        self.msg = None

        # from the Status-Line of the response
        self.version = _UNKNOWN         # HTTP-Version
        self.status = _UNKNOWN          # Status-Code
        self.reason = _UNKNOWN          # Reason-Phrase

        self.chunked = _UNKNOWN         # is "chunked" being used?
        self.chunk_left = _UNKNOWN      # bytes left to read in current chunk
        self.length = _UNKNOWN          # number of bytes left in response
        self.will_close = _UNKNOWN      # conn will close at end of response

    def expect_response(self):
        if self.fp:
            self.fp.close()
            self.fp = None
        self.fp = self.sock.makefile('rb', 0)
        version, status, reason = self._read_status()
        if status != CONTINUE:
            self._read_status = lambda: (version, status, reason)
            self.begin()
        else:
            self.status = status
            self.reason = reason.strip()
            self.version = 11
            self.msg = HTTPMessage(self.fp, 0)
            self.msg.fp = None


class BufferedHTTPConnection(HTTPConnection):
    """HTTPConnection class that uses BufferedHTTPResponse"""
    response_class = BufferedHTTPResponse

    def getexpect(self):
        response = BufferedHTTPResponse(self.sock, strict=self.strict,
                                        method=self._method)
        response.expect_response()
        return response


class BufferedHTTPSConnection(HTTPSConnection):
    """HTTPConnection class that uses BufferedHTTPResponse"""
    response_class = BufferedHTTPResponse

    def getexpect(self):
        response = BufferedHTTPResponse(self.sock, strict=self.strict,
                                        method=self._method)
        response.expect_response()
        return response
