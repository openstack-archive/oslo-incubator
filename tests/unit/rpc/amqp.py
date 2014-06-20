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
import mock
from oslo.config import cfg

from openstack.common.rpc import amqp as rpc_amqp
from openstack.common.rpc import common as rpc_common
from tests.unit.rpc import common


FLAGS = cfg.CONF
LOG = logging.getLogger(__name__)


class MyException(Exception):
    pass


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
            raise Exception('moo')

        self.stubs.Set(rpc_amqp, 'unpack_context', fake_unpack_context)

        value = 41
        self.rpc.cast(FLAGS, self.context, self.topic,
                      {"method": "echo", "args": {"value": value}})

        # Wait for the cast to complete.
        for x in range(50):
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

        # Now turn it on for notifications
        self.rpc.notify(FLAGS, self.context, 'notifications.info', raw_msg,
                        envelope=True)
        # Make sure the msg envelope was applied
        self.assertTrue('oslo.version' in self.test_msg)

    def test_single_reply_queue_caller_on(
            self, single_reply_queue_for_callee_off=False):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

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
                # with open('mylog', 'a') as f:
                #     f.write('my_process_data: ' + str(message_data) + '\n')
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
        except rpc_common.Timeout:
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

    def test_single_reply_queue_caller_on_callee_off(self):
        self.test_single_reply_queue_caller_on(
            single_reply_queue_for_callee_off=True)

    def test_duplicate_message_check(self):
        """Test sending *not-dict* to a topic exchange/queue."""

        conn = self.rpc.create_connection(FLAGS)
        message = {'args': 'topic test message', '_unique_id': 'aaaabbbbcccc'}

        self.received_message = None
        cache = rpc_amqp._MsgIdCache()
        self.exc_raised = False

        def _callback(message):
            try:
                cache.check_duplicate_message(message)
            except rpc_common.DuplicateMessageError:
                self.exc_raised = True

        conn.declare_topic_consumer('a_topic', _callback)
        conn.topic_send('a_topic', rpc_common.serialize_msg(message))
        conn.topic_send('a_topic', rpc_common.serialize_msg(message))
        conn.consume(limit=2)
        conn.close()

        self.assertTrue(self.exc_raised)

    def test_context_dict_type_check(self):
        """Test that context is handled properly depending on the type."""
        fake_context = {'fake': 'context'}
        mock_msg = mock.MagicMock()
        rpc_amqp.pack_context(mock_msg, fake_context)

        # assert first arg in args was a dict type
        args = mock_msg.update.call_args[0]
        self.assertIsInstance(args[0], dict)

    def test_callback_wrapper_exception_no_wait(self):
        def my_callback(message, **kwargs):
            raise MyException("boom")

        x = rpc_amqp.CallbackWrapper(FLAGS, my_callback, self.conn.pool,
                                     wait_for_consumers=False)
        try:
            x({'foo': 'blah'})
        except Exception:
            self.fail("Should not raise")

    def test_callback_wrapper_exception_wait(self):
        def my_callback(message, **kwargs):
            raise MyException("boom")

        x = rpc_amqp.CallbackWrapper(FLAGS, my_callback, self.conn.pool,
                                     wait_for_consumers=True)
        self.assertRaises(MyException, x, {'foo': 'blah'})

    def test_callback_wrapper_no_exception_wait(self):
        def my_callback(message, **kwargs):
            pass

        x = rpc_amqp.CallbackWrapper(FLAGS, my_callback, self.conn.pool,
                                     wait_for_consumers=True)
        try:
            x({'foo': 'blah'})
        except Exception:
            self.fail("Should not raise")
