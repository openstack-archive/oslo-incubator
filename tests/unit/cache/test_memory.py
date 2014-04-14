# Copyright 2013 Red Hat, Inc.
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

try:
    import mock
except ImportError:
    import unittest.mock

from tests.unit.cache import base


class MemorycacheTest(base.CacheBaseTest):
    """Test memory backend

    Since it is the default driver, nothing
    has to be done here.
    """

    cache_url = 'memory://'

    def test_timeout(self):
        now = time.time()
        with mock.patch('time.time') as time_mock:
            time_mock.return_value = now
            self.client.set('foo', 'bar', ttl=3)
            time_mock.return_value = now + 1
            self.assertEqual(self.client.get('foo'), 'bar')
            time_mock.return_value = now + 3
            self.assertIsNone(self.client.get('foo'))

    def test_timeout_unset(self):
        now = time.time()
        with mock.patch('time.time') as time_mock:
            time_mock.return_value = now
            self.client.set('foo', 'bar', ttl=3)
            self.client.set('fooo', 'bar', ttl=4)
            self.client.set('foooo', 'bar', ttl=5)
            self.client.set('fooooo', 'bar', ttl=6)
            time_mock.return_value = now + 1
            self.assertEqual(self.client.get('foo'), 'bar')
            self.assertEqual(self.client.get('fooo'), 'bar')
            self.assertEqual(self.client.get('foooo'), 'bar')
            self.assertEqual(self.client.get('fooooo'), 'bar')

            time_mock.return_value = now + 5
            del self.client['foo']
            self.assertIsNone(self.client.get('foo'))
            self.assertIsNone(self.client.get('fooo'))
            self.assertIsNone(self.client.get('foooo'))
            self.assertEqual(self.client.get('fooooo'), 'bar')

    def test_timeout_unset_pop(self):
        now = time.time()
        with mock.patch('time.time') as time_mock:
            time_mock.return_value = now
            self.client.set('foo', 'bar', ttl=3)
            self.client.set('fooo', 'bar', ttl=4)
            self.client.set('foooo', 'bar', ttl=5)
            self.client.set('fooooo', 'bar', ttl=6)
            time_mock.return_value = now + 1
            self.assertEqual(self.client.get('foo'), 'bar')
            self.assertEqual(self.client.get('fooo'), 'bar')
            self.assertEqual(self.client.get('foooo'), 'bar')
            self.assertEqual(self.client.get('fooooo'), 'bar')

            time_mock.return_value = now + 4

            # NOTE(flaper87): Let unset delete foooo and timeout
            # expire foo and fooo.
            del self.client['foooo']
            self.assertIsNone(self.client.get('foo'))
            self.assertIsNone(self.client.get('fooo'))
            self.assertIsNone(self.client.get('foooo'))
            self.assertEqual(self.client.get('fooooo'), 'bar')
