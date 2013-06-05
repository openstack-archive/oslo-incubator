# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2010 OpenStack, LLC.
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

"""
Base settings for Scheduler Service
"""

from oslo.config import cfg

from openstack.common import importutils
from openstack.common import log as logging
from openstack.common.manager import base_service_manager


LOG = logging.getLogger(__name__)


scheduler_driver_opt = cfg.StrOpt('scheduler_driver',
                                  default='openstack.common.scheduler.'
                                          'base_filter_scheduler.'
                                          'BaseFilterScheduler',
                                  help='Default scheduler driver to use')

CONF = cfg.CONF
CONF.register_opt(scheduler_driver_opt)


class BaseSchedulerManager(base_service_manager.BaseManager):
    """Chooses a host to service operations."""

    RPC_API_VERSION = None

    def __init__(self, component_name, scheduler_driver=None,
                 *args, **kwargs):
        super(BaseSchedulerManager, self).__init__(service_name='scheduler',
                                                   *args, **kwargs)
        if not scheduler_driver:
            scheduler_driver = CONF.scheduler_driver
        self.driver = importutils.import_object(scheduler_driver,
                                                component_name)

    def get_host_list(self, context):
        """Get a list of hosts from the HostManager."""
        return self.driver.get_host_list()

    def get_service_capabilities(self, context):
        """Get the normalized set of capabilities for this zone."""
        return self.driver.get_service_capabilities()

    def update_service_capabilities(self, context, service_name=None,
                                    host=None, capabilities=None, **kwargs):
        """Process a capability update from a service node."""
        if not isinstance(capabilities, list):
            capabilities = [capabilities]
        for capability in capabilities:
            if capability is None:
                capability = {}
            self.driver.update_service_capabilities(service_name,
                                                    host,
                                                    capability)
