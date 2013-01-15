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
Unit Tests for remote procedure calls shared between all implementations
"""

import logging
import time
import datetime

import eventlet
from eventlet import greenthread
import nose

from openstack.common import cfg
from openstack.common import exception
from openstack.common.gettextutils import _
from openstack.common import jsonutils
from openstack.common.rpc import amqp as rpc_amqp
from openstack.common.rpc import common as rpc_common
from openstack.common.rpc import dispatcher as rpc_dispatcher
from tests import utils as test_utils


FLAGS = cfg.CONF
LOG = logging.getLogger(__name__)


class BaseRpcTestCase(test_utils.BaseTestCase):
    def setUp(self, supports_timeouts=True, topic='test',
              topic_nested='nested'):
        super(BaseRpcTestCase, self).setUp()
        self.topic = topic or self.topic
        self.topic_nested = topic_nested or self.topic_nested
        self.supports_timeouts = supports_timeouts
        self.context = rpc_common.CommonRpcContext(user='fake_user',
                                                   pw='fake_pw')

        if self.rpc:
            receiver = TestReceiver()
            self.conn = self._create_consumer(receiver, self.topic)

    def tearDown(self):
        if self.rpc:
            self.conn.close()
        super(BaseRpcTestCase, self).tearDown()

    def _create_consumer(self, proxy, topic, fanout=False):
        dispatcher = rpc_dispatcher.RpcDispatcher([proxy])
        conn = self.rpc.create_connection(FLAGS, True)
        conn.create_consumer(topic, dispatcher, fanout)
        conn.consume_in_thread()
        return conn

    def test_call_succeed(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        value = 42
        result = self.rpc.call(FLAGS, self.context, self.topic,
                               {"method": "echo", "args": {"value": value}})
        self.assertEqual(value, result)

    def test_call_succeed_despite_missing_args(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        result = self.rpc.call(FLAGS, self.context, self.topic,
                               {"method": "fortytwo"})
        self.assertEqual(42, result)

    def test_call_succeed_despite_multiple_returns_yield(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        value = 42
        result = self.rpc.call(FLAGS, self.context, self.topic,
                               {"method": "echo_three_times_yield",
                                "args": {"value": value}})
        self.assertEqual(value + 2, result)

    def test_multicall_succeed_once(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        value = 42
        result = self.rpc.multicall(FLAGS, self.context,
                                    self.topic,
                                    {"method": "echo",
                                     "args": {"value": value}})
        for i, x in enumerate(result):
            if i > 0:
                self.fail('should only receive one response')
            self.assertEqual(value + i, x)

    def test_multicall_three_nones(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        value = 42
        result = self.rpc.multicall(FLAGS, self.context,
                                    self.topic,
                                    {"method": "multicall_three_nones",
                                     "args": {"value": value}})
        for i, x in enumerate(result):
            self.assertEqual(x, None)
        # i should have been 0, 1, and finally 2:
        self.assertEqual(i, 2)

    def test_multicall_succeed_three_times_yield(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        value = 42
        result = self.rpc.multicall(FLAGS, self.context,
                                    self.topic,
                                    {"method": "echo_three_times_yield",
                                     "args": {"value": value}})
        for i, x in enumerate(result):
            self.assertEqual(value + i, x)

    def test_context_passed(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        """Makes sure a context is passed through rpc call."""
        value = 42
        result = self.rpc.call(FLAGS, self.context,
                               self.topic, {"method": "context",
                                            "args": {"value": value}})
        self.assertEqual(self.context.to_dict(), result)

    def _test_cast(self, method, value, args=None, fanout=False):
        """Test casts by pushing items through a channeled queue.

           @param: method a reference to a method returning a value
           @param: value the value expected from method
           @param: args optional dictionary arguments to method
           @param: fanout boolean for use of rpc fanout method
        """
        # Not a true global, but capitalized so
        # it is clear it is leaking scope into Nested()
        QUEUE = eventlet.queue.Queue()

        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        # We use the nested topic so we don't need QUEUE to be a proper
        # global, and do not keep state outside this test.
        class Nested(object):
            @staticmethod
            def curry(*args, **kwargs):
                QUEUE.put(method(*args, **kwargs))

        nested = Nested()
        conn = self._create_consumer(nested, self.topic_nested, fanout)

        rpc_method = (self.rpc.cast, self.rpc.fanout_cast)[fanout]

        msg = {'method': 'curry'}
        if args and isinstance(args, dict):
            msg['args'] = {}
            msg['args'].update(args)

        rpc_method(FLAGS, self.context,
                   self.topic_nested,
                   msg)

        try:
            # If it does not succeed in 2 seconds, give up and assume
            # failure.
            result = QUEUE.get(True, 2)
        except Exception:
            self.assertEqual(value, None)

        conn.close()
        self.assertEqual(value, result)

    def test_cast_success(self):
        self._test_cast(TestReceiver.echo, 42, {"value": 42}, fanout=False)

    def test_fanout_success(self):
        self._test_cast(TestReceiver.echo, 42, {"value": 42}, fanout=True)

    def test_cast_success_despite_missing_args(self):
        self._test_cast(TestReceiver.fortytwo, 42, fanout=True)

    def test_nested_calls(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        """Test that we can do an rpc.call inside another call."""
        class Nested(object):
            @staticmethod
            def echo(context, queue, value):
                """Calls echo in the passed queue."""
                LOG.debug(_("Nested received %(queue)s, %(value)s")
                          % locals())
                # TODO(comstud):
                # so, it will replay the context and use the same REQID?
                # that's bizarre.
                ret = self.rpc.call(FLAGS, context,
                                    queue,
                                    {"method": "echo",
                                     "args": {"value": value}})
                LOG.debug(_("Nested return %s"), ret)
                return value

        nested = Nested()
        conn = self._create_consumer(nested, self.topic_nested)

        value = 42
        result = self.rpc.call(FLAGS, self.context,
                               self.topic_nested,
                               {"method": "echo",
                                "args": {"queue": "test", "value": value}})
        conn.close()
        self.assertEqual(value, result)

    def test_call_timeout(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        """Make sure rpc.call will time out."""
        if not self.supports_timeouts:
            raise nose.SkipTest(_("RPC backend does not support timeouts"))

        value = 42
        self.assertRaises(rpc_common.Timeout,
                          self.rpc.call,
                          FLAGS, self.context,
                          self.topic,
                          {"method": "block",
                           "args": {"value": value}}, timeout=1)
        try:
            self.rpc.call(FLAGS, self.context,
                          self.topic,
                          {"method": "block",
                           "args": {"value": value}},
                          timeout=1)
            self.fail("should have thrown Timeout")
        except rpc_common.Timeout as exc:
            pass


class BaseRpcAMQPTestCase(BaseRpcTestCase):
    """Base test class for all AMQP-based RPC tests."""
    def test_proxycallback_handles_exceptions(self):
        """Make sure exceptions unpacking messages don't cause hangs."""
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

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
        self.assertEqual(self.test_msg, msg)

        # Make sure envelopes are still on notifications, even if turned off
        # for general messages.
        self.stubs.Set(rpc_common, '_SEND_RPC_ENVELOPE', False)
        self.rpc.notify(FLAGS, self.context, 'notifications.info', raw_msg,
                        envelope=True)
        self.assertEqual(self.test_msg, msg)

    def test_single_reply_queue_on_has_ids(
            self, single_reply_queue_for_callee_off=False):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        self.config(amqp_rpc_single_reply_queue=True)

        self.orig_unpack_context = rpc_amqp.unpack_context

        def my_unpack_context(conf, msg):
            self.assertTrue('_reply_id' in msg)
            if single_reply_queue_for_callee_off:
                # Simulate a downlevel RPC callee by removing the reply_id.
                # This will make the callee think it got a request
                # from a downlevel caller and thus respond in a downlevel
                # way.  In fact we are testing an uplevel caller.
                msg.pop('_reply_id')
            return self.orig_unpack_context(conf, msg)

        self.stubs.Set(rpc_amqp, 'unpack_context', my_unpack_context)

        self.ReplyProxy_was_called = False

        class MyReplyProxy(rpc_amqp.ReplyProxy):
            def _process_data(myself, message_data):
                #with open('mylog', 'a') as f:
                #    f.write('my_process_data: ' + str(message_data) + '\n')
                if not single_reply_queue_for_callee_off:
                    self.assertTrue('_reply_id' in message_data)
                else:
                    self.assertTrue(not '_reply_id' in message_data)
                self.ReplyProxy_was_called = True
                super(MyReplyProxy, myself)._process_data(message_data)

        self.orig_reply_proxy = self.conn.pool.reply_proxy
        self.conn.pool.reply_proxy = MyReplyProxy(FLAGS, self.conn.pool)

        value = 42
        try:
            result = self.rpc.call(
                    FLAGS, self.context, self.topic,
                    {"method": "echo", "args": {"value": value}},
                    timeout=1)
        except rpc_common.Timeout as exc:
            if single_reply_queue_for_callee_off:
                result = 42

        self.assertEqual(value, result)
        self.assertTrue(self.ReplyProxy_was_called)

        self.stubs.UnsetAll()
        self.conn.pool.reply_proxy = self.orig_reply_proxy

    def test_single_reply_queue_off_no_ids(
            self, single_reply_queue_for_callee_on=False):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        self.config(amqp_rpc_single_reply_queue=False)

        def my_unpack_context(conf, msg):
            self.assertTrue(not '_reply_id' in msg)
            if single_reply_queue_for_callee_on:
                self.config(amqp_rpc_single_reply_queue=True)
            return self.orig_unpack_context(conf, msg)

        self.orig_unpack_context = rpc_amqp.unpack_context
        self.stubs.Set(rpc_amqp, 'unpack_context', my_unpack_context)

        self.MulticallWaiter_call_was_called = False

        def my_MulticallWaiter_call(myself, data):
            #with open('mylog', 'a') as f:
            #    f.write('my_MulticallWaiter_call: ' + str(data) + '\n')
            self.assertTrue(not '_reply_id' in data)
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

        self.stubs.UnsetAll()

    def test_single_reply_queue_caller_off_callee_on(self):

        self.test_single_reply_queue_off_no_ids(
            single_reply_queue_for_callee_on=True)

    def test_single_reply_queue_caller_on_callee_off(self):

        self.my_amqp_error_was_called = False

        def my_amqp_error(*args):
            self.my_amqp_error_was_called  = True
            return

        self.stubs.Set(rpc_amqp.LOG, 'error', my_amqp_error)

        def my_amqp_exception(*args):
            return

        self.stubs.Set(rpc_amqp.LOG, 'exception', my_amqp_exception)

        self.test_single_reply_queue_on_has_ids(
            single_reply_queue_for_callee_off=True)

        self.assertTrue(self.my_amqp_error_was_called)

    def multithreaded_resp_routing(self):

        global synced_echo_call
        synced_echo_call = SyncedEchoCall()

        callid1 = synced_echo_call.spawn(self.rpc.call, FLAGS, self.context,
                                         self.topic, value=1)
        callid2 = synced_echo_call.spawn(self.rpc.call, FLAGS, self.context,
                                         self.topic, value=2)
        callid3 = synced_echo_call.spawn(self.rpc.call, FLAGS, self.context,
                                         self.topic, value=3)

        r3 = synced_echo_call.post(callid3)
        self.assertEqual(synced_echo_call.wait_states(),
                         synced_echo_call.expected_wait_states())
        r1 = synced_echo_call.post(callid1)
        self.assertEqual(synced_echo_call.wait_states(),
                         synced_echo_call.expected_wait_states())
        r2 = synced_echo_call.post(callid2)
        self.assertEqual(synced_echo_call.wait_states(),
                         synced_echo_call.expected_wait_states())

        #synced_echo_call.print_times()
        self.assertEqual((r1, r2, r3), (1, 2, 3))
        self.assertTrue(synced_echo_call.verify_time_order(callid3, callid1,
                                                           callid2))

    def test_multithreaded_resp_routing(self):
        if not self.rpc:
            raise nose.SkipTest('rpc driver not available.')

        self.config(amqp_rpc_single_reply_queue=False)
        self.multithreaded_resp_routing()
        self.config(amqp_rpc_single_reply_queue=True)
        self.multithreaded_resp_routing()


