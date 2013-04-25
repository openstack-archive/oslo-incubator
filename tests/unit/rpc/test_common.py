# vim: tabstop=4 shiftwidth=4 softtabstop=4

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
Unit Tests for 'common' functions used through rpc code.
"""

import logging
import sys

from oslo.config import cfg
import six

from openstack.common import exception
from openstack.common import importutils
from openstack.common import jsonutils
from openstack.common import rpc
from openstack.common.rpc import common as rpc_common
from openstack.common.rpc import securemessage as rpc_secmsg
from tests import utils as test_utils


FLAGS = cfg.CONF
LOG = logging.getLogger(__name__)


def raise_exception():
    raise Exception("test")


class FakeUserDefinedException(Exception):
    def __init__(self, *args, **kwargs):
        super(FakeUserDefinedException, self).__init__(*args)
        self.kwargs = kwargs


class RpcCommonTestCase(test_utils.BaseTestCase):
    def test_serialize_remote_exception(self):
        expected = {
            'class': 'Exception',
            'module': 'exceptions',
            'message': 'test',
        }

        try:
            raise_exception()
        except Exception:
            failure = rpc_common.serialize_remote_exception(sys.exc_info())

        failure = jsonutils.loads(failure)
        self.assertEqual(expected['class'], failure['class'])
        self.assertEqual(expected['module'], failure['module'])
        self.assertEqual(expected['message'], failure['message'])

    def test_serialize_remote_custom_exception(self):
        def raise_custom_exception():
            raise exception.MalformedRequestBody(reason='test')

        expected = {
            'class': 'MalformedRequestBody',
            'module': 'openstack.common.exception',
            'message': str(exception.MalformedRequestBody(reason='test')),
        }

        try:
            raise_custom_exception()
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
            'class': 'OpenstackException',
            'module': 'openstack.common.exception',
            'message': exception.OpenstackException.msg_fmt,
        }

        def raise_remote_exception():
            try:
                raise exception.OpenstackException()
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

        after_exc = rpc_common.deserialize_remote_exception(FLAGS, serialized)
        self.assertTrue(isinstance(after_exc, NotImplementedError))
        #assure the traceback was added
        self.assertTrue('raise NotImplementedError' in
                        six.text_type(after_exc))

    def test_deserialize_remote_custom_exception(self):
        failure = {
            'class': 'OpenstackException',
            'module': 'openstack.common.exception',
            'message': exception.OpenstackException.msg_fmt,
            'tb': ['raise OpenstackException'],
        }
        serialized = jsonutils.dumps(failure)

        after_exc = rpc_common.deserialize_remote_exception(FLAGS, serialized)
        self.assertTrue(isinstance(after_exc, exception.OpenstackException))
        self.assertTrue('An unknown' in six.text_type(after_exc))
        #assure the traceback was added
        self.assertTrue('raise OpenstackException' in six.text_type(after_exc))
        self.assertEqual('OpenstackException_Remote',
                         after_exc.__class__.__name__)
        self.assertEqual('openstack.common.exception_Remote',
                         after_exc.__class__.__module__)
        self.assertTrue(isinstance(after_exc, exception.OpenstackException))

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

        after_exc = rpc_common.deserialize_remote_exception(FLAGS, serialized)
        self.assertTrue(isinstance(after_exc, FakeUserDefinedException))
        self.assertEqual(after_exc.args, ('fakearg',))
        self.assertEqual(after_exc.kwargs, {'fakekwarg': 'fake'})

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
        self.assertTrue(six.text_type(after_exc).startswith(
            "Remote error: FakeIDontExistException"))
        #assure the traceback was added
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
        self.assertTrue(e._exc_info[1], ValueError)

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

    def _test_msg_signing(self, msg, src, dst, sm='required'):
        cfg.CONF.secure_messages = sm

        try:
            rpc.set_service_name(src[0], src[1])

            serialized = rpc_common.serialize_msg(msg, '%s.%s' % dst)

            rpc_secmsg.KEY_STORE.clear()
            rpc.set_service_name(dst[0], dst[1])

            ret = rpc_common.deserialize_msg(serialized)
        finally:
            cfg.CONF.secure_messages = 'optional'

        return ret

    def test_msg_signing_ok(self):
        msg = {'foo': 'bar'}
        src = ('foo', 'host.example.com')
        dst = ('bar', 'host.example.com')
        # Pre-calculated key material for testing
        skey = '87\xb8\x18\xc0}\x1b\xdc\x8ay\xc1\x9c\x84\x10\x03\x14'
        ekey = 'x\xfbG\xb4\xec\xd4\xbbY:\xe7\xcf\xb9\x96p\xe7\xa6'
        esek = ('2I/cRSclVIQasMiYa0Yazd8ZYIm75jIu4vHK6mJOi+Z9MK+t/ojhCrZL'
                'C0ffeMBhScl7k4JdgzZMY7l85WwVUTtkdNT+ZUs3etXBqOfLc0XgzUYY'
                'P1fioKt3/f8Rgujp9v6e1lCum/GJJJGTeb+gzK72tVK+bWIyVQhKOJkV'
                'aI0=')

        cfg.CONF.secure_message_key = [src[0] + ':DwsLDwsLDwsLDwsLDwsLDw==,',
                                       dst[0] + ':CwsLCwsLCwsLCwsLCwsLCw==']
        source = '%s.%s' % src
        target = '%s.%s' % dst
        # Adds test keys in cache, we do it twice, once for client side use,
        # then for server side use as we run both in the same process
        store = rpc_secmsg.KEYstore()
        store.put_ticket(source, target, skey, ekey, esek, 2000000000)
        store.put_sek(source, target, skey, ekey, 2000000000)
        rpc_secmsg.KEY_STORE = store

        ret = self._test_msg_signing(msg, src, dst)

        self.assertEqual(msg, ret)

    def test_msg_signing_fail_no_dest(self):
        msg = {'foo': 'bar'}
        src = ('foo', 'host.example.com')
        dst = ('bar', 'host.example.com')
        # Pre-calculated key material for testing
        skey = '\xfe@\x1f\xe5\xcb61CJ^\xbf\x0b\xc8\x93\xb1\x1b'
        ekey = '\x9c\xb3?\x8d\x1b%\xe3\xc2\x1e\xca5z0\x95\x1c3'
        esek = ('On17zCDLp4J8otr/AEdWNEGbFJ4MkmfWeZqdrvYJq6q+0JFOPnl3rKiJ'
                'sIw9q09BHDqN2rp7W6ubcRydy7dyrD8PQKTIf5paXljnstoJB/8hJYqG'
                'v6OjUtEh18TeTPOz0isPjR7UgDS7Sm/uCV6BKYW176LSmo6aZcS6xwPi'
                '11k=')

        cfg.CONF.secure_message_key = [src[0] + ':DwsLDwsLDwsLDwsLDwsLDw==,',
                                       dst[0] + ':CwsLCwsLCwsLCwsLCwsLCw==']
        source = '%s.%s' % src
        target = '%s.%s' % dst
        # Adds test keys in cache, we do it twice, once for client side use,
        # then for server side use as we run both in the same process
        store = rpc_secmsg.KEYstore()
        store.put_ticket(source, target, skey, ekey, esek, 2000000000)
        store.put_sek(source, target, skey, ekey, 2000000000)
        rpc_secmsg.KEY_STORE = store

        # NOTE: bad destination
        self.assertRaises(rpc_secmsg.CommunicationError,
                          self._test_msg_signing, msg, src, ('bad', 'host'))

    def test_msg_signing_opt_nofail_no_dest(self):
        msg = {'foo': 'bar'}
        src = ('foo', 'host.example.com')
        dst = ('bar', 'host.example.com')
        # Pre-calculated key material for testing
        skey = '\xd6\x03\x8c y\xeezGo\xcbq\x944\xb9\x0f\x98'
        ekey = '\xd3"|\xab\xde\xb2*\xa1\r\xc5\x0fR\x1d\x81J\xa1'
        esek = ('bMCfdFdh+mZCIl0v72tYb0hLHoPWS7sNp4sLt/EUwhuS9ndVmDhKEPVn'
                'HbOterqV6DHiMWLsGff/pF9zsKJnITyRef1FPYd6DEoIA3buUgJCfT2u'
                'If0/RBEFwFkvJHb/wN/OtddkoL6V/dL7WA3bg+qJhcRXOnqlOTL3Zdd+'
                'ikc=')

        cfg.CONF.secure_message_key = [src[0] + ':DwsLDwsLDwsLDwsLDwsLDw==,',
                                       dst[0] + ':CwsLCwsLCwsLCwsLCwsLCw==']
        source = '%s.%s' % src
        target = '%s.%s' % dst
        store = rpc_secmsg.KEYstore()
        store.put_ticket(source, target, skey, ekey, esek, 2000000000)
        store.put_sek(source, target, skey, ekey, 2000000000)
        rpc_secmsg.KEY_STORE = store

        # NOTE: bad destination cause no failure if signing is optional
        ret = self._test_msg_signing(msg, src, ('bad', 'host'), sm='optional')

        self.assertEqual(msg, ret)

    def test_msg_signing_fail_dstkey(self):
        msg = {'foo': 'bar'}
        src = ('foo', 'host.example.com')
        dst = ('bar', 'host.example.com')
        # Pre-calculated key material for testing
        skey = '\x9aB\xdf\xd7\x14\xae\xe0\x81\x0f\x15U\xdb\x8c\xb8\x8b+'
        ekey = '\x12Ie\xfe\xd7\x04\x88\xec~yUm\xc6$B\x8a'
        esek = ('v2XvNd4vTSudfT8Gxr387vO4IzXtOqBe9CHuIi2Idt7O9MVlm9618ZMU'
                'fu8/yZ0hClp6Gb1l72S93OrIV//UZvXT3URj4xvYQ9MMW1e5ybzwU08n'
                'v9f2tPD2pSITqQkxB/RoJfmbxdTUrkDGXKmWQBAvsVL2Mr/9TTAxoFUx'
                '0H8=')

        # NOTE: Uses wrong decryption key so that we get a bad metadata error
        cfg.CONF.secure_message_key = [src[0] + ':BadLDwsLDwsLDwsLDwsLDw==,',
                                       dst[0] + ':BadLCwsLCwsLCwsLCwsLCw==']
        source = '%s.%s' % src
        target = '%s.%s' % dst
        store = rpc_secmsg.KEYstore()
        store.put_ticket(source, target, skey, ekey, esek, 2000000000)
        store.put_sek(source, target, skey, ekey, 2000000000)
        rpc_secmsg.KEY_STORE = store

        self.assertRaises(rpc_secmsg.InvalidMetadata,
                          self._test_msg_signing, msg, src, dst)

    def test_msg_signing_fail_signature(self):
        msg = {'foo': 'bar'}
        src = ('foo', 'host.example.com')
        dst = ('bar', 'host.example.com')
        # Pre-calculated key material for testing
        # NOTE: Uses a bad signing key to cause signature errors
        skey = 'Bad\xd7\x14\xae\xe0\x81\x0f\x15U\xdb\x8c\xb8\x8b+'
        ekey = '\x12Ie\xfe\xd7\x04\x88\xec~yUm\xc6$B\x8a'
        esek = ('v2XvNd4vTSudfT8Gxr387vO4IzXtOqBe9CHuIi2Idt7O9MVlm9618ZMU'
                'fu8/yZ0hClp6Gb1l72S93OrIV//UZvXT3URj4xvYQ9MMW1e5ybzwU08n'
                'v9f2tPD2pSITqQkxB/RoJfmbxdTUrkDGXKmWQBAvsVL2Mr/9TTAxoFUx'
                '0H8=')

        cfg.CONF.secure_message_key = [src[0] + ':DwsLDwsLDwsLDwsLDwsLDw==,',
                                       dst[0] + ':CwsLCwsLCwsLCwsLCwsLCw==']
        source = '%s.%s' % src
        target = '%s.%s' % dst
        store = rpc_secmsg.KEYstore()
        store.put_ticket(source, target, skey, ekey, esek, 2000000000)
        store.put_sek(source, target, skey, ekey, 2000000000)
        rpc_secmsg.KEY_STORE = store

        self.assertRaises(rpc_secmsg.InvalidSignature,
                          self._test_msg_signing, msg, src, dst)

    def test_msg_signing_fail_opt_signature(self):
        msg = {'foo': 'bar'}
        src = ('foo', 'host.example.com')
        dst = ('bar', 'host.example.com')
        # Pre-calculated key material for testing
        # NOTE: Uses a bad signing key to cause signature errors
        skey = 'Bad\xd7\x14\xae\xe0\x81\x0f\x15U\xdb\x8c\xb8\x8b+'
        ekey = '\x12Ie\xfe\xd7\x04\x88\xec~yUm\xc6$B\x8a'
        esek = ('v2XvNd4vTSudfT8Gxr387vO4IzXtOqBe9CHuIi2Idt7O9MVlm9618ZMU'
                'fu8/yZ0hClp6Gb1l72S93OrIV//UZvXT3URj4xvYQ9MMW1e5ybzwU08n'
                'v9f2tPD2pSITqQkxB/RoJfmbxdTUrkDGXKmWQBAvsVL2Mr/9TTAxoFUx'
                '0H8=')

        cfg.CONF.secure_message_key = [src[0] + ':DwsLDwsLDwsLDwsLDwsLDw==,',
                                       dst[0] + ':CwsLCwsLCwsLCwsLCwsLCw==']
        source = '%s.%s' % src
        target = '%s.%s' % dst
        store = rpc_secmsg.KEYstore()
        store.put_ticket(source, target, skey, ekey, esek, 2000000000)
        store.put_sek(source, target, skey, ekey, 2000000000)
        rpc_secmsg.KEY_STORE = store

        # NOTE: Receiver should fail if it receives a bad signature, even if
        # signing is optional
        self.assertRaises(rpc_secmsg.InvalidSignature,
                          self._test_msg_signing, msg, src, dst, sm='optional')

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

    def test_safe_log_sanitizes_any_password_in_context(self):
        def logger_method(msg, data):
            self.assertEquals('<SANITIZED>', data['_context_password'])
            self.assertEquals('<SANITIZED>', data['password'])

        data = {'_context_auth_token': 'banana',
                'auth_token': 'cheese',
                'password': 'passw0rd',
                '_context_password': 'passw0rd'
                }
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
