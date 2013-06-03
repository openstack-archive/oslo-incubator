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
Scheduler base class that all Schedulers from all services should inherit from
"""

from openstack.common import importutils


class BaseScheduler(object):
    """The base class that all Scheduler classes should inherit from."""

    def __init__(self, conf, *args, **kwargs):
        self.conf = conf
        self.host_manager = importutils.import_object(
            self.conf.scheduler_host_manager)

    def service_get_all_by_topic(self):
        raise NotImplementedError(_("Method of getting running service "
                                    "for topic should be defined."))

    def service_is_up(self):
        raise NotImplementedError(_("Method of checking running service "
                                    " should be defined"))

    def get_service_capabilities(self):
        """Get the normalized set of capabilities for the services.
        """
        return self.host_manager.get_service_capabilities()

    def update_service_capabilities(self, service_name, host, capabilities):
        """Process a capability update from a service node."""
        self.host_manager.update_service_capabilities(service_name,
                                                      host,
                                                      capabilities)

    def get_host_list(self):
        """Get a list of hosts from the HostManager."""
        return self.host_manager.get_host_list()

    def hosts_up(self, context, topic):
        """Return the list of hosts that have a running service for topic."""
        services = self.service_get_all_by_topic(context, topic)
        return [service['host']
                for service in services
                if self.service_is_up(service)]

    def schedule(self, context, topic, method, *_args, **_kwargs):
        """Must override schedule method for scheduler to work."""
        raise NotImplementedError(_("Must implement a fallback schedule"))

    def _schedule(self, context, topic, request_spec, *_args, **_kwargs):
        """Must override schedule method for scheduler to work."""
        raise NotImplementedError(_("Must implement a fallback schedule"))