synced_echo_call = None


def rpc_wrapper(callid, func, *args):
    """This wrapper was added because tests would hang when there was a bug
       that caused the RPC to timeout.  The post event would hang waiting for
       the wait event.  The missing wait is added here.  It just makes
       debugging the unit tests easier.
    """
    try:
        ret = func(*args)
    except rpc_common.Timeout as exc:
        synced_echo_call.wait(callid)
        ret = None
    return ret


class SyncedEchoCall():
    """Class to control the synchronization of the synced_echo method of the
       TestReceiver class
    """
    class data():
        def __init__(self):
            self.gthread = None
            self.event = eventlet.event.Event()
            self.waiting = False
            self.expected_wait_state = False
            self.time = 0

    def __init__(self):
        self.list = []

    def spawn(self, *args, **kwargs):
        idx = len(self.list)
        self.list.append(SyncedEchoCall.data())
        args = list(args)
        value = kwargs['value']
        args.append({"method": "synced_echo", "args":
                     {"value": value, "callid": idx}})
        args.insert(0, idx)
        args.insert(0, rpc_wrapper)
        self.list[idx].gthread = eventlet.spawn(*args)
        self.list[idx].expected_wait_state = True
        return idx

    def wait_states(self):
        rlist = []
        for i in self.list:
            rlist.append(i.waiting)
        return rlist

    def expected_wait_states(self):
        rlist = []
        for i in self.list:
            rlist.append(i.expected_wait_state)
        return rlist

    def post(self, idx):
        self.list[idx].event.send()
        retval = self.list[idx].gthread.wait()
        self.list[idx].expected_wait_state = False
        #self.print_wait_states()
        return retval

    def wait(self, idx):
        self.list[idx].waiting = True
        self.list[idx].event.wait()
        self.list[idx].waiting = False
        self.list[idx].time = datetime.datetime.now()

    def verify_time_order(self, idx1, idx2, idx3):
        return self.list[idx1].time < self.list[idx2].time and \
            self.list[idx2].time < self.list[idx3].time

    def print_times(self):
        with open('mylog', 'a') as f:
            f.write('SyncedEchoCall times: ' + '\n')
            f.write('        ' + str(self.list[0].time) + '\n')
            f.write('        ' + str(self.list[1].time) + '\n')
            f.write('        ' + str(self.list[2].time) + '\n')

    def print_wait_states(self):
        with open('mylog', 'a') as f:
            f.write('SyncedEchoCall times: ' +
                    str(self.wait_states()) + '\n')


