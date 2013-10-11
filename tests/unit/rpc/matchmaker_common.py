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


LOG = logging.getLogger(__name__)


class _MatchMakerDirectedTopicTestCase(object):
    """Mix-in to test directed topics."""
    def test_firstval_is_directed_topic(self):
        matches = self.driver.queues(self.topic)
        topics = map(lambda x: x[0], matches)

        for topic in topics:
            self.assertTrue('.' in topic)


class _MatchMakerTestCase(_MatchMakerDirectedTopicTestCase):
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


class _MatchMakerDynRegTestCase(object):
    def test_registers_host(self):
        """Registers a host, ensures it is registered."""
        self.driver.register(self.topic, self.hosts[0])

        match = self.driver.queues(self.topic)
        self.assertEqual(match[0][1], self.hosts[0])

    def test_unregister(self):
        """Tests that hosts unregister cleanly.

        Registers a host, ensures it is registered, then unregisters and
        ensures is no longer registered.
        """
        # Can only unregister if registrations work.
        self.test_registers_host()

        self.driver.unregister(self.topic, self.hosts[0])
        self.assertEqual(self.driver.queues(self.topic), [])
