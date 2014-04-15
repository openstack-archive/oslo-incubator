# Copyright 2014 Rackspace Hosting
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
from oslotest import base as test_base

from openstack.common import request_utils


class RequestUtilsTestCase(test_base.BaseTestCase):
    def setUp(self):
        super(RequestUtilsTestCase, self).setUp()
        self.notifier = mock.MagicMock()

    def test_happy_day(self):
        with mock.patch('openstack.common.request_utils.LOG') as mylog:
            request_utils.link_request_ids(None, "source_id",
                                           target_id="target_id",
                                           stage="start",
                                           target_name="network service",
                                           notifier=self.notifier)
            self.assertTrue(mylog.info.called)
            self.assertEqual(mylog.info.call_args, mock.call(
                u"Request ID Link: request.link.start 'source_id' -> "
                "Target='network service' TargetId=target_id "))

            payload = {"source_request_id": "source_id",
                       "target_request_id": "target_id",
                       "target_name": "network service",
                       "stage": "start"}
            self.assertEqual(self.notifier.info.call_args,
                             mock.call(None, "request.link.start", payload))

    def test_no_notifier(self):
        with mock.patch('openstack.common.request_utils.LOG') as mylog:
            request_utils.link_request_ids(None, "source_id",
                                           target_id="target_id",
                                           stage="start",
                                           target_name="network service")
            self.assertTrue(mylog.info.called)
            self.assertEqual(mylog.info.call_args, mock.call(
                u"Request ID Link: request.link.start 'source_id' -> "
                "Target='network service' TargetId=target_id "))

            self.assertFalse(self.notifier.info.called)

    def test_log_no_target_id(self):
        with mock.patch('openstack.common.request_utils.LOG') as mylog:
            request_utils.link_request_ids(None, "source_id",
                                           stage="start",
                                           target_name="network service")
            self.assertTrue(mylog.info.called)
            self.assertEqual(mylog.info.call_args, mock.call(
                u"Request ID Link: request.link.start 'source_id' -> "
                "Target='network service' "))

            self.assertFalse(self.notifier.info.called)

    def test_log_no_target_name(self):
        with mock.patch('openstack.common.request_utils.LOG') as mylog:
            request_utils.link_request_ids(None, "source_id",
                                           stage="start")
            self.assertTrue(mylog.info.called)
            self.assertEqual(mylog.info.call_args, mock.call(
                u"Request ID Link: request.link.start 'source_id'"))

    def test_log_no_stage(self):
        with mock.patch('openstack.common.request_utils.LOG') as mylog:
            request_utils.link_request_ids(None, "source_id")
            self.assertTrue(mylog.info.called)
            self.assertEqual(mylog.info.call_args, mock.call(
                u"Request ID Link: request.link 'source_id'"))
