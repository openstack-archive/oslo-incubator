# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
# Copyright 2012, Red Hat, Inc.
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
Unit Tests for remote procedure calls using qpid
"""

import eventlet
eventlet.monkey_patch()

import logging

import fixtures
import time
import testtools
import mox
from oslo.config import cfg

from openstack.common import context
from openstack.common import jsonutils
from openstack.common.rpc import amqp as rpc_amqp
from tests import utils
from openstack.common.rpc import common as rpc_common

try:
    import qpid
    from openstack.common.rpc import impl_qpid
except ImportError:
    qpid = None
    impl_qpid = None

FLAGS = cfg.CONF


class RpcQpidTestCase(utils.BaseTestCase):
    """
    Exercise the public API of impl_qpid utilizing mox.

    This set of tests utilizes mox to replace the Qpid objects and ensures
    that the right operations happen on them when the various public rpc API
    calls are exercised.  The API calls tested here include:

        openstack.common.rpc.create_connection()
        openstack.common.rpc.common.Connection.create_consumer()
        openstack.common.rpc.common.Connection.close()
        openstack.common.rpc.cast()
        openstack.common.rpc.fanout_cast()
        openstack.common.rpc.call()
        openstack.common.rpc.multicall()
    """

    def setUp(self):
        super(RpcQpidTestCase, self).setUp()

        if qpid is None:
            self.skipTest("Test required qpid")

        self.mock_connection = None
        self.mock_session = None
        self.mock_sender = None
        self.mock_receiver = None
        self.mox = mox.Mox()

        self.orig_connection = qpid.messaging.Connection
        self.orig_session = qpid.messaging.Session
        self.orig_sender = qpid.messaging.Sender
        self.orig_receiver = qpid.messaging.Receiver

        self.useFixture(
            fixtures.MonkeyPatch('qpid.messaging.Connection',
                                 lambda *_x, **_y: self.mock_connection))
        self.useFixture(
            fixtures.MonkeyPatch('qpid.messaging.Session',
                                 lambda *_x, **_y: self.mock_session))
        self.useFixture(
            fixtures.MonkeyPatch('qpid.messaging.Sender',
                                 lambda *_x, **_y: self.mock_sender))
        self.useFixture(
            fixtures.MonkeyPatch('qpid.messaging.Receiver',
                                 lambda *_x, **_y: self.mock_receiver))

    def cleanUp(self):
        if impl_qpid:
            # Need to reset this in case we changed the connection_cls
            # in self._setup_to_server_tests()
            impl_qpid.Connection.pool.connection_cls = impl_qpid.Connection

    def test_create_connection(self):
        self.mock_connection = self.mox.CreateMock(self.orig_connection)
        self.mock_session = self.mox.CreateMock(self.orig_session)

        self.mock_connection.opened().AndReturn(False)
        self.mock_connection.open()
        self.mock_connection.session().AndReturn(self.mock_session)
        self.mock_connection.close()

        self.mox.ReplayAll()

        connection = impl_qpid.create_connection(FLAGS)
        connection.close()

    def _test_create_consumer(self, fanout):
        self.mock_connection = self.mox.CreateMock(self.orig_connection)
        self.mock_session = self.mox.CreateMock(self.orig_session)
        self.mock_receiver = self.mox.CreateMock(self.orig_receiver)

        self.mock_connection.opened().AndReturn(False)
        self.mock_connection.open()
        self.mock_connection.session().AndReturn(self.mock_session)
        if fanout:
            # The link name includes a UUID, so match it with a regex.
            expected_address = mox.Regex(
                r'^impl_qpid_test_fanout ; '
                '{"node": {"x-declare": {"auto-delete": true, "durable": '
                'false, "type": "fanout"}, "type": "topic"}, "create": '
                '"always", "link": {"x-declare": {"auto-delete": true, '
                '"exclusive": true, "durable": false}, "durable": true, '
                '"name": "impl_qpid_test_fanout_.*"}}$')
        else:
            expected_address = (
                'openstack/impl_qpid_test ; {"node": {"x-declare": '
                '{"auto-delete": true, "durable": true}, "type": "topic"}, '
                '"create": "always", "link": {"x-declare": {"auto-delete": '
                'true, "exclusive": false, "durable": false}, "durable": '
                'true, "name": "impl_qpid_test"}}')
        self.mock_session.receiver(expected_address).AndReturn(
            self.mock_receiver)
        self.mock_receiver.capacity = 1
        self.mock_connection.close()

        self.mox.ReplayAll()

        connection = impl_qpid.create_connection(FLAGS)
        connection.create_consumer("impl_qpid_test",
                                   lambda *_x, **_y: None,
                                   fanout)
        connection.close()

    def test_create_consumer(self):
        self._test_create_consumer(fanout=False)

    def test_create_consumer_fanout(self):
        self._test_create_consumer(fanout=True)

    def test_create_worker(self):
        self.mock_connection = self.mox.CreateMock(self.orig_connection)
        self.mock_session = self.mox.CreateMock(self.orig_session)
        self.mock_receiver = self.mox.CreateMock(self.orig_receiver)

        self.mock_connection.opened().AndReturn(False)
        self.mock_connection.open()
        self.mock_connection.session().AndReturn(self.mock_session)
        expected_address = (
            'openstack/impl_qpid_test ; {"node": {"x-declare": '
            '{"auto-delete": true, "durable": true}, "type": "topic"}, '
            '"create": "always", "link": {"x-declare": {"auto-delete": '
            'true, "exclusive": false, "durable": false}, "durable": '
            'true, "name": "impl.qpid.test.workers"}}')
        self.mock_session.receiver(expected_address).AndReturn(
            self.mock_receiver)
        self.mock_receiver.capacity = 1
        self.mock_connection.close()

        self.mox.ReplayAll()

        connection = impl_qpid.create_connection(FLAGS)
        connection.create_worker("impl_qpid_test",
                                 lambda *_x, **_y: None,
                                 'impl.qpid.test.workers',
                                 )
        connection.close()

    def test_join_consumer_pool(self):
        self.mock_connection = self.mox.CreateMock(self.orig_connection)
        self.mock_session = self.mox.CreateMock(self.orig_session)
        self.mock_receiver = self.mox.CreateMock(self.orig_receiver)

        self.mock_connection.opened().AndReturn(False)
        self.mock_connection.open()
        self.mock_connection.session().AndReturn(self.mock_session)
        expected_address = (
            'exchange-name/impl_qpid_test ; {"node": {"x-declare": '
            '{"auto-delete": true, "durable": true}, "type": "topic"}, '
            '"create": "always", "link": {"x-declare": {"auto-delete": '
            'true, "exclusive": false, "durable": false}, "durable": '
            'true, "name": "impl.qpid.test.consumer.pool"}}')
        self.mock_session.receiver(expected_address).AndReturn(
            self.mock_receiver)
        self.mock_receiver.capacity = 1
        self.mock_connection.close()

        self.mox.ReplayAll()

        connection = impl_qpid.create_connection(FLAGS)
        connection.join_consumer_pool(
            callback=lambda *_x, **_y: None,
            pool_name='impl.qpid.test.consumer.pool',
            topic="impl_qpid_test",
            exchange_name='exchange-name',
        )
        connection.close()

    def test_topic_consumer(self):
        self.mock_connection = self.mox.CreateMock(self.orig_connection)
        self.mock_session = self.mox.CreateMock(self.orig_session)
        self.mock_receiver = self.mox.CreateMock(self.orig_receiver)

        self.mock_connection.opened().AndReturn(False)
        self.mock_connection.open()
        self.mock_connection.session().AndReturn(self.mock_session)
        expected_address = (
            'foobar/impl_qpid_test ; {"node": {"x-declare": '
            '{"auto-delete": true, "durable": true}, "type": "topic"}, '
            '"create": "always", "link": {"x-declare": {"auto-delete": '
            'true, "exclusive": false, "durable": false}, "durable": '
            'true, "name": "impl.qpid.test.workers"}}')
        self.mock_session.receiver(expected_address).AndReturn(
            self.mock_receiver)
        self.mock_receiver.capacity = 1
        self.mock_connection.close()

        self.mox.ReplayAll()

        connection = impl_qpid.create_connection(FLAGS)
        connection.declare_topic_consumer("impl_qpid_test",
                                          lambda *_x, **_y: None,
                                          queue_name='impl.qpid.test.workers',
                                          exchange_name='foobar')
        connection.close()

    def _test_cast(self, fanout, server_params=None):
        self.mock_connection = self.mox.CreateMock(self.orig_connection)
        self.mock_session = self.mox.CreateMock(self.orig_session)
        self.mock_sender = self.mox.CreateMock(self.orig_sender)

        self.mock_connection.opened().AndReturn(False)
        self.mock_connection.open()

        self.mock_connection.session().AndReturn(self.mock_session)
        if fanout:
            expected_address = (
                'impl_qpid_test_fanout ; '
                '{"node": {"x-declare": {"auto-delete": true, '
                '"durable": false, "type": "fanout"}, '
                '"type": "topic"}, "create": "always"}')
        else:
            expected_address = (
                'openstack/impl_qpid_test ; {"node": {"x-declare": '
                '{"auto-delete": true, "durable": false}, "type": "topic"}, '
                '"create": "always"}')
        self.mock_session.sender(expected_address).AndReturn(self.mock_sender)
        self.mock_sender.send(mox.IgnoreArg())
        if not server_params:
            # This is a pooled connection, so instead of closing it, it
            # gets reset, which is just creating a new session on the
            # connection.
            self.mock_session.close()
            self.mock_connection.session().AndReturn(self.mock_session)

        self.mox.ReplayAll()

        try:
            ctx = context.RequestContext("user", "project")

            args = [FLAGS, ctx, "impl_qpid_test",
                    {"method": "test_method", "args": {}}]

            if server_params:
                args.insert(2, server_params)
                if fanout:
                    method = impl_qpid.fanout_cast_to_server
                else:
                    method = impl_qpid.cast_to_server
            else:
                if fanout:
                    method = impl_qpid.fanout_cast
                else:
                    method = impl_qpid.cast

            method(*args)
        finally:
            while impl_qpid.Connection.pool.free_items:
                # Pull the mock connection object out of the connection pool so
                # that it doesn't mess up other test cases.
                impl_qpid.Connection.pool.get()

    def test_cast(self):
        self._test_cast(fanout=False)

    def test_fanout_cast(self):
        self._test_cast(fanout=True)

    def _setup_to_server_tests(self, server_params):
        class MyConnection(impl_qpid.Connection):
            def __init__(myself, *args, **kwargs):
                super(MyConnection, myself).__init__(*args, **kwargs)
                self.assertEqual(myself.connection.username,
                                 server_params['username'])
                self.assertEqual(myself.connection.password,
                                 server_params['password'])
                self.assertEqual(myself.brokers,
                                 [server_params['hostname'] + ':' +
                                 str(server_params['port'])])

        MyConnection.pool = rpc_amqp.Pool(FLAGS, MyConnection)
        self.stubs.Set(impl_qpid, 'Connection', MyConnection)

    def test_cast_to_server(self):
        server_params = {'username': 'fake_username',
                         'password': 'fake_password',
                         'hostname': 'fake_hostname',
                         'port': 31337}
        self._setup_to_server_tests(server_params)
        self._test_cast(fanout=False, server_params=server_params)

    def test_fanout_cast_to_server(self):
        server_params = {'username': 'fake_username',
                         'password': 'fake_password',
                         'hostname': 'fake_hostname',
                         'port': 31337}
        self._setup_to_server_tests(server_params)
        self._test_cast(fanout=True, server_params=server_params)

    def _test_call(self, multi):
        self.mock_connection = self.mox.CreateMock(self.orig_connection)
        self.mock_session = self.mox.CreateMock(self.orig_session)
        self.mock_sender = self.mox.CreateMock(self.orig_sender)
        self.mock_receiver = self.mox.CreateMock(self.orig_receiver)

        self.mock_connection.opened().AndReturn(False)
        self.mock_connection.open()
        self.mock_connection.session().AndReturn(self.mock_session)
        rcv_addr = mox.Regex(
            r'^.*/.* ; {"node": {"x-declare": {"auto-delete":'
            ' true, "durable": true, "type": "direct"}, "type": '
            '"topic"}, "create": "always", "link": {"x-declare": '
            '{"auto-delete": true, "exclusive": true, "durable": '
            'false}, "durable": true, "name": ".*"}}')
        self.mock_session.receiver(rcv_addr).AndReturn(self.mock_receiver)
        self.mock_receiver.capacity = 1
        send_addr = (
            'openstack/impl_qpid_test ; {"node": {"x-declare": '
            '{"auto-delete": true, "durable": false}, "type": "topic"}, '
            '"create": "always"}')
        self.mock_session.sender(send_addr).AndReturn(self.mock_sender)
        self.mock_sender.send(mox.IgnoreArg())

        self.mock_session.next_receiver(timeout=mox.IsA(int)).AndReturn(
            self.mock_receiver)
        self.mock_receiver.fetch().AndReturn(qpid.messaging.Message(
            {"result": "foo", "failure": False, "ending": False}))
        self.mock_session.acknowledge(mox.IgnoreArg())
        if multi:
            self.mock_session.next_receiver(timeout=mox.IsA(int)).AndReturn(
                self.mock_receiver)
            self.mock_receiver.fetch().AndReturn(
                qpid.messaging.Message({"result": "bar", "failure": False,
                                        "ending": False}))
            self.mock_session.acknowledge(mox.IgnoreArg())
            self.mock_session.next_receiver(timeout=mox.IsA(int)).AndReturn(
                self.mock_receiver)
            self.mock_receiver.fetch().AndReturn(
                qpid.messaging.Message({"result": "baz", "failure": False,
                                        "ending": False}))
            self.mock_session.acknowledge(mox.IgnoreArg())
        self.mock_session.next_receiver(timeout=mox.IsA(int)).AndReturn(
            self.mock_receiver)
        self.mock_receiver.fetch().AndReturn(qpid.messaging.Message(
            {"failure": False, "ending": True}))
        self.mock_session.acknowledge(mox.IgnoreArg())
        self.mock_session.close()
        self.mock_connection.session().AndReturn(self.mock_session)

        self.mox.ReplayAll()

        try:
            ctx = context.RequestContext("user", "project")

            if multi:
                method = impl_qpid.multicall
            else:
                method = impl_qpid.call

            res = method(FLAGS, ctx, "impl_qpid_test",
                         {"method": "test_method", "args": {}})

            if multi:
                self.assertEquals(list(res), ["foo", "bar", "baz"])
            else:
                self.assertEquals(res, "foo")
        finally:
            while impl_qpid.Connection.pool.free_items:
                # Pull the mock connection object out of the connection pool so
                # that it doesn't mess up other test cases.
                impl_qpid.Connection.pool.get()

    def test_call(self):
        self._test_call(multi=False)

    def _test_call_with_timeout(self, timeout, expect_failure):
        # TODO(beagles): should be possible to refactor this method and
        # _test_call to share common code. Maybe making the messages
        # and test checks parameters, etc.
        self.mock_connection = self.mox.CreateMock(self.orig_connection)
        self.mock_session = self.mox.CreateMock(self.orig_session)
        self.mock_sender = self.mox.CreateMock(self.orig_sender)
        self.mock_receiver = self.mox.CreateMock(self.orig_receiver)

        self.mock_connection.opened().AndReturn(False)
        self.mock_connection.open()
        self.mock_connection.session().AndReturn(self.mock_session)
        rcv_addr = mox.Regex(
            r'^.*/.* ; {"node": {"x-declare": {"auto-delete":'
            ' true, "durable": true, "type": "direct"}, "type": '
            '"topic"}, "create": "always", "link": {"x-declare": '
            '{"auto-delete": true, "exclusive": true, "durable": '
            'false}, "durable": true, "name": ".*"}}')
        self.mock_session.receiver(rcv_addr).AndReturn(self.mock_receiver)
        self.mock_receiver.capacity = 1
        send_addr = (
            'openstack/impl_qpid_test ; {"node": {"x-declare": '
            '{"auto-delete": true, "durable": false}, "type": "topic"}, '
            '"create": "always"}')
        self.mock_session.sender(send_addr).AndReturn(self.mock_sender)
        self.mock_sender.send(mox.IgnoreArg())

        if expect_failure:
            self.mock_session.next_receiver(timeout=mox.IsA(int)).AndRaise(
                qpid.messaging.exceptions.Empty())
            self.mock_receiver.fetch()
            self.mock_session.close()
            self.mock_connection.session().AndReturn(self.mock_session)
        else:
            self.mock_session.next_receiver(timeout=mox.IsA(int)).AndReturn(
                self.mock_receiver)
            self.mock_receiver.fetch().AndReturn(qpid.messaging.Message(
                {"result": "foo", "failure": False, "ending": False}))
            self.mock_session.acknowledge(mox.IgnoreArg())
            self.mock_session.next_receiver(timeout=mox.IsA(int)).AndReturn(
                self.mock_receiver)
            self.mock_receiver.fetch().AndReturn(qpid.messaging.Message(
                {"failure": False, "ending": True}))
            self.mock_session.acknowledge(mox.IgnoreArg())
            self.mock_session.close()
            self.mock_connection.session().AndReturn(self.mock_session)

        self.mox.ReplayAll()

        try:
            ctx = context.RequestContext("user", "project")
            method = impl_qpid.call
            if expect_failure:
                try:
                    res = method(FLAGS, ctx, "impl_qpid_test",
                                 {"method": "test_method", "args": {}},
                                 timeout)
                    self.fail('Expected a timeout exception')
                except rpc_common.Timeout:
                    # Good, this is expected!
                    pass
            else:
                res = method(FLAGS, ctx, "impl_qpid_test",
                             {"method": "test_method", "args": {}}, timeout)
                self.assertEquals(res, "foo")
        finally:
            while impl_qpid.Connection.pool.free_items:
                # Pull the mock connection object out of the connection pool so
                # that it doesn't mess up other test cases.
                impl_qpid.Connection.pool.get()

    def test_call(self):
        self._test_call(multi=False)

    def test_call_with_timeout(self):
        """A little more indepth for a timeout test. Specifically we are
        looking to simulate the event sent to qpid dying on the vine due
        to a TTL. A string test that actually involved qpid would be
        excellent, but this at least verifies that the exceptions flow
        like they should.  TODO(beagles): is this really necessary or is
        the the case for qpid at least the basic timeout test is
        sufficient.
        """
        self._test_call_with_timeout(timeout=5, expect_failure=False)
        self._test_call_with_timeout(timeout=0, expect_failure=True)

    def test_multicall(self):
        self._test_call(multi=True)

    def _test_publisher(self, message=True):
        """Test that messages containing long strings are correctly serialized
           in a way that Qpid can handle.

        :param message: The publisher may be passed either a Qpid Message
        object or a bare dict.  This parameter controls which of those the test
        will send.
        """
        self.sent_msg = None

        def send_stub(msg):
            self.sent_msg = msg

        # Qpid cannot serialize a dict containing a string > 65535 chars.
        raw_msg = {'test': 'a' * 65536}
        if message:
            base_msg = qpid.messaging.Message(raw_msg)
        else:
            base_msg = raw_msg
        expected_msg = qpid.messaging.Message(jsonutils.dumps(raw_msg))
        expected_msg.content_type = impl_qpid.JSON_CONTENT_TYPE
        mock_session = self.mox.CreateMock(self.orig_session)
        mock_sender = self.mox.CreateMock(self.orig_sender)
        mock_session.sender(mox.IgnoreArg()).AndReturn(mock_sender)
        self.stubs.Set(mock_sender, 'send', send_stub)
        self.mox.ReplayAll()

        publisher = impl_qpid.Publisher(mock_session, 'test_node')
        publisher.send(base_msg)

        self.assertEqual(self.sent_msg.content, expected_msg.content)
        self.assertEqual(self.sent_msg.content_type, expected_msg.content_type)

    def test_publisher_long_message(self):
        self._test_publisher(message=True)

    def test_publisher_long_dict(self):
        self._test_publisher(message=False)

    def _test_consumer_long_message(self, json=True):
        """Verify that the Qpid implementation correctly deserializes
           message content.

        :param json: For compatibility, this code needs to support both
            messages that are and are not JSON encoded.  This param
            specifies which is being tested.
        """
        def fake_callback(msg):
            self.received_msg = msg

        # The longest string Qpid can handle itself
        chars = 65535
        if json:
            # The first length that requires JSON encoding
            chars = 65536
        raw_msg = {'test': 'a' * chars}
        if json:
            fake_message = qpid.messaging.Message(jsonutils.dumps(raw_msg))
            fake_message.content_type = impl_qpid.JSON_CONTENT_TYPE
        else:
            fake_message = qpid.messaging.Message(raw_msg)
        mock_session = self.mox.CreateMock(self.orig_session)
        mock_receiver = self.mox.CreateMock(self.orig_receiver)
        mock_session.receiver(mox.IgnoreArg()).AndReturn(mock_receiver)
        mock_receiver.fetch().AndReturn(fake_message)
        mock_session.acknowledge(mox.IgnoreArg())
        self.mox.ReplayAll()

        consumer = impl_qpid.DirectConsumer(None,
                                            mock_session,
                                            'bogus_msg_id',
                                            fake_callback)
        consumer.consume()

        self.assertEqual(self.received_msg, raw_msg)

    def test_consumer_long_message(self):
        self._test_consumer_long_message(json=True)

    def test_consumer_long_message_no_json(self):
        self._test_consumer_long_message(json=False)


#
#from nova.tests.rpc import common
#
# Qpid does not have a handy in-memory transport like kombu, so it's not
# terribly straight forward to take advantage of the common unit tests.
# However, at least at the time of this writing, the common unit tests all pass
# with qpidd running.
#
# class RpcQpidCommonTestCase(common._BaseRpcTestCase):
#     def setUp(self):
#         self.rpc = impl_qpid
#         super(RpcQpidCommonTestCase, self).setUp()
#
#     def tearDown(self):
#         super(RpcQpidCommonTestCase, self).tearDown()
#
