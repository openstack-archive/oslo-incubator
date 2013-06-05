# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack Foundation.
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
from openstack.common import context
from openstack.common.plugin import pluginmanager
from openstack.common.scheduler import base_rpcapi as scheduler_rpcapi
from tests.unit.manager import fake_manager
from tests import utils


class BaseServiceManagerTest(utils.BaseTestCase):

    def test_additional_apis_for_dispatcher(self):
        class MyAPI(object):
            pass

        self.mox.StubOutClassWithMocks(pluginmanager, 'PluginManager')
        self.mox.StubOutWithMock(pluginmanager.PluginManager, 'load_plugins')

        plugmanager = pluginmanager.PluginManager('fake_project',
                                                  fake_manager.FakeManager)
        plugmanager.load_plugins()
        self.mox.ReplayAll()
        manager = fake_manager.FakeManager()
        api = MyAPI()
        dispatch = manager.create_rpc_dispatcher(additional_apis=[api])
        self.assertEqual(len(dispatch.callbacks), 2)
        self.assertTrue(api in dispatch.callbacks)

    def test_publish_service_capabilities(self):
        ctx = context.RequestContext()
        self.mox.StubOutClassWithMocks(scheduler_rpcapi, 'BaseSchedulerAPI')
        self.mox.StubOutClassWithMocks(pluginmanager, 'PluginManager')
        self.mox.StubOutWithMock(pluginmanager.PluginManager, 'load_plugins')
        self.mox.StubOutWithMock(scheduler_rpcapi.BaseSchedulerAPI,
                                 'update_service_capabilities')

        scheduler_api = scheduler_rpcapi.BaseSchedulerAPI()
        plugmanager = pluginmanager.PluginManager('fake_project', 'undefined')
        plugmanager.load_plugins()
        scheduler_api.update_service_capabilities(ctx,
                                                  'undefined',
                                                  'fake_host',
                                                  ['fake_capabilities'])

        self.mox.ReplayAll()
        manager = fake_manager.FakeSchedulerDependentManager(host='fake_host')

        manager.update_service_capabilities('fake_capabilities')
        manager.publish_service_capabilities(ctx)
