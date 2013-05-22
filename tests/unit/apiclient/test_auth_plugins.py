# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import argparse

import fixtures
import mock
import pkg_resources
import requests

try:
    import json
except ImportError:
    import simplejson as json

from openstack.common.apiclient import auth_plugin
from openstack.common.apiclient import client
from openstack.common.apiclient import exceptions
from openstack.common.apiclient import fake_client

from tests import utils


TEST_REQUEST_BASE = {
    'verify': True,
}


def mock_http_request(resp=None):
    """Mock an HTTP Request."""
    if not resp:
        resp = {
            "access": {
                "token": {
                    "expires": "12345",
                    "id": "FAKE_ID",
                    "tenant": {
                        "id": "FAKE_TENANT_ID",
                    }
                },
                "serviceCatalog": [
                    {
                        "type": "compute",
                        "endpoints": [
                            {
                                "region": "RegionOne",
                                "adminURL": "http://localhost:8774/v1.1",
                                "internalURL": "http://localhost:8774/v1.1",
                                "publicURL": "http://localhost:8774/v1.1/",
                            },
                        ],
                    },
                ],
            },
        }

    auth_response = fake_client.TestResponse({
        "status_code": 200,
        "text": json.dumps(resp),
    })
    return mock.Mock(return_value=(auth_response))


def requested_headers(cs):
    """Return requested passed headers."""
    return {
        'User-Agent': cs.user_agent,
        'Content-Type': 'application/json',
    }


class GlobalFunctionsTest(utils.BaseTestCase):

    def test_load_auth_system_opts(self):
        self.useFixture(fixtures.MonkeyPatch(
            "os.environ",
            {"NOVA_PROJECT_ID": "fake-project",
            "OS_USERNAME": "fake-username"}))
        parser = argparse.ArgumentParser()
        auth_plugin.discover_auth_systems()
        auth_plugin.load_auth_system_opts(parser, "nova")
        options = parser.parse_args(
            ["--os-auth-url=fake-url", "--os_auth_system=fake-system"])
        self.assertTrue(options.os_tenant_name, "fake-project")
        self.assertTrue(options.os_username, "fake-username")
        self.assertTrue(options.os_auth_url, "fake-url")
        self.assertTrue(options.os_auth_system, "fake-system")


class DeprecatedAuthPluginTest(utils.BaseTestCase):
    def test_auth_system_success(self):
        fake_auth_url = "auth_url/v2.0"

        class MockEntrypoint(pkg_resources.EntryPoint):
            def load(self):
                if self.name.endswith("authenticate"):
                    return self.authenticate
                else:
                    return self.auth_url

            def auth_url(self):
                return fake_auth_url

            def authenticate(self, cls, auth_url):
                cls.request(
                    "POST", auth_url + "/tokens",
                    json={"fake": "me"}, allow_redirects=True)

        def mock_iter_entry_points(_type, name):
            if _type.startswith('openstack.common.apiclient.'):
                return [MockEntrypoint(_type, "fake", ["fake"])]
            else:
                return []

        mock_request = mock_http_request()

        @mock.patch.object(pkg_resources, "iter_entry_points",
                           mock_iter_entry_points)
        @mock.patch.object(requests.Session, "request", mock_request)
        def test_auth_call():
            plugin = auth_plugin.DeprecatedAuthPlugin("fake")
            cs = client.HttpClient(auth_plugin=plugin)
            cs.authenticate()

            headers = requested_headers(cs)

            mock_request.assert_called_with(
                "POST",
                fake_auth_url + "/tokens",
                headers=headers,
                data='{"fake": "me"}',
                allow_redirects=True,
                **TEST_REQUEST_BASE)

        test_auth_call()

    def test_auth_system_not_exists(self):
        def mock_iter_entry_points(_t, name=None):
            return [pkg_resources.EntryPoint("fake", "fake", ["fake"])]

        mock_request = mock_http_request()

        @mock.patch.object(pkg_resources, "iter_entry_points",
                           mock_iter_entry_points)
        @mock.patch.object(requests.Session, "request", mock_request)
        def test_auth_call():
            auth_plugin.discover_auth_systems()
            plugin = auth_plugin.DeprecatedAuthPlugin("notexists")
            cs = client.HttpClient(auth_plugin=plugin)
            self.assertRaises(exceptions.AuthSystemNotFound,
                              cs.authenticate)

        test_auth_call()


