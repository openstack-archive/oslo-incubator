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
from openstack.common.plugin import callbackplugin
from openstack.common.plugin import pluginmanager
from tests import utils as test_utils

userdatastring = "magic user data string"


class TestCBP(callbackplugin.CallbackPlugin):

    def callback1(self, context, message, userdata):
        self.callback1count += 1

    def callback2(self, context, message, userdata):
        self.callback2count += 1

    def callback3(self, context, message, userdata):
        self.callback3count += 1
        self.userdata = userdata

    def __init__(self, service_name):
        super(TestCBP, self).__init__(service_name)
        self.callback1count = 0
        self.callback2count = 0
        self.callback3count = 0

        self._add_callback(self.callback1, 'type1', None)
        self._add_callback(self.callback2, 'type1', None)
        self._add_callback(self.callback3, 'type2', 'magic user data string')


class CallbackTestCase(test_utils.BaseTestCase):
    """Tests for the callback plugin convenience class."""

    def test_callback_plugin_subclass(self):

        class MockEntrypoint(pkg_resources.EntryPoint):
            def load(self):
                return TestCBP

        def mock_iter_entry_points(_t):
            return [MockEntrypoint("fake", "fake", ["fake"])]

        self.stubs.Set(pkg_resources, 'iter_entry_points',
                       mock_iter_entry_points)

        plugmgr = pluginmanager.PluginManager("testproject", "testservice")
        plugmgr.load_plugins()
        self.assertEqual(len(plugmgr.plugins), 1)
        plugin = plugmgr.plugins[0]
        self.assertEqual(len(plugin.notifiers), 1)

        notifier_api.notify('contextarg', 'publisher_id', 'type1',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(plugin.callback1count, 1)
        self.assertEqual(plugin.callback2count, 1)
        self.assertEqual(plugin.callback3count, 0)

        notifier_api.notify('contextarg', 'publisher_id', 'type2',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(plugin.callback1count, 1)
        self.assertEqual(plugin.callback2count, 1)
        self.assertEqual(plugin.callback3count, 1)
        self.assertEqual(plugin.userdata, userdatastring)

        plugin._remove_callback(plugin.callback1)

        notifier_api.notify('contextarg', 'publisher_id', 'type1',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(plugin.callback1count, 1)
        self.assertEqual(plugin.callback2count, 2)
        self.assertEqual(plugin.callback3count, 1)
