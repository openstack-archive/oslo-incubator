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

import pkg_resources
import unittest

from openstack.common import notifier
from openstack.common.notifier import api as notifier_api
from openstack.common.notifier import no_op_notifier
from openstack.common.plugin import plugin
from openstack.common.plugin import pluginmanager
from tests import utils as test_utils


class SimpleNotifier(object):
    def __init__(self):
        self.message_list = []

    def notify(self, context, message):
        self.context = context
        self.message_list.append(message)


class ManagerTestCase(test_utils.BaseTestCase):
    def tearDown(self):
        super(ManagerTestCase, self).tearDown()

    def test_constructs(self):
        manager1 = pluginmanager.PluginManager("testproject", "testservice")
        self.assertNotEqual(manager1, False)


class NotifyTestCase(test_utils.BaseTestCase):
    """Test case for the plugin notification interface"""
    def setUp(self):
        super(NotifyTestCase, self).setUp()

        # Set up a 'normal' notifier to make sure the plugin logic
        #  doesn't mess anything up.
        self.config(
                notification_driver='openstack.common.notifier.no_op_notifier')

        def mock_notify(cls, *args):
            self.no_op_notify_called = True
        self.stubs.Set(no_op_notifier, 'notify',
                mock_notify)

    def tearDown(self):
        super(NotifyTestCase, self).tearDown()

    def test_init(self):
        notifier = SimpleNotifier()
        testplugin = plugin.Plugin()
        testplugin.add_notifier(notifier)

        notifier_api.notify('contextarg', 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(len(notifier.message_list), 1)
        self.assertTrue(self.no_op_notify_called)

    def test_add_and_remove(self):
        notifier1 = SimpleNotifier()
        notifier2 = SimpleNotifier()
        notifier3 = SimpleNotifier()

        testplugin = plugin.Plugin()
        testplugin.add_notifier(notifier1)
        testplugin.add_notifier(notifier2)

        notifier_api.notify('contextarg', 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(len(notifier1.message_list), 1)
        self.assertEqual(len(notifier2.message_list), 1)
        self.assertTrue(self.no_op_notify_called)

        testplugin.add_notifier(notifier3)

        self.no_op_notify_called = False
        notifier_api.notify('contextarg', 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(len(notifier1.message_list), 2)
        self.assertEqual(len(notifier2.message_list), 2)
        self.assertEqual(len(notifier3.message_list), 1)
        self.assertTrue(self.no_op_notify_called)

        testplugin.remove_notifier(notifier1)
        testplugin.remove_notifier(notifier3)

        self.no_op_notify_called = False
        notifier_api.notify('contextarg', 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(len(notifier1.message_list), 2)
        self.assertEqual(len(notifier2.message_list), 3)
        self.assertEqual(len(notifier3.message_list), 1)
        self.assertTrue(self.no_op_notify_called)

        testplugin.remove_notifier(notifier2)

        self.no_op_notify_called = False
        notifier_api.notify('contextarg', 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(len(notifier1.message_list), 2)
        self.assertEqual(len(notifier2.message_list), 3)
        self.assertEqual(len(notifier3.message_list), 1)
        self.assertTrue(self.no_op_notify_called)


class StubControllerExtension(object):
    name = 'stubextension'
    alias = 'stubby'


class TestPluginClass(plugin.Plugin):

    def __init__(self):
        super(TestPluginClass, self).__init__()
        self.add_api_extension_descriptor(StubControllerExtension)


class MockEntrypoint(pkg_resources.EntryPoint):
    def load(self):
        return TestPluginClass


class MockExtManager():
    def __init__(self):
        self.descriptors = []

    def load_extension(self, descriptor):
        self.descriptors.append(descriptor)


class APITestCase(test_utils.BaseTestCase):
    """Test case for the plugin api extension interface"""
    def tearDown(self):
        super(APITestCase, self).tearDown()

    def test_add_extension(self):
        def mock_load(_s):
            return TestPluginClass()

        def mock_iter_entry_points(_t):
            return [MockEntrypoint("fake", "fake", "fake")]

        self.stubs.Set(pkg_resources, 'iter_entry_points',
                mock_iter_entry_points)

        stubLoaded = False

        mgr = MockExtManager()
        plugmgr = pluginmanager.PluginManager("testproject", "testservice")
        plugmgr.plugin_extension_factory(mgr)

        self.assertIn(StubControllerExtension, mgr.descriptors)
