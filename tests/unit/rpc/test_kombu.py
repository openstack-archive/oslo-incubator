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
import logging

import mock
from oslo.config import cfg
import six

from openstack.common import exception
from openstack.common.rpc import amqp as rpc_amqp
from openstack.common.rpc import common as rpc_common
from tests.unit.rpc import amqp
from tests import utils

try:
    import kombu
    from openstack.common.rpc import impl_kombu
except ImportError:
    kombu = None
    impl_kombu = None


FLAGS = cfg.CONF
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


class KombuStubs:
    @staticmethod
    def setUp(self):
        if kombu:
            self.config(fake_rabbit=True)
            self.config(rpc_response_timeout=5)
            self.rpc = impl_kombu
            self.addCleanup(impl_kombu.cleanup)
        else:
            self.rpc = None


class RpcKombuTestCase(amqp.BaseRpcAMQPTestCase):
    def setUp(self):
        KombuStubs.setUp(self)
        super(RpcKombuTestCase, self).setUp()
        if kombu is None:
            self.skipTest("Test requires kombu")

    def test_reusing_connection(self):
        """Test that reusing a connection returns same one."""
        conn_context = self.rpc.create_connection(FLAGS, new=False)
        conn1 = conn_context.connection
        conn_context.close()
        conn_context = self.rpc.create_connection(FLAGS, new=False)
        conn2 = conn_context.connection
        conn_context.close()
        self.assertEqual(conn1, conn2)

    def test_topic_send_receive(self):
        """Test sending to a topic exchange/queue"""

        conn = self.rpc.create_connection(FLAGS)
        message = 'topic test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message

        conn.declare_topic_consumer('a_topic', _callback)
        conn.topic_send('a_topic', rpc_common.serialize_msg(message))
        conn.consume(limit=1)
        conn.close()

        self.assertEqual(self.received_message, message)

    def test_message_ttl_on_timeout(self):
        """Test message ttl being set by request timeout. The message
        should die on the vine and never arrive.
        """
        conn = self.rpc.create_connection(FLAGS)
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
        """Test sending to a topic exchange/queue with an exchange name"""

        conn = self.rpc.create_connection(FLAGS)
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
        """Test sending to a topic exchange with multiple queues"""

        conn = self.rpc.create_connection(FLAGS)
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

        conn = self.rpc.create_connection(FLAGS)
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

        conn = self.rpc.create_connection(FLAGS)
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
        """Test sending to a direct exchange/queue"""
        conn = self.rpc.create_connection(FLAGS)
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
        """Test kombu rpc.cast"""

        ctxt = rpc_common.CommonRpcContext(user='fake_user',
                                           project='fake_project')

        class MyConnection(impl_kombu.Connection):
            def __init__(myself, *args, **kwargs):
                super(MyConnection, myself).__init__(*args, **kwargs)
                self.assertEqual(
                    myself.params_list,
                    [{'hostname': FLAGS.rabbit_host,
                      'userid': FLAGS.rabbit_userid,
                      'password': FLAGS.rabbit_password,
                      'port': FLAGS.rabbit_port,
                      'virtual_host': FLAGS.rabbit_virtual_host,
                      'transport': 'memory'}])

            def topic_send(_context, topic, msg):
                pass

        MyConnection.pool = rpc_amqp.Pool(FLAGS, MyConnection)
        self.stubs.Set(impl_kombu, 'Connection', MyConnection)

        impl_kombu.cast(FLAGS, ctxt, 'fake_topic', {'msg': 'fake'})

    def test_cast_to_server_uses_server_params(self):
        """Test kombu rpc.cast"""

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

        MyConnection.pool = rpc_amqp.Pool(FLAGS, MyConnection)
        self.stubs.Set(impl_kombu, 'Connection', MyConnection)

        impl_kombu.cast_to_server(FLAGS, ctxt, server_params,
                                  'fake_topic', {'msg': 'fake'})

    def test_fanout_send_receive(self):
        """Test sending to a fanout exchange and consuming from 2 queues"""

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

        conn = self.rpc.Connection(FLAGS)
        result = conn.declare_consumer(self.rpc.DirectConsumer,
                                       'test_topic', None)

        self.assertEqual(info['called'], 3)
        self.assertTrue(isinstance(result, self.rpc.DirectConsumer))

        # Test that any exception in transport.connection_errors causes
        # a reconnection
        self.stubs.UnsetAll()

        info = _raise_exc_stub(self.stubs, 1, self.rpc.DirectConsumer,
                               '__init__', 'meow')

        conn = self.rpc.Connection(FLAGS)
        conn.connection_errors = (MyException, )

        result = conn.declare_consumer(self.rpc.DirectConsumer,
                                       'test_topic', None)

        self.assertEqual(info['called'], 2)
        self.assertTrue(isinstance(result, self.rpc.DirectConsumer))

    def test_declare_consumer_ioerrors_will_reconnect(self):
        """Test that an IOError exception causes a reconnection"""
        info = _raise_exc_stub(self.stubs, 2, self.rpc.DirectConsumer,
                               '__init__', 'Socket closed', exc_class=IOError)

        conn = self.rpc.Connection(FLAGS)
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

        conn = self.rpc.Connection(FLAGS)
        conn.publisher_send(self.rpc.DirectPublisher, 'test_topic', 'msg')

        self.assertEqual(info['called'], 3)
        self.stubs.UnsetAll()

        info = _raise_exc_stub(self.stubs, 2, self.rpc.DirectPublisher,
                               'send', 'foo timeout foo')

        conn = self.rpc.Connection(FLAGS)
        conn.publisher_send(self.rpc.DirectPublisher, 'test_topic', 'msg')

        self.assertEqual(info['called'], 3)

        # Test that any exception in transport.connection_errors causes
        # a reconnection when declaring the publisher class and when
        # calling send()
        self.stubs.UnsetAll()

        info = _raise_exc_stub(self.stubs, 1, self.rpc.DirectPublisher,
                               '__init__', 'meow')

        conn = self.rpc.Connection(FLAGS)
        conn.connection_errors = (MyException, )

        conn.publisher_send(self.rpc.DirectPublisher, 'test_topic', 'msg')

        self.assertEqual(info['called'], 2)
        self.stubs.UnsetAll()

        info = _raise_exc_stub(self.stubs, 1, self.rpc.DirectPublisher,
                               'send', 'meow')

        conn = self.rpc.Connection(FLAGS)
        conn.connection_errors = (MyException, )

        conn.publisher_send(self.rpc.DirectPublisher, 'test_topic', 'msg')

        self.assertEqual(info['called'], 2)

    def test_iterconsume_errors_will_reconnect(self):
        conn = self.rpc.Connection(FLAGS)
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
                          FLAGS,
                          self.context,
                          'test',
                          {"method": "fail",
                           "args": {"value": value}})
        try:
            self.rpc.call(FLAGS, self.context,
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
        self.assertRaises(exception.ApiError,
                          self.rpc.call,
                          FLAGS,
                          self.context,
                          'test',
                          {"method": "fail_converted",
                           "args": {"value": value}})
        try:
            self.rpc.call(FLAGS, self.context,
                          'test',
                          {"method": "fail_converted",
                           "args": {"value": value}})
            self.fail("should have thrown Exception")
        except exception.ApiError as exc:
            self.assertTrue(value in six.text_type(exc))
            #Traceback should be included in exception message
            self.assertTrue('exception.ApiError' in six.text_type(exc))

    def test_create_worker(self):
        meth = 'declare_topic_consumer'
        with mock.patch.object(self.rpc.Connection, meth) as p:
            conn = self.rpc.create_connection(FLAGS)
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

    def test_join_consumer_pool(self):
        meth = 'declare_topic_consumer'
        with mock.patch.object(self.rpc.Connection, meth) as p:
            conn = self.rpc.create_connection(FLAGS)
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
            )


