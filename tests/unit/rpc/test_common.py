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
from openstack.common import context
from openstack.common import exception
from openstack.common import importutils
from openstack.common import jsonutils
from openstack.common import rpc
from openstack.common.rpc import amqp as rpc_amqp
from openstack.common.rpc import common as rpc_common
from tests.unit.rpc import common
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
