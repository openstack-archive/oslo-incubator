# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
# All Rights Reserved.
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

from openstack.common.middleware import cors
from tests import utils

import webob


class FakeApp(object):
    def __call__(self, env, start_response):
        start_response('200 OK', [('X-Testme', 'ok')])
        return ['boring response']


class CorsMiddlewareTest(utils.BaseTestCase):

    def test_add_headers(self):
        # Get factory without config, so we'll get the defaults.
        factory = cors.filter_factory({})

        app = FakeApp()
        request = webob.Request({})

        mid = factory(app)
        response = mid(request)

        self.assertEqual(response.headers['x-testme'], 'ok')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(
            response.headers['access-control-allow-origin'],
            '*')
        self.assertEqual(
            response.headers['access-control-max-age'], '3600')
        self.assertEqual(
            response.headers['access-control-allow-methods'],
            'GET, POST, PUT, DELETE, OPTIONS')
        self.assertEqual(
            response.headers['access-control-allow-headers'],
            'Origin, Content-type, Accept, X-Auth-Token')
        self.assertEqual(
            response.headers['access-control-allow-credentials'],
            'false')
        self.assertEqual(
            response.headers['access-control-expose-headers'],
            'etag, x-timestamp, x-trans-id, vary')

    def test_deny_origin(self):
        # Get factory without config, so we'll get the defaults.
        factory = cors.filter_factory({}, allow_origin='http://foo')

        app = FakeApp()
        request = webob.Request({})
        request.headers['Origin'] = 'http://notfoo'

        mid = factory(app)
        response = mid(request)
        self.assertEqual(response.status, '401 Unauthorized')
        self.assertNotIn('x-testme', request.headers)

    def test_allow_origin(self):
        # Get factory without config, so we'll get the defaults.
        factory = cors.filter_factory({}, allow_origin='http://foo')

        app = FakeApp()
        request = webob.Request({})
        request.headers['Origin'] = 'http://foo'

        mid = factory(app)
        response = mid(request)
        self.assertEqual(response.headers['x-testme'], 'ok')
        self.assertEqual(response.status, '200 OK')

    def test_deny_method(self):
        # Get factory without config, so we'll get the defaults.
        factory = cors.filter_factory({}, allow_method='POST')

        app = FakeApp()
        request = webob.Request({"REQUEST_METHOD": "PUT"})
        request.headers['Origin'] = 'http://foo'

        mid = factory(app)
        response = mid(request)
        self.assertEqual(response.status, '401 Unauthorized')
        #self.assertNotIn('x-testme', request.headers)

    def test_allow_method(self):
        # Get factory without config, so we'll get the defaults.
        factory = cors.filter_factory({}, allow_method='POST')

        app = FakeApp()
        request = webob.Request({"REQUEST_METHOD": "POST"})
        request.headers['Origin'] = 'http://foo'

        mid = factory(app)
        response = mid(request)
        self.assertEqual(response.headers['x-testme'], 'ok')
        self.assertEqual(response.status, '200 OK')

    def test_preflight(self):
        # Get factory without config, so we'll get the defaults.
        factory = cors.filter_factory({}, hijack_options=True)

        app = FakeApp()
        request = webob.Request({'REQUEST_METHOD': 'OPTIONS'})
        request.headers['Origin'] = 'http://foo'

        mid = factory(app)
        response = mid(request)
        self.assertEqual(response.status, '200 OK')
        self.assertNotIn('x-testme', request.headers)
        self.assertEqual(
            response.headers['access-control-allow-origin'],
            '*')
        self.assertEqual(response.headers['access-control-max-age'], '3600')
        self.assertEqual(
            response.headers['access-control-allow-methods'],
            'GET, POST, PUT, DELETE, OPTIONS')
        self.assertEqual(
            response.headers['access-control-allow-headers'],
            'Origin, Content-type, Accept, X-Auth-Token')
        self.assertEqual(
            response.headers['access-control-allow-credentials'],
            'false')
