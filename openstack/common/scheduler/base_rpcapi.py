# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012, Red Hat, Inc.
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
Default settings of Client side of the scheduler manager RPC API.
"""

from oslo.config import cfg
import openstack.common.rpc.proxy


CONF = cfg.CONF


class BaseSchedulerAPI(openstack.common.rpc.proxy.RpcProxy):
    """Client side of the scheduler rpc API."""

    RPC_API_VERSION = None

    def __init__(self):
        super(BaseSchedulerAPI, self).__init__(
            topic=CONF.scheduler_topic,
            default_version=self.RPC_API_VERSION)

    def update_service_capabilities(self, ctxt,
                                    service_name, host,
                                    capabilities):
        self.fanout_cast(ctxt, self.make_msg('update_service_capabilities',
                         service_name=service_name, host=host,
                         capabilities=capabilities))
