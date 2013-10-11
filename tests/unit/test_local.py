# Copyright 2012 OpenStack Foundation.
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

import threading

from openstack.common import local
from openstack.common import test


class Dict(dict):
    """Make weak referencable object."""
    pass


class LocalStoreTestCase(test.BaseTestCase):
    v1 = Dict(a='1')
    v2 = Dict(a='2')
    v3 = Dict(a='3')

    def setUp(self):
        super(LocalStoreTestCase, self).setUp()
        # NOTE(mrodden): we need to make sure that local store
        # gets imported in the current python context we are
        # testing in (eventlet vs normal python threading) so
        # we test the correct type of local store for the current
        # threading model
        reload(local)

    def test_thread_unique_storage(self):
        """Make sure local store holds thread specific values."""
        expected_set = []
        local.store.a = self.v1

        def do_something():
            local.store.a = self.v2
            expected_set.append(getattr(local.store, 'a'))

        def do_something2():
            local.store.a = self.v3
            expected_set.append(getattr(local.store, 'a'))

        t1 = threading.Thread(target=do_something)
        t2 = threading.Thread(target=do_something2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        expected_set.append(getattr(local.store, 'a'))

        self.assertTrue(self.v1 in expected_set)
        self.assertTrue(self.v2 in expected_set)
        self.assertTrue(self.v3 in expected_set)
