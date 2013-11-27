# -*- coding: utf-8 -*-
#
# Copyright 2012 OpenStack Foundation
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


import mock
import requests

from openstack.common.apiclient import auth
from openstack.common.apiclient import client
from openstack.common.apiclient import exceptions
from openstack.common.apiclient import fake_client
from openstack.common import test


class TestClient(client.BaseClient):
    service_type = "test"


class FakeAuthPlugin(auth.BaseAuthPlugin):
    auth_system = "fake"
    attempt = -1

    def _do_authenticate(self, http_client):
        pass

    def token_and_endpoint(self, endpoint_type, service_type):
        self.attempt = self.attempt + 1
        return ("token-%s" % self.attempt, "/endpoint-%s" % self.attempt)


class ClientTest(test.BaseTestCase):

    def test_client_with_timeout(self):
        http_client = client.HTTPClient(None, timeout=2)
        self.assertEqual(http_client.timeout, 2)
        mock_request = mock.Mock()
        mock_request.return_value = requests.Response()
        mock_request.return_value.status_code = 200
        with mock.patch("requests.Session.request", mock_request):
            http_client.request("GET", "/", json={"1": "2"})
            requests.Session.request.assert_called_with(
                "GET",
                "/",
                timeout=2,
                headers=mock.ANY,
                verify=mock.ANY,
                data=mock.ANY)

    def test_concat_url(self):
        self.assertEqual(client.HTTPClient.concat_url("/a", "/b"), "/a/b")
        self.assertEqual(client.HTTPClient.concat_url("/a", "b"), "/a/b")
        self.assertEqual(client.HTTPClient.concat_url("/a/", "/b"), "/a/b")

    def test_client_request(self):
        http_client = client.HTTPClient(FakeAuthPlugin())
        mock_request = mock.Mock()
        mock_request.return_value = requests.Response()
        mock_request.return_value.status_code = 200
        with mock.patch("requests.Session.request", mock_request):
            http_client.client_request(
                TestClient(http_client), "GET", "/resource", json={"1": "2"})
            requests.Session.request.assert_called_with(
                "GET",
                "/endpoint-0/resource",
                headers={
                    "User-Agent": http_client.user_agent,
                    "Content-Type": "application/json",
                    "X-Auth-Token": "token-0"
                },
                data='{"1": "2"}',
                verify=True)

    def test_client_request_reissue(self):
        reject_token = None

        def fake_request(method, url, **kwargs):
            if kwargs["headers"]["X-Auth-Token"] == reject_token:
                raise exceptions.Unauthorized(method=method, url=url)
            return "%s %s" % (method, url)

        http_client = client.HTTPClient(FakeAuthPlugin())
        test_client = TestClient(http_client)
        http_client.request = fake_request

        self.assertEqual(
            http_client.client_request(
                test_client, "GET", "/resource"),
            "GET /endpoint-0/resource")
        reject_token = "token-0"
        self.assertEqual(
            http_client.client_request(
                test_client, "GET", "/resource"),
            "GET /endpoint-1/resource")


class FakeClientTest(test.BaseTestCase):
    def test_fake_client_request(self):
        fixtures = {
            '/endpoint/resource': {
                'GET': (
                    {},
                    {'foo': u'bär'}
                )
            }
        }

        fake_http_client = fake_client.FakeHTTPClient(fixtures=fixtures)
        test_client = TestClient(fake_http_client)
        resp = test_client.get('/endpoint/resource')
        self.assertEqual(resp.status_code, 200)
        resp_data = resp.json()
        self.assertEqual(u'bär', resp_data['foo'])

    def test_fake_client_encode(self):
        fixtures = {
            '/endpoint/resource': {
                'GET': (
                    {},
                    {'foo': u'bär'}
                )
            }
        }

        def guess_json_utf(data):
            self.assertIsInstance(data, bytes)
            return 'utf-8'

        fake_http_client = fake_client.FakeHTTPClient(fixtures=fixtures)
        test_client = TestClient(fake_http_client)
        with mock.patch("requests.utils.guess_json_utf", guess_json_utf):
            resp = test_client.get('/endpoint/resource')
            self.assertEqual(resp.status_code, 200)


class FakeClient1(object):
    pass


class FakeClient21(object):
    pass


class GetClientClassTestCase(test.BaseTestCase):
    version_map = {
        "1": "%s.FakeClient1" % __name__,
        "2.1": "%s.FakeClient21" % __name__,
    }

    def test_get_int(self):
        self.assertEqual(
            client.BaseClient.get_class("fake", 1, self.version_map),
            FakeClient1)

    def test_get_str(self):
        self.assertEqual(
            client.BaseClient.get_class("fake", "2.1", self.version_map),
            FakeClient21)

    def test_unsupported_version(self):
        self.assertRaises(
            exceptions.UnsupportedVersion,
            client.BaseClient.get_class,
            "fake", "7", self.version_map)
