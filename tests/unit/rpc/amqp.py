# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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
Unit Tests for AMQP-based remote procedure calls
"""

import logging

from eventlet import greenthread
from oslo.config import cfg

from openstack.common.gettextutils import _
from openstack.common import jsonutils
from openstack.common.rpc import amqp as rpc_amqp
from openstack.common.rpc import common as rpc_common
from tests.unit.rpc import common


FLAGS = cfg.CONF
LOG = logging.getLogger(__name__)


class BaseRpcAMQPTestCase(common.BaseRpcTestCase):
    """Base test class for all AMQP-based RPC tests."""
    def test_proxycallback_handles_exceptions(self):
        """Make sure exceptions unpacking messages don't cause hangs."""
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        orig_unpack = rpc_amqp.unpack_context

        info = {'unpacked': False}

        def fake_unpack_context(*args, **kwargs):
            info['unpacked'] = True
            raise test.TestingException('moo')

        self.stubs.Set(rpc_amqp, 'unpack_context', fake_unpack_context)

        value = 41
        self.rpc.cast(FLAGS, self.context, self.topic,
                      {"method": "echo", "args": {"value": value}})

        # Wait for the cast to complete.
        for x in xrange(50):
            if info['unpacked']:
                break
            greenthread.sleep(0.1)
        else:
            self.fail("Timeout waiting for message to be consumed")

        # Now see if we get a response even though we raised an
        # exception for the cast above.
        self.stubs.Set(rpc_amqp, 'unpack_context', orig_unpack)

        value = 42
        result = self.rpc.call(FLAGS, self.context, self.topic,
                               {"method": "echo",
                                "args": {"value": value}})
        self.assertEqual(value, result)

    def test_notification_envelope(self):
        raw_msg = {'a': 'b'}
        self.test_msg = None

        def fake_notify_send(_conn, topic, msg):
            self.test_msg = msg

        self.stubs.Set(self.rpc.Connection, 'notify_send', fake_notify_send)

        self.rpc.notify(FLAGS, self.context, 'notifications.info', raw_msg,
                        envelope=False)
        self.assertEqual(self.test_msg, raw_msg)

        # Envelopes enabled, but not enabled for notifications
        self.stubs.Set(rpc_common, '_SEND_RPC_ENVELOPE', True)
        self.rpc.notify(FLAGS, self.context, 'notifications.info', raw_msg,
                        envelope=False)
        self.assertEqual(self.test_msg, raw_msg)

        # Now turn it on for notifications
        msg = {
            'oslo.version': rpc_common._RPC_ENVELOPE_VERSION,
            'oslo.message': jsonutils.dumps(raw_msg),
        }
        self.rpc.notify(FLAGS, self.context, 'notifications.info', raw_msg,
                        envelope=True)
        for k, v in msg.items():
            self.assertIn(k, self.test_msg)
            self.assertEqual(self.test_msg[k], v)

        # Make sure envelopes are still on notifications, even if turned off
        # for general messages.
        self.stubs.Set(rpc_common, '_SEND_RPC_ENVELOPE', False)
        self.rpc.notify(FLAGS, self.context, 'notifications.info', raw_msg,
                        envelope=True)
        for k, v in msg.items():
            self.assertIn(k, self.test_msg)
            self.assertEqual(self.test_msg[k], v)

    def test_single_reply_queue_on_has_ids(
            self, single_reply_queue_for_callee_off=False):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        # TODO(pekowski): Remove these lines in Havana where the option will be
        # removed and the default will be true.
        self.assertFalse(FLAGS.amqp_rpc_single_reply_queue)
        self.config(amqp_rpc_single_reply_queue=True)

        self.orig_unpack_context = rpc_amqp.unpack_context

        def my_unpack_context(conf, msg):
            self.assertTrue('_reply_q' in msg)
            if single_reply_queue_for_callee_off:
                # Simulate a downlevel RPC callee by removing the reply_q.
                # This will make the callee think it got a request
                # from a downlevel caller and thus respond in a downlevel
                # way.  In fact we are testing an uplevel caller.
                msg.pop('_reply_q')
            return self.orig_unpack_context(conf, msg)

        self.stubs.Set(rpc_amqp, 'unpack_context', my_unpack_context)

        self.ReplyProxy_was_called = False

        class MyReplyProxy(rpc_amqp.ReplyProxy):
            def _process_data(myself, message_data):
                #with open('mylog', 'a') as f:
                #    f.write('my_process_data: ' + str(message_data) + '\n')
                if single_reply_queue_for_callee_off:
                    self.assertTrue('_msg_id' not in message_data)
                else:
                    self.assertTrue('_msg_id' in message_data)
                self.ReplyProxy_was_called = True
                super(MyReplyProxy, myself)._process_data(message_data)

        self.orig_reply_proxy = self.conn.pool.reply_proxy
        self.conn.pool.reply_proxy = MyReplyProxy(FLAGS, self.conn.pool)

        value = 42
        result = None
        try:
            result = self.rpc.call(
                FLAGS, self.context, self.topic,
                {"method": "echo", "args": {"value": value}},
                timeout=1)
        except rpc_common.Timeout as exc:
            # expect a timeout in this case
            if single_reply_queue_for_callee_off:
                result = 42

        self.assertEqual(value, result)
        if single_reply_queue_for_callee_off:
            self.assertFalse(self.ReplyProxy_was_called)
        else:
            self.assertTrue(self.ReplyProxy_was_called)

        self.stubs.UnsetAll()
        self.conn.pool.reply_proxy = self.orig_reply_proxy

        # TODO(pekowski): Remove this line in Havana
        self.config(amqp_rpc_single_reply_queue=False)

    # TODO(pekowski): Unfortunately remove this test in Havana.
    # The amqp_rpc_single_reply_queue option will go away in Havana.
    # There will be no way to send a downlevel RPC in Havana, yet
    # Havana will be able to receive downlevel RPCs.  We would
    # need a downlevel caller to test it.
    def test_single_reply_queue_off_no_ids(
            self, single_reply_queue_for_callee_on=False):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        self.assertFalse(FLAGS.amqp_rpc_single_reply_queue)

        def my_unpack_context(conf, msg):
            self.assertTrue('_reply_q' not in msg)
            if single_reply_queue_for_callee_on:
                self.config(amqp_rpc_single_reply_queue=True)
            return self.orig_unpack_context(conf, msg)

        self.orig_unpack_context = rpc_amqp.unpack_context
        self.stubs.Set(rpc_amqp, 'unpack_context', my_unpack_context)

        self.MulticallWaiter_call_was_called = False

        def my_MulticallWaiter_call(myself, data):
            #with open('mylog', 'a') as f:
            #    f.write('my_MulticallWaiter_call: ' + str(data) + '\n')
            self.assertTrue('_reply_q' not in data)
            self.MulticallWaiter_call_was_called = True
            return self.orig_MulticallWaiter_call(myself, data)

        self.orig_MulticallWaiter_call = rpc_amqp.MulticallWaiter.__call__
        self.stubs.Set(rpc_amqp.MulticallWaiter, '__call__',
                       my_MulticallWaiter_call)

        value = 42
        result = self.rpc.call(FLAGS, self.context, self.topic,
                               {"method": "echo", "args": {"value": value}})
        self.assertEqual(value, result)
        self.assertTrue(self.MulticallWaiter_call_was_called)

        self.config(amqp_rpc_single_reply_queue=False)
        self.stubs.UnsetAll()

    # TODO(pekowski): Remove this test in Havana.
    def test_single_reply_queue_caller_off_callee_on(self):
        self.test_single_reply_queue_off_no_ids(
            single_reply_queue_for_callee_on=True)

    def test_single_reply_queue_caller_on_callee_off(self):
        self.test_single_reply_queue_on_has_ids(
            single_reply_queue_for_callee_off=True)

    #TODO(pekowski): remove this test in Havana
    def test_single_reply_queue_mt_resp_rting(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        self.config(amqp_rpc_single_reply_queue=True)
        self.test_multithreaded_resp_routing()
        self.config(amqp_rpc_single_reply_queue=False)
