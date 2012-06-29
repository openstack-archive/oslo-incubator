# Copyright 2011 OpenStack LLC.
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

from openstack.common import log as logging
from openstack.common.notifier import api
from openstack.common.notifier import list_notifier
from openstack.common.notifier import log_notifier
from openstack.common.notifier import no_op_notifier
from tests import utils as test_utils


class SimpleNotifier(object):
    def __init__(self):
        self.notified = False

    def notify(self, *args):
        self.notified = True


class NotifierListTestCase(test_utils.BaseTestCase):
    """Test case for notifications"""

    def setUp(self):
        super(NotifierListTestCase, self).setUp()
        list_notifier._reset_drivers()
        # Mock log to add one to exception_count when log.exception is called

        def mock_exception(cls, *args):
            self.exception_count += 1

        self.exception_count = 0
        list_notifier_log = logging.getLogger(
            'openstack.common.notifier.list_notifier')
        self.stubs.Set(list_notifier_log, "exception", mock_exception)
        # Mock no_op notifier to add one to notify_count when called.

        def mock_notify(cls, *args):
            self.notify_count += 1

        self.notify_count = 0
        self.stubs.Set(no_op_notifier, 'notify', mock_notify)
        # Mock log_notifier to raise RuntimeError when called.

        def mock_notify2(cls, *args):
            raise RuntimeError("Bad notifier.")

        self.stubs.Set(log_notifier, 'notify', mock_notify2)

    def tearDown(self):
        list_notifier._reset_drivers()
        super(NotifierListTestCase, self).tearDown()

    def test_send_notifications_successfully(self):
        self.config(notification_driver='openstack.common.'
                                        'notifier.list_notifier',
                    list_notifier_drivers=[
                        'openstack.common.notifier.no_op_notifier',
                        'openstack.common.notifier.no_op_notifier'])
        api.notify('contextarg', 'publisher_id', 'event_type',
                   api.WARN, dict(a=3))
        self.assertEqual(self.notify_count, 2)
        self.assertEqual(self.exception_count, 0)

    def test_send_notifications_with_errors(self):

        self.config(notification_driver='openstack.common.'
                                        'notifier.list_notifier',
                    list_notifier_drivers=[
                        'openstack.common.notifier.no_op_notifier',
                        'openstack.common.notifier.log_notifier'])
        api.notify('contextarg', 'publisher_id',
                   'event_type', api.WARN, dict(a=3))
        self.assertEqual(self.notify_count, 1)
        self.assertEqual(self.exception_count, 1)

    def test_when_driver_fails_to_import(self):
        self.config(notification_driver='openstack.common.'
                                        'notifier.list_notifier',
                    list_notifier_drivers=[
                        'openstack.common.notifier.no_op_notifier',
                        'openstack.common.notifier.logo_notifier',
                        'fdsjgsdfhjkhgsfkj'])
        api.notify('contextarg', 'publisher_id',
                   'event_type', api.WARN, dict(a=3))
        self.assertEqual(self.exception_count, 2)
        self.assertEqual(self.notify_count, 1)

    def test_adding_and_removing_notifier_object(self):
        self.notifier_object = SimpleNotifier()
        self.config(notification_driver='openstack.common.'
                                        'notifier.list_notifier',
                    list_notifier_drivers=[
                        'openstack.common.notifier.no_op_notifier'])

        list_notifier.add_driver(self.notifier_object)
        api.notify(None, 'publisher_id', 'event_type',
                   api.WARN, dict(a=3))
        self.assertEqual(self.notify_count, 1)
        self.assertTrue(self.notifier_object.notified)

        self.notifier_object.notified = False
        list_notifier.remove_driver(self.notifier_object)

        api.notify(None, 'publisher_id', 'event_type',
                   api.WARN, dict(a=3))
        self.assertEqual(self.notify_count, 2)
        self.assertFalse(self.notifier_object.notified)

    def test_adding_and_removing_notifier_module(self):
        self.config(notification_driver='openstack.common.'
                                        'notifier.list_notifier',
                    list_notifier_drivers=[])

        list_notifier.add_driver('openstack.common.notifier.no_op_notifier')
        api.notify(None, 'publisher_id', 'event_type',
                   api.WARN, dict(a=3))
        self.assertEqual(self.notify_count, 1)

        list_notifier.remove_driver('openstack.common.notifier.no_op_notifier')

        api.notify(None, 'publisher_id', 'event_type',
                   api.WARN, dict(a=3))
        self.assertEqual(self.notify_count, 1)
