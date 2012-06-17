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

import logging
import unittest

import stubout

from openstack.common import cfg
from openstack.common import exception
from openstack.common.rpc import amqp as rpc_amqp
from openstack.common.rpc import common as rpc_common
from openstack.common import testutils
from tests.unit.rpc import common

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


class RpcKombuTestCase(common.BaseRpcAMQPTestCase):
    def setUp(self):
        self.stubs = stubout.StubOutForTesting()
        if kombu:
            FLAGS.set_override('fake_rabbit', True)
            FLAGS.set_override('rpc_response_timeout', 5)
            self.rpc = impl_kombu
        else:
            self.rpc = None
        super(RpcKombuTestCase, self).setUp()

    def tearDown(self):
        self.stubs.UnsetAll()
        self.stubs.SmartUnsetAll()
        if kombu:
            impl_kombu.cleanup()
            FLAGS.reset()
        super(RpcKombuTestCase, self).tearDown()

    @testutils.skip_if(kombu is None, "Test requires kombu")
    def test_reusing_connection(self):
        """Test that reusing a connection returns same one."""
        conn_context = self.rpc.create_connection(FLAGS, new=False)
        conn1 = conn_context.connection
        conn_context.close()
        conn_context = self.rpc.create_connection(FLAGS, new=False)
        conn2 = conn_context.connection
        conn_context.close()
        self.assertEqual(conn1, conn2)

    @testutils.skip_if(kombu is None, "Test requires kombu")
    def test_topic_send_receive(self):
        """Test sending to a topic exchange/queue"""

        conn = self.rpc.create_connection(FLAGS)
        message = 'topic test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message

        conn.declare_topic_consumer('a_topic', _callback)
        conn.topic_send('a_topic', message)
        conn.consume(limit=1)
        conn.close()

        self.assertEqual(self.received_message, message)

    @testutils.skip_if(kombu is None, "Test requires kombu")
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
        conn.topic_send('a_topic', message)
        conn.consume(limit=2)
        conn.close()

        self.assertEqual(self.received_message_1, message)
        self.assertEqual(self.received_message_2, message)

    @testutils.skip_if(kombu is None, "Test requires kombu")
    def test_direct_send_receive(self):
        """Test sending to a direct exchange/queue"""
        conn = self.rpc.create_connection(FLAGS)
        message = 'direct test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message

        conn.declare_direct_consumer('a_direct', _callback)
        conn.direct_send('a_direct', message)
        conn.consume(limit=1)
        conn.close()

        self.assertEqual(self.received_message, message)

    @testutils.skip_if(kombu is None, "Test requires kombu")
    def test_cast_interface_uses_default_options(self):
        """Test kombu rpc.cast"""

        ctxt = rpc_common.CommonRpcContext(user='fake_user',
                                           project='fake_project')

        class MyConnection(impl_kombu.Connection):
            def __init__(myself, *args, **kwargs):
                super(MyConnection, myself).__init__(*args, **kwargs)
                self.assertEqual(
                    myself.params,
                    {'hostname': FLAGS.rabbit_host,
                     'userid': FLAGS.rabbit_userid,
                     'password': FLAGS.rabbit_password,
                     'port': FLAGS.rabbit_port,
                     'virtual_host': FLAGS.rabbit_virtual_host,
                     'transport': 'memory'})

            def topic_send(_context, topic, msg):
                pass

        MyConnection.pool = rpc_amqp.Pool(FLAGS, MyConnection)
        self.stubs.Set(impl_kombu, 'Connection', MyConnection)

        impl_kombu.cast(FLAGS, ctxt, 'fake_topic', {'msg': 'fake'})

    @testutils.skip_if(kombu is None, "Test requires kombu")
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
                    myself.params,
                    {'hostname': server_params['hostname'],
                     'userid': server_params['username'],
                     'password': server_params['password'],
                     'port': server_params['port'],
                     'virtual_host': server_params['virtual_host'],
                     'transport': 'memory'})

            def topic_send(_context, topic, msg):
                pass

        MyConnection.pool = rpc_amqp.Pool(FLAGS, MyConnection)
        self.stubs.Set(impl_kombu, 'Connection', MyConnection)

        impl_kombu.cast_to_server(FLAGS, ctxt, server_params,
                                  'fake_topic', {'msg': 'fake'})

    @testutils.skip_test("kombu memory transport seems buggy with "
                         "fanout queues as this test passes when "
                         "you use rabbit (fake_rabbit=False)")
    def test_fanout_send_receive(self):
        """Test sending to a fanout exchange and consuming from 2 queues"""

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

    @testutils.skip_if(kombu is None, "Test requires kombu")
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

    @testutils.skip_if(kombu is None, "Test requires kombu")
    def test_declare_consumer_ioerrors_will_reconnect(self):
        """Test that an IOError exception causes a reconnection"""
        info = _raise_exc_stub(self.stubs, 2, self.rpc.DirectConsumer,
                               '__init__', 'Socket closed', exc_class=IOError)

        conn = self.rpc.Connection(FLAGS)
        result = conn.declare_consumer(self.rpc.DirectConsumer,
                                       'test_topic', None)

        self.assertEqual(info['called'], 3)
        self.assertTrue(isinstance(result, self.rpc.DirectConsumer))

    @testutils.skip_if(kombu is None, "Test requires kombu")
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

    @testutils.skip_if(kombu is None, "Test requires kombu")
    def test_iterconsume_errors_will_reconnect(self):
        conn = self.rpc.Connection(FLAGS)
        message = 'reconnect test message'

        self.received_message = None

        def _callback(message):
            self.received_message = message

        conn.declare_direct_consumer('a_direct', _callback)
        conn.direct_send('a_direct', message)

        info = _raise_exc_stub(self.stubs, 1, conn.connection,
                               'drain_events', 'foo timeout foo')
        conn.consume(limit=1)
        conn.close()

        self.assertEqual(self.received_message, message)
        # Only called once, because our stub goes away during reconnection

    @testutils.skip_if(kombu is None, "Test requires kombu")
    def test_call_exception(self):
        """Test that exception gets passed back properly.

        rpc.call returns an Exception object.  The value of the
        exception is converted to a string.

        """
        FLAGS.set_override('allowed_rpc_exception_modules', ['exceptions'])
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
            self.assertTrue(value in unicode(exc))
            #Traceback should be included in exception message
            self.assertTrue('raise NotImplementedError(value)' in unicode(exc))

        FLAGS.reset()

    @testutils.skip_if(kombu is None, "Test requires kombu")
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
            self.assertTrue(value in unicode(exc))
            #Traceback should be included in exception message
            self.assertTrue('exception.ApiError' in unicode(exc))
