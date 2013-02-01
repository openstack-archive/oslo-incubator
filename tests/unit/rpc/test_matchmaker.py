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

from openstack.common.rpc import matchmaker
from tests import utils


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


class MatchMakerFileTestCase(utils.BaseTestCase, _MatchMakerTestCase):
    def setUp(self):
        super(MatchMakerFileTestCase, self).setUp()
        self.topic = "test"
        self.hosts = ['hello', 'world', 'foo', 'bar', 'baz']
        ring = {
            self.topic: self.hosts
        }
        self.driver = matchmaker.MatchMakerRing(ring)


class MatchMakerLocalhostTestCase(utils.BaseTestCase, _MatchMakerTestCase):
    def setUp(self):
        super(MatchMakerLocalhostTestCase, self).setUp()
        self.driver = matchmaker.MatchMakerLocalhost()
        self.topic = "test"
        self.hosts = ['localhost']


class MatchMakerDirectExchangeTestCase(utils.BaseTestCase, _MatchMakerDirectedTopicTestCase):
    """Test lookups against a directed topic."""
    def setUp(self):
        super(MatchMakerDirectExchangeTestCase, self).setUp()
        self.driver = matchmaker.MatchMakerLocalhost()
        self.topic = "test.localhost"
        self.hosts = ['localhost']
