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
import socket

import fixtures

from openstack.common import cfg
from openstack.common import exception
from openstack.common.gettextutils import _
from openstack.common import processutils
from openstack.common import rpc
from tests.unit.rpc import common

try:
    from eventlet.green import zmq
    from openstack.common.rpc import impl_zmq
except ImportError:
    zmq = None
    impl_zmq = None

LOG = logging.getLogger(__name__)
FLAGS = cfg.CONF


def get_unused_port():
    """
    Returns an unused port on localhost.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 0))
    addr, port = s.getsockname()
    s.close()
    return port


class _RpcZmqBaseTestCase(common.BaseRpcTestCase):
    rpc = impl_zmq

    def setUp(self, topic='test', topic_nested='nested'):
        if not impl_zmq:
            self.skipTest("ZeroMQ library required")

        self.reactor = None
        self.rpc = impl_zmq

        self.config(rpc_zmq_bind_address='127.0.0.1')
        self.config(rpc_zmq_host='127.0.0.1')
        self.config(rpc_response_timeout=5)
        self.rpc._get_matchmaker(host='127.0.0.1')

        # We'll change this if we detect no daemon running.
        ipc_dir = FLAGS.rpc_zmq_ipc_dir

        # Only launch the router if it isn't running.
        if not os.path.exists(os.path.join(ipc_dir, "zmq_topic_zmq_replies")):
            # NOTE(ewindisch): rpc_zmq_port and internal_ipc_dir must
            #                  increment to avoid async socket
            #                  closing/wait delays causing races
            #                  between tearDown() and setUp()
            # TODO(mordred): replace this with testresources once we're on
            #                testr
            self.config(rpc_zmq_port=get_unused_port())
            internal_ipc_dir = self.useFixture(fixtures.TempDir()).path
            self.config(rpc_zmq_ipc_dir=internal_ipc_dir)

            LOG.info(_("Running internal zmq receiver."))
            reactor = impl_zmq.ZmqProxy(FLAGS)
            self.addCleanup(self._close_reactor)
            reactor.consume_in_thread()
        else:
            LOG.warning(_("Detected zmq-receiver socket."))
            LOG.warning(_("Assuming nova-rpc-zmq-receiver is running."))
            LOG.warning(_("Using system zmq receiver deamon."))
        super(_RpcZmqBaseTestCase, self).setUp(
            topic=topic, topic_nested=topic_nested)

    def _close_reactor(self):
        if self.reactor:
            self.reactor.close()


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
            topic='test.127.0.0.1',
            topic_nested='nested.127.0.0.1')
