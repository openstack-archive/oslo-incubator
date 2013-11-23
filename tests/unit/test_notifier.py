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

import socket

from openstack.common import context
from openstack.common.fixture import config
from openstack.common.fixture import moxstubout
from openstack.common import log
from openstack.common.notifier import api as notifier_api
from openstack.common.notifier import log_notifier
from openstack.common.notifier import no_op_notifier
from openstack.common import rpc
from openstack.common import test


ctxt = context.get_admin_context()
ctxt2 = context.get_admin_context()


class NotifierTestCase(test.BaseTestCase):
    """Test case for notifications."""
    def setUp(self):
        super(NotifierTestCase, self).setUp()
        notification_driver = [
            'openstack.common.notifier.no_op_notifier'
        ]
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        self.config = self.useFixture(config.Config()).config
        self.CONF = self.useFixture(config.Config()).conf
        self.config(notification_driver=notification_driver)
        self.config(default_publisher_id='publisher')
        self.addCleanup(notifier_api._reset_drivers)

    def test_send_notification(self):
        self.notify_called = False

        def mock_notify(cls, *args):
            self.notify_called = True

        self.stubs.Set(no_op_notifier, 'notify',
                       mock_notify)

        notifier_api.notify(ctxt, 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))
        self.assertEqual(self.notify_called, True)

    def test_verify_message_format(self):
        """A test to ensure changing the message format is prohibitively
        annoying.
        """

        def message_assert(context, message):
            fields = [('publisher_id', 'publisher_id'),
                      ('event_type', 'event_type'),
                      ('priority', 'WARN'),
                      ('payload', dict(a=3))]
            for k, v in fields:
                self.assertEqual(message[k], v)
            self.assertTrue(len(message['message_id']) > 0)
            self.assertTrue(len(message['timestamp']) > 0)
            self.assertEqual(context, ctxt)

        self.stubs.Set(no_op_notifier, 'notify',
                       message_assert)
        notifier_api.notify(ctxt, 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))

    def _test_rpc_notify(self, driver, envelope=False):
        self.stubs.Set(self.CONF, 'notification_driver', [driver])
        self.mock_notify = False
        self.envelope = False

        def mock_notify(cls, *args, **kwargs):
            self.mock_notify = True
            self.envelope = kwargs.get('envelope', False)

        self.stubs.Set(rpc, 'notify', mock_notify)
        notifier_api.notify(ctxt, 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(self.mock_notify, True)
        self.assertEqual(self.envelope, envelope)

    def test_rpc_notifier(self):
        self._test_rpc_notify('openstack.common.notifier.rpc_notifier')

    def test_rpc_notifier2(self):
        self._test_rpc_notify('openstack.common.notifier.rpc_notifier2', True)

    def test_invalid_priority(self):
        self.assertRaises(notifier_api.BadPriorityException,
                          notifier_api.notify, ctxt, 'publisher_id',
                          'event_type', 'not a priority', dict(a=3))

    def test_rpc_priority_queue(self):
        self.stubs.Set(self.CONF, 'notification_driver',
                       ['openstack.common.notifier.rpc_notifier'])
        self.stubs.Set(self.CONF, 'notification_topics',
                       ['testnotify', ])

        self.test_topic = None

        def mock_notify(context, topic, msg):
            self.test_topic = topic

        self.stubs.Set(rpc, 'notify', mock_notify)
        notifier_api.notify(ctxt, 'publisher_id',
                            'event_type', 'DEBUG', dict(a=3))
        self.assertEqual(self.test_topic, 'testnotify.debug')

    def test_error_notification(self):
        self.config(publish_errors=True,
                    use_stderr=False)

        def mock_notify(context, message):
            msgs.append(message)

        msgs = []
        self.stubs.Set(no_op_notifier, 'notify', mock_notify)

        LOG = log.getLogger('test_error_notification.common')
        log.setup('test_error_notification')

        LOG.error('foo')
        self.assertEqual(1, len(msgs))
        msg = msgs[0]
        self.assertEqual(msg['event_type'], 'error_notification')
        self.assertEqual(msg['priority'], 'ERROR')
        self.assertEqual(msg['payload']['error'], 'foo')

    def test_send_notification_by_decorator(self):
        self.notify_called = False

        def example_api(arg1, arg2):
            return arg1 + arg2

        example_api = notifier_api.notify_decorator(
            'example_api',
            example_api)

        def mock_notify(cls, *args):
            self.notify_called = True

        self.stubs.Set(no_op_notifier, 'notify',
                       mock_notify)

        self.assertEqual(3, example_api(1, 2))
        self.assertEqual(self.notify_called, True)

    def test_decorator_context(self):
        """Verify that the notify decorator can extract the 'context' arg."""
        self.notify_called = False
        self.context_arg = None

        def example_api(arg1, arg2, context):
            return arg1 + arg2

        def example_api2(arg1, arg2, **kw):
            return arg1 + arg2

        example_api = notifier_api.notify_decorator(
            'example_api',
            example_api)

        example_api2 = notifier_api.notify_decorator(
            'example_api2',
            example_api2)

        def mock_notify(context, cls, _type, _priority, _payload):
            self.notify_called = True
            self.context_arg = context

        self.stubs.Set(notifier_api, 'notify',
                       mock_notify)

        # Test positional context
        self.assertEqual(3, example_api(1, 2, ctxt))
        self.assertEqual(self.notify_called, True)
        self.assertEqual(self.context_arg, ctxt)

        self.notify_called = False
        self.context_arg = None

        # Test named context
        self.assertEqual(3, example_api2(1, 2, context=ctxt2))
        self.assertEqual(self.notify_called, True)
        self.assertEqual(self.context_arg, ctxt2)

        # Test missing context
        self.assertEqual(3, example_api2(1, 2, bananas="delicious"))
        self.assertEqual(self.notify_called, True)
        self.assertEqual(self.context_arg, None)


class MultiNotifierTestCase(test.BaseTestCase):
    """Test case for notifications."""

    def setUp(self):
        super(MultiNotifierTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        # Mock log to add one to exception_count when log.exception is called

        def mock_exception(cls, *args):
            self.exception_count += 1

        self.exception_count = 0

        notifier_log = log.getLogger(
            'openstack.common.notifier.api')
        self.stubs.Set(notifier_log, "exception", mock_exception)

        # Mock no_op notifier to add one to notify_count when called.
        def mock_notify(cls, *args):
            self.notify_count += 1

        self.notify_count = 0
        self.stubs.Set(no_op_notifier, 'notify', mock_notify)
        # Mock log_notifier to raise RuntimeError when called.

        def mock_notify2(cls, *args):
            raise RuntimeError("Bad notifier.")

        self.stubs.Set(log_notifier, 'notify', mock_notify2)
        self.addCleanup(notifier_api._reset_drivers)

    def test_send_notifications_successfully(self):
        notification_driver = [
            'openstack.common.notifier.no_op_notifier'
        ]
        self.config(notification_driver=notification_driver)
        notifier_api.notify('contextarg',
                            'publisher_id',
                            'event_type',
                            notifier_api.WARN,
                            dict(a=3))
        self.assertEqual(self.notify_count, 1)
        self.assertEqual(self.exception_count, 0)

    def test_send_notifications_with_errors(self):
        notification_driver = [
            'openstack.common.notifier.no_op_notifier',
            'openstack.common.notifier.log_notifier'
        ]
        self.config(notification_driver=notification_driver)
        notifier_api.notify('contextarg',
                            'publisher_id',
                            'event_type',
                            notifier_api.WARN,
                            dict(a=3))
        self.assertEqual(self.notify_count, 1)
        self.assertEqual(self.exception_count, 1)

    def test_when_driver_fails_to_import(self):
        notification_driver = [
            'openstack.common.notifier.no_op_notifier',
            'openstack.common.notifier.logo_notifier',
            'fdsjgsdfhjkhgsfkj'
        ]
        self.config(notification_driver=notification_driver)
        notifier_api.notify('contextarg',
                            'publisher_id',
                            'event_type',
                            notifier_api.WARN,
                            dict(a=3))
        self.assertEqual(self.exception_count, 2)
        self.assertEqual(self.notify_count, 1)

    def test_publisher_id(self):
        self.assertEqual(notifier_api.publisher_id('foobar'),
                         'foobar.' + socket.gethostname())
        self.assertEqual(notifier_api.publisher_id('foobar', 'baz'),
                         'foobar.baz')


class PublishErrorsTestCase(test.BaseTestCase):
    """Test case for notifications via publish_errors."""
    def setUp(self):
        super(PublishErrorsTestCase, self).setUp()
        notification_driver = [
            'openstack.common.notifier.no_op_notifier',
            'openstack.common.notifier.log_notifier']

        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        self.config = self.useFixture(config.Config()).config
        self.CONF = self.useFixture(config.Config()).conf
        self.config(notification_driver=notification_driver)
        self.stubs.Set(self.CONF, "notification_driver", notification_driver)
        self.real_log_notify = getattr(log_notifier, 'notify')

        def mock_notify(context, message):
            self.no_op_flg = True

        def mock_log_notify(context, message):
            self.real_log_notify(context, message)
            if (message['publisher_id'] == 'error.publisher'):
                self.error_flg = True
            else:
                self.log_flg = True

        self.stubs.Set(no_op_notifier, 'notify', mock_notify)
        self.stubs.Set(log_notifier, 'notify', mock_log_notify)
        self.config(publish_errors=True,
                    use_stderr=False)
        log.setup('test_error_notifications')

        self.addCleanup(notifier_api._reset_drivers)

    def test_log_error_notifications(self):
        '''Test Logging ERROR.'''
        self.no_op_flg = False
        self.log_flg = False
        self.error_flg = False

        LOG = log.getLogger('test_error_notifications')
        LOG.error('foobar')

        self.assertTrue(self.no_op_flg)
        self.assertFalse(self.log_flg)
        self.assertTrue(self.error_flg)

    def test_error_notifications(self):
        '''Test notification with ERROR.'''
        self.no_op_flg = False
        self.log_flg = False
        self.error_flg = False

        notifier_api.notify(ctxt, 'test.publisher',
                            'error_notification', notifier_api.ERROR,
                            dict(error='foo'))

        self.assertTrue(self.no_op_flg)
        self.assertTrue(self.log_flg)
        self.assertTrue(self.error_flg)

    def test_warn_notifications(self):
        '''Test notification with WARN.'''
        self.no_op_flg = False
        self.log_flg = False
        self.error_flg = False

        notifier_api.notify(ctxt, 'test.publisher',
                            'error_notification', notifier_api.WARN,
                            dict(error='bar'))

        self.assertTrue(self.no_op_flg)
        self.assertTrue(self.log_flg)
        self.assertFalse(self.error_flg)
