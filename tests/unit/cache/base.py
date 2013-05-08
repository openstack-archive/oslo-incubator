# Copyright 2013 Red Hat, Inc.
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

from openstack.common.cache import cache
from tests import utils


class CacheBaseTest(utils.BaseTestCase):

    def setUp(self):
        super(CacheBaseTest, self).setUp()
        self.client = cache.get_cache(self.conf)

    def tearDown(self):
        self.client.flush()
        super(CacheBaseTest, self).tearDown()

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

    def test_set_unset(self):
        self.client.set('foo', 'bar')
        self.client.unset('foo')
        self.assertIsNone(self.client.get('foo'))

    def test_incr(self):
        self.client.set('foo', 1)
        self.assertEqual(self.client.get('foo'), 1)

        self.client.incr('foo', 2)
        self.assertEqual(self.client.get('foo'), 3)

        self.client.incr('foo', -3)
        self.assertEqual(self.client.get('foo'), 0)

    def test_append(self):
        self.client.set('foo', [1, 2])
        self.assertEqual(self.client.get('foo'), [1, 2])

        self.client.append('foo', [3, 4])
        self.assertEqual(self.client.get('foo'), [1, 2, 3, 4])

    def test_set_many(self):
        self.client.set_many(dict(foo=0, bar=1))
        self.assertEqual(self.client.get('foo'), 0)
        self.assertEqual(self.client.get('bar'), 1)

    def test_unset_many(self):
        self.client.set('foo', 0)
        self.client.set('bar', 1)
        self.assertEqual(self.client.get('foo'), 0)
        self.assertEqual(self.client.get('bar'), 1)
        self.client.unset_many(['foo', 'bar'])
        self.assertIsNone(self.client.get('foo'))
        self.assertIsNone(self.client.get('bar'))

    def test_get_many(self):
        self.client.set('foo', 0)
        self.client.set('bar', 1)
        values = self.client.get_many(["foo", "bar"])
        self.assertEqual(list(values), [('foo', 0), ('bar', 1)])

    def test_timeout(self):
        self.client.set('foo', 'bar', ttl=1)
        self.assertEqual(self.client.get('foo'), 'bar')

        # NOTE(flaper87): It's not funny
        # to sleep tests but this test is
        # supposed to work for all backends.
        time.sleep(1)
        self.assertIsNone(self.client.get('foo'))

    def test_flush(self):
        self.client.set('foo', 0)
        self.client.set('bar', 1)

        self.client.flush()

        self.assertIsNone(self.client.get('foo'))
        self.assertIsNone(self.client.get('bar'))

    def test_exists(self):
        self.client.set('foo', "value")
        self.assertTrue(self.client.exists("foo"))

        self.client.unset('foo')
        self.assertFalse(self.client.exists("foo"))
