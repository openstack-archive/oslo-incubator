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

import logging

from openstack.common.apiclient.auth import base
from openstack.common.apiclient import exceptions


logger = logging.getLogger(__name__)


class EndpointTokenAuthPlugin(base.BaseAuthPlugin):
    auth_system = "endpoint-token"
    opt_names = [
        "token",
        "endpoint",
    ]

    def authenticate(self, http_client):
        # we can work without an endpoint (`BaseClient.endpoint` can be used),
        # but a token is required
        if not self.opts.get("token"):
            raise exceptions.AuthPluginOptionsMissing(["token"])
        http_client.token = self.opts["token"]
        http_client.endpoint = self.opts["endpoint"]
