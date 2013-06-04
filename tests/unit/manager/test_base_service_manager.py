# vim: tabstop=4 shiftwidth=4 softtabstop=4

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
from openstack.common import exception
from openstack.common import importutils
from openstack.common.manager import base_service_manager as manager
from tests import utils


class BaseServiceManagerTest(utils.BaseTestCase):

    def test_missing_db_driver_opt(self):
        self.assertRaises(exception.Invalid, manager.BaseManager)

    def test_additional_apis_for_dispatcher(self):
        class MyAPI(object):
            pass

        self.config(db_driver='fake_db_driver')
        self.mox.StubOutWithMock(importutils, 'import_module')

        importutils.import_module('fake_db_driver')
        self.mox.ReplayAll()
        m = manager.BaseManager()
        api = MyAPI()
        dispatch = m.create_rpc_dispatcher(additional_apis=[api])
        self.assertEqual(len(dispatch.callbacks), 2)
        self.assertTrue(api in dispatch.callbacks)
        self.mox.VerifyAll()

    def test_missing_scheduler_rpcapi_opt(self):
        self.assertRaises(exception.Invalid,
                          manager.BaseSchedulerDependentManager)

    def test_publish_service_capabilities(self):
        fake_rpc = 'tests.unit.manager.fake_rpc.FakeSchedulerAPI'
        self.config(scheduler_rpcapi=fake_rpc, group="scheduler")
        self.config(db_driver='tests.unit.manager')
        ctx = context.RequestContext()

        self.mox.ReplayAll()
        sched_manager = manager.BaseSchedulerDependentManager(host='fake_host')

        sched_manager.update_service_capabilities('fake_capabilities')
        sched_manager.publish_service_capabilities(ctx)
        self.mox.VerifyAll()
