#
# Copyright 2013 - Red Hat, Inc.
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
#

"""
Test the base rpc API.
"""

from oslo.config import cfg

from openstack.common import context
from openstack.common.rpc import baserpc
from openstack.common.rpc import proxy
from tests import utils

CONF = cfg.CONF


class BaseAPITestCase(utils.BaseTestCase):

    def setUp(self):
        super(BaseAPITestCase, self).setUp()
        self.user_id = 'fake'
        self.project_id = 'fake'
        self.context = context.RequestContext(self.user_id,
                                              self.project_id)
        self.base_rpcapi = baserpc.BaseAPI('fake_service')

    def test_ping(self):
        self.mox.StubOutWithMock(proxy.RpcProxy, 'call')
        proxy.RpcProxy.call(self.context,
                            {'args': {'arg': 'foo'},
                             'namespace': 'baseapi',
                             'method': 'ping'},
                            timeout=None).AndReturn({'service': 'fake_service',
                                                     'arg': 'foo'})

        self.mox.ReplayAll()

        res = self.base_rpcapi.ping(self.context, 'foo')
        self.assertEqual(res, {'service': 'fake_service', 'arg': 'foo'})
        self.mox.VerifyAll()

    def test_get_backdoor_port(self):
        self.mox.StubOutWithMock(proxy.RpcProxy, 'call')
        proxy.RpcProxy.call(self.context,
                            {'args': {}, 'namespace': 'baseapi',
                             'method': 'get_backdoor_port'},
                            topic='fake_service.fake_host',
                            version='1.1').AndReturn('fake_port')
        self.mox.ReplayAll()
        res = self.base_rpcapi.get_backdoor_port(self.context, 'fake_host')
        self.assertEqual(res, 'fake_port')
        self.mox.VerifyAll()
