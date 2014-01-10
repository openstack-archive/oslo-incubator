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

import datetime
import logging
import time

import eventlet

from openstack.common.fixture import config
from openstack.common.gettextutils import _
from openstack.common.rpc import common as rpc_common
from openstack.common.rpc import dispatcher as rpc_dispatcher
from openstack.common import test


LOG = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, message='Unknown', code='Unknown'):
        self.api_message = message
        self.code = code
        super(ApiError, self).__init__('%s: %s' % (code, message))


class BaseRpcTestCase(test.BaseTestCase):

    def setUp(self, supports_timeouts=True, topic='test',
              topic_nested='nested'):
        super(BaseRpcTestCase, self).setUp()
        self.topic = topic or self.topic
        self.topic_nested = topic_nested or self.topic_nested
        self.supports_timeouts = supports_timeouts
        self.context = rpc_common.CommonRpcContext(user='fake_user',
                                                   pw='fake_pw')
        self.FLAGS = self.useFixture(config.Config()).conf
        if self.rpc:
            receiver = TestReceiver()
            self.conn = self._create_consumer(receiver, self.topic)
            self.addCleanup(self.conn.close)

    def _create_consumer(self, proxy, topic, fanout=False):
        dispatcher = rpc_dispatcher.RpcDispatcher([proxy])
        conn = self.rpc.create_connection(self.FLAGS, True)
        conn.create_consumer(topic, dispatcher, fanout)
        conn.consume_in_thread()
        return conn

    def test_call_succeed(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        value = 42
        result = self.rpc.call(self.FLAGS, self.context, self.topic,
                               {"method": "echo", "args": {"value": value}})
        self.assertEqual(value, result)

    def test_call_succeed_despite_missing_args(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        result = self.rpc.call(self.FLAGS, self.context, self.topic,
                               {"method": "fortytwo"})
        self.assertEqual(42, result)

    def test_call_succeed_despite_multiple_returns_yield(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        value = 42
        result = self.rpc.call(self.FLAGS, self.context, self.topic,
                               {"method": "echo_three_times_yield",
                                "args": {"value": value}})
        self.assertEqual(value + 2, result)

    def test_multicall_succeed_once(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        value = 42
        result = self.rpc.multicall(self.FLAGS, self.context,
                                    self.topic,
                                    {"method": "echo",
                                     "args": {"value": value}})
        for i, x in enumerate(result):
            if i > 0:
                self.fail('should only receive one response')
            self.assertEqual(value + i, x)

    def test_multicall_three_nones(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        value = 42
        result = self.rpc.multicall(self.FLAGS, self.context,
                                    self.topic,
                                    {"method": "multicall_three_nones",
                                     "args": {"value": value}})
        for i, x in enumerate(result):
            self.assertIsNone(x)
        # i should have been 0, 1, and finally 2:
        self.assertEqual(i, 2)

    def test_multicall_succeed_three_times_yield(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        value = 42
        result = self.rpc.multicall(self.FLAGS, self.context,
                                    self.topic,
                                    {"method": "echo_three_times_yield",
                                     "args": {"value": value}})
        for i, x in enumerate(result):
            self.assertEqual(value + i, x)

    def test_context_passed(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        """Makes sure a context is passed through rpc call."""
        value = 42
        result = self.rpc.call(self.FLAGS, self.context,
                               self.topic, {"method": "context",
                                            "args": {"value": value}})
        self.assertEqual(self.context.to_dict(), result)

    def _test_cast(self, method, value, args=None, fanout=False,
                   topic_nested=None):
        """Test casts by pushing items through a channeled queue.

           @param: method a reference to a method returning a value
           @param: value the value expected from method
           @param: args optional dictionary arguments to method
           @param: fanout boolean for use of rpc fanout method
        """
        topic_nested = topic_nested or self.topic_nested

        # Not a true global, but capitalized so
        # it is clear it is leaking scope into Nested()
        QUEUE = eventlet.queue.Queue()

        if not self.rpc:
            self.skipTest('rpc driver not available.')

        # We use the nested topic so we don't need QUEUE to be a proper
        # global, and do not keep state outside this test.
        class Nested(object):
            @staticmethod
            def curry(*args, **kwargs):
                QUEUE.put(method(*args, **kwargs))

        nested = Nested()
        conn = self._create_consumer(nested, topic_nested, fanout)

        rpc_method = (self.rpc.cast, self.rpc.fanout_cast)[fanout]

        msg = {'method': 'curry'}
        if args and isinstance(args, dict):
            msg['args'] = {}
            msg['args'].update(args)

        rpc_method(self.FLAGS, self.context,
                   topic_nested,
                   msg)

        try:
            # If it does not succeed in 2 seconds, give up and assume
            # failure.
            result = QUEUE.get(True, 2)
        except Exception:
            self.assertIsNone(value)

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
            self.skipTest('rpc driver not available.')

        """Test that we can do an rpc.call inside another call."""
        class Nested(object):
            @staticmethod
            def echo(context, queue, value):
                """Calls echo in the passed queue."""
                LOG.debug(_("Nested received %(queue)s, %(value)s")
                          % {'queue': queue, 'value': value})
                # TODO(comstud):
                # so, it will replay the context and use the same REQID?
                # that's bizarre.
                ret = self.rpc.call(self.FLAGS, context,
                                    queue,
                                    {"method": "echo",
                                     "args": {"value": value}})
                LOG.debug(_("Nested return %s"), ret)
                return value

        nested = Nested()
        conn = self._create_consumer(nested, self.topic_nested)

        value = 42
        result = self.rpc.call(self.FLAGS, self.context,
                               self.topic_nested,
                               {"method": "echo",
                                "args": {"queue": "test", "value": value}})
        conn.close()
        self.assertEqual(value, result)

    def test_call_timeout(self):
        """Make sure rpc.call will time out."""
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        if not self.supports_timeouts:
            self.skipTest(_("RPC backend does not support timeouts"))

        value = 42
        self.assertRaises(rpc_common.Timeout,
                          self.rpc.call,
                          self.FLAGS, self.context,
                          self.topic,
                          {"method": "block",
                           "args": {"value": value}}, timeout=1)
        try:
            self.rpc.call(self.FLAGS, self.context,
                          self.topic,
                          {"method": "block",
                           "args": {"value": value}},
                          timeout=1)
            self.fail("should have thrown Timeout")
        except rpc_common.Timeout:
            pass

    def test_multithreaded_resp_routing(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        global synced_echo_call
        synced_echo_call = SyncedEchoCall()

        callid1 = synced_echo_call.spawn(self.rpc.call, self.FLAGS,
                                         self.context, self.topic, value=1)
        callid2 = synced_echo_call.spawn(self.rpc.call, self.FLAGS,
                                         self.context, self.topic, value=2)
        callid3 = synced_echo_call.spawn(self.rpc.call, self.FLAGS,
                                         self.context, self.topic, value=3)

        r3 = synced_echo_call.post(callid3)
        self.assertEqual(synced_echo_call.wait_states(),
                         synced_echo_call.expected_wait_states())
        r1 = synced_echo_call.post(callid1)
        self.assertEqual(synced_echo_call.wait_states(),
                         synced_echo_call.expected_wait_states())
        r2 = synced_echo_call.post(callid2)
        self.assertEqual(synced_echo_call.wait_states(),
                         synced_echo_call.expected_wait_states())

        #synced_echo_call.print_times() #for DEBUG
        self.assertEqual((r1, r2, r3), (1, 2, 3))
        self.assertTrue(synced_echo_call.verify_time_order(callid3, callid1,
                                                           callid2))

synced_echo_call = None


def rpc_wrapper(callid, func, *args):
    """This wrapper was added because tests would hang when there was a bug
       that caused the RPC to timeout.  The post event would hang waiting for
       the wait event.  The missing wait is added here.  It just makes
       debugging the unit tests easier.
    """
    try:
        ret = func(*args)
    except rpc_common.Timeout:
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
        #self.print_wait_states() #for DEBUG
        return retval

    def wait(self, idx):
        self.list[idx].waiting = True
        self.list[idx].event.wait()
        self.list[idx].waiting = False
        self.list[idx].time = datetime.datetime.now()

    def verify_time_order(self, idx1, idx2, idx3):
        return self.list[idx1].time < self.list[idx2].time and \
            self.list[idx2].time < self.list[idx3].time

    # for DEBUG
    #def print_times(self):
    #    # change /dev/null to name to get output to a log file
    #    with open('mylog', 'a') as f:
    #            f.write('SyncedEchoCall times: ' + '\n')
    #            f.write(' ' + str(self.list[0].time) + '\n')
    #            f.write(' ' + str(self.list[1].time) + '\n')
    #            f.write(' ' + str(self.list[2].time) + '\n')

    # for DEBUG
    #def print_wait_states(self):
    #    # change /dev/null to name to get output to a log file
    #    with open('mylog', 'a') as f:
    #        f.write('SyncedEchoCall times: ' +
    #                str(self.wait_states()) + '\n')


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
        raise ApiError(message=value, code='500')

    @staticmethod
    def block(context, value):
        time.sleep(2)
