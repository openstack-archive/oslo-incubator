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

from openstack.common.notifier import api as notifier_api
from openstack.common.plugin import callbackplugin
from tests import utils as test_utils


class SimpleNotifier(object):
    def __init__(self):
        self.message_list = []

    def notify(self, context, message):
        self.context = context
        self.message_list.append(message)


class CallbackTestCase(test_utils.BaseTestCase):
    """Tests for the callback plugin convenience class"""

    def test_init(self):
        notifier = SimpleNotifier()
        testplugin = callbackplugin.CallbackPlugin()
        testplugin.add_notifier(notifier)

        notifier_api.notify('contextarg', 'publisher_id', 'event_type',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(len(notifier.message_list), 1)

    def test_add_and_remove_callbacks(self):
        self.callback1count = 0
        self.callback2count = 0
        self.callback3count = 0

        def callback1(context, message, userdata):
            self.callback1count += 1

        def callback2(context, message, userdata):
            self.callback2count += 1

        def callback3(context, message, userdata):
            self.callback3count += 1

        testplugin = callbackplugin.CallbackPlugin([], [])
        testplugin.add_callback(callback1, 'type1', None)

        notifier_api.notify('contextarg', 'publisher_id', 'type1',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(self.callback1count, 1)
        self.assertEqual(self.callback2count, 0)
        self.assertEqual(self.callback3count, 0)

        testplugin.add_callback(callback2, 'type1', None)
        testplugin.add_callback(callback3, 'type2', None)

        notifier_api.notify('contextarg', 'publisher_id', 'type1',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(self.callback1count, 2)
        self.assertEqual(self.callback2count, 1)
        self.assertEqual(self.callback3count, 0)

        notifier_api.notify('contextarg', 'publisher_id', 'type2',
                            notifier_api.WARN, dict(a=3))

        self.assertEqual(self.callback1count, 2)
        self.assertEqual(self.callback2count, 1)
        self.assertEqual(self.callback3count, 1)

        testplugin.remove_callback(callback1)
        testplugin.remove_callback(callback2)
        testplugin.remove_callback(callback3)

        self.assertEqual(self.callback1count, 2)
        self.assertEqual(self.callback2count, 1)
        self.assertEqual(self.callback3count, 1)
