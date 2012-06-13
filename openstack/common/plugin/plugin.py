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

from openstack.common import cfg
from openstack.common import log as logging
from openstack.common.notifier import list_notifier


CONF = cfg.CONF

LOG = logging.getLogger(__name__)


class Plugin(object):
    """Defines an interface for adding functionality to an OpenStack service.

    A plugin interacts with a service via the following pathways:

    - An optional set of notifiers, managed via
      add_notifier() and remove_notifier()

    - A set of api extensions, managed via add_api_extension_descriptor()

    - Direct calls to service functions.

    - Whatever else the plugin wants to do on its own.

    This is the reference implementation.
    """

    def __init__(self):
        self._notifiers = []
        self._api_extension_descriptors = []

        # Make sure we're using the list_notifier.
        if not hasattr(CONF, "list_notifier_drivers"):
            CONF.list_notifier_drivers = []
        old_notifier = CONF.notification_driver
        CONF.notification_driver = 'openstack.common.notifier.list_notifier'
        if (old_notifier and
            old_notifier != 'openstack.common.notifier.list_notifier'):
            list_notifier.add_driver(old_notifier)

    def on_service_load(self, service_name):
        """Called when a project API service loads this plugin.

        Plugins should override this method when they want to
        perform service-specific initializations.
        """
        pass

    def add_api_extension_descriptor(self, descriptor):
        """Subclass convenience method which adds an extension descriptor.

           Subclass constructors should call this method when
           extending a project's REST interface.

           Note that once the api service has loaded, the
           API extension set is more-or-less fixed, so
           this should mainly be called by subclass constructors.
        """
        self._api_extension_descriptors.append(descriptor)

    def add_notifier(self, notifier):
        """Subclass convenience method which adds a notifier.

           Notifier objects should implement the function notify(message).
           Each notifier receives a notify() call whenever an openstack
           service broadcasts a notification.
        """
        self._notifiers.append(notifier)
        list_notifier.add_driver(notifier)

    def remove_notifier(self, notifier):
        """Remove a notifier from the notification driver chain."""
        self._notifiers.remove(notifier)
        list_notifier.remove_driver(notifier)

    # The following methods are called by OpenStack services to query
    #  plugin featuers.  Subclasses should probably not override these.
    def notifiers(self):
        """Returns list of notifiers for this plugin."""
        return self._notifiers

    def get_api_extension_descriptors(self):
        """Return a list of API extension descriptors.

           Called by a project API during its load sequence.
        """
        return self._api_extension_descriptors
