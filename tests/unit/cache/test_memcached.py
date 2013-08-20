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

import testtools

try:
    import memcache
except ImportError:
    memcache = None

from openstack.common.cache import cache
from tests.unit.cache import base
from tests import utils


class MemcachedTest(base.CacheBaseTest):

    @testtools.skipUnless(memcache, "memcache not available")
    def setUp(self):
        super(MemcachedTest, self).setUp()
        self.config(cache_backend='memcached', group='oslo_cache')
        self.client = cache.get_cache(self.conf)

        for s in self.client._cache.servers:
            if s.connect():
                break
        else:
            self.skipTest("No memcached servers found")


class MockedMemcachedTests(utils.BaseTestCase):

    def setUp(self):

        if not memcache:
            self.skipTest("python-memcache required")

        super(MockedMemcachedTests, self).setUp()

        # NOTE(flaper87): We need to do this to register
        # configs and groups and then be able to override
        # them.
        self.client = cache.get_cache(self.conf)
        self.config(cache_backend='memcached', group='oslo_cache')
        self.client = cache.get_cache(self.conf)

        def do_nothing(*args, **kwargs):
            pass

        self.stubs.Set(memcache.Client, 'set', do_nothing)
        self.stubs.Set(memcache.Client, 'set_multi', do_nothing)

    def _return_val(self, ret_val):
        def fake_return(*args, **kwargs):
            return ret_val
        return fake_return

    def test_ttl_method(self):
        self.assertEquals(self.client._get_ttl(30), 30)
        t = time.time()
        self.stubs.Set(time, 'time', self._return_val(t))
        max_ttl = 2592001
        self.assertEqual(self.client._get_ttl(max_ttl), int(t) + max_ttl)

    def test_set_get(self):
        self.client.set('foo', 'bar')
        self.stubs.Set(memcache.Client, 'get', self._return_val('bar'))
        self.assertEqual(self.client.get('foo'), 'bar')

    def test_set_and_get_many(self):
        data = {'foo': 0, 'bar': 1}
        self.client.set_many(data)

        self.stubs.Set(memcache.Client, 'get_multi', self._return_val(data))
        values = self.client.get_many(["foo", "bar"])
        self.assertEqual(list(values), [('foo', 0), ('bar', 1)])

    def test_get_many_no_rst(self):
        self.stubs.Set(memcache.Client, 'get_multi', self._return_val({}))
        self.assertEqual(list(self.client.get_many(["foo", "bar"])),
                         [('foo', None), ('bar', None)])

    def test_incr(self):
        self.stubs.Set(memcache.Client, 'incr', self._return_val(1))
        self.stubs.Set(memcache.Client, 'decr', self.fail)

        # NOTE(flaper87): Since 1 >= 0, this should
        # return 1 (based on the mock)
        self.assertEqual(self.client.incr('foo', 1), 1)

    def test_incr_negative(self):
        self.stubs.Set(memcache.Client, 'decr', self._return_val(1))
        self.stubs.Set(memcache.Client, 'incr', self.fail)

        # NOTE(flaper87): Since -1 < 0, this should
        # return 1 (based on the mock)
        self.assertEqual(self.client.incr('foo', -1), 1)
