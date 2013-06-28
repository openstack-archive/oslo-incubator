# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import eventlet
import threading

from openstack.common import local
from tests import utils


class Dict(dict):
    """Make weak referencable object."""
    pass


class LocalStoreTestCase(utils.BaseTestCase):
    v1 = Dict(a='1')
    v2 = Dict(a='2')
    v3 = Dict(a='3')

    def setUp(self):
        super(LocalStoreTestCase, self).setUp()

        self.eventlet_builder = local.LocalStoreBuilder(eventlet)  # noqa
        self.threading_builder = local.LocalStoreBuilder()         # noqa

    def test_local_store_builder_eventlet(self):
        """Make sure LocalStoreBuilder object builds an eventlet local store
           object.
        """
        self.assertIsInstance(type(self.eventlet_builder), object)

    def test_local_store_builder_threading(self):
        """Make sure LocalStoreBuilder object builds an eventlet local store
           object.
        """
        self.assertIsInstance(type(self.threading_builder), object)

    def test_local_store_builder_strong_store_eventlet(self):
        """Test to make sure our LocalStoreBuilder object's strong_store is in
           fact the same as eventlet.corolocal.local when using Eventlet.
        """
        self.assertEqual(self.eventlet_builder.strong_store,
                         eventlet.corolocal.local)

    def test_local_store_builder_strong_store_threading(self):
        """Test to make sure our LocalStoreBuilder object's strong_store is in
           fact the same as threading.local when using threading from Python
           standard library.
        """
        self.assertEqual(self.threading_builder.strong_store, threading.local)

    def test_thread_unique_storage(self):
        """Make sure local store holds thread specific values."""
        expected_set = []

        def do_something():
            local.store.a = self.v2
            expected_set.append(getattr(local.store, 'a'))

        def do_something2():
            local.store.a = self.v3
            expected_set.append(getattr(local.store, 'a'))

        eventlet.spawn(do_something).wait()
        eventlet.spawn(do_something2).wait()
        local.store.a = self.v1
        expected_set.append(getattr(local.store, 'a'))

        self.assertTrue(self.v1 in expected_set)
        self.assertTrue(self.v2 in expected_set)
        self.assertTrue(self.v3 in expected_set)

    def test_threading_unique_storage(self):
        """Test thread storage using threading library from the Python
           standard library, instead of Eventlet
        """
        expected_set = []

        def do_something():
            local.store.a = self.v2
            expected_set.append(getattr(local.store, 'a'))

        def do_something2():
            local.store.a = self.v3
            expected_set.append(getattr(local.store, 'a'))

        t1 = threading.Thread(target=do_something)
        t1.start()
        t2 = threading.Thread(target=do_something2)
        t2.start()

        local.store.a = self.v1
        expected_set.append(getattr(local.store, 'a'))

        self.assertTrue(self.v1 in expected_set)
        self.assertTrue(self.v2 in expected_set)
        self.assertTrue(self.v3 in expected_set)
