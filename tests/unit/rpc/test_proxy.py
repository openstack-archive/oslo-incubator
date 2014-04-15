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
Unit Tests for rpc.proxy
"""

import copy

from oslotest import base as test_base
import six

from openstack.common import context
from openstack.common.fixture import config
from openstack.common.fixture import moxstubout
from openstack.common import rpc
from openstack.common.rpc import common as rpc_common
from openstack.common.rpc import proxy
from openstack.common.rpc import serializer as rpc_serializer


class RpcProxyTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(RpcProxyTestCase, self).setUp()
        self.config = self.useFixture(config.Config()).config
        moxfixture = self.useFixture(moxstubout.MoxStubout())
        self.mox = moxfixture.mox
        self.stubs = moxfixture.stubs

    def cleanUp(self):
        super(RpcProxyTestCase, self).cleanUp()
        self.mox.VerifyAll()

    def _test_rpc_method(self, rpc_method, has_timeout=False, has_retval=False,
                         server_params=None, supports_topic_override=True):
        topic = 'fake_topic'
        rpc_proxy = proxy.RpcProxy(topic, '1.0')
        ctxt = context.RequestContext('fake_user', 'fake_project')
        msg = {'method': 'fake_method', 'args': {'x': 'y'}}
        expected_msg = {'method': 'fake_method', 'args': {'x': 'y'},
                        'version': '1.0'}

        expected_retval = 'hi' if has_retval else None

        self.fake_args = None
        self.fake_kwargs = None

        def _fake_rpc_method(*args, **kwargs):
            self.fake_args = args
            self.fake_kwargs = kwargs
            if has_retval:
                return expected_retval

        def _fake_rpc_method_timeout(*args, **kwargs):
            self.fake_args = args
            self.fake_kwargs = kwargs
            raise rpc_common.Timeout("The spider got you")

        def _check_args(context, topic, msg, timeout=None):
            expected_args = [context, topic, msg]
            if server_params:
                expected_args.insert(1, server_params)
            if has_timeout:
                expected_args.append(timeout)
            self.assertEqual(tuple(expected_args), self.fake_args)

        self.stubs.Set(rpc, rpc_method, _fake_rpc_method)

        args = [ctxt, msg]
        if server_params:
            args.insert(1, server_params)

        # Base method usage
        retval = getattr(rpc_proxy, rpc_method)(*args)
        self.assertEqual(retval, expected_retval)
        _check_args(ctxt, topic, expected_msg)

        # overriding the version
        retval = getattr(rpc_proxy, rpc_method)(*args, version='1.1')
        self.assertEqual(retval, expected_retval)
        new_msg = copy.deepcopy(expected_msg)
        new_msg['version'] = '1.1'
        _check_args(ctxt, topic, new_msg)

        # override the version to be above a specified cap
        rpc_proxy.version_cap = '1.0'
        self.assertRaises(rpc_common.RpcVersionCapError,
                          getattr(rpc_proxy, rpc_method), *args, version='1.1')
        rpc_proxy.version_cap = None

        if has_timeout:
            # Set a timeout
            retval = getattr(rpc_proxy, rpc_method)(ctxt, msg, timeout=42)
            self.assertEqual(retval, expected_retval)
            _check_args(ctxt, topic, expected_msg, timeout=42)

            # Make it timeout and check that the exception is written as
            # expected
            self.stubs.Set(rpc, rpc_method, _fake_rpc_method_timeout)
            try:
                getattr(rpc_proxy, rpc_method)(*args, timeout=42)
                self.fail("This should have raised a Timeout exception")
            except rpc_common.Timeout as exc:
                self.assertEqual(exc.info, 'The spider got you')
                self.assertEqual(exc.topic, 'fake_topic')
                self.assertEqual(exc.method, 'fake_method')
                self.assertEqual(
                    u'Timeout while waiting on RPC response - '
                    'topic: "fake_topic", RPC method: "fake_method" '
                    'info: "The spider got you"', six.text_type(exc))
            _check_args(ctxt, topic, expected_msg, timeout=42)
            self.stubs.Set(rpc, rpc_method, _fake_rpc_method)

        if supports_topic_override:
            # set a topic
            new_topic = 'foo.bar'
            retval = getattr(rpc_proxy, rpc_method)(*args, topic=new_topic)
            self.assertEqual(retval, expected_retval)
            _check_args(ctxt, new_topic, expected_msg)

    def test_call(self):
        self._test_rpc_method('call', has_timeout=True, has_retval=True)

    def test_multicall(self):
        self._test_rpc_method('multicall', has_timeout=True, has_retval=True)

    def test_cast(self):
        self._test_rpc_method('cast')

    def test_fanout_cast(self):
        self._test_rpc_method('fanout_cast', supports_topic_override=False)

    def test_cast_to_server(self):
        self._test_rpc_method('cast_to_server', server_params={'blah': 1})

    def test_fanout_cast_to_server(self):
        self._test_rpc_method(
            'fanout_cast_to_server',
            server_params={'blah': 1}, supports_topic_override=False)

    def test_make_namespaced_msg(self):
        msg = proxy.RpcProxy.make_namespaced_msg('test_method', 'x', a=1, b=2)
        expected = {'method': 'test_method', 'namespace': 'x',
                    'args': {'a': 1, 'b': 2}}
        self.assertEqual(msg, expected)

    def test_make_msg_with_no_namespace(self):
        proxy_obj = proxy.RpcProxy('fake', '1.0')
        msg = proxy_obj.make_msg('test_method', a=1, b=2)
        expected = {'method': 'test_method', 'namespace': None,
                    'args': {'a': 1, 'b': 2}}
        self.assertEqual(msg, expected)

    def test_make_msg_with_namespace(self):
        class TestProxy(proxy.RpcProxy):
            RPC_API_NAMESPACE = 'meow'

        proxy_obj = TestProxy('fake', '1.0')
        msg = proxy_obj.make_msg('test_method', a=1, b=2)
        expected = {'method': 'test_method', 'namespace': 'meow',
                    'args': {'a': 1, 'b': 2}}
        self.assertEqual(msg, expected)

    def test_serializer(self):
        ctxt = context.RequestContext('fake', 'fake')
        serializer = rpc_serializer.NoOpSerializer()

        self.mox.StubOutWithMock(serializer, 'serialize_entity')
        self.mox.StubOutWithMock(serializer, 'deserialize_entity')
        self.mox.StubOutWithMock(rpc, 'call')

        serializer.serialize_entity(ctxt, 1).AndReturn(1)
        serializer.serialize_entity(ctxt, 2).AndReturn(2)
        rpc.call(ctxt, 'fake',
                 {'args': {'a': 1, 'b': 2},
                  'namespace': None,
                  'method': 'foo',
                  'version': '1.0'},
                 None).AndReturn('foo')
        serializer.deserialize_entity(ctxt, 'foo').AndReturn('worked!')

        self.mox.ReplayAll()

        rpc_proxy = proxy.RpcProxy('fake', '1.0', serializer=serializer)
        msg = rpc_proxy.make_msg('foo', a=1, b=2)
        result = rpc_proxy.call(ctxt, msg)
        self.assertEqual(result, 'worked!')

    def test_can_send_version(self):
        proxy_obj = proxy.RpcProxy('fake', '1.0', version_cap='1.5')
        self.assertTrue(proxy_obj.can_send_version('1.5'))
        self.assertFalse(proxy_obj.can_send_version('1.6'))

    def test_can_send_version_with_no_cap(self):
        proxy_obj = proxy.RpcProxy('fake', '1.0')
        self.assertTrue(proxy_obj.can_send_version('1.5'))
        self.assertTrue(proxy_obj.can_send_version('1.99'))
