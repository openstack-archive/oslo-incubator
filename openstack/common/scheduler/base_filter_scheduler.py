# Copyright (c) 2011 Intel Corporation
# Copyright (c) 2011 OpenStack, LLC.
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
Base logic for building specific filter scheduler.
"""

from openstack.common import exception
from nova.openstack.common import log as logging
from openstack.common.scheduler import base_driver
from openstack.common.scheduler import base_scheduler_options


LOG = logging.getLogger(__name__)


class BaseFilterScheduler(base_driver.BaseScheduler):
    """Scheduler that can be used for filtering and weighing."""
    def __init__(self, *args, **kwargs):
        super(BaseFilterScheduler, self).__init__(*args, **kwargs)
        self.options = base_scheduler_options.BaseSchedulerOptions(self.conf)

        # this attributes should be redefined for each service
        self.service_object_name = None
        self.service_object_name_id = None

    def _get_configuration_options(self):
        """Fetch options dictionary. Broken out for testing."""
        return self.options.get_configuration()

    def _post_select_populate_filter_properties(self, filter_properties,
                                                host_state):
        """Add additional information to the filter properties after a host has
        been selected by the scheduling process.
        """
        # Add a retry entry for the selected volume backend:
        self._add_retry_host(filter_properties, host_state.host)

    def _add_retry_host(self, filter_properties, *args):
        """Add a retry entry for the selected volume backend. In the event that
        the request gets re-scheduled, this entry will signal that the given
        backend has already been tried.
        """
        retry = filter_properties.get('retry', None)
        if not retry:
            return
        hosts = retry['hosts']
        hosts.append(list(args))

    def _max_attempts(self):
        max_attempts = self.conf.scheduler_max_attempts
        if max_attempts < 1:
            msg = _("Invalid value for 'scheduler_max_attempts', "
                    "must be >=1")
            raise exception.InvalidParameterValue(err=msg)
        return max_attempts

    def _log_service_error(self, service_object, retry):
        """If the request contained an exception from a previous service
        node operation, log it to aid debugging
        """
        exc = retry.pop('exc', None)  # string-ified exception from volume
        if not exc:
            return  # no exception info from a previous attempt, skip

        hosts = retry.get('hosts', None)
        if not hosts:
            return  # no previously attempted hosts, skip

        last_settings = hosts[-1]
        msg = _("Error scheduling %(service_object)s from last host: "
                "%(last_settings)s : %(exc)s") % locals()
        LOG.error(msg)

    def _populate_retry(self, filter_properties, properties):
        """Populate filter properties with history of retries for this
        request. If maximum retries is exceeded, raise NoValidHost.
        """
        service_object_name_id = self.service_object_name_id
        service_object_name = self.service_object_name
        max_attempts = self.max_attempts()
        retry = filter_properties.pop('retry', {})

        if max_attempts == 1:
            # re-scheduling is disabled.
            return

        # retry is enabled, update attempt count:
        if retry:
            retry['num_attempts'] += 1
        else:
            retry = {
                'num_attempts': 1,
                'hosts': []  # list of volume service hosts tried
            }
        filter_properties['retry'] = retry

        service_object = properties.get(service_object_name_id)
        self._log_service_error(service_object, retry)

        if retry['num_attempts'] > max_attempts:
            msg = _("Exceeded max scheduling attempts %(max_attempts)d for "
                    "%(service_object_name) %(service_object)s") % locals()
            raise exception.NoValidHost(reason=msg)

    def schedule(self, context, topic, method, *args, **kwargs):
        """The schedule() contract requires we return the one
        best-suited host for this request.
        """
        self._schedule(context, topic, *args, **kwargs)

    def _schedule(self, context, topic, request_spec, *_args, **_kwargs):
        """Must override schedule method for scheduler to work."""
        raise NotImplementedError(_("Must implement a fallback schedule"))
