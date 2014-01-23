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

from openstack.common.db import api
from tests import utils as test_utils


def get_backend():
    return DBAPI()


class DBAPI(object):
    def api_class_call1(_self, *args, **kwargs):
        return args, kwargs


class DBAPITestCase(test_utils.BaseTestCase):
    def test_dbapi_full_path_module_method(self):
        dbapi = api.DBAPI('tests.unit.db.test_api')
        result = dbapi.api_class_call1(1, 2, kwarg1='meow')
        expected = ((1, 2), {'kwarg1': 'meow'})
        self.assertEqual(expected, result)

    def test_dbapi_unknown_invalid_backend(self):
        self.assertRaises(ImportError, api.DBAPI, 'tests.unit.db.not_existent')
