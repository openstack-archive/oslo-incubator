# vim: tabstop=4 shiftwidth=4 softtabstop=4
# Copyright (c) 2012 Rackspace Hosting
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

import sys

from eventlet import tpool

from openstack.common.db import api
from tests import utils as test_utils


def module_api_call1(*args, **kwargs):
    return {'module_api_call1': (args, kwargs)}


class DBAPITestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(DBAPITestCase, self).setUp()
        self.our_module = sys.modules[__name__]

    def tearDown(self):
        if hasattr(self.our_module, 'API'):
            delattr(self.our_module, 'API')
        super(DBAPITestCase, self).tearDown()

    def test_dbapi_known_backend_module_method(self):
        known_backends = {'test_known': 'tests.unit.db.test_api'}
        self.config(db_backend='test_known')
        dbapi = api.DBAPI(known_backends)
        result = dbapi.module_api_call1(1, 2, kwarg1='meow')
        expected = {'module_api_call1': ((1, 2), {'kwarg1': 'meow'})}
        self.assertEqual(expected, result)

    def test_dbapi_full_path_module_method(self):
        known_backends = {'test_known': 'tests.unit.db.test_api'}
        self.config(db_backend='tests.unit.db.test_api')
        dbapi = api.DBAPI(known_backends)
        result = dbapi.module_api_call1(1, 2, kwarg1='meow')
        expected = {'module_api_call1': ((1, 2), {'kwarg1': 'meow'})}
        self.assertEqual(expected, result)

    def test_dbapi_unknown_invalid_backend(self):
        known_backends = {'test_known': 'tests.unit.db.test_api'}
        self.config(db_backend='tests.unit.db.not_existant')
        dbapi = api.DBAPI(known_backends)

        def call_it():
            dbapi.module_api_call1(1, 2, kwarg1='meow')

        self.assertRaises(ImportError, call_it)

    def test_dbapi_api_class_method_and_tpool_false(self):
        class API(object):
            def api_class_call1(_self, *args, **kwargs):
                return {'api_class_call1': (args, kwargs)}

        setattr(self.our_module, 'API', API)

        known_backends = {'test_known': 'tests.unit.db.test_api'}
        self.config(db_backend='test_known', dbapi_use_tpool=False)

        info = dict(tpool=False)
        orig_execute = tpool.execute

        def our_execute(*args, **kwargs):
            info['tpool'] = True
            return orig_execute(*args, **kwargs)

        self.stubs.Set(tpool, 'execute', our_execute)

        dbapi = api.DBAPI(known_backends)
        result = dbapi.api_class_call1(1, 2, kwarg1='meow')
        expected = {'api_class_call1': ((1, 2), {'kwarg1': 'meow'})}
        self.assertEqual(expected, result)
        self.assertFalse(info['tpool'])

    def test_dbapi_api_class_method_and_tpool_true(self):
        class API(object):
            def api_class_call1(_self, *args, **kwargs):
                return {'api_class_call1': (args, kwargs)}

        setattr(self.our_module, 'API', API)

        known_backends = {'test_known': 'tests.unit.db.test_api'}
        self.config(db_backend='test_known', dbapi_use_tpool=True)

        info = dict(tpool=False)
        orig_execute = tpool.execute

        def our_execute(*args, **kwargs):
            info['tpool'] = True
            return orig_execute(*args, **kwargs)

        self.stubs.Set(tpool, 'execute', our_execute)

        dbapi = api.DBAPI(known_backends)
        result = dbapi.api_class_call1(1, 2, kwarg1='meow')
        expected = {'api_class_call1': ((1, 2), {'kwarg1': 'meow'})}
        self.assertEqual(expected, result)
        self.assertTrue(info['tpool'])
