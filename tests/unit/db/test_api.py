# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright (c) 2013 Rackspace Hosting
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

"""Unit tests for DB API."""

from eventlet import tpool

from openstack.common.db import api
from tests import utils as test_utils


def get_backend():
    return DBAPI()


class DBAPI(object):
    def api_class_call1(_self, *args, **kwargs):
        return args, kwargs


class DBAPITestCase(test_utils.BaseTestCase):

    def test_deprecated_dbapi_parameters(self):
        paths = self.create_tempfiles([('test',
                                        '[DEFAULT]\n'
                                        'db_backend=test_123\n'
                                        'dbapi_use_tpool=True\n'
                                        )])

        test_utils.CONF(['--config-file', paths[0]])
        self.assertEquals(test_utils.CONF.database.backend, 'test_123')
        self.assertEquals(test_utils.CONF.database.use_tpool, True)

    def test_dbapi_parameters(self):
        paths = self.create_tempfiles([('test',
                                        '[database]\n'
                                        'backend=test_123\n'
                                        'use_tpool=True\n'
                                        )])

        test_utils.CONF(['--config-file', paths[0]])
        self.assertEquals(test_utils.CONF.database.backend, 'test_123')
        self.assertEquals(test_utils.CONF.database.use_tpool, True)

    def test_dbapi_api_class_method_and_tpool_false(self):
        backend_mapping = {'test_known': 'tests.unit.db.test_api'}
        self.config(backend='test_known', use_tpool=False,
                    group='database')

        info = dict(tpool=False)
        orig_execute = tpool.execute

        def our_execute(*args, **kwargs):
            info['tpool'] = True
            return orig_execute(*args, **kwargs)

        self.stubs.Set(tpool, 'execute', our_execute)

        dbapi = api.DBAPI(backend_mapping=backend_mapping)
        result = dbapi.api_class_call1(1, 2, kwarg1='meow')
        expected = ((1, 2), {'kwarg1': 'meow'})
        self.assertEqual(expected, result)
        self.assertFalse(info['tpool'])

    def test_dbapi_api_class_method_and_tpool_true(self):
        backend_mapping = {'test_known': 'tests.unit.db.test_api'}
        self.config(backend='test_known', use_tpool=True,
                    group='database')

        info = dict(tpool=False)
        orig_execute = tpool.execute

        def our_execute(*args, **kwargs):
            info['tpool'] = True
            return orig_execute(*args, **kwargs)

        self.stubs.Set(tpool, 'execute', our_execute)

        dbapi = api.DBAPI(backend_mapping=backend_mapping)
        result = dbapi.api_class_call1(1, 2, kwarg1='meow')
        expected = ((1, 2), {'kwarg1': 'meow'})
        self.assertEqual(expected, result)
        self.assertTrue(info['tpool'])

    def test_dbapi_full_path_module_method(self):
        self.config(backend='tests.unit.db.test_api',
                    group='database')
        dbapi = api.DBAPI()
        result = dbapi.api_class_call1(1, 2, kwarg1='meow')
        expected = ((1, 2), {'kwarg1': 'meow'})
        self.assertEqual(expected, result)

    def test_dbapi_unknown_invalid_backend(self):
        self.config(backend='tests.unit.db.not_existent',
                    group='database')
        dbapi = api.DBAPI()

        def call_it():
            dbapi.api_class_call1(1, 2, kwarg1='meow')

        self.assertRaises(ImportError, call_it)
