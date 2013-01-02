# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack, LLC
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
Unit Tests for 'common' functons used through rpc code.
"""

import logging
import sys

from openstack.common import cfg
from openstack.common import exception
from openstack.common import importutils
from openstack.common import jsonutils
from openstack.common import rpc
from openstack.common.rpc import common as rpc_common
from tests import utils as test_utils


FLAGS = cfg.CONF
LOG = logging.getLogger(__name__)


def raise_exception():
    raise Exception("test")


class FakeUserDefinedException(Exception):
    def __init__(self):
        Exception.__init__(self, "Test Message")


class RpcCommonTestCase(test_utils.BaseTestCase):
    def test_serialize_remote_exception(self):
        expected = {
            'class': 'Exception',
            'module': 'exceptions',
            'message': 'test',
        }

        try:
            raise_exception()
        except Exception as exc:
            failure = rpc_common.serialize_remote_exception(sys.exc_info())

        failure = jsonutils.loads(failure)
        #assure the traceback was added
        self.assertEqual(expected['class'], failure['class'])
        self.assertEqual(expected['module'], failure['module'])
        self.assertEqual(expected['message'], failure['message'])

    def test_serialize_remote_custom_exception(self):
        def raise_custom_exception():
            raise exception.OpenstackException()

        expected = {
            'class': 'OpenstackException',
            'module': 'openstack.common.exception',
            'message': exception.OpenstackException.message,
        }

        try:
            raise_custom_exception()
        except Exception as exc:
            failure = rpc_common.serialize_remote_exception(sys.exc_info())

        failure = jsonutils.loads(failure)
        #assure the traceback was added
        self.assertEqual(expected['class'], failure['class'])
        self.assertEqual(expected['module'], failure['module'])
        self.assertEqual(expected['message'], failure['message'])

    def test_deserialize_remote_exception(self):
        failure = {
            'class': 'NotImplementedError',
            'module': 'exceptions',
            'message': '',
            'tb': ['raise NotImplementedError'],
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(FLAGS, serialized)
        self.assertTrue(isinstance(after_exc, NotImplementedError))
        #assure the traceback was added
        self.assertTrue('raise NotImplementedError' in unicode(after_exc))

    def test_deserialize_remote_custom_exception(self):
        failure = {
            'class': 'OpenstackException',
            'module': 'openstack.common.exception',
            'message': exception.OpenstackException.message,
            'tb': ['raise OpenstackException'],
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(FLAGS, serialized)
        self.assertTrue(isinstance(after_exc, exception.OpenstackException))
        self.assertTrue('An unknown' in unicode(after_exc))
        #assure the traceback was added
        self.assertTrue('raise OpenstackException' in unicode(after_exc))

    def test_deserialize_remote_exception_bad_module(self):
        failure = {
            'class': 'popen2',
            'module': 'os',
            'kwargs': {'cmd': '/bin/echo failed'},
            'message': 'foo',
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(FLAGS, serialized)
        self.assertTrue(isinstance(after_exc, rpc_common.RemoteError))

    def test_deserialize_remote_exception_user_defined_exception(self):
        """Ensure a user defined exception can be deserialized."""
        self.config(allowed_rpc_exception_modules=[self.__class__.__module__])
        failure = {
            'class': 'FakeUserDefinedException',
            'module': self.__class__.__module__,
            'tb': ['raise FakeUserDefinedException'],
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(FLAGS, serialized)
        self.assertTrue(isinstance(after_exc, FakeUserDefinedException))
        #assure the traceback was added
        self.assertTrue('raise FakeUserDefinedException' in unicode(after_exc))

    def test_deserialize_remote_exception_cannot_recreate(self):
        """Ensure a RemoteError is returned on initialization failure.

        If an exception cannot be recreated with it's original class then a
        RemoteError with the exception informations should still be returned.

        """
        self.config(allowed_rpc_exception_modules=[self.__class__.__module__])
        failure = {
            'class': 'FakeIDontExistException',
            'module': self.__class__.__module__,
            'tb': ['raise FakeIDontExistException'],
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(FLAGS, serialized)
        self.assertTrue(isinstance(after_exc, rpc_common.RemoteError))
        #assure the traceback was added
        self.assertTrue('raise FakeIDontExistException' in unicode(after_exc))

    def test_loading_old_nova_config(self):
        self.config(rpc_backend='nova.rpc.impl_qpid')
        rpc._RPCIMPL = None

        self.mod = None

        def fake_import_module(m):
            if not self.mod:
                # The first time import_module is called, before the replace()
                self.mod = m
                raise ImportError
            self.mod = m

        orig_import_module = importutils.import_module
        importutils.import_module = fake_import_module

        rpc._get_impl()

        importutils.import_module = orig_import_module

        self.assertEqual(self.mod, 'nova.openstack.common.rpc.impl_qpid')

    def test_queue_get_for(self):
        self.assertEqual(rpc.queue_get_for(None, 'a', 'b'), 'a.b')
        self.assertEqual(rpc.queue_get_for(None, 'a', None), 'a')

    def test_client_exception(self):
        e = None
        try:
            try:
                raise ValueError()
            except Exception:
                raise rpc_common.ClientException()
        except rpc_common.ClientException, e:
            pass

        self.assertTrue(isinstance(e, rpc_common.ClientException))
        self.assertTrue(e._exc_info[1], ValueError)

    def test_catch_client_exception(self):
        def naughty(param):
            int(param)

        e = None
        try:
            rpc_common.catch_client_exception([ValueError], naughty, 'a')
        except rpc_common.ClientException, e:
            pass

        self.assertTrue(isinstance(e, rpc_common.ClientException))
        self.assertTrue(isinstance(e._exc_info[1], ValueError))

    def test_catch_client_exception_other(self):
        class FooException(Exception):
            pass

        def naughty():
            raise FooException()

        e = None
        self.assertRaises(FooException,
                          rpc_common.catch_client_exception,
                          [ValueError], naughty)

    def test_client_exceptions_decorator(self):
        class FooException(Exception):
            pass

        @rpc_common.client_exceptions(FooException)
        def naughty():
            raise FooException()

        @rpc_common.client_exceptions(FooException)
        def really_naughty():
            raise ValueError()

        self.assertRaises(rpc_common.ClientException, naughty)
        self.assertRaises(ValueError, really_naughty)

    def test_serialize_msg_v1(self):
        self.stubs.Set(rpc_common, '_SEND_RPC_ENVELOPE', False)
        msg = {'foo': 'bar'}
        self.assertEqual(msg, rpc_common.serialize_msg(msg))

    def test_serialize_msg_v2(self):
        self.stubs.Set(rpc_common, '_SEND_RPC_ENVELOPE', True)
        msg = {'foo': 'bar'}
        s_msg = {'oslo.version': rpc_common._RPC_ENVELOPE_VERSION,
                 'oslo.message': jsonutils.dumps(msg)}
        serialized = rpc_common.serialize_msg(msg)

        self.assertEqual(s_msg, rpc_common.serialize_msg(msg))

        self.assertEqual(msg, rpc_common.deserialize_msg(serialized))

    def test_deserialize_msg_no_envelope(self):
        self.assertEqual(1, rpc_common.deserialize_msg(1))
        self.assertEqual([], rpc_common.deserialize_msg([]))
        self.assertEqual({}, rpc_common.deserialize_msg({}))
        self.assertEqual('foo', rpc_common.deserialize_msg('foo'))

    def test_deserialize_msg_bad_version(self):
        s_msg = {'oslo.version': '8675309.0',
                 'oslo.message': 'whatever'}

        self.assertRaises(rpc_common.UnsupportedRpcEnvelopeVersion,
                          rpc_common.deserialize_msg, s_msg)

    def test_safe_log_sanitizes_globals(self):
        def logger_method(msg, data):
            self.assertEquals('<SANITIZED>', data['_context_auth_token'])
            self.assertEquals('<SANITIZED>', data['auth_token'])

        data = {'_context_auth_token': 'banana',
                'auth_token': 'cheese'}
        rpc_common._safe_log(logger_method, 'foo', data)

    def test_safe_log_sanitizes_set_admin_password(self):
        def logger_method(msg, data):
            self.assertEquals('<SANITIZED>', data['args']['new_pass'])

        data = {'_context_auth_token': 'banana',
                'auth_token': 'cheese',
                'method': 'set_admin_password',
                'args': {'new_pass': 'gerkin'}}
        rpc_common._safe_log(logger_method, 'foo', data)

    def test_safe_log_sanitizes_run_instance(self):
        def logger_method(msg, data):
            self.assertEquals('<SANITIZED>', data['args']['admin_password'])

        data = {'_context_auth_token': 'banana',
                'auth_token': 'cheese',
                'method': 'run_instance',
                'args': {'admin_password': 'gerkin'}}
        rpc_common._safe_log(logger_method, 'foo', data)

    def test_safe_log_sanitizes_cells_route_message(self):
        def logger_method(msg, data):
            vals = data['args']['message']['args']['method_info']
            self.assertEquals('<SANITIZED>', vals['method_kwargs']['password'])

        meth_info = {'method_args': ['aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'],
                     'method': 'set_admin_password',
                     'method_kwargs': {'password': 'this_password_is_visible'}}
        data = {'method': 'route_message',
                'args': {'routing_path': 'a.fake.path',
                         'direction': 'down',
                         'message': {'args': {'is_broadcast': False,
                                              'service_name': 'compute',
                                              'method_info': meth_info},
                                     'method': 'run_service_api_method'},
                         'dest_cell_name': 'cell!0001'}}
        rpc_common._safe_log(logger_method, 'foo', data)
