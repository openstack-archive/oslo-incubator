# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import datetime

from oslo.config import cfg

from openstack.common.cache import cache
from openstack.common import timeutils
from tests import utils


class MemorycacheTest(utils.BaseTestCase):

    def setUp(self):
        self.client = cache.get_cache(cfg.CONF)
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

    def test_set_unset(self):
        self.client.set('foo', 'bar')
        self.client.unset('foo')
        self.assertEqual(self.client.get('foo'), None)

    def test_timeout(self):
        try:
            now = datetime.datetime.utcnow()
            timeutils.set_time_override(now)
            self.client.set('foo', 'bar', ttl=3)
            timeutils.set_time_override(now + datetime.timedelta(seconds=1))
            self.assertEqual(self.client.get('foo'), 'bar')
            timeutils.set_time_override(now + datetime.timedelta(seconds=3))
            self.assertEqual(self.client.get('foo'), None)
        finally:
            timeutils.clear_time_override()

    def test_timeout_unset(self):
        try:
            now = datetime.datetime.utcnow()
            timeutils.set_time_override(now)
            self.client.set('foo', 'bar', ttl=3)
            self.client.set('fooo', 'bar', ttl=4)
            self.client.set('foooo', 'bar', ttl=5)
            self.client.set('fooooo', 'bar', ttl=6)
            timeutils.set_time_override(now + datetime.timedelta(seconds=1))
            self.assertEqual(self.client.get('foo'), 'bar')
            self.assertEqual(self.client.get('fooo'), 'bar')
            self.assertEqual(self.client.get('foooo'), 'bar')
            self.assertEqual(self.client.get('fooooo'), 'bar')

            timeutils.set_time_override(now + datetime.timedelta(seconds=5))
            self.client.unset('foo')
            self.assertEqual(self.client.get('foo'), None)
            self.assertEqual(self.client.get('fooo'), None)
            self.assertEqual(self.client.get('foooo'), None)
            self.assertEqual(self.client.get('fooooo'), 'bar')
        finally:
            timeutils.clear_time_override()

    def test_timeout_unset_pop(self):
        try:
            now = datetime.datetime.utcnow()
            timeutils.set_time_override(now)
            self.client.set('foo', 'bar', ttl=3)
            self.client.set('fooo', 'bar', ttl=4)
            self.client.set('foooo', 'bar', ttl=5)
            self.client.set('fooooo', 'bar', ttl=6)
            timeutils.set_time_override(now + datetime.timedelta(seconds=1))
            self.assertEqual(self.client.get('foo'), 'bar')
            self.assertEqual(self.client.get('fooo'), 'bar')
            self.assertEqual(self.client.get('foooo'), 'bar')
            self.assertEqual(self.client.get('fooooo'), 'bar')

            timeutils.set_time_override(now + datetime.timedelta(seconds=4))

            # NOTE(flaper87): Let unset delete foooo and timeout
            # expire foo and fooo.
            self.client.unset('foooo')
            self.assertEqual(self.client.get('foo'), None)
            self.assertEqual(self.client.get('fooo'), None)
            self.assertEqual(self.client.get('foooo'), None)
            self.assertEqual(self.client.get('fooooo'), 'bar')
        finally:
            timeutils.clear_time_override()

    def test_incr(self):
        self.client.set('foo', 1)
        self.assertEquals(self.client.get('foo'), 1)

        self.client.incr('foo', 2)
        self.assertEquals(self.client.get('foo'), 3)

        self.client.incr('foo', -3)
        self.assertEquals(self.client.get('foo'), 0)

    def test_append(self):
        self.client.set('foo', [1, 2])
        self.assertEquals(self.client.get('foo'), [1, 2])

        self.client.append('foo', [3, 4])
        self.assertEquals(self.client.get('foo'), [1, 2, 3, 4])

    def test_set_many(self):
        self.client.set_many(dict(foo=0, bar=1))
        self.assertEquals(self.client.get('foo'), 0)
        self.assertEquals(self.client.get('bar'), 1)

    def test_get_many(self):
        self.client.set('foo', 0)
        self.client.set('bar', 1)
        values = self.client.get_many(["foo", "bar"])
        self.assertEquals(list(values), [('foo', 0), ('bar', 1)])
