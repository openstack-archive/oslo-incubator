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

from openstack.common.apiclient.auth import nova
from openstack.common.apiclient import client
from openstack.common.apiclient import fake_client

from tests import utils


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
            auth = nova.NovaLegacyAuthPlugin(
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
