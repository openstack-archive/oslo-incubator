# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

from openstack.common import context
from openstack.common import lockutils
from openstack.common import rpc
from openstack.common.rpc import proxy
from tests import utils


class UniqueException(Exception):
    pass


class RpcProxyTestCase(utils.BaseTestCase):

    def _test_rpc_method(self, rpc_method, has_timeout=False, has_retval=False,
                         server_params=None, supports_topic_override=True,
                         raise_exception=False):
        topic = 'fake_topic'
        timeout = 123
        rpc_proxy = proxy.RpcProxy(topic, '1.0')
        ctxt = context.RequestContext('fake_user', 'fake_project')
        msg = {'method': 'fake_method', 'args': {'x': 'y'}}
        expected_msg = {'method': 'fake_method', 'args': {'x': 'y'},
                        'version': '1.0'}
        expected_log = ('RPC call Exception: Topic: "fake_topic" - '
                        'Method: "fake_method" - '
                        'Exception: "The spider got you"')

        expected_retval = 'hi' if has_retval else None

        self.fake_args = None
        self.fake_kwargs = None
        self.fake_log_msg = 'NOT LOGGED'

        def _fake_rpc_method(*args, **kwargs):
            rpc._check_for_lock()
            self.fake_args = args
            self.fake_kwargs = kwargs
            if has_retval:
                return expected_retval

        def _fake_rpc_exploding_method(*args, **kwargs):
            _fake_rpc_method(*args, **kwargs)
            raise UniqueException("The spider got you")

        def _fake_logger(msg):
            self.fake_log_msg = msg

        if raise_exception:
            self.stubs.Set(rpc, rpc_method, _fake_rpc_exploding_method)
            self.stubs.Set(proxy.LOG, 'exception', _fake_logger)
        else:
            self.stubs.Set(rpc, rpc_method, _fake_rpc_method)

        args = [ctxt, msg]
        if server_params:
            args.insert(1, server_params)

        def do_call(*args, **kwargs):
            """Actually performs the call and checks the result"""
            self.fake_log_msg = 'NOT LOGGED'
            reraised = False
            try:
                retval = getattr(rpc_proxy, rpc_method)(*args, **kwargs)
            except UniqueException:
                reraised = True
            if raise_exception:
                self.assertEqual(reraised, True)
                self.assertEqual(self.fake_log_msg, expected_log)
            else:
                self.assertEqual(retval, expected_retval)
                self.assertEqual(self.fake_log_msg, 'NOT LOGGED')

        # Base method usage
        do_call(*args)
        expected_args = [ctxt, topic, expected_msg]
        if server_params:
            expected_args.insert(1, server_params)
        for arg, expected_arg in zip(self.fake_args, expected_args):
            self.assertEqual(arg, expected_arg)

        # overriding the version
        do_call(*args, version='1.1')
        new_msg = copy.deepcopy(expected_msg)
        new_msg['version'] = '1.1'
        expected_args = [ctxt, topic, new_msg]
        if server_params:
            expected_args.insert(1, server_params)
        for arg, expected_arg in zip(self.fake_args, expected_args):
            self.assertEqual(arg, expected_arg)

        if has_timeout:
            # set a timeout
            do_call(ctxt, msg, timeout=timeout)
            expected_args = [ctxt, topic, expected_msg, timeout]
            for arg, expected_arg in zip(self.fake_args, expected_args):
                self.assertEqual(arg, expected_arg)

        if supports_topic_override:
            # set a topic
            new_topic = 'foo.bar'
            expected_log = ('RPC call Exception: Topic: "foo.bar" - '
                            'Method: "fake_method" - '
                            'Exception: "The spider got you"')
            do_call(*args, topic=new_topic)
            expected_args = [ctxt, new_topic, expected_msg]
            if server_params:
                expected_args.insert(1, server_params)
            for arg, expected_arg in zip(self.fake_args, expected_args):
                self.assertEqual(arg, expected_arg)

        # Call ourselves again, but this time each call will raise an
        # exception
        if raise_exception is False:
            self._test_rpc_method(rpc_method, has_timeout, has_retval,
                                  server_params, supports_topic_override,
                                  raise_exception=True)

    def test_call(self):
        self._test_rpc_method('call', has_timeout=True, has_retval=True)

    def test_multicall(self):
        self._test_rpc_method('multicall', has_timeout=True, has_retval=True)

    def test_multicall_with_lock_held(self):
        self.config(debug=True)
        self.assertFalse(rpc._check_for_lock())

        @lockutils.synchronized('detecting', 'test-')
        def f():
            self.assertTrue(rpc._check_for_lock())
        f()

        self.assertFalse(rpc._check_for_lock())

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

    def test_make_msg(self):
        self.assertEqual(proxy.RpcProxy.make_msg('test_method', a=1, b=2),
                         {'method': 'test_method', 'args': {'a': 1, 'b': 2}})
