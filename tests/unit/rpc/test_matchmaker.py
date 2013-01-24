# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2012 Cloudscaling Group, Inc
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
import logging
import nose
from tests import utils as test_utils

from openstack.common import importutils
from openstack.common.rpc import matchmaker
from openstack.common import testutils

redis = importutils.try_import('redis')

LOG = logging.getLogger(__name__)
MatchMakerException = matchmaker.MatchMakerException


class _MatchMakerTestCase(test_utils.BaseTestCase):
    def test_valid_host_matches(self):
        queues = self.driver.queues(self.topic)
        matched_hosts = map(lambda x: x[1], queues)

        LOG.info("Received result from matchmaker: %s", matched_hosts)
        for host in matched_hosts:
            self.assertTrue(host in self.hosts)

    def test_fanout_host_matches(self):
        """For known hosts, see if they're in fanout."""
        queues = self.driver.queues("fanout~" + self.topic)
        matched_hosts = map(lambda x: x[1], queues)

        LOG.info("Received result from matchmaker: %s", matched_hosts)
        for host in self.hosts:
            self.assertTrue(host in matched_hosts)


class _MatchMakerDynRegTestCase(test_utils.BaseTestCase):
    def test_registers_host(self):
        """
        Registers a host, ensures it is registered.
        """
        self.driver.register(self.topic, self.hosts[0])

        match = self.driver.queues(self.topic)
        self.assertEqual(match[0][1], self.hosts[0])

    def test_unregister(self):
        """
        Tests that hosts unregister cleanly.
        Registers a host, ensures it is registered,
        then unregisters and ensures is no
        longer registered.
        """
        # Can only unregister if registrations work.
        self.test_registers_host()

        self.driver.unregister(self.topic, self.hosts[0])
        self.assertEqual(self.driver.queues(self.topic), [])


class MatchMakerFileTestCase(_MatchMakerTestCase):
    def setUp(self):
        self.topic = "test"
        self.hosts = ['hello', 'world', 'foo', 'bar', 'baz']
        ring = {
            self.topic: self.hosts
        }
        self.driver = matchmaker.MatchMakerRing(ring)
        super(MatchMakerFileTestCase, self).setUp()


class MatchMakerLocalhostTestCase(_MatchMakerTestCase):
    def setUp(self):
        self.driver = matchmaker.MatchMakerLocalhost()
        self.topic = "test"
        self.hosts = ['localhost']
        super(MatchMakerLocalhostTestCase, self).setUp()


class MatchMakerRedisTestCase(_MatchMakerTestCase):
    @testutils.skip_if(not redis, "Redis required for test.")
    def setUp(self):
        self.config(matchmaker_heartbeat_ttl=1)

        self.topic = "test"
        self.hosts = map(lambda x: 'mockhost-' + str(x), range(1, 10))

        try:
            self.driver = matchmaker.MatchMakerRedis()
            # Just test the connection
            self.driver.redis.ping()
        except:
            raise nose.SkipTest("Redis server not available.")

        # Wipe all entries...
        for host in self.hosts:
            self.driver.unregister(self.topic, host)

        for h in self.hosts:
            self.driver.register(self.topic, h)

        self.driver.start_heartbeat()

        super(MatchMakerRedisTestCase, self).setUp()

    @testutils.skip_if(not redis, "Redis required for test.")
    def tearDown(self):
        self.driver.stop_heartbeat()


class MatchMakerRedisHeartbeatTestCase(_MatchMakerDynRegTestCase):
    @testutils.skip_if(not redis, "Redis required for test.")
    def setUp(self):
        self.config(matchmaker_heartbeat_ttl=1)
        self.driver = matchmaker.MatchMakerRedis()
        self.topic = "test"
        self.hosts = map(lambda x: 'mockhost-' + str(x), range(1, 10))

        try:
            self.driver = matchmaker.MatchMakerRedis()
            # Just test the connection
            self.driver.redis.ping()
        except:
            raise nose.SkipTest("Redis server not available.")

        # Wipe all entries...
        for host in self.hosts:
            self.driver.unregister(self.topic, host)

        super(MatchMakerRedisHeartbeatTestCase, self).setUp()

    def test_expires_set(self):
        """
        Test that expirations are set.
        """
        self.driver.register(self.topic, self.hosts[0])

        ttl = self.driver.redis.ttl('.'.join((self.topic, self.hosts[0])))
        self.assertTrue(ttl > -1)

    def test_expires_hosts(self):
        """
        Tests that hosts expire.
        Registers a host, ensures it is registered,
        then waits for it to expire. Ensures is no
        longer registered.
        """
        self.driver.register(self.topic, self.hosts[0])

        key_host = '.'.join((self.topic, self.hosts[0]))

        ttl = self.driver.redis.ttl(key_host)
        eventlet.sleep(ttl + 1)
        ttl2 = self.driver.redis.ttl(key_host)

        # Tests that host has actually expired.
        self.assertEqual(ttl2, -1)

    def test_expired_hosts_removed(self):
        """
        Test that expired hosts are removed from results.
        """
        self.test_expires_hosts()
        self.assertEqual(self.driver.queues(self.topic), [])