class TestReceiver(object):
    """Simple Proxy class so the consumer has methods to call.

    Uses static methods because we aren't actually storing any state.

    """
    @staticmethod
    def echo(context, value):
        """Simply returns whatever value is sent in."""
        LOG.debug(_("Received %s"), value)
        return value

    @staticmethod
    def synced_echo(context, value, callid):
        """Waits on the event identified by callid."""
        LOG.debug(_("Received %s"), value)
        global synced_echo_call
        synced_echo_call.wait(callid)
        return value

    @staticmethod
    def fortytwo(context):
        """Simply returns 42."""
        return 42

    @staticmethod
    def context(context, value):
        """Returns dictionary version of context."""
        LOG.debug(_("Received %s"), context)
        return context.to_dict()

    @staticmethod
    def multicall_three_nones(context, value):
        yield None
        yield None
        yield None

    @staticmethod
    def echo_three_times_yield(context, value):
        yield value
        yield value + 1
        yield value + 2

    @staticmethod
    def fail(context, value):
        """Raises an exception with the value sent in."""
        raise NotImplementedError(value)

    @staticmethod
    def fail_converted(context, value):
        """Raises an exception with the value sent in."""
        raise exception.ApiError(message=value, code='500')

    @staticmethod
    def block(context, value):
        time.sleep(2)
