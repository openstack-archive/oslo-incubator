#    Copyright 2013 Cloudscaling Group, Inc
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

import logging

import eventlet
from oslotest import base as test_base
from six import moves

from openstack.common.fixture import config
from openstack.common import importutils
from openstack.common.rpc import matchmaker_redis as matchmaker
from tests.unit.rpc import matchmaker_common as common

redis = importutils.try_import('redis')

LOG = logging.getLogger(__name__)


class MatchMakerRedisLookupTestCase(test_base.BaseTestCase,
                                    common._MatchMakerTestCase):
    """Test lookups against the Redis matchmaker."""
    def setUp(self):
        super(MatchMakerRedisLookupTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        if not redis:
            self.skipTest("Redis required for test.")

        self.config(matchmaker_heartbeat_ttl=1)

        self.topic = "test"
        self.hosts = map(lambda x: 'mockhost-' + str(x), range(1, 10))

        try:
            self.driver = matchmaker.MatchMakerRedis()
            self.driver.redis.connection_pool.connection_kwargs[
                'socket_timeout'] = 1
            # Test the connection
            self.driver.redis.ping()
        except redis.exceptions.ConnectionError:
            raise self.skipTest("Redis server not available.")

        # Wipe all entries...
        for host in self.hosts:
            self.driver.unregister(self.topic, host)

        for h in self.hosts:
            self.driver.register(self.topic, h)

        self.driver.start_heartbeat()

    def tearDown(self):
        super(MatchMakerRedisLookupTestCase, self).tearDown()
        if not redis:
            self.skipTest("Redis required for test.")
        self.driver.stop_heartbeat()


class MatchMakerRedisHeartbeatTestCase(test_base.BaseTestCase,
                                       common._MatchMakerDynRegTestCase):
    """Test the ability to register and perform heartbeats."""
    def setUp(self):
        super(MatchMakerRedisHeartbeatTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        if not redis:
            self.skipTest("Redis required for test.")

        self.config(matchmaker_heartbeat_ttl=1)
        self.driver = matchmaker.MatchMakerRedis()
        self.topic = "test"
        self.hosts = map(lambda x: 'mockhost-' + str(x), range(1, 10))

        try:
            self.driver = matchmaker.MatchMakerRedis()
            self.driver.redis.connection_pool.connection_kwargs[
                'socket_timeout'] = 1
            # Test the connection
            self.driver.redis.ping()
        except redis.exceptions.ConnectionError:
            raise self.skipTest("Redis server not available.")

        # Wipe all entries...
        for host in self.hosts:
            self.driver.unregister(self.topic, host)

    def test_expires_set(self):
        """Test that expirations are set."""
        self.driver.register(self.topic, self.hosts[0])

        ttl = self.driver.redis.ttl('.'.join((self.topic, self.hosts[0])))
        self.assertTrue(ttl > -1)

    def test_expires_hosts(self):
        """Tests that hosts expire.

        Registers a host, ensures it is registered, then waits for it to
        expire. Ensures is no longer registered.
        """
        self.driver.register(self.topic, self.hosts[0])

        key_host = '.'.join((self.topic, self.hosts[0]))

        ttl = self.driver.redis.ttl(key_host)
        eventlet.sleep(ttl + 1)
        ttl2 = self.driver.redis.ttl(key_host)

        # Tests that host has actually expired.
        self.assertEqual(ttl2, None)

    def test_expired_hosts_removed(self):
        """Test that expired hosts are removed from results."""
        self.test_expires_hosts()
        self.assertEqual(self.driver.queues(self.topic), [])


class MatchMakerRedisTestCase(test_base.BaseTestCase):
    """Generic tests that do not require a Redis server."""
    def test_redis_import_exception(self):
        """Try initializing an object without redis."""
        matchmaker.redis = None
        self.assertRaises(ImportError, matchmaker.MatchMakerRedis)
        moves.reload_module(matchmaker)
