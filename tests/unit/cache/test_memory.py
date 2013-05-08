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

import datetime

from openstack.common import timeutils
from tests.unit.cache import base


class MemorycacheTest(base.CacheBaseTest):
    """Test memory backend

    Since it is the default driver, nothing
    has to be done here.
    """

    cache_url = 'memory://'

    def test_timeout(self):
        try:
            now = datetime.datetime.utcnow()
            timeutils.set_time_override(now)
            self.client.set('foo', 'bar', ttl=3)
            timeutils.set_time_override(now + datetime.timedelta(seconds=1))
            self.assertEqual(self.client.get('foo'), 'bar')
            timeutils.set_time_override(now + datetime.timedelta(seconds=3))
            self.assertIsNone(self.client.get('foo'))
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
            self.assertIsNone(self.client.get('foo'))
            self.assertIsNone(self.client.get('fooo'))
            self.assertIsNone(self.client.get('foooo'))
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
            self.assertIsNone(self.client.get('foo'))
            self.assertIsNone(self.client.get('fooo'))
            self.assertIsNone(self.client.get('foooo'))
            self.assertEqual(self.client.get('fooooo'), 'bar')
        finally:
            timeutils.clear_time_override()
