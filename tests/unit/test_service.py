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
from openstack.common import service
from openstack.common import manager
from tests import utils


test_service_opts = [
    cfg.StrOpt("fake_manager",
               default="tests.unit.test_service.FakeManager",
               help="Manager for testing"),
    cfg.StrOpt("test_service_listen",
               default='127.0.0.1',
               help="Host to bind test service to"),
    cfg.IntOpt("test_service_listen_port",
               default=0,
               help="Port number to bind test service to"),
    ]

cfg.CONF.register_opts(test_service_opts)


class FakeManager(manager.Manager):
    """Fake manager for tests"""
    def test_method(self):
        return 'manager'


class ExtendedService(service.Service):
    def test_method(self):
        return 'service'


class ServiceManagerTestCase(utils.BaseTestCase):
    """Test cases for Services"""
    def setUp(self):
        super(ServiceManagerTestCase, self).setUp()
        self.config(fake_rabbit=True)
        self.config(rpc_backend='openstack.common.rpc.impl_fake')
        self.config(verbose=True)
        self.config(rpc_response_timeout=5)
        self.config(rpc_cast_timeout=5)


    def test_message_gets_to_manager(self):
        serv = service.Service('test',
                               'test',
                               'test',
                               'tests.unit.test_service.FakeManager')
        serv.start()
        self.assertEqual(serv.test_method(), 'manager')

    def test_override_manager_method(self):
        serv = ExtendedService('test',
                               'test',
                               'test',
                               'tests.unit.test_service.FakeManager')
        serv.start()
        self.assertEqual(serv.test_method(), 'service')


class ServiceTestCase(utils.BaseTestCase):
    """Test cases for Services"""

    def setUp(self):
        super(ServiceTestCase, self).setUp()

    def test_create(self):
        host = 'foo'
        binary = 'nova-fake'
        topic = 'fake'

        app = service.Service.create(host=host, binary=binary, topic=topic)
        self.assert_(app)
