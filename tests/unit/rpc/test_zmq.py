# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Cloudscaling Group, Inc.
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
"""
Unit Tests for remote procedure calls using zeromq
"""

import eventlet
eventlet.monkey_patch()

import logging
import os

from openstack.common import cfg
from openstack.common import exception
from openstack.common.gettextutils import _
from openstack.common import processutils
from openstack.common import rpc
from openstack.common import testutils
from tests.unit.rpc import common

try:
    from eventlet.green import zmq
    from openstack.common.rpc import impl_zmq
except ImportError:
    zmq = None
    impl_zmq = None

LOG = logging.getLogger(__name__)
FLAGS = cfg.CONF


class _RpcZmqBaseTestCase(common.BaseRpcTestCase):
    # TESTCNT needs to be a class var as each run
    # by subclasses must have a unique identifier
    TESTCNT = 0

    @testutils.skip_if(not impl_zmq, "ZeroMQ library required")
    def setUp(self, topic='test', topic_nested='nested'):
        _RpcZmqBaseTestCase.TESTCNT += 1
        testcnt = _RpcZmqBaseTestCase.TESTCNT

        self.reactor = None
        self.rpc = impl_zmq

        self.config(rpc_zmq_bind_address='127.0.0.1')
        self.config(rpc_zmq_host='127.0.0.1')
        self.config(rpc_response_timeout=5)
        self.config(rpc_zmq_matchmaker='mod_matchmaker.MatchMakerLocalhost')

        # We'll change this if we detect no daemon running.
        ipc_dir = FLAGS.rpc_zmq_ipc_dir

        # Only launch the router if it isn't running.
        if not os.path.exists(os.path.join(ipc_dir, "zmq_topic_zmq_replies")):
            # NOTE(ewindisch): rpc_zmq_port and internal_ipc_dir must
            #                  increment to avoid async socket
            #                  closing/wait delays causing races
            #                  between tearDown() and setUp()
            self.config(rpc_zmq_port=9500 + testcnt)
            internal_ipc_dir = "/tmp/openstack-zmq.ipc.test.%s" % testcnt
            self.config(rpc_zmq_ipc_dir=internal_ipc_dir)

            LOG.info(_("Running internal zmq receiver."))
            reactor = impl_zmq.ZmqProxy(FLAGS)
            reactor.consume_in_thread()
        else:
            LOG.warning(_("Detected zmq-receiver socket."))
            LOG.warning(_("Assuming nova-rpc-zmq-receiver is running."))
            LOG.warning(_("Using system zmq receiver deamon."))

        super(_RpcZmqBaseTestCase, self).setUp(
            topic=topic, topic_nested=topic_nested)

    @testutils.skip_if(not impl_zmq, "ZeroMQ library required")
    def tearDown(self):
        if self.reactor:
            self.reactor.close()

            try:
                processutils.execute('rm', '-rf', FLAGS.rpc_zmq_ipc_dir)
            except exception.Error:
                pass

        super(_RpcZmqBaseTestCase, self).tearDown()


class RpcZmqBaseTopicTestCase(_RpcZmqBaseTestCase):
    """
    This tests with topics such as 'test' and 'nested',
    without any .host appended. Stresses the matchmaker.
    """
    pass


class RpcZmqDirectTopicTestCase(_RpcZmqBaseTestCase):
    """
    Test communication directly to a host,
    tests use 'localhost'.
    """
    def setUp(self):
        super(RpcZmqDirectTopicTestCase, self).setUp(
            topic='test.localhost',
            topic_nested='nested.localhost')
