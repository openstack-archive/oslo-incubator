# Copyright 2013 Nebula, Inc.
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

import time

import mock
from oslotest import base as test_base

from openstack.common import memorycache


class MemorycacheTest(test_base.BaseTestCase):
    def setUp(self):
        self.client = memorycache.get_client()
        super(MemorycacheTest, self).setUp()

    def test_set_get(self):
        self.client.set('foo', 'bar')
        self.assertEqual(self.client.get('foo'), 'bar')

    def test_add_get(self):
        self.client.add('foo', 'bar')
        self.assertEqual(self.client.get('foo'), 'bar')

    def test_set_add_get(self):
        self.client.set('foo', 'bar')
        self.client.add('foo', 'baz')
        self.assertEqual(self.client.get('foo'), 'bar')

    def test_set_delete(self):
        self.client.set('foo', 'bar')
        self.client.delete('foo')
        self.assertIsNone(self.client.get('foo'))

    def test_timeout(self):
        now = time.time()
        with mock.patch('time.time') as time_mock:
            time_mock.return_value = now
            self.client.set('foo', 'bar', time=3)
            time_mock.return_value = now + 1
            self.assertEqual(self.client.get('foo'), 'bar')
            time_mock.return_value = now + 3
            self.assertIsNone(self.client.get('foo'))

    def test_eviction(self):
        now = time.time()
        with mock.patch('time.time') as time_mock:
            time_mock.return_value = now
            self.client.set('foo-1', 'bar-1', time=1)
            self.client.set('foo-2', 'bar-2', time=60)

            time_mock.return_value = now + 2
            self.assertEqual(2, len(self.client.cache))
            self.assertEqual(2, len(self.client.priority_queue))
            self.assertEqual('bar-2', self.client.get('foo-2'))
            self.assertEqual(1, len(self.client.cache))
            self.assertEqual(1, len(self.client.priority_queue))
            self.assertEqual('bar-2', self.client.get('foo-2'))

    def test_duplicate_keys(self):
            self.client.set('foo-1', 'bar-1', time=1)
            self.client.set('foo-1', 'bar-1', time=5)
            self.client.set('foo-1', 'bar-1', time=1)
            self.client.set('foo-1', 'bar-1', time=99)
            self.assertEqual(1, len(self.client.priority_queue))
            self.assertEqual(1, len(self.client.cache))

    def test_build_cache(self):
        """Construct a cache that will break if not heapified on
        deletion of keys."""
        now = 0
        with mock.patch('time.time') as time_mock:
            time_mock.return_value = now
            self.client.set('key-4', 'val-0', time=1)
            self.client.set('key-5', 'val-0', time=7)
            self.client.set('key-0', 'val-0', time=5)
            self.client.set('key-7', 'val-0', time=5)
            self.client.set('key-8', 'val-0', time=5)
            self.client.set('key-1', 'val-1', time=40)
            self.client.set('key-2', 'val-2', time=20)
            self.client.set('key-3', 'val-3', time=10)
            self.client.set('key-6', 'val-6', time=30)

            self.client.delete('key-4')
            self.client.delete('key-5')
            self.client.delete('key-0')
            self.client.delete('key-7')
            self.client.delete('key-8')

            time_mock.return_value = now + 30
            self.assertEqual('val-1', self.client.get('key-1'))
            self.assertEqual(1, len(self.client.priority_queue))
            self.assertEqual(1, len(self.client.cache))
