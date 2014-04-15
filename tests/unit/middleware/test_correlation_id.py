# Copyright (c) 2013 Rackspace Hosting
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

import uuid

import mock
from oslotest import base as test_base

from openstack.common.fixture import moxstubout
from openstack.common.middleware import correlation_id


class CorrelationIdMiddlewareTest(test_base.BaseTestCase):

    def setUp(self):
        super(CorrelationIdMiddlewareTest, self).setUp()
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs

    def test_process_request(self):
        app = mock.Mock()
        req = mock.Mock()
        req.headers = {}

        mock_uuid4 = mock.Mock()
        mock_uuid4.return_value = "fake_uuid"
        self.stubs.Set(uuid, 'uuid4', mock_uuid4)

        middleware = correlation_id.CorrelationIdMiddleware(app)
        middleware(req)

        self.assertEqual(req.headers.get("X_CORRELATION_ID"), "fake_uuid")

    def test_process_request_should_not_regenerate_correlation_id(self):
        app = mock.Mock()
        req = mock.Mock()
        req.headers = {"X_CORRELATION_ID": "correlation_id"}

        middleware = correlation_id.CorrelationIdMiddleware(app)
        middleware(req)

        self.assertEqual(req.headers.get("X_CORRELATION_ID"), "correlation_id")
