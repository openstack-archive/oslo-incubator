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

    cache_url = None

    def setUp(self):
        super(CacheBaseTest, self).setUp()
        self.client = cache.get_cache(self.cache_url)

    def tearDown(self):
        self.client.clear()
        super(CacheBaseTest, self).tearDown()

    def test_set_get(self):
        self.client['foo'] = 'bar'
        self.assertEqual(self.client['foo'], 'bar')

    def test_set_not_exists_get(self):
        self.client.set('foo', 'bar', not_exists=True)
        self.assertEqual(self.client.get('foo'), 'bar')

    def test_set_not_exists_false_get(self):
        self.client.set('foo', 'bar')
        ret = self.client.set('foo', 'baz', not_exists=True)
        self.assertFalse(ret)
        self.assertEqual(self.client.get('foo'), 'bar')

    def test_set_unset(self):
        self.client['foo'] = 'bar'
        self.assertEqual(self.client['foo'], 'bar')

        del self.client['foo']
        self.assertIsNone(self.client.get('foo'))

    def test_incr(self):
        self.client['foo'] = 1
        self.assertEqual(self.client['foo'], 1)

        self.client.incr('foo', 2)
        self.assertEqual(self.client['foo'], 3)

        self.client.incr('foo', -3)
        self.assertEqual(self.client['foo'], 0)

        self.client.incr('foo', -3)
        self.assertEqual(self.client['foo'], -3)

    def test_append(self):
        self.client['foo'] = [1, 2]
        self.assertEqual(self.client['foo'], [1, 2])

        self.client.append('foo', [3, 4])
        self.assertEqual(self.client['foo'], [1, 2, 3, 4])

    def test_set_many(self):
        self.client.set_many(dict(foo=0, bar=1))
        self.assertEqual(self.client['foo'], 0)
        self.assertEqual(self.client['bar'], 1)

    def test_unset_many(self):
        self.client['foo'] = 0
        self.client['bar'] = 1
        self.assertEqual(self.client['foo'], 0)
        self.assertEqual(self.client['bar'], 1)

        self.client.unset_many(['foo', 'bar'])
        self.assertIsNone(self.client['foo'])
        self.assertIsNone(self.client['bar'])

    def test_get_many(self):
        self.client['foo'] = 0
        self.client['bar'] = 1
        values = self.client.get_many(["foo", "bar"])
        self.assertEqual(list(values), [('foo', 0), ('bar', 1)])

    def test_timeout(self):
        self.client.set('foo', 'bar', ttl=1)
        self.assertEqual(self.client.get('foo'), 'bar')

        # NOTE(flaper87): It's not funny
        # to sleep tests but this test is
        # supposed to work for all backends.
        time.sleep(1)
        self.assertIsNone(self.client['foo'])

    def test_clear(self):
        self.client['foo'] = 0
        self.client['bar'] = 1

        self.client.clear()

        self.assertIsNone(self.client['foo'])
        self.assertIsNone(self.client['bar'])

    def test_exists(self):
        self.client['foo'] = 'bar'
        self.assertTrue(self.client.exists("foo"))

        self.client.unset('foo')
        self.assertFalse(self.client.exists("foo"))

    def test_update(self):
        self.client.update(foo='bar', bar='foo')
        self.assertEqual(self.client.get('foo'), 'bar')
        self.assertEqual(self.client.get('bar'), 'foo')
