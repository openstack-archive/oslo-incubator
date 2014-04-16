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

from oslotest import base as test_base

from openstack.common.rpc import matchmaker
from openstack.common.rpc import matchmaker_ring
from tests.unit.rpc import matchmaker_common as common


LOG = logging.getLogger(__name__)


class MatchMakerFileTestCase(test_base.BaseTestCase,
                             common._MatchMakerTestCase):
    def setUp(self):
        super(MatchMakerFileTestCase, self).setUp()
        self.topic = "test"
        self.hosts = ['hello', 'world', 'foo', 'bar', 'baz']
        ring = {
            self.topic: self.hosts
        }
        self.driver = matchmaker_ring.MatchMakerRing(ring)


class MatchMakerLocalhostTestCase(test_base.BaseTestCase,
                                  common._MatchMakerTestCase):
    def setUp(self):
        super(MatchMakerLocalhostTestCase, self).setUp()
        self.driver = matchmaker.MatchMakerLocalhost()
        self.topic = "test"
        self.hosts = ['localhost']


class MatchMakerDirectExchangeTestCase(test_base.BaseTestCase, common.
                                       _MatchMakerDirectedTopicTestCase):
    """Test lookups against a directed topic."""
    def setUp(self):
        super(MatchMakerDirectExchangeTestCase, self).setUp()
        self.driver = matchmaker.MatchMakerLocalhost()
        self.topic = "test.localhost"
        self.hosts = ['localhost']


class MatchMakerStubTestCase(test_base.BaseTestCase,
                             common._MatchMakerDirectedTopicTestCase):
    """Test lookups against the stub/no-op matchmaker."""
    def setUp(self):
        super(MatchMakerStubTestCase, self).setUp()
        self.driver = matchmaker.MatchMakerStub()
        self.topic = "test.localhost"
        self.hosts = ['localhost']
