# Copyright 2012 OpenStack LLC.
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

from openstack.common.plugin import plugin
from openstack.common import log as logging


LOG = logging.getLogger(__name__)


class _CallbackNotifier(object):
    """Manages plugin-defined notification callbacks.

    For each Plugin, a CallbackNotifier will be added to the
    notification driver list.  Calls to notify() with appropriate
    messages will be hooked and prompt callbacks.

    A callback should look like this:
      def callback(context, message, user_data)
    """

    def __init__(self):
        self.callback_list = []

    def add_callback(self, event_type, callback, user_data):
        self.callback_list.append({'type': event_type,
                                   'function': callback,
                                   'user_data': user_data})

    def remove_callback(self, callback):
        remove_list = []
        for entry in self.callback_list:
            if entry['function'] == callback:
                remove_list.append(entry)

        for entry in remove_list:
            self.callback_list.remove(entry)

    def notify(self, context, message):
        for entry in self.callback_list:
            if entry['type'] == message.get('event_type'):
                entry['function'](context, message, entry.get('user_data'))

    def callbacks(self):
        return self.callback_list


class CallbackPlugin(plugin.Plugin):
    """ Plugin with a simple callback interface.

    This class is provided as a convenience for producing a simple
    plugin that only watches a couple of events.  For example, here's
    a subclass which prints a line the first time an instance is created.

    class HookInstanceCreation(CallbackPlugin):

        def __init__(self):
            super(HookInstanceCreation, self).__init__()
            self.add_callback(self.magic, 'compute.instance.create.start')

        def magic(self):
            print "An instance was created!"
            self.remove_callback(self, self.magic)
    """

    def __init__(self, api_extension_descriptors=[],
                 notifiers=[]):
        self._callback_notifier = _CallbackNotifier()
        super(CallbackPlugin, self).__init__()

    def add_callback(self, callback, event_type, user_data=None):
        """Add callback for a given event notification.

        Subclasses can call this as an alternative to implementing
        a fullblown notify notifier.
        """
        if self._callback_notifier not in self._notifiers:
            self.add_notifier(self._callback_notifier)
        self._callback_notifier.add_callback(event_type, callback, user_data)

    def remove_callback(self, callback):
        """Remove all notification callbacks to specified function."""
        self._callback_notifier.remove_callback(callback)
        if not self._callback_notifier.callbacks():
            self.remove_notifier(self._callback_notifier)