class RpcKombuHATestCase(utils.BaseTestCase):
    def setUp(self):
        super(RpcKombuHATestCase, self).setUp()
        KombuStubs.setUp(self)
        self.addCleanup(FLAGS.reset)

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
                'userid': FLAGS.rabbit_userid,
                'password': FLAGS.rabbit_password,
                'port': 1234,
                'virtual_host': FLAGS.rabbit_virtual_host,
                'transport': 'memory'},
               {'hostname': 'host2',
                'userid': FLAGS.rabbit_userid,
                'password': FLAGS.rabbit_password,
                'port': 5678,
                'virtual_host': FLAGS.rabbit_virtual_host,
                'transport': 'memory'},
               {'hostname': '::1',
                'userid': FLAGS.rabbit_userid,
                'password': FLAGS.rabbit_password,
                'port': 2345,
                'virtual_host': FLAGS.rabbit_virtual_host,
                'transport': 'memory'},
               {'hostname': '2001:0db8:85a3:0042:0000:8a2e:0370:7334',
                'userid': FLAGS.rabbit_userid,
                'password': FLAGS.rabbit_password,
                'port': 5672,
                'virtual_host': FLAGS.rabbit_virtual_host,
                'transport': 'memory'},
            ]
        }

        import kombu.connection

        class MyConnection(kombu.connection.BrokerConnection):
            def __init__(myself, *args, **params):
                super(MyConnection, myself).__init__(*args, **params)
                self.assertEqual(params,
                                 info['params_list'][info['attempt'] %
                                                     len(info['params_list'])])
                info['attempt'] = info['attempt'] + 1

            def connect(myself):
                if info['attempt'] < 5:
                    # the word timeout is important (see impl_kombu.py:486)
                    raise Exception('connection timeout')
                super(kombu.connection.BrokerConnection, myself).connect()

        self.stubs.Set(kombu.connection, 'BrokerConnection', MyConnection)

        self.rpc.Connection(FLAGS)

        self.assertEqual(info['attempt'], 5)

    def test_queue_not_declared_ha_if_ha_off(self):
        self.config(rabbit_ha_queues=False)

        import kombu.entity

        def my_declare(myself):
            self.assertEqual(None,
                             (myself.queue_arguments or {}).get('x-ha-policy'))

        self.stubs.Set(kombu.entity.Queue, 'declare', my_declare)

        with contextlib.closing(self.rpc.create_connection(FLAGS)) as conn:
            conn.declare_topic_consumer('a_topic', lambda *args: None)

    def test_queue_declared_ha_if_ha_on(self):
        self.config(rabbit_ha_queues=True)

        import kombu.entity

        def my_declare(myself):
            self.assertEqual('all',
                             (myself.queue_arguments or {}).get('x-ha-policy'))

        self.stubs.Set(kombu.entity.Queue, 'declare', my_declare)

        with contextlib.closing(self.rpc.create_connection(FLAGS)) as conn:
            conn.declare_topic_consumer('a_topic', lambda *args: None)
