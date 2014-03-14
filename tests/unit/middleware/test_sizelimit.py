# Copyright (c) 2012 Red Hat, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import six
import webob

from openstack.common.fixture import config
from openstack.common.middleware import sizelimit
from openstack.common import test


class TestLimitingReader(test.BaseTestCase):

    def test_limiting_reader(self):
        BYTES = 1024
        bytes_read = 0
        data = six.StringIO("*" * BYTES)
        for chunk in sizelimit.LimitingReader(data, BYTES):
            bytes_read += len(chunk)

        self.assertEqual(bytes_read, BYTES)

        bytes_read = 0
        data = six.StringIO("*" * BYTES)
        reader = sizelimit.LimitingReader(data, BYTES)
        byte = reader.read(1)
        while len(byte) != 0:
            bytes_read += 1
            byte = reader.read(1)

        self.assertEqual(bytes_read, BYTES)

    def test_limiting_reader_fails(self):
        BYTES = 1024

        def _consume_all_iter():
            bytes_read = 0
            data = six.StringIO("*" * BYTES)
            for chunk in sizelimit.LimitingReader(data, BYTES - 1):
                bytes_read += len(chunk)

        self.assertRaises(webob.exc.HTTPRequestEntityTooLarge,
                          _consume_all_iter)

        def _consume_all_read():
            bytes_read = 0
            data = six.StringIO("*" * BYTES)
            reader = sizelimit.LimitingReader(data, BYTES - 1)
            byte = reader.read(1)
            while len(byte) != 0:
                bytes_read += 1
                byte = reader.read(1)

        self.assertRaises(webob.exc.HTTPRequestEntityTooLarge,
                          _consume_all_read)


class TestRequestBodySizeLimiter(test.BaseTestCase):

    def setUp(self):
        super(TestRequestBodySizeLimiter, self).setUp()
        self.MAX_REQUEST_BODY_SIZE = \
            self.useFixture(config.Config()).conf.max_request_body_size

        @webob.dec.wsgify()
        def fake_app(req):
            return webob.Response(req.body)

        self.middleware = sizelimit.RequestBodySizeLimiter(fake_app)
        self.request = webob.Request.blank('/', method='POST')

    def test_content_length_acceptable(self):
        self.request.headers['Content-Length'] = self.MAX_REQUEST_BODY_SIZE
        self.request.body = b"0" * self.MAX_REQUEST_BODY_SIZE
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status_int, 200)

    def test_content_length_too_large(self):
        self.request.headers['Content-Length'] = self.MAX_REQUEST_BODY_SIZE + 1
        self.request.body = b"0" * (self.MAX_REQUEST_BODY_SIZE + 1)
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status_int, 413)

    def test_request_too_large_no_content_length(self):
        self.request.body = b"0" * (self.MAX_REQUEST_BODY_SIZE + 1)
        self.request.headers['Content-Length'] = None
        response = self.request.get_response(self.middleware)
        self.assertEqual(response.status_int, 413)
