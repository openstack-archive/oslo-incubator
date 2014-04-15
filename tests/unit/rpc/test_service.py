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

from oslotest import base as test_base

from openstack.common.fixture import config
from openstack.common.rpc import service


class FakeService(service.Service):
    """Fake manager for tests."""
    def __init__(self, host, topic):
        super(FakeService, self).__init__(host, topic, None)
        self.method_result = 'manager'

    def test_method(self):
        return self.method_result


class FakeHookService(FakeService):
    def __init__(self, host, topic):
        super(FakeService, self).__init__(host, topic)
        self.hooked = False

    def initialize_service_hook(self, service):
        self.hooked = True

    def test_hook(self):
        return self.hooked


class RpcServiceManagerTestCase(test_base.BaseTestCase):
    """Test cases for Services."""
    def setUp(self):
        super(RpcServiceManagerTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        self.config(fake_rabbit=True)
        self.config(rpc_backend='openstack.common.rpc.impl_fake')
        self.config(verbose=True)
        self.config(rpc_response_timeout=5)
        self.config(rpc_cast_timeout=5)

    def test_message_default(self):
        serv = FakeService('test-host', 'test-topic')
        serv.start()
        self.assertEqual(serv.test_method(), 'manager')
        serv.stop()

    def test_hook_default(self):
        serv = FakeHookService('test-host', 'test-topic')
        serv.start()
        self.assertTrue(serv.test_hook())
        serv.stop()
