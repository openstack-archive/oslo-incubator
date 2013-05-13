# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation.
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

from tests import utils
from openstack.common import uuidutils, correlation_id


class CorrelationIdMiddlewareTest(utils.BaseTestCase):

    def test_process_request(self):
        opts = {}
        app = mock.Mock()
        req = mock.Mock()
        req.headers = {}
        mock_generate_uuid = mock.Mock()
        mock_generate_uuid.return_value = "fake_uuid"
        uuidutils.generate_uuid = mock_generate_uuid

        middleware = correlation_id.CorrelationIdMiddleware(app, opts)
        middleware(req)

        self.assertEquals(req.headers.get("X_CORRELATION_ID"), "fake_uuid")

    def test_process_request_should_not_regenerate_correlation_id(self):
        opts = {}
        app = mock.Mock()
        req = mock.Mock()
        req.headers = {"X_CORRELATION_ID": "correlation_id"}

        middleware = correlation_id.CorrelationIdMiddleware(app, opts)
        middleware(req)

        self.assertEquals(req.headers.get("X_CORRELATION_ID"),
                          "correlation_id")
