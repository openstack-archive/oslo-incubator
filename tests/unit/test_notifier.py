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

import mock
from stevedore import extension
from stevedore.tests import manager as test_manager
import yaml

from openstack.common import context
from openstack.common.fixture import config
from openstack.common.fixture import moxstubout
from openstack.common import log
from openstack.common.notifier import api as notifier_api
from openstack.common.notifier import log_notifier
from openstack.common.notifier import no_op_notifier
from openstack.common.notifier import routing_notifier
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


class RoutingNotifierTestCase(test.BaseTestCase):
    def _fake_extension_manager(self, ext):
        return test_manager.TestExtensionManager(
            [extension.Extension('test', None, None, ext), ])

    def _empty_extension_manager(self):
        return test_manager.TestExtensionManager([])

    def test_should_load_plugin(self):
        self.config = self.useFixture(config.Config())
        self.config.conf.set_override("disabled_notification_driver",
                                      ['foo', 'blah'])
        ext = mock.MagicMock()
        ext.name = "foo"
        self.assertFalse(routing_notifier._should_load_plugin(ext))
        ext.name = "zoo"
        self.assertTrue(routing_notifier._should_load_plugin(ext))

    def test_load_notifiers_no_config(self):
        # default routing_notifier_config=""
        with mock.patch('stevedore.dispatch.DispatchExtensionManager',
                        return_value=self._fake_extension_manager(
                            mock.MagicMock())):
            routing_notifier._load_notifiers()
        self.assertEqual(routing_notifier.routing_groups, {})

    def test_load_notifiers_no_extensions(self):
        # default routing_notifier_config=""
        with mock.patch('stevedore.dispatch.DispatchExtensionManager',
                        return_value=self._empty_extension_manager()):
            with mock.patch('openstack.common.notifier.'
                            'routing_notifier.LOG') as mylog:
                routing_notifier._load_notifiers()
                self.assertTrue(mylog.warning.called)

    def test_load_notifiers_config(self):
        self.config = self.useFixture(config.Config())
        self.config.conf.set_override("routing_notifier_config",
                                      "routing_notifier.yaml")
        routing_config = r"""
group_1:
   - rpc
group_2:
   - rpc
        """

        config_file = mock.MagicMock()
        config_file.return_value = routing_config

        with mock.patch('openstack.common.notifier.routing_notifier.'
                        '_get_notifier_config_file', config_file):
            with mock.patch('stevedore.dispatch.DispatchExtensionManager',
                            return_value=self._fake_extension_manager(
                                mock.MagicMock())):
                routing_notifier._load_notifiers()
                groups = routing_notifier.routing_groups.keys()
                groups.sort()
                self.assertEqual(['group_1', 'group_2'], groups)

    def test_get_drivers_for_message_accepted_events(self):
        config = r"""
group_1:
   - rpc:
         accepted_events:
            - foo.*
            - blah.zoo.*
            - zip
        """
        groups = yaml.load(config)
        group = groups['group_1']

        # No matching event ...
        self.assertEqual([],
                         routing_notifier._get_drivers_for_message(
                             group, "unknown", None))

        # Child of foo ...
        self.assertEqual(['rpc'],
                         routing_notifier._get_drivers_for_message(
                             group, "foo.1", None))

        # Foo itself ...
        self.assertEqual([],
                         routing_notifier._get_drivers_for_message(
                             group, "foo", None))

        # Child of blah.zoo
        self.assertEqual(['rpc'],
                         routing_notifier._get_drivers_for_message(
                             group, "blah.zoo.zing", None))

    def test_get_drivers_for_message_accepted_priorities(self):
        config = r"""
group_1:
   - rpc:
         accepted_priorities:
            - info
            - error
        """
        groups = yaml.load(config)
        group = groups['group_1']

        # No matching priority
        self.assertEqual([],
                         routing_notifier._get_drivers_for_message(
                             group, None, "unknown"))

        # Info ...
        self.assertEqual(['rpc'],
                         routing_notifier._get_drivers_for_message(
                             group, None, "info"))

        # Error (to make sure the list is getting processed) ...
        self.assertEqual(['rpc'],
                         routing_notifier._get_drivers_for_message(
                             group, None, "error"))

    def test_get_drivers_for_message_both(self):
        config = r"""
group_1:
   - rpc:
         accepted_priorities:
            - info
         accepted_events:
            - foo.*
   - driver_1:
         accepted_priorities:
            - info
   - driver_2:
        accepted_events:
            - foo.*
        """
        groups = yaml.load(config)
        group = groups['group_1']

        # Valid event, but no matching priority
        self.assertEqual(['driver_2'],
                         routing_notifier._get_drivers_for_message(
                             group, 'foo.blah', "unknown"))

        # Valid priority, but no matching event
        self.assertEqual(['driver_1'],
                         routing_notifier._get_drivers_for_message(
                             group, 'unknown', "info"))

        # Happy day ...
        x = routing_notifier._get_drivers_for_message(group, 'foo.blah',
                                                      "info")
        x.sort()
        self.assertEqual(['driver_1', 'driver_2', 'rpc'], x)

    def test_filter_func(self):
        routing_notifier.routing_groups = {'group_1': None, 'group_2': None}

        ext = mock.MagicMock()
        ext.name = "rpc"

        message = {'event_type': 'my_event', 'priority': 'my_priority'}

        # Driver included (top-level) ...
        drivers_mock = mock.MagicMock()
        drivers_mock.side_effect = [['rpc'], ['foo'], ['blah', 'zip']]

        with mock.patch('openstack.common.notifier.routing_notifier.'
                        '_get_drivers_for_message', drivers_mock):
            self.assertTrue(routing_notifier._filter_func(ext, {}, message))

        # Driver included (sub-list) ...
        drivers_mock = mock.MagicMock()
        drivers_mock.side_effect = [['foo'], ['blah', 'rpc']]

        with mock.patch('openstack.common.notifier.routing_notifier.'
                        '_get_drivers_for_message', drivers_mock):
            self.assertTrue(routing_notifier._filter_func(ext, {}, message))

        # Bad message for this driver ...
        drivers_mock = mock.MagicMock()
        drivers_mock.side_effect = [['foo'], ['blah', 'zip']]
        with mock.patch('openstack.common.notifier.routing_notifier.'
                        '_get_drivers_for_message', drivers_mock):
            self.assertFalse(routing_notifier._filter_func(ext, {}, message))
