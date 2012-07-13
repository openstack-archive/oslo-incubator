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

import imp
import os
import pkg_resources

from openstack.common import cfg
from openstack.common import log as logging
from openstack.common.notifier import list_notifier


CONF = cfg.CONF
LOG = logging.getLogger(__name__)


class PluginManager(object):
    """Manages plugin entrypoints and loading.

    For a service to implement this plugin interface for callback purposes:

      - Make use of the openstack-common notifier system
      - Instantiate this manager in each process (passing in
        project and service name)

    For an API service to extend itself using this plugin interface,
    it needs to query the plugin_extension_factory provided by
    the already-instantiated PluginManager.
    """

    def __init__(self, project_name, service_name):
        """ Construct Plugin Manager; load and initialize plugins.

        project_name (e.g. 'nova' or 'glance') is used
        to construct the entry point that identifies plugins.

        The service_name (e.g. 'compute') is passed on to
        each plugin as a raw string for it to do what it will.
        """
        self._project_name = project_name
        self._service_name = service_name
        self.plugins = []

    def _force_use_list_notifier(self):
        if (CONF.notification_driver !=
            'openstack.common.notifier.list_notifier'):
            if not hasattr(CONF, "list_notifier_drivers"):
                CONF.list_notifier_drivers = []
            old_notifier = CONF.notification_driver
            drvstring = 'openstack.common.notifier.list_notifier'
            CONF.notification_driver = drvstring
            if old_notifier:
                list_notifier.add_driver(old_notifier)

    def load_plugins(self):
        self.plugins = []

        for entrypoint in pkg_resources.iter_entry_points('%s.plugin' %
                                                          self._project_name):
            try:
                pluginclass = entrypoint.load()
                plugin = pluginclass(self._service_name)
                self.plugins.append(plugin)
            except Exception, exc:
                LOG.error(_("Failed to load plugin %(plug)s: %(exc)s") %
                          {'plug': entrypoint, 'exc': exc})

        # See if we need to turn on the list notifier
        for plugin in self.plugins:
            if plugin.notifiers:
                self._force_use_list_notifier()
                break

        # Register individual notifiers.
        for plugin in self.plugins:
            for notifier in plugin.notifiers:
                list_notifier.add_driver(notifier)

    def plugin_extension_factory(self, ext_mgr):
        for plugin in self.plugins:
            descriptors = plugin.api_extension_descriptors
            for descriptor in descriptors:
                ext_mgr.load_extension(descriptor)
