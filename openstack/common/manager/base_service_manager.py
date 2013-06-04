# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""Base Manager class.

Managers are responsible for a certain aspect of the system.  It is a logical
grouping of code relating to a portion of the system.  In general other
components should be using the manager to make changes to the components that
it is responsible for.

For example, other components that need to deal with volumes in some way,
should do so by calling methods on the VolumeManager instead of directly
changing fields in the database.  This allows us to keep all of the code
relating to volumes in the same place.

We have adopted a basic strategy of Smart managers and dumb data, which means
rather than attaching methods to data objects, components should call manager
methods that act on the data.

Methods on managers that can be executed locally should be called directly. If
a particular method must execute on a remote host, this should be done via rpc
to the service that wraps the manager

Managers should be responsible for most of the db access, and
non-implementation specific data.  Anything implementation specific that can't
be generalized should be done by the Driver.

In general, we prefer to have one manager with multiple drivers for different
implementations, but sometimes it makes sense to have multiple managers.  You
can think of it this way: Abstract different overall strategies at the manager
level(FlatNetwork vs VlanNetwork), and different implementations at the driver
level(LinuxNetDriver vs CiscoNetDriver).

Managers will often provide methods for initial setup of a host or periodic
tasks to a wrapping service.

This module provides Manager, a base class for managers.

"""

import socket

from oslo.config import cfg

from openstack.common import log as logging
from openstack.common import periodic_task
from openstack.common.plugin import pluginmanager
from openstack.common.rpc import dispatcher as rpc_dispatcher
from openstack.common.scheduler import base_rpcapi as scheduler_rpcapi


LOG = logging.getLogger(__name__)

host_opt = cfg.StrOpt('host',
                      default=socket.gethostname(),
                      help='Name of this node. This can be an opaque '
                           'identifier. It is not necessarily a hostname, '
                           'FQDN, or IP address.')

CONF = cfg.CONF
CONF.register_opt(host_opt)


class BaseManager(periodic_task.PeriodicTasks):
    # Set RPC API version to 1.0 by default.
    RPC_API_VERSION = 1.0

    def __init__(self, host=None, db_driver=None,
                 service_name='undefined'):
        super(BaseManager, self).__init__()
        if host is None:
            host = CONF.host
        self.host = host
        self.load_plugins()
        self.backdoor_port = None
        self.service_name = service_name

    def get_project_name(self):
        """Return component name for loading plugins.
        For each service should be redefined.
        """
        return None

    def load_plugins(self):
        project_name = self.get_project_name()
        if project_name is not None:
            pluginmgr = pluginmanager.PluginManager(project_name,
                                                    self.__class__)
            pluginmgr.load_plugins()

    def _base_rpc_api(self, *args, **kwargs):
        """Return object that can be server side of RPC API
        for specific service
        """
        return None

    def _get_apis(self, *args, **kwargs):
        apis = [self]
        additional_apis = kwargs.get('additional_apis')
        if additional_apis:
            apis.extend(additional_apis)
        base_rpc = self._base_rpc_api(*args, **kwargs)
        if base_rpc:
            apis.extend([base_rpc])
        return apis

    def _get_serializer(self, *args, **kwargs):
        return None

    def create_rpc_dispatcher(self, *args, **kwargs):
        '''Get the rpc dispatcher for this manager.

        If a manager would like to set an rpc API version, or support more than
        one class as the target of rpc messages, override this method.
        '''
        apis = self._get_apis(*args, **kwargs)
        serializer = self._get_serializer(*args, **kwargs)
        return rpc_dispatcher.RpcDispatcher(apis, serializer)

    def periodic_tasks(self, context, raise_on_error=False):
        """Tasks to be run at a periodic interval."""
        return self.run_periodic_tasks(context, raise_on_error=raise_on_error)

    def init_host(self):
        """Handle initialization. This is called before any service record
        is created. Child classes should override this method.
        """
        raise NotImplementedError(_("Host initialization should be defined."))

    def pre_start_hook(self, **kwargs):
        """Hook to provide the manager the ability to do additional
        start-up work before any RPC queues/consumers are created. This is
        called after other initialization has succeeded and a service
        record is created. Child classes should override this method.
        """
        raise NotImplementedError(_("Preliminary actions should be defined."))

    def post_start_hook(self):
        """Hook to provide the manager the ability to do additional
        start-up work immediately after a service creates RPC consumers
        and starts 'running'.
        Child classes should override this method.
        """
        raise NotImplementedError(_("Post-started actions should be defined."))

    def service_config(self, context):
        config = {}
        for key in CONF:
            config[key] = CONF.get(key, None)
        return config
