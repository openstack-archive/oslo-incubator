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

import mock
import requests

try:
    import json
except ImportError:
    import simplejson as json

from openstack.common.apiclient.auth import keystone
from openstack.common.apiclient import client
from openstack.common.apiclient import exceptions
from openstack.common.apiclient import fake_client

from tests import utils


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
                auth = keystone.KeystoneV2AuthPlugin(**kwargs)
                http_client.auth_plugin = auth
                http_client.authenticate()
                requests.Session.request.assert_called_with(
                    "POST",
                    "auth_url/tokens",
                    headers=mock.ANY,
                    allow_redirects=True,
                    data=json.dumps(test["data"]),
                    verify=mock.ANY)

            auth = keystone.KeystoneV2AuthPlugin(
                password="password",
                tenant_name="tenant_name",
                auth_url="auth_url")
            http_client.auth_plugin = auth
            self.assertRaises(exceptions.AuthPluginOptionsMissing,
                              http_client.authenticate)
