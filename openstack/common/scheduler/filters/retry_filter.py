# Copyright (c) 2011 OpenStack Foundation.
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

from openstack.common.gettextutils import _
from openstack.common import log as logging
from openstack.common.scheduler import filters

LOG = logging.getLogger(__name__)


class RetryFilter(filters.BaseHostFilter):
    """Filter out nodes that have already been attempted for scheduling
    purposes, host passes if it's not in the list of previously attempted
    hosts, previously attempted hosts need to be updated to retry hosts
    in scheduler.
    """

    def host_passes(self, host_state, filter_properties):
        """Skip nodes that have already been attempted."""
        retry = filter_properties.get('retry', None)
        if not retry:
            # Re-scheduling is disabled
            LOG.debug(_("Re-scheduling is disabled"))
            return True

        hosts = retry.get('hosts', [])
        host = host_state.host

        passes = host not in hosts
        pass_msg = "passes" if passes else "fails"

        LOG.debug(_("Host %(host)s %(pass_msg)s.  Previously tried hosts: "
                    "%(hosts)s") % {'host': host,
                                    'pass_msg': pass_msg,
                                    'hosts': hosts})
        return passes