class AuthPluginTest(utils.BaseTestCase):
    @mock.patch.object(requests.Session, "request")
    @mock.patch.object(pkg_resources, "iter_entry_points")
    def test_auth_system_success(self, mock_iter_entry_points, mock_request):
        """Test that we can authenticate using the auth system."""
        class MockEntrypoint(pkg_resources.EntryPoint):
            def load(self):
                return FakePlugin

        class FakePlugin(auth_plugin.BaseAuthPlugin):
            def authenticate(self, cls):
                cls.request(
                    "POST", "http://auth/tokens",
                    json={"fake": "me"}, allow_redirects=True)

        mock_iter_entry_points.side_effect = lambda _t: [
            MockEntrypoint("fake", "fake", ["FakePlugin"])]

        mock_request.side_effect = mock_http_request()

        auth_plugin.discover_auth_systems()
        plugin = auth_plugin.load_plugin("fake")
        cs = client.HttpClient(auth_plugin=plugin)
        cs.authenticate()

        headers = requested_headers(cs)

        mock_request.assert_called_with(
            "POST",
            "http://auth/tokens",
            headers=headers,
            data='{"fake": "me"}',
            allow_redirects=True,
            **TEST_REQUEST_BASE)

    @mock.patch.object(pkg_resources, "iter_entry_points")
    def test_discover_auth_system_options(self, mock_iter_entry_points):
        """Test that we can load the auth system options."""
        class FakePlugin(auth_plugin.BaseAuthPlugin):
            @staticmethod
            def add_opts(parser):
                parser.add_argument('--auth_system_opt',
                                    default=False,
                                    action='store_true',
                                    help="Fake option")
                return parser

            def authenticate(self, client):
                pass

        class MockEntrypoint(pkg_resources.EntryPoint):
            def load(self):
                return FakePlugin

        mock_iter_entry_points.side_effect = lambda _t: [
            MockEntrypoint("fake", "fake", ["FakePlugin"])]

        parser = argparse.ArgumentParser()
        auth_plugin.discover_auth_systems()
        auth_plugin.load_auth_system_opts(parser)
        opts, args = parser.parse_known_args(['--auth_system_opt'])

        self.assertTrue(opts.auth_system_opt)

    @mock.patch.object(pkg_resources, "iter_entry_points")
    def test_parse_auth_system_options(self, mock_iter_entry_points):
        """Test that we can parse the auth system options."""
        class MockEntrypoint(pkg_resources.EntryPoint):
            def load(self):
                return FakePlugin

        class FakePlugin(auth_plugin.BaseAuthPlugin):
            def __init__(self):
                self.opts = {"fake_argument": True}

            def parse_opts(self, args):
                return self.opts

            def authenticate(self, client):
                pass

        mock_iter_entry_points.side_effect = lambda _t: [
            MockEntrypoint("fake", "fake", ["FakePlugin"])]

        auth_plugin.discover_auth_systems()
        plugin = auth_plugin.load_plugin("fake")

        plugin.parse_opts([])
        self.assertIn("fake_argument", plugin.opts)


class KeystoneV2AuthPluginTest(utils.BaseTestCase):

    def test_authenticate(self):
        http_client = client.HttpClient(None)
        mock_request = mock.Mock()
        mock_request.return_value = fake_client.TestResponse({
            "status_code": 200,
            "text": {"access": {}}
        })
        successful_tests = [
            {
                "kwargs": ["tenant_id", "token", "auth_url"],
                "data": {
                    "auth": {
                        "token": {"id": "token"}, "tenantId": "tenant_id"
                    },
                },
            },
            {
                "kwargs": ["tenant_name", "token", "auth_url"],
                "data": {
                    "auth": {
                        "token": {"id": "token"}, "tenantName": "tenant_name"
                    },
                },
            },
            {
                "kwargs": ["username", "password", "tenant_name", "auth_url"],
                "data": {
                    "auth": {
                        "tenantName": "tenant_name",
                        "passwordCredentials": {
                            "username": "username",
                            "password": "password",
                        },
                    },
                },
            },
        ]
        with mock.patch("requests.Session.request", mock_request):
            for test in successful_tests:
                kwargs = dict((k, k) for k in test["kwargs"])
                auth = auth_plugin.KeystoneV2AuthPlugin(**kwargs)
                http_client.auth_plugin = auth
                http_client.authenticate()
                requests.Session.request.assert_called_with(
                    "POST",
                    "auth_url/tokens",
                    headers=mock.ANY,
                    allow_redirects=True,
                    data=json.dumps(test["data"]),
                    verify=mock.ANY)

            auth = auth_plugin.KeystoneV2AuthPlugin(
                password="password",
                tenant_name="tenant_name",
                auth_url="auth_url")
            http_client.auth_plugin = auth
            self.assertRaises(exceptions.AuthPluginOptionsMissing,
                              http_client.authenticate)


class NovaLegacyAuthPluginTest(utils.BaseTestCase):

    def test_authenticate(self):
        http_client = client.HttpClient(None)
        mock_request = mock.Mock()
        mock_request.return_value = fake_client.TestResponse({
            "status_code": 200,
            "text": {"access": {}},
            "headers": {
                "X-Auth-Token": "token",
                "X-Server-Management-Url": "url",
            },
        })
        with mock.patch("requests.Session.request", mock_request):
            auth = auth_plugin.NovaLegacyAuthPlugin(
                username="username",
                password="password",
                project_id="project_id",
                auth_url="auth_url")
            http_client.auth_plugin = auth
            http_client.authenticate()
            requests.Session.request.assert_called_with(
                "GET",
                "auth_url",
                headers={
                    "X-Auth-Project-Id": "project_id",
                    "X-Auth-Key": "password",
                    "X-Auth-User": "username",
                    "User-Agent": http_client.user_agent
                },
                allow_redirects=True,
                verify=True)
