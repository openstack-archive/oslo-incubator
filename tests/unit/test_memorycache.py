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

from openstack.common import memorycache
from openstack.common import test


class MemorycacheTest(test.BaseTestCase):
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
            self.client.set('foo-a', 'bar', time=1)
            self.client.set('foo-b', 'bar', time=60)

            time_mock.return_value = now + 2
            self.assertEqual(len(self.client.cache), 2)
            self.client.clean_expired_items()
            self.assertEqual(len(self.client.cache), 1)
