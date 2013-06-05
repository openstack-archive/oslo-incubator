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
Tests For Scheduler
"""

from oslo.config import cfg

from openstack.common import context
from openstack.common.rpc import common as rpc_common
from openstack.common.scheduler import base_driver
from openstack.common.scheduler import base_manager
from tests import utils

CONF = cfg.CONF


class SchedulerManagerTestCase(utils.BaseTestCase):
    """Test case for scheduler manager."""

    manager_cls = base_manager.BaseSchedulerManager
    driver_cls = base_driver.BaseScheduler
    driver_cls_name = 'openstack.common.scheduler.base_driver.BaseScheduler'
    host_manager_cls = 'openstack.common.scheduler.base_host_manager.'\
                       'BaseHostManager'

    def setUp(self):
        super(SchedulerManagerTestCase, self).setUp()
        self.manager = self.manager_cls('openstack.common',
                                        self.driver_cls_name,
                                        host='fake_host')
        self.config(scheduler_host_manager=self.host_manager_cls)
        self.config(scheduler_host_manager=self.host_manager_cls)
        self.config(scheduler_default_filters=['fake_filter'])
        self.config(scheduler_default_weighers=['fake_weighers'])
        self.context = context.RequestContext(user='fake_user')
        self.topic = 'fake_topic'
        self.fake_args = (1, 2, 3)
        self.fake_kwargs = {'cat': 'meow', 'dog': 'woof'}

    def stub_out_client_exceptions(self):
        def passthru(exceptions, func, *args, **kwargs):
            return func(*args, **kwargs)

        self.stubs.Set(rpc_common, 'catch_client_exception', passthru)

    def test_1_correct_init(self):
        # Correct scheduler driver
        manager = self.manager
        self.assertTrue(isinstance(manager.driver, self.driver_cls))

    def test_update_service_capabilities(self):
        service_name = 'fake_service'
        host = 'fake_host'

        self.mox.StubOutWithMock(self.manager.driver,
                                 'update_service_capabilities')

        # Test no capabilities passes empty dictionary
        self.manager.driver.update_service_capabilities(service_name,
                                                        host, {})
        self.mox.ReplayAll()
        self.manager.update_service_capabilities(self.context,
                                                 service_name=service_name,
                                                 host=host,
                                                 capabilities={})
        self.mox.VerifyAll()

        self.mox.ResetAll()
        # Test capabilities passes correctly
        capabilities = {'fake_capability': 'fake_value'}
        self.manager.driver.update_service_capabilities(service_name,
                                                        host,
                                                        capabilities)
        self.mox.ReplayAll()
        self.manager.update_service_capabilities(self.context,
                                                 service_name=service_name,
                                                 host=host,
                                                 capabilities=capabilities)

    def test_update_service_multiple_capabilities(self):
        service_name = 'fake_service'
        host = 'fake_host'

        self.mox.StubOutWithMock(self.manager.driver,
                                 'update_service_capabilities')

        capab1 = {'fake_capability': 'fake_value1'},
        capab2 = {'fake_capability': 'fake_value2'},
        capab3 = None
        self.manager.driver.update_service_capabilities(service_name,
                                                        host,
                                                        capab1)
        self.manager.driver.update_service_capabilities(service_name,
                                                        host,
                                                        capab2)
        # None is converted to {}
        self.manager.driver.update_service_capabilities(service_name, host, {})
        self.mox.ReplayAll()
        self.manager.update_service_capabilities(self.context,
                                                 service_name=service_name,
                                                 host=host,
                                                 capabilities=[capab1,
                                                               capab2,
                                                               capab3])

    def test_get_host_list(self):
        self.mox.StubOutWithMock(self.manager.driver.host_manager,
                                 'get_host_list')
        self.manager.driver.host_manager.get_host_list()
        self.mox.ReplayAll()

        self.manager.get_host_list(self.context)

    def test_get_service_capabilities(self):
        self.mox.StubOutWithMock(self.manager.driver.host_manager,
                                 'get_service_capabilities')
        self.manager.driver.host_manager.get_service_capabilities()
        self.mox.ReplayAll()

        self.manager.get_service_capabilities(self.context)

    def _mox_schedule_method_helper(self, method_name):
        # Make sure the method exists that we're going to test call
        def stub_method(*args, **kwargs):
            pass

        setattr(self.manager.driver, method_name, stub_method)

        self.mox.StubOutWithMock(self.manager.driver,
                                 method_name)
