# Copyright 2012 OpenStack Foundation
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

from oslo.utils import importutils
from oslotest import base as test_base
import six

from openstack.common.fixture import config
from openstack.common import jsonutils
from openstack.common import rpc
from openstack.common.rpc import common as rpc_common


LOG = logging.getLogger(__name__)


class FakeUserDefinedException(Exception):
    def __init__(self, *args, **kwargs):
        super(FakeUserDefinedException, self).__init__(*args)
        self.kwargs = kwargs


class RpcCommonTestCase(test_base.BaseTestCase):

    def setUp(self):
        super(RpcCommonTestCase, self).setUp()
        configfixture = self.useFixture(config.Config())
        self.config = configfixture.config
        self.FLAGS = configfixture.conf

    def test_serialize_remote_exception(self):
        expected = {
            'class': 'Exception',
            'module': 'exceptions',
            'message': 'test',
        }

        try:
            raise Exception("test")
        except Exception:
            failure = rpc_common.serialize_remote_exception(sys.exc_info())

        failure = jsonutils.loads(failure)
        self.assertEqual(expected['class'], failure['class'])
        self.assertEqual(expected['module'], failure['module'])
        self.assertEqual(expected['message'], failure['message'])

    def test_serialize_remote_custom_exception(self):
        expected = {
            'class': 'FakeUserDefinedException',
            'module': self.__class__.__module__,
            'message': 'test',
        }

        try:
            raise FakeUserDefinedException('test')
        except Exception:
            failure = rpc_common.serialize_remote_exception(sys.exc_info())

        failure = jsonutils.loads(failure)
        self.assertEqual(expected['class'], failure['class'])
        self.assertEqual(expected['module'], failure['module'])
        self.assertEqual(expected['message'], failure['message'])

    def test_serialize_remote_exception_cell_hop(self):
        # A remote remote (no typo) exception should maintain its type and
        # module, when being re-serialized, so that through any amount of cell
        # hops up, it can pop out with the right type
        expected = {
            'class': 'FakeUserDefinedException',
            'module': self.__class__.__module__,
            'message': 'foobar',
        }

        def raise_remote_exception():
            try:
                raise FakeUserDefinedException('foobar')
            except Exception as e:
                ex_type = type(e)
                message = str(e)
                str_override = lambda self: message
                new_ex_type = type(ex_type.__name__ + "_Remote", (ex_type,),
                                   {'__str__': str_override,
                                    '__unicode__': str_override})
                new_ex_type.__module__ = '%s_Remote' % e.__class__.__module__
                e.__class__ = new_ex_type
                raise

        try:
            raise_remote_exception()
        except Exception:
            failure = rpc_common.serialize_remote_exception(sys.exc_info())

        failure = jsonutils.loads(failure)
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

        after_exc = rpc_common.deserialize_remote_exception(self.FLAGS,
                                                            serialized)
        self.assertTrue(isinstance(after_exc, NotImplementedError))
        # assure the traceback was added
        self.assertTrue('raise NotImplementedError' in
                        six.text_type(after_exc))

    def test_deserialize_remote_exception_bad_module(self):
        failure = {
            'class': 'popen2',
            'module': 'os',
            'kwargs': {'cmd': '/bin/echo failed'},
            'message': 'foo',
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(self.FLAGS,
                                                            serialized)
        self.assertTrue(isinstance(after_exc, rpc_common.RemoteError))

    def test_deserialize_remote_exception_user_defined_exception(self):
        """Ensure a user defined exception can be deserialized."""
        self.config(allowed_rpc_exception_modules=[self.__class__.__module__])
        failure = {
            'class': 'FakeUserDefinedException',
            'message': 'foobar',
            'module': self.__class__.__module__,
            'tb': ['raise FakeUserDefinedException'],
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(self.FLAGS,
                                                            serialized)
        self.assertTrue(isinstance(after_exc, FakeUserDefinedException))
        self.assertTrue('foobar' in six.text_type(after_exc))
        # assure the traceback was added
        self.assertTrue('raise FakeUserDefinedException' in
                        six.text_type(after_exc))

    def test_deserialize_remote_exception_args_and_kwargs(self):
        """Test user exception deserialization.

        Ensure a user defined exception will be supplied the correct args and
        kwargs while being deserialized.
        """
        self.config(allowed_rpc_exception_modules=[self.__class__.__module__])
        failure = {
            'class': 'FakeUserDefinedException',
            'module': self.__class__.__module__,
            'tb': ['raise FakeUserDefinedException'],
            'args': ('fakearg',),
            'kwargs': {'fakekwarg': 'fake'},
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(self.FLAGS,
                                                            serialized)
        self.assertTrue(isinstance(after_exc, FakeUserDefinedException))
        self.assertEqual(after_exc.args, ('fakearg',))
        self.assertEqual(after_exc.kwargs, {'fakekwarg': 'fake'})

    def test_deserialize_remote_exception_cannot_recreate(self):
        """Ensure a RemoteError is returned on initialization failure.

        If an exception cannot be recreated with its original class then a
        RemoteError with the exception informations should still be returned.

        """
        self.config(allowed_rpc_exception_modules=[self.__class__.__module__])
        failure = {
            'class': 'FakeIDontExistException',
            'module': self.__class__.__module__,
            'tb': ['raise FakeIDontExistException'],
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(self.FLAGS,
                                                            serialized)
        self.assertTrue(isinstance(after_exc, rpc_common.RemoteError))
        self.assertTrue(six.text_type(after_exc).startswith(
            "Remote error: FakeIDontExistException"))
        # assure the traceback was added
        self.assertTrue('raise FakeIDontExistException' in
                        six.text_type(after_exc))

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
        except rpc_common.ClientException as e:
            pass

        self.assertTrue(isinstance(e, rpc_common.ClientException))
        self.assertTrue(isinstance(e._exc_info[1], ValueError))

    def test_catch_client_exception(self):
        def naughty(param):
            int(param)

        e = None
        try:
            rpc_common.catch_client_exception([ValueError], naughty, 'a')
        except rpc_common.ClientException as e:
            pass

        self.assertTrue(isinstance(e, rpc_common.ClientException))
        self.assertTrue(isinstance(e._exc_info[1], ValueError))

    def test_catch_client_exception_other(self):
        class FooException(Exception):
            pass

        def naughty():
            raise FooException()

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

    def test_serialize_msg_v2(self):
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
            self.assertEqual('<SANITIZED>', data['_context_auth_token'])
            self.assertEqual('<SANITIZED>', data['auth_token'])

        data = {'_context_auth_token': 'banana',
                'auth_token': 'cheese'}
        rpc_common._safe_log(logger_method, 'foo', data)

    def test_safe_log_sanitizes_set_admin_password(self):
        def logger_method(msg, data):
            self.assertEqual('<SANITIZED>', data['args']['new_pass'])

        data = {'_context_auth_token': 'banana',
                'auth_token': 'cheese',
                'method': 'set_admin_password',
                'args': {'new_pass': 'gerkin'}}
        rpc_common._safe_log(logger_method, 'foo', data)

    def test_safe_log_sanitizes_run_instance(self):
        def logger_method(msg, data):
            self.assertEqual('<SANITIZED>', data['args']['admin_password'])

        data = {'_context_auth_token': 'banana',
                'auth_token': 'cheese',
                'method': 'run_instance',
                'args': {'admin_password': 'gerkin'}}
        rpc_common._safe_log(logger_method, 'foo', data)

    def test_safe_log_sanitizes_any_password_in_context(self):
        def logger_method(msg, data):
            self.assertEqual('<SANITIZED>', data['_context_password'])
            self.assertEqual('<SANITIZED>', data['password'])

        data = {'_context_auth_token': 'banana',
                'auth_token': 'cheese',
                'password': 'passw0rd',
                '_context_password': 'passw0rd'
                }
        rpc_common._safe_log(logger_method, 'foo', data)

    def test_safe_log_sanitizes_cells_route_message(self):
        def logger_method(msg, data):
            vals = data['args']['message']['args']['method_info']
            self.assertEqual('<SANITIZED>', vals['method_kwargs']['password'])

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

    def test_safe_log_sanitizes_any_password_in_list_of_dicts(self):
        def logger_method(msg, data):
            self.assertEqual('<SANITIZED>', data['users'][0]['_password'])
            self.assertEqual('<SANITIZED>', data['users'][1]['_password'])

        users = [{'_host': '%', '_password': 'passw0rd', '_name': 'mydb'},
                 {'_host': '%', '_password': 'secret', '_name': 'newdb'}]
        data = {'_request_id': 'req-44adf4ac-12bb-44c5-be3d-da2cc73b2e05',
                'users': users}
        rpc_common._safe_log(logger_method, 'foo', data)

    def test_version_is_compatible_same(self):
        self.assertTrue(rpc_common.version_is_compatible('1.23', '1.23'))

    def test_version_is_compatible_newer_minor(self):
        self.assertTrue(rpc_common.version_is_compatible('1.24', '1.23'))

    def test_version_is_compatible_older_minor(self):
        self.assertFalse(rpc_common.version_is_compatible('1.22', '1.23'))

    def test_version_is_compatible_major_difference1(self):
        self.assertFalse(rpc_common.version_is_compatible('2.23', '1.23'))

    def test_version_is_compatible_major_difference2(self):
        self.assertFalse(rpc_common.version_is_compatible('1.23', '2.23'))

    def test_version_is_compatible_newer_rev(self):
        self.assertFalse(rpc_common.version_is_compatible('1.23', '1.23.1'))

    def test_version_is_compatible_newer_rev_both(self):
        self.assertFalse(rpc_common.version_is_compatible('1.23.1', '1.23.2'))

    def test_version_is_compatible_older_rev_both(self):
        self.assertTrue(rpc_common.version_is_compatible('1.23.2', '1.23.1'))

    def test_version_is_compatible_older_rev(self):
        self.assertTrue(rpc_common.version_is_compatible('1.24', '1.23.1'))

    def test_version_is_compatible_no_rev_is_zero(self):
        self.assertTrue(rpc_common.version_is_compatible('1.23.0', '1.23'))
