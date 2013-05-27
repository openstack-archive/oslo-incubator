# Copyright 2012 OpenStack Foundation.
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

from openstack.common.notifier import api as notifier_api
from openstack.common.plugin import plugin
from openstack.common.plugin import pluginmanager
from tests import utils


class SimpleNotifier(object):
    def __init__(self):
        self.message_list = []

    def notify(self, context, message):
        self.context = context
        self.message_list.append(message)


class ManagerTestCase(utils.BaseTestCase):
    def test_constructs(self):
        manager1 = pluginmanager.PluginManager("testproject", "testservice")
        self.assertNotEqual(manager1, False)


class NotifyTestCase(utils.BaseTestCase):
    """Test case for the plugin notification interface."""

    def test_add_notifier(self):
        notifier1 = SimpleNotifier()
        notifier2 = SimpleNotifier()
        notifier3 = SimpleNotifier()

        testplugin = plugin.Plugin('service')
        testplugin._add_notifier(notifier1)
        testplugin._add_notifier(notifier2)
        self.assertEqual(len(testplugin.notifiers), 2)

        testplugin._add_notifier(notifier3)
        self.assertEqual(len(testplugin.notifiers), 3)

    def test_notifier_action(self):
        def mock_iter_entry_points(_t):
            return [MockEntrypoint("fake", "fake", ["fake"])]

        self.stubs.Set(pkg_resources, 'iter_entry_points',
                       mock_iter_entry_points)

        plugmgr = pluginmanager.PluginManager("testproject", "testservice")
        plugmgr.load_plugins()
        self.assertEqual(len(plugmgr.plugins), 1)
        self.assertEqual(len(plugmgr.plugins[0].notifiers), 1)
        notifier = plugmgr.plugins[0].notifiers[0]

        notifier_api.notify('contextarg', 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(len(notifier.message_list), 1)


class StubControllerExtension(object):
    name = 'stubextension'
    alias = 'stubby'


class TestPluginClass(plugin.Plugin):

    def __init__(self, service_name):
        super(TestPluginClass, self).__init__(service_name)
        self._add_api_extension_descriptor(StubControllerExtension)
        notifier1 = SimpleNotifier()
        self._add_notifier(notifier1)


class MockEntrypoint(pkg_resources.EntryPoint):
    def load(self):
        return TestPluginClass


class MockExtManager():
    def __init__(self):
        self.descriptors = []

    def load_extension(self, descriptor):
        self.descriptors.append(descriptor)


class APITestCase(utils.BaseTestCase):
    """Test case for the plugin api extension interface."""
    def test_add_extension(self):
        def mock_load(_s):
            return TestPluginClass()

        def mock_iter_entry_points(_t):
            return [MockEntrypoint("fake", "fake", ["fake"])]

        self.stubs.Set(pkg_resources, 'iter_entry_points',
                       mock_iter_entry_points)

        mgr = MockExtManager()
        plugmgr = pluginmanager.PluginManager("testproject", "testservice")
        plugmgr.load_plugins()
        plugmgr.plugin_extension_factory(mgr)

        self.assertTrue(StubControllerExtension in mgr.descriptors)
