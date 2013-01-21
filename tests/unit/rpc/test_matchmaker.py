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


LOG = logging.getLogger(__name__)


class _MatchMakerTestCase(unittest.TestCase):
    def test_valid_host_matches(self):
        queues = self.driver.queues(self.topic)
        matched_hosts = map(lambda x: x[1], queues)

        for host in matched_hosts:
            self.assertTrue(host in self.hosts)

    def test_fanout_host_matches(self):
        """For known hosts, see if they're in fanout."""
        queues = self.driver.queues("fanout~" + self.topic)
        matched_hosts = map(lambda x: x[1], queues)

        LOG.info("Received result from matchmaker: %s", queues)
        for host in self.hosts:
            self.assertTrue(host in matched_hosts)


class MatchMakerRingTestCase(_MatchMakerTestCase):
    def setUp(self):
        self.topic = "test"
        self.hosts = ['hello', 'world', 'foo', 'bar', 'baz']
        ring = {
            self.topic: self.hosts
        }
        self.driver = matchmaker.MatchMakerRing(ring)
        super(MatchMakerRingTestCase, self).setUp()

    def test_hosts_not_in_order(self):
        # Technically we could get randomly get
        # our results in-order. Running 5 times
        # to minimize false-negatives.
        for i in range(1, 5):
            tmp_host_list = []

            for host in self.hosts:
                queues = self.driver.queues(self.topic)
                self.assertTrue(len(queues) == 1)
                matched_host = queues[0][1]
                tmp_host_list.append(matched_host)

            self.assertFalse(self.hosts == tmp_host_list)


class MatchMakerRoundRobinRingTestCase(_MatchMakerTestCase):
    def setUp(self):
        self.topic = "test"
        self.hosts = ['hello', 'world', 'foo', 'bar', 'baz']
        ring = {
            self.topic: self.hosts
        }
        self.driver = matchmaker.MatchMakerRoundRobinRing(ring)
        super(MatchMakerRoundRobinRingTestCase, self).setUp()

    def test_hosts_in_order(self):
        # Technically we could get randomly get
        # our results in-order. Running 5 times
        # to minimize false-negatives.
        for i in range(1, 5):
            tmp_host_list = []
            for host in self.hosts:
                queues = self.driver.queues(self.topic)
                self.assertTrue(len(queues) == 1)
                matched_host = queues[0][1]
                tmp_host_list.append(matched_host)

            self.assertTrue(self.hosts == tmp_host_list)


class MatchMakerLocalhostTestCase(_MatchMakerTestCase):
    def setUp(self):
        self.driver = matchmaker.MatchMakerLocalhost()
        self.topic = "test"
        self.hosts = ['localhost']
        super(MatchMakerLocalhostTestCase, self).setUp()
