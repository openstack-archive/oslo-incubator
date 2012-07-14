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
from openstack.common import rpc
from openstack.common import testutils
from openstack.common import utils
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
#    @testutils.skip_if(zmq is None, "Test requires zmq")
    @testutils.skip_if(True, "Zmq tests broken on jenkins")
    def setUp(self, topic='test', topic_nested='nested'):
        if not impl_zmq:
            return None

        self.reactor = None
        self.rpc = impl_zmq

        FLAGS.set_override('rpc_zmq_bind_address', '127.0.0.1')
        FLAGS.set_override('rpc_zmq_host', '127.0.0.1')
        FLAGS.set_override('rpc_response_timeout', 5)
        FLAGS.set_default('rpc_zmq_matchmaker',
                          'mod_matchmaker.MatchMakerLocalhost')

        # We'll change this if we detect no daemon running.
        ipc_dir = FLAGS.rpc_zmq_ipc_dir

        # Only launch the router if it isn't running independently.
        if not os.path.exists(os.path.join(ipc_dir, "zmq_topic_zmq_replies")):
            LOG.info(_("Running internal zmq receiver."))
            # The normal ipc_dir default needs to run as root,
            # /tmp is easier within a testing environment.
            FLAGS.set_default('rpc_zmq_ipc_dir', '/tmp/openstack-zmq.ipc.test')

            # Value has changed.
            ipc_dir = FLAGS.rpc_zmq_ipc_dir

        try:
            # Only launch the receiver if it isn't running independently.
            # This is checked again, with the (possibly) new ipc_dir.
            if os.path.exists(os.path.join(ipc_dir, "zmq_topic_zmq_replies")):
                LOG.warning(_("Detected zmq-receiver socket. "
                              "Assuming nova-rpc-zmq-receiver is running."))
                return

            if not os.path.isdir(ipc_dir):
                os.mkdir(ipc_dir)

            self.reactor = impl_zmq.ZmqProxy(FLAGS)
            consume_in = "tcp://%s:%s" % \
                (FLAGS.rpc_zmq_bind_address,
                 FLAGS.rpc_zmq_port)
            consumption_proxy = impl_zmq.InternalContext(None)

            self.reactor.register(consumption_proxy,
                                  consume_in,
                                  zmq.PULL,
                                  out_bind=True)
            self.reactor.consume_in_thread()
        except zmq.ZMQError:
            assert False, _("Could not create ZeroMQ receiver daemon. "
                            "Socket may already be in use.")
        except OSError:
            assert False, _("Could not create IPC directory %s") % (ipc_dir, )
        finally:
            super(_RpcZmqBaseTestCase, self).setUp(
                topic=topic, topic_nested=topic_nested)

    def tearDown(self):
        if not impl_zmq:
            return None
        if self.reactor:
            self.reactor.close()

            try:
                utils.execute('rm', '-rf', FLAGS.rpc_zmq_ipc_dir)
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
