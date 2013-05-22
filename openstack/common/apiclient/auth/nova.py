# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack Foundation
# Copyright 2013 Spanish National Research Council.
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

# E0202: An attribute inherited from %s hide this method
# pylint: disable=E0202

import logging

from openstack.common.apiclient.auth import base
from openstack.common.apiclient import exceptions


logger = logging.getLogger(__name__)


class NovaLegacyAuthPlugin(base.BaseAuthPlugin):
    auth_system = "nova"
    opt_names = [
        "username",
        "password",
        "project_id",
        "auth_url",
    ]

    def authenticate(self, http_client):
        headers = {"X-Auth-User": self.opts["username"],
                   "X-Auth-Key": self.opts["password"]}
        if self.opts.get("project_id"):
            headers["X-Auth-Project-Id"] = self.opts.get("project_id")

        resp = http_client.request(
            "GET", self.opts["auth_url"],
            headers=headers, allow_redirects=True)
        try:
            endpoint = resp.headers["X-Server-Management-Url"].rstrip("/")
            token = resp.headers["X-Auth-Token"]
        except (KeyError, TypeError):
            raise exceptions.AuthorizationFailure()
        http_client.token = token
        # set endpoint for compute if it exists
        try:
            http_client.compute.endpoint = endpoint
        except AttributeError:
            pass
