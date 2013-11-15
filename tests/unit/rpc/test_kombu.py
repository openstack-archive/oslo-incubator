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
Unit Tests for remote procedure calls using kombu
"""

import eventlet
eventlet.monkey_patch()

import contextlib
import functools
import logging
import time
import weakref

import fixtures
import mock
import six

from openstack.common.fixture import config
from openstack.common.fixture import moxstubout
from openstack.common.rpc import amqp as rpc_amqp
from openstack.common.rpc import common as rpc_common
from openstack.common import test as test_base
from tests.unit.rpc import amqp
from tests.unit.rpc import common

try:
    import kombu
    import kombu.connection
    import kombu.entity
    from openstack.common.rpc import impl_kombu
except ImportError:
    kombu = None
    impl_kombu = None


LOG = logging.getLogger(__name__)


class MyException(Exception):
    pass


def _raise_exc_stub(stubs, times, obj, method, exc_msg,
                    exc_class=MyException):
    info = {'called': 0}
    orig_method = getattr(obj, method)

    def _raise_stub(*args, **kwargs):
        info['called'] += 1
        if info['called'] <= times:
            raise exc_class(exc_msg)
        orig_method(*args, **kwargs)
    stubs.Set(obj, method, _raise_stub)
    return info


class KombuStubs(fixtures.Fixture):
    def __init__(self, test):
        super(KombuStubs, self).__init__()

        # NOTE(rpodolyaka): use a weak ref here to prevent ref cycles
        self.test = weakref.ref(test)

    def setUp(self):
        super(KombuStubs, self).setUp()

        test = self.test()
        if kombu:
            test.conf = self.useFixture(config.Config()).conf
            test.config(fake_rabbit=True)
            test.config(rpc_response_timeout=5)
            test.rpc = impl_kombu
            self.addCleanup(impl_kombu.cleanup)
        else:
            test.rpc = None


class FakeMessage(object):
    acked = False
    requeued = False

    def __init__(self, payload):
        self.payload = payload

    def ack(self):
        self.acked = True

    def requeue(self):
        self.requeued = True


class RpcKombuTestCase(amqp.BaseRpcAMQPTestCase):
    def setUp(self):
        if kombu is None:
            self.skipTest("Test requires kombu")
        configfixture = self.useFixture(config.Config())
        self.config = configfixture.config
        self.FLAGS = configfixture.conf
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        self.useFixture(KombuStubs(self))
        self.called = []
        self._saved_flags = {}
        self.save_flags_state()
        super(RpcKombuTestCase, self).setUp()

    def tearDown(self):
        self.restore_flags_state()
        self.stubs.UnsetAll()
        super(RpcKombuTestCase, self).tearDown()

    def save_flags_state(self):
        """Any flags modified should be saved here."""
        self._saved_flags['concurrency_control_enabled'] = \
            self.FLAGS.concurrency_control_enabled
        self._saved_flags['concurrency_control_actions'] = \
            self.FLAGS.concurrency_control_actions
        self._saved_flags['concurrency_control_limit'] = \
            self.FLAGS.concurrency_control_limit

    def restore_flags_state(self):
        """Any flags modified should be restored here."""
        self.FLAGS.concurrency_control_enabled = \
            self._saved_flags['concurrency_control_enabled']
        self.FLAGS.concurrency_control_actions = \
            self._saved_flags['concurrency_control_actions']
        self.FLAGS.concurrency_control_limit = \
            self._saved_flags['concurrency_control_limit']

    def _mock_process_data(self, ctxt, version, method, namespace, args):
        self.called.append('mock_process_data')

    def _mock_cc_process_data(self, ctxt, version, method, namespace, args):
        self.called.append('mock_cc_process_data')

    def _mock_spawn_n(self, f, *args, **kwargs):
        f(*args, **kwargs)

    def test_proxycallback_cc(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        self.FLAGS.concurrency_control_enabled = True
        callback = rpc_amqp.ProxyCallback(self.FLAGS, None, self.conn.pool)

        self.stubs.Set(callback.pool, 'spawn_n', self._mock_spawn_n)
        self.stubs.Set(callback, '_process_data', self._mock_process_data)
        self.stubs.Set(callback, '_cc_process_data',
                       self._mock_cc_process_data)

        methods = 'methodA, methodB'
        message = {'args': {'value': 1234}}

        self.FLAGS.concurrency_control_enabled = True
        self.FLAGS.concurrency_control_actions = methods
        message['method'] = 'methodA'
        callback(message)

        self.FLAGS.concurrency_control_enabled = True
        self.FLAGS.concurrency_control_actions = methods
        message['method'] = 'methodB'
        callback(message)

        self.assertEquals(['mock_cc_process_data', 'mock_cc_process_data'],
                          self.called)

    def test_proxycallback_no_cc(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        callback = rpc_amqp.ProxyCallback(self.FLAGS, None, self.conn.pool)

        self.stubs.Set(callback.pool, 'spawn_n', self._mock_spawn_n)
        self.stubs.Set(callback, '_process_data', self._mock_process_data)
        self.stubs.Set(callback, '_cc_process_data',
                       self._mock_cc_process_data)

        message = {'args': {'value': 1234}}

        self.FLAGS.concurrency_control_enabled = True
        message['method'] = 'methodA'
        callback(message)

        self.FLAGS.concurrency_control_enabled = False
        message['method'] = 'methodB'
        callback(message)

        self.assertEquals(['mock_process_data', 'mock_process_data'],
                          self.called,)

    def test_proxycallback_cc_semaphore(self):
        if not self.rpc:
            self.skipTest('rpc driver not available.')

        limit = 3
        counter = [0]
        sema_state = []
        callback = None

        def mock_process_data(inst, ctxt, version, method, namespace, args):
            # We expect the semaphore to have been acquired by this point
            if inst.concurrency_control_semaphore.locked():
                sema_state.append('inner-blocking')

            if counter[0] <= limit:
                message['method'] = 'methodB'
                callback(message)

            self.called.append('mock_process_data')

        self.stubs.Set(rpc_amqp.ProxyCallback, '_process_data',
                       mock_process_data)

        orig_cc_process_data = rpc_amqp.ProxyCallback._cc_process_data

        def mock_cc_process_data(inst, *args, **kwargs):
            if counter[0] < limit:
                # We expect the semaphore to be free at this point
                if not inst.concurrency_control_semaphore.locked():
                    sema_state.append('non-blocking')
            else:
                # We expect the semaphore to be taken at this point
                if inst.concurrency_control_semaphore.locked():
                    sema_state.append('blocking')

            self.called.append('mock_cc_process_data')
            if counter[0] < limit:
                print counter
                counter[0] += 1
                orig_cc_process_data(inst, *args, **kwargs)

        self.stubs.Set(rpc_amqp.ProxyCallback, '_cc_process_data',
                       mock_cc_process_data)

        methods = 'methodA, methodB'
        message = {'args': {'value': 1234}}

        self.FLAGS.concurrency_control_enabled = True
        self.FLAGS.concurrency_control_actions = methods
        self.FLAGS.concurrency_control_limit = limit
        message['method'] = 'methodA'
        callback = rpc_amqp.ProxyCallback(self.FLAGS, None, self.conn.pool)

        # For some reason spawn_n ignores these mocks so we have to mock it out
        # and ensure we don't acquire the semaphore more than once.
        self.stubs.Set(callback.pool, 'spawn_n', self._mock_spawn_n)

        callback(message)
        expected_sema_state = []
        for i in xrange(0, limit):
            expected_sema_state.append('non-blocking')

        expected_sema_state += ['inner-blocking', 'blocking']

        self.assertEquals(sema_state, expected_sema_state)

        expected_called = []
        for i in xrange(0, limit + 1):
            expected_called.append('mock_cc_process_data')

        for i in xrange(0, limit):
            expected_called.append('mock_process_data')

        self.assertEquals(self.called, expected_called)

    def test_reusing_connection(self):
        """Test that reusing a connection returns same one."""
        conn_context = self.rpc.create_connection(self.FLAGS, new=False)
        conn1 = conn_context.connection
        conn_context.close()
        conn_context = self.rpc.create_connection(self.FLAGS, new=False)
        conn2 = conn_context.connection
        conn_context.close()
        self.assertEqual(conn1, conn2)

    def test_topic_send_receive(self):
        """Test sending to a topic exchange/queue."""

        conn = self.rpc.create_connection(self.FLAGS)
        message = 'topic test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message

        conn.declare_topic_consumer('a_topic', _callback)
        conn.topic_send('a_topic', rpc_common.serialize_msg(message))
        conn.consume(limit=1)
        conn.close()

        self.assertEqual(self.received_message, message)

    def test_callback_handler_ack_on_error(self):
        """The default case will ack on error. Same as before.
        """
        def _callback(msg):
            pass

        conn = self.rpc.create_connection(self.FLAGS)
        consumer = conn.declare_consumer(functools.partial(
                                         impl_kombu.TopicConsumer,
                                         name=None,
                                         exchange_name=None),
                                         "a_topic", _callback)
        message = FakeMessage("some message")
        consumer._callback_handler(message, _callback)
        self.assertTrue(message.acked)
        self.assertFalse(message.requeued)

    def test_callback_handler_ack_on_error_exception(self):

        def _callback(msg):
            raise MyException()

        conn = self.rpc.create_connection(self.FLAGS)
        consumer = conn.declare_consumer(functools.partial(
                                         impl_kombu.TopicConsumer,
                                         name=None,
                                         exchange_name=None,
                                         ack_on_error=True),
                                         "a_topic", _callback)
        message = FakeMessage("some message")
        consumer._callback_handler(message, _callback)
        self.assertTrue(message.acked)
        self.assertFalse(message.requeued)

    def test_callback_handler_no_ack_on_error_exception(self):

        def _callback(msg):
            raise MyException()

        conn = self.rpc.create_connection(self.FLAGS)
        consumer = conn.declare_consumer(functools.partial(
                                         impl_kombu.TopicConsumer,
                                         name=None,
                                         exchange_name=None,
                                         ack_on_error=False),
                                         "a_topic", _callback)
        message = FakeMessage("some message")
        consumer._callback_handler(message, _callback)
        self.assertFalse(message.acked)
        self.assertTrue(message.requeued)

    def test_callback_handler_no_ack_on_error(self):

        def _callback(msg):
            pass

        conn = self.rpc.create_connection(self.FLAGS)
        consumer = conn.declare_consumer(functools.partial(
                                         impl_kombu.TopicConsumer,
                                         name=None,
                                         exchange_name=None,
                                         ack_on_error=False),
                                         "a_topic", _callback)
        message = FakeMessage("some message")
        consumer._callback_handler(message, _callback)
        self.assertTrue(message.acked)
        self.assertFalse(message.requeued)

    def test_message_ttl_on_timeout(self):
        """Test message ttl being set by request timeout. The message
        should die on the vine and never arrive.
        """
        conn = self.rpc.create_connection(self.FLAGS)
        message = 'topic test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message
            self.fail("should not have received this message")

        conn.declare_topic_consumer('a_topic', _callback)
        conn.topic_send('a_topic', rpc_common.serialize_msg(message), 0)
        conn.iterconsume(1, 2)

        conn.close()

    def test_topic_send_receive_exchange_name(self):
        """Test sending to a topic exchange/queue with an exchange name."""

        conn = self.rpc.create_connection(self.FLAGS)
        message = 'topic test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message

        conn.declare_topic_consumer('a_topic', _callback,
                                    exchange_name="foorbar")
        conn.topic_send('a_topic', rpc_common.serialize_msg(message))
        conn.consume(limit=1)
        conn.close()

        self.assertEqual(self.received_message, message)

    def test_topic_multiple_queues(self):
        """Test sending to a topic exchange with multiple queues."""

        conn = self.rpc.create_connection(self.FLAGS)
        message = 'topic test message'

        self.received_message_1 = None
        self.received_message_2 = None

        def _callback1(message):
            self.received_message_1 = message

        def _callback2(message):
            self.received_message_2 = message

        conn.declare_topic_consumer('a_topic', _callback1, queue_name='queue1')
        conn.declare_topic_consumer('a_topic', _callback2, queue_name='queue2')
        conn.topic_send('a_topic', rpc_common.serialize_msg(message))
        conn.consume(limit=2)
        conn.close()

        self.assertEqual(self.received_message_1, message)
        self.assertEqual(self.received_message_2, message)

    def test_topic_multiple_queues_specify_exchange(self):
        """Test sending to a topic exchange with multiple queues and one
        exchange

        """

        conn = self.rpc.create_connection(self.FLAGS)
        message = 'topic test message'

        self.received_message_1 = None
        self.received_message_2 = None

        def _callback1(message):
            self.received_message_1 = message

        def _callback2(message):
            self.received_message_2 = message

        conn.declare_topic_consumer('a_topic', _callback1, queue_name='queue1',
                                    exchange_name="abc")
        conn.declare_topic_consumer('a_topic', _callback2, queue_name='queue2',
                                    exchange_name="abc")
        conn.topic_send('a_topic', rpc_common.serialize_msg(message))
        conn.consume(limit=2)
        conn.close()

        self.assertEqual(self.received_message_1, message)
        self.assertEqual(self.received_message_2, message)

    def test_topic_one_queues_multiple_exchange(self):
        """Test sending to a topic exchange with one queues and several
        exchanges

        """

        conn = self.rpc.create_connection(self.FLAGS)
        message = 'topic test message'

        self.received_message_1 = None
        self.received_message_2 = None

        def _callback1(message):
            self.received_message_1 = message

        def _callback2(message):
            self.received_message_2 = message

        conn.declare_topic_consumer('a_topic', _callback1, queue_name='queue1',
                                    exchange_name="abc")
        conn.declare_topic_consumer('a_topic', _callback2, queue_name='queue2',
                                    exchange_name="def")
        conn.topic_send('a_topic', rpc_common.serialize_msg(message))
        conn.consume(limit=2)
        conn.close()

        self.assertEqual(self.received_message_1, message)
        self.assertEqual(self.received_message_2, message)

    def test_direct_send_receive(self):
        """Test sending to a direct exchange/queue."""
        conn = self.rpc.create_connection(self.FLAGS)
        message = 'direct test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message

        conn.declare_direct_consumer('a_direct', _callback)
        conn.direct_send('a_direct', rpc_common.serialize_msg(message))
        conn.consume(limit=1)
        conn.close()

        self.assertEqual(self.received_message, message)

    def test_cast_interface_uses_default_options(self):
        """Test kombu rpc.cast."""

        ctxt = rpc_common.CommonRpcContext(user='fake_user',
                                           project='fake_project')

        class MyConnection(impl_kombu.Connection):
            def __init__(myself, *args, **kwargs):
                super(MyConnection, myself).__init__(*args, **kwargs)
                self.assertEqual(
                    myself.params_list,
                    [{'hostname': self.FLAGS.rabbit_host,
                      'userid': self.FLAGS.rabbit_userid,
                      'password': self.FLAGS.rabbit_password,
                      'port': self.FLAGS.rabbit_port,
                      'virtual_host': self.FLAGS.rabbit_virtual_host,
                      'transport': 'memory'}])

            def topic_send(_context, topic, msg):
                pass

        MyConnection.pool = rpc_amqp.Pool(self.FLAGS, MyConnection)
        self.stubs.Set(impl_kombu, 'Connection', MyConnection)

        impl_kombu.cast(self.FLAGS, ctxt, 'fake_topic', {'msg': 'fake'})

    def test_cast_to_server_uses_server_params(self):
        """Test kombu rpc.cast."""

        ctxt = rpc_common.CommonRpcContext(user='fake_user',
                                           project='fake_project')

        server_params = {'username': 'fake_username',
                         'password': 'fake_password',
                         'hostname': 'fake_hostname',
                         'port': 31337,
                         'virtual_host': 'fake_virtual_host'}

        class MyConnection(impl_kombu.Connection):
            def __init__(myself, *args, **kwargs):
                super(MyConnection, myself).__init__(*args, **kwargs)
                self.assertEqual(
                    myself.params_list,
                    [{'hostname': server_params['hostname'],
                      'userid': server_params['username'],
                      'password': server_params['password'],
                      'port': server_params['port'],
                      'virtual_host': server_params['virtual_host'],
                      'transport': 'memory'}])

            def topic_send(_context, topic, msg):
                pass

        MyConnection.pool = rpc_amqp.Pool(self.FLAGS, MyConnection)
        self.stubs.Set(impl_kombu, 'Connection', MyConnection)

        impl_kombu.cast_to_server(self.FLAGS, ctxt, server_params,
                                  'fake_topic', {'msg': 'fake'})

    def test_fanout_success(self):
        # Overriding the method in the base class because the test
        # seems to fail for the same reason as
        # test_fanout_send_receive().
        self.skipTest("kombu memory transport seems buggy with "
                      "fanout queues as this test passes when "
                      "you use rabbit (fake_rabbit=False)")

    def test_cast_success_despite_missing_args(self):
        # Overriding the method in the base class because the test
        # seems to fail for the same reason as
        # test_fanout_send_receive().
        self.skipTest("kombu memory transport seems buggy with "
                      "fanout queues as this test passes when "
                      "you use rabbit (fake_rabbit=False)")

    def test_fanout_send_receive(self):
        """Test sending to a fanout exchange and consuming from 2 queues."""

        self.skipTest("kombu memory transport seems buggy with "
                      "fanout queues as this test passes when "
                      "you use rabbit (fake_rabbit=False)")
        conn = self.rpc.create_connection()
        conn2 = self.rpc.create_connection()
        message = 'fanout test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message

        conn.declare_fanout_consumer('a_fanout', _callback)
        conn2.declare_fanout_consumer('a_fanout', _callback)
        conn.fanout_send('a_fanout', message)

        conn.consume(limit=1)
        conn.close()
        self.assertEqual(self.received_message, message)

        self.received_message = None
        conn2.consume(limit=1)
        conn2.close()
        self.assertEqual(self.received_message, message)

    def test_declare_consumer_errors_will_reconnect(self):
        # Test that any exception with 'timeout' in it causes a
        # reconnection
        info = _raise_exc_stub(self.stubs, 2, self.rpc.DirectConsumer,
                               '__init__', 'foo timeout foo')

        conn = self.rpc.Connection(self.FLAGS)
        result = conn.declare_consumer(self.rpc.DirectConsumer,
                                       'test_topic', None)

        self.assertEqual(info['called'], 3)
        self.assertTrue(isinstance(result, self.rpc.DirectConsumer))

        # Test that any exception in transport.connection_errors causes
        # a reconnection
        self.stubs.UnsetAll()

        info = _raise_exc_stub(self.stubs, 1, self.rpc.DirectConsumer,
                               '__init__', 'meow')

        conn = self.rpc.Connection(self.FLAGS)
        conn.connection_errors = (MyException, )

        result = conn.declare_consumer(self.rpc.DirectConsumer,
                                       'test_topic', None)

        self.assertEqual(info['called'], 2)
        self.assertTrue(isinstance(result, self.rpc.DirectConsumer))

    def test_declare_consumer_ioerrors_will_reconnect(self):
        """Test that an IOError exception causes a reconnection."""
        info = _raise_exc_stub(self.stubs, 2, self.rpc.DirectConsumer,
                               '__init__', 'Socket closed', exc_class=IOError)

        conn = self.rpc.Connection(self.FLAGS)
        result = conn.declare_consumer(self.rpc.DirectConsumer,
                                       'test_topic', None)

        self.assertEqual(info['called'], 3)
        self.assertTrue(isinstance(result, self.rpc.DirectConsumer))

    def test_publishing_errors_will_reconnect(self):
        # Test that any exception with 'timeout' in it causes a
        # reconnection when declaring the publisher class and when
        # calling send()
        info = _raise_exc_stub(self.stubs, 2, self.rpc.DirectPublisher,
                               '__init__', 'foo timeout foo')

        conn = self.rpc.Connection(self.FLAGS)
        conn.publisher_send(self.rpc.DirectPublisher, 'test_topic', 'msg')

        self.assertEqual(info['called'], 3)
        self.stubs.UnsetAll()

        info = _raise_exc_stub(self.stubs, 2, self.rpc.DirectPublisher,
                               'send', 'foo timeout foo')

        conn = self.rpc.Connection(self.FLAGS)
        conn.publisher_send(self.rpc.DirectPublisher, 'test_topic', 'msg')

        self.assertEqual(info['called'], 3)

        # Test that any exception in transport.connection_errors causes
        # a reconnection when declaring the publisher class and when
        # calling send()
        self.stubs.UnsetAll()

        info = _raise_exc_stub(self.stubs, 1, self.rpc.DirectPublisher,
                               '__init__', 'meow')

        conn = self.rpc.Connection(self.FLAGS)
        conn.connection_errors = (MyException, )

        conn.publisher_send(self.rpc.DirectPublisher, 'test_topic', 'msg')

        self.assertEqual(info['called'], 2)
        self.stubs.UnsetAll()

        info = _raise_exc_stub(self.stubs, 1, self.rpc.DirectPublisher,
                               'send', 'meow')

        conn = self.rpc.Connection(self.FLAGS)
        conn.connection_errors = (MyException, )

        conn.publisher_send(self.rpc.DirectPublisher, 'test_topic', 'msg')

        self.assertEqual(info['called'], 2)

    def test_iterconsume_errors_will_reconnect(self):
        conn = self.rpc.Connection(self.FLAGS)
        message = 'reconnect test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message

        conn.declare_direct_consumer('a_direct', _callback)
        conn.direct_send('a_direct', rpc_common.serialize_msg(message))

        _raise_exc_stub(self.stubs, 1, conn.connection,
                        'drain_events', 'foo timeout foo')
        conn.consume(limit=1)
        conn.close()

        self.assertEqual(self.received_message, message)
        # Only called once, because our stub goes away during reconnection

    def test_call_exception(self):
        """Test that exception gets passed back properly.

        rpc.call returns an Exception object.  The value of the
        exception is converted to a string.

        """
        self.config(allowed_rpc_exception_modules=['exceptions'])
        value = "This is the exception message"
        self.assertRaises(NotImplementedError,
                          self.rpc.call,
                          self.FLAGS,
                          self.context,
                          'test',
                          {"method": "fail",
                           "args": {"value": value}})
        try:
            self.rpc.call(self.FLAGS, self.context,
                          'test',
                          {"method": "fail",
                           "args": {"value": value}})
            self.fail("should have thrown Exception")
        except NotImplementedError as exc:
            self.assertTrue(value in six.text_type(exc))
            #Traceback should be included in exception message
            self.assertTrue('raise NotImplementedError(value)' in
                            six.text_type(exc))

    def test_call_converted_exception(self):
        """Test that exception gets passed back properly.

        rpc.call returns an Exception object.  The value of the
        exception is converted to a string.

        """
        value = "This is the exception message"
        # The use of ApiError is an arbitrary choice here ...
        self.config(allowed_rpc_exception_modules=[common.__name__])
        self.assertRaises(common.ApiError,
                          self.rpc.call,
                          self.FLAGS,
                          self.context,
                          'test',
                          {"method": "fail_converted",
                           "args": {"value": value}})
        try:
            self.rpc.call(self.FLAGS, self.context,
                          'test',
                          {"method": "fail_converted",
                           "args": {"value": value}})
            self.fail("should have thrown Exception")
        except common.ApiError as exc:
            self.assertTrue(value in six.text_type(exc))
            #Traceback should be included in exception message
            self.assertTrue('ApiError' in six.text_type(exc))

    def test_create_worker(self):
        meth = 'declare_topic_consumer'
        with mock.patch.object(self.rpc.Connection, meth) as p:
            conn = self.rpc.create_connection(self.FLAGS)
            conn.create_worker(
                'topic.name',
                lambda *a, **k: (a, k),
                'pool.name',
            )
            p.assert_called_with(
                'topic.name',
                mock.ANY,  # the proxy
                'pool.name',
            )

    def test_join_consumer_pool_default(self):
        meth = 'declare_topic_consumer'
        with mock.patch.object(self.rpc.Connection, meth) as p:
            conn = self.rpc.create_connection(self.FLAGS)
            conn.join_consumer_pool(
                callback=lambda *a, **k: (a, k),
                pool_name='pool.name',
                topic='topic.name',
                exchange_name='exchange.name',
            )
            p.assert_called_with(
                callback=mock.ANY,  # the callback wrapper
                queue_name='pool.name',
                exchange_name='exchange.name',
                topic='topic.name',
                ack_on_error=True,
            )

    def test_join_consumer_pool_no_ack(self):
        meth = 'declare_topic_consumer'
        with mock.patch.object(self.rpc.Connection, meth) as p:
            conn = self.rpc.create_connection(self.FLAGS)
            conn.join_consumer_pool(
                callback=lambda *a, **k: (a, k),
                pool_name='pool.name',
                topic='topic.name',
                exchange_name='exchange.name',
                ack_on_error=False,
            )
            p.assert_called_with(
                callback=mock.ANY,  # the callback wrapper
                queue_name='pool.name',
                exchange_name='exchange.name',
                topic='topic.name',
                ack_on_error=False,
            )

    # used to make unexpected exception tests run faster
    def my_time_sleep(self, sleep_time):
        return

    def test_service_consume_thread_unexpected_exceptions(self):

        def my_TopicConsumer_consume(myself, *args, **kwargs):
            self.consume_calls += 1
            # see if it can sustain three failures
            if self.consume_calls < 3:
                raise Exception('unexpected exception')
            else:
                self.orig_TopicConsumer_consume(myself, *args, **kwargs)

        self.consume_calls = 0
        self.orig_TopicConsumer_consume = impl_kombu.TopicConsumer.consume
        self.stubs.Set(impl_kombu.TopicConsumer, 'consume',
                       my_TopicConsumer_consume)
        self.stubs.Set(time, 'sleep', self.my_time_sleep)

        value = 42
        result = self.rpc.call(self.FLAGS, self.context, self.topic,
                               {"method": "echo",
                                "args": {"value": value}})
        self.assertEqual(value, result)

    def test_replyproxy_consume_thread_unexpected_exceptions(self):

        def my_DirectConsumer_consume(myself, *args, **kwargs):
            self.consume_calls += 1
            # see if it can sustain three failures
            if self.consume_calls < 3:
                raise Exception('unexpected exception')
            else:
                self.orig_DirectConsumer_consume(myself, *args, **kwargs)

        self.consume_calls = 1
        self.orig_DirectConsumer_consume = impl_kombu.DirectConsumer.consume
        self.stubs.Set(impl_kombu.DirectConsumer, 'consume',
                       my_DirectConsumer_consume)
        self.stubs.Set(time, 'sleep', self.my_time_sleep)

        value = 42
        result = self.rpc.call(self.FLAGS, self.context, self.topic,
                               {"method": "echo",
                                "args": {"value": value}})
        self.assertEqual(value, result)

    def test_reconnect_max_retries(self):
        self.config(rabbit_hosts=[
            'host1:1234', 'host2:5678', '[::1]:2345',
            '[2001:0db8:85a3:0042:0000:8a2e:0370:7334]'],
            rabbit_max_retries=2,
            rabbit_retry_interval=0.1,
            rabbit_retry_backoff=0.1)

        info = {'attempt': 0}

        class MyConnection(kombu.connection.BrokerConnection):
            def __init__(self, *args, **params):
                super(MyConnection, self).__init__(*args, **params)
                info['attempt'] += 1

            def connect(self):
                if info['attempt'] < 3:
                    # the word timeout is important (see impl_kombu.py:486)
                    raise Exception('connection timeout')
                super(kombu.connection.BrokerConnection, self).connect()

        self.stubs.Set(kombu.connection, 'BrokerConnection', MyConnection)

        self.assertRaises(rpc_common.RPCException, self.rpc.Connection,
                          self.FLAGS)
        self.assertEqual(info['attempt'], 2)


class RpcKombuHATestCase(test_base.BaseTestCase):
    def setUp(self):
        super(RpcKombuHATestCase, self).setUp()
        configfixture = self.useFixture(config.Config())
        self.config = configfixture.config
        self.FLAGS = configfixture.conf
        self.stubs = self.useFixture(moxstubout.MoxStubout()).stubs
        self.useFixture(KombuStubs(self))

    def test_roundrobin_reconnect(self):
        """Test that rabbits are tried in roundrobin at connection failures."""
        self.config(rabbit_hosts=[
            'host1:1234', 'host2:5678', '[::1]:2345',
            '[2001:0db8:85a3:0042:0000:8a2e:0370:7334]'],
            rabbit_retry_interval=0.1,
            rabbit_retry_backoff=0.1)

        info = {
            'attempt': 0,
            'params_list': [
               {'hostname': 'host1',
                'userid': self.FLAGS.rabbit_userid,
                'password': self.FLAGS.rabbit_password,
                'port': 1234,
                'virtual_host': self.FLAGS.rabbit_virtual_host,
                'transport': 'memory'},
               {'hostname': 'host2',
                'userid': self.FLAGS.rabbit_userid,
                'password': self.FLAGS.rabbit_password,
                'port': 5678,
                'virtual_host': self.FLAGS.rabbit_virtual_host,
                'transport': 'memory'},
               {'hostname': '::1',
                'userid': self.FLAGS.rabbit_userid,
                'password': self.FLAGS.rabbit_password,
                'port': 2345,
                'virtual_host': self.FLAGS.rabbit_virtual_host,
                'transport': 'memory'},
               {'hostname': '2001:0db8:85a3:0042:0000:8a2e:0370:7334',
                'userid': self.FLAGS.rabbit_userid,
                'password': self.FLAGS.rabbit_password,
                'port': 5672,
                'virtual_host': self.FLAGS.rabbit_virtual_host,
                'transport': 'memory'},
            ]
        }

        class MyConnection(kombu.connection.BrokerConnection):
            def __init__(myself, *args, **params):
                super(MyConnection, myself).__init__(*args, **params)
                self.assertEqual(params,
                                 info['params_list'][info['attempt'] %
                                                     len(info['params_list'])])
                info['attempt'] += 1

            def connect(myself):
                if info['attempt'] < 5:
                    # the word timeout is important (see impl_kombu.py:486)
                    raise Exception('connection timeout')
                super(kombu.connection.BrokerConnection, myself).connect()

        self.stubs.Set(kombu.connection, 'BrokerConnection', MyConnection)

        self.rpc.Connection(self.FLAGS)

        self.assertEqual(info['attempt'], 5)

    def test_queue_not_declared_ha_if_ha_off(self):
        self.config(rabbit_ha_queues=False)

        def my_declare(myself):
            self.assertEqual(None,
                             (myself.queue_arguments or {}).get('x-ha-policy'))

        self.stubs.Set(kombu.entity.Queue, 'declare', my_declare)

        with contextlib.closing(
                self.rpc.create_connection(self.FLAGS)) as conn:
            conn.declare_topic_consumer('a_topic', lambda *args: None)

    def test_queue_declared_ha_if_ha_on(self):
        self.config(rabbit_ha_queues=True)

        def my_declare(myself):
            self.assertEqual('all',
                             (myself.queue_arguments or {}).get('x-ha-policy'))

        self.stubs.Set(kombu.entity.Queue, 'declare', my_declare)

        with contextlib.closing(
                self.rpc.create_connection(self.FLAGS)) as conn:
            conn.declare_topic_consumer('a_topic', lambda *args: None)
