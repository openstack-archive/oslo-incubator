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
import requests
from stevedore import extension

try:
    import json
except ImportError:
    import simplejson as json

from openstack.common.apiclient import auth
from openstack.common.apiclient import client
from openstack.common.apiclient import fake_client
from openstack.common import test


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


class BaseFakePlugin(auth.BaseAuthPlugin):
    def _do_authenticate(self, http_client):
        pass

    def token_and_endpoint(self, endpoint_type, service_type):
        pass


class GlobalFunctionsTest(test.BaseTestCase):

    def test_load_auth_system_opts(self):
        self.useFixture(fixtures.MonkeyPatch(
            "os.environ",
            {"OS_TENANT_NAME": "fake-project",
            "OS_USERNAME": "fake-username"}))
        parser = argparse.ArgumentParser()
        auth.load_auth_system_opts(parser)
        options = parser.parse_args(
            ["--os-auth-url=fake-url", "--os_auth_system=fake-system"])
        self.assertEqual(options.os_tenant_name, "fake-project")
        self.assertEqual(options.os_username, "fake-username")
        self.assertEqual(options.os_auth_url, "fake-url")
        self.assertEqual(options.os_auth_system, "fake-system")


class MockEntrypoint(object):
    def __init__(self, name, plugin):
        self.name = name
        self.plugin = plugin


class AuthPluginTest(test.BaseTestCase):
    @mock.patch.object(requests.Session, "request")
    @mock.patch.object(extension.ExtensionManager, "map")
    def test_auth_system_success(self, mock_mgr_map, mock_request):
        """Test that we can authenticate using the auth system."""
        class FakePlugin(BaseFakePlugin):
            def authenticate(self, cls):
                cls.request(
                    "POST", "http://auth/tokens",
                    json={"fake": "me"}, allow_redirects=True)

        mock_mgr_map.side_effect = (
            lambda func: func(MockEntrypoint("fake", FakePlugin)))

        mock_request.side_effect = mock_http_request()

        auth.discover_auth_systems()
        plugin = auth.load_plugin("fake")
        cs = client.HTTPClient(auth_plugin=plugin)
        cs.authenticate()

        headers = requested_headers(cs)

        mock_request.assert_called_with(
            "POST",
            "http://auth/tokens",
            headers=headers,
            data='{"fake": "me"}',
            allow_redirects=True,
            **TEST_REQUEST_BASE)

    @mock.patch.object(extension.ExtensionManager, "map")
    def test_discover_auth_system_options(self, mock_mgr_map):
        """Test that we can load the auth system options."""
        class FakePlugin(BaseFakePlugin):
            @classmethod
            def add_opts(cls, parser):
                parser.add_argument('--auth_system_opt',
                                    default=False,
                                    action='store_true',
                                    help="Fake option")

        mock_mgr_map.side_effect = (
            lambda func: func(MockEntrypoint("fake", FakePlugin)))

        parser = argparse.ArgumentParser()
        auth.discover_auth_systems()
        auth.load_auth_system_opts(parser)
        opts, _args = parser.parse_known_args(['--auth_system_opt'])

        self.assertTrue(opts.auth_system_opt)

    @mock.patch.object(extension.ExtensionManager, "map")
    def test_parse_auth_system_options(self, mock_mgr_map):
        """Test that we can parse the auth system options."""
        class FakePlugin(BaseFakePlugin):
            opt_names = ["fake_argument"]

        mock_mgr_map.side_effect = (
            lambda func: func(MockEntrypoint("fake", FakePlugin)))

        auth.discover_auth_systems()
        plugin = auth.load_plugin("fake")

        plugin.parse_opts([])
        self.assertIn("fake_argument", plugin.opts)
