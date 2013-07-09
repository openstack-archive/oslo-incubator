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

import itertools
import logging
import os
import socket

import fixtures
from oslo.config import cfg

from openstack.common.gettextutils import _
from tests.unit.rpc import common

try:
    from openstack.common.rpc import impl_zmq
except ImportError:
    impl_zmq = None

LOG = logging.getLogger(__name__)
FLAGS = cfg.CONF


def get_unused_port():
    """Returns an unused port on localhost."""
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
            LOG.warning(_("Assuming oslo-rpc-zmq-receiver is running."))
            LOG.warning(_("Using system zmq receiver deamon."))
        super(_RpcZmqBaseTestCase, self).setUp(
            topic=topic, topic_nested=topic_nested)

    def _close_reactor(self):
        if self.reactor:
            self.reactor.close()

    def test_cast_pathsep_topic(self):
        """Ensure topics with a contain a path separator result in error."""
        tmp_topic = self.topic_nested

        # All OS path separators
        badchars = itertools.ifilter(None,
                                     set((os.sep, os.altsep, '/', '\\')))
        for char in badchars:
            self.topic_nested = char.join(('hello', 'world'))
            try:
                # TODO(ewindisch): Determine which exception is raised.
                #                  pending bug #1121348
                self.assertRaises(Exception, self._test_cast,
                                  common.TestReceiver.echo, 42, {"value": 42},
                                  fanout=False)
            finally:
                self.topic_nested = tmp_topic

    def _test_cast_before_consumer(self):
        """Attempt casting before a consumer exists.

           Similar to _test_cast, but creates consumer after
           casting message with optional delay.
        """
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        self.rpc.cast(FLAGS, self.context, self.topic_nested, {
                      'method': 'curry', 'args': {"value": 42}})

        # Not a true global, but capitalized so
        # it is clear it is leaking scope into Nested()
        QUEUE = eventlet.queue.Queue()

        # We use the nested topic so we don't need QUEUE to be a proper
        # global, and do not keep state outside this test.
        class Nested(object):
            @staticmethod
            def curry(*args, **kwargs):
                QUEUE.put(common.TestReceiver.echo(*args, **kwargs))

        eventlet.sleep(.5)
        conn = self._create_consumer(Nested(), self.topic_nested, False)
        try:
            return QUEUE.get(True, .5)
        finally:
            conn.close()

    def test_cast_then_consume(self):
        """Assures message can be consumed if cast before consumer created.

           Note that this behavorism does not presently match that of the
           Kombu driver. The ZeroMQ driver expects to attempt delivery
           as long as the message timeout has not expired.

           Without this test, we'd have no coverage of curry() within
           _test_cast_before_consumer's Nested class.
        """
        value = self._test_cast_before_consumer()
        self.assertEqual(value, 42)

    def test_cast_timeout_not_consumed(self):
        """Timeout a message, create consumer, assure message not consumed.

           This test will attempt, but should fail, to execute
           the curry method of _test_cast_before_consumer's Nested class.
        """
        self.config(rpc_cast_timeout=0)
        self.assertRaises(eventlet.queue.Empty,
                          self._test_cast_before_consumer)


class RpcZmqBaseTopicTestCase(_RpcZmqBaseTestCase):
    """Base topic RPC ZMQ test case.

    This tests with topics such as 'test' and 'nested',
    without any .host appended. Stresses the matchmaker.
    """
    pass


class RpcZmqDirectTopicTestCase(_RpcZmqBaseTestCase):
    """Test communication directly to a host, tests use 'localhost'."""
    def setUp(self):
        super(RpcZmqDirectTopicTestCase, self).setUp(
            topic='test.127.0.0.1',
            topic_nested='nested.127.0.0.1')

    def test_cast_wrong_direct_topic_failure(self):
        try:
            self._test_cast(common.TestReceiver.echo, 42, {"value": 42},
                            fanout=False, topic_nested='nested.localhost')
        except Exception:
            return
        self.expectFailure("Message should not have been consumed.",
                           self.assertTrue, True)
