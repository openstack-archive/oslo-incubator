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

import logging
import unittest

from openstack.common.rpc import matchmaker
from tests import utils as test_utils


LOG = logging.getLogger(__name__)


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


class _MatchMakerHeartbeatTestCase(test_utils.BaseTestCase):
    def test_expires_host(self):
        """
        Registers a host, ensures it is registered,
        then waits for it to expire. Ensures is no
        longer registered.
        """
        self.driver.register(self.topic, self.hosts[0])

        # Raises if doesn't work.
        self.driver.queues(self.topic)
        # Timeout is set to 1 second...
        eventlet.sleep(2)

        assertRaises(MatchMakerException,
                     self.driver.queues,
                     self.topic)

    def test_unregister(self):
        """
        Registers a host, ensures it is registered,
        then unregisters and ensures is no
        longer registered.
        """
        self.driver.register(self.topic, self.hosts[0])

        # Raises if it doesn't work...
        self.driver.queues(self.topic)

        self.driver.unregister(self.topic, self.hosts[0])

        assertRaises(MatchMakerException,
                     self.driver.queues,
                     self.topic)

    def test_registers_host(self):
        """
        Registers a host, ensures it is registered.
        """
        self.driver.register(self.topic, self.hosts[0])

        host = self.driver.queues(self.topic)
        self.assertIn(host, self.hosts)


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
    def setUp(self):
        self.config(matchmaker_heartbeat_ttl=1)
        #self.config(matchmaker_redis_host='sock')
        self.driver = matchmaker.MatchMakerRedis()
        self.topic = "test"
        self.hosts = map(lambda x: 'mockhost-' + str(x), range(1, 10))

        for h in self.hosts:
            self.driver.register(self.topic, h)
        self.driver.start_heartbeat()

        super(MatchMakerRedisTestCase, self).setUp()
