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

"""
Unit Tests for remote procedure calls using queue
"""
from eventlet import greenthread

from openstack.common import cfg
from openstack.common.rpc import service
from openstack.common.rpc import manager
from tests import utils


class FakeManager(manager.Manager):
    """Fake manager for tests"""
    def __init__(self, host):
        super(FakeManager, self).__init__(host)
        self.method_result = 'manager'

    def test_method(self):
        return self.method_result


class ServiceManagerTestCase(utils.BaseTestCase):
    """Test cases for Services"""
    def setUp(self):
        super(ServiceManagerTestCase, self).setUp()
        self.config(fake_rabbit=True)
        self.config(rpc_backend='openstack.common.rpc.impl_fake')
        self.config(verbose=True)
        self.config(rpc_response_timeout=5)
        self.config(rpc_cast_timeout=5)

    def test_message_default(self):
        fm = FakeManager('test')
        serv = service.Service('test', 'test', fm)
        serv.start()
        self.assertEqual(serv.manager.test_method(), 'manager')
        serv.stop()
