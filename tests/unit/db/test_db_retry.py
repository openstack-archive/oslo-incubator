# Copyright 2013 Mirantis Inc.
# All Rights Reserved
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

from openstack.common.db import api
from openstack.common.db import exception
from openstack.common import importutils
from tests import utils as test_utils

sqla = importutils.import_module('sqlalchemy')


class TestDBAPI(object):
    def _api_raise(self, *args, **kwargs):
        """Simulate raising a database-has-gone-away error

        This method creates a fake OperationalError with an ID matching
        a valid MySQL "database has gone away" situation. It also decrements
        the error_counter so that we can artificially keep track of
        how many times this function is called by the wrapper. When
        error_counter reaches zero, this function returns True, simulating
        the database becoming available again and the query succeeding.
        """

        if self.error_counter > 0:
            self.error_counter -= 1
            orig = sqla.exc.DBAPIError(False, False, False)
            orig.args = [2006, 'Test raise operational error']
            e = exception.DBConnectionError(orig)
            raise e
        else:
            return True

    def api_raise_default(self, *args, **kwargs):
        return self._api_raise(*args, **kwargs)

    @api.safe_for_db_retry
    def api_raise_enable_retry(self, *args, **kwargs):
        return self._api_raise(*args, **kwargs)


class DBReconnectTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(DBReconnectTestCase, self).setUp()

        self.test_db_api = TestDBAPI()
        self.dbapi = api.DBAPI()
        self.dbapi._DBAPI__backend = self.test_db_api
        self.dbapi._DBAPI__use_tpool = False

    def test_raise_connection_error(self):
        self.test_db_api.error_counter = 5
        self.assertRaises(exception.DBConnectionError, self.dbapi._api_raise)

    def test_raise_connection_error_decorated(self):
        self.test_db_api.error_counter = 5
        self.assertRaises(exception.DBConnectionError,
                          self.dbapi.api_raise_enable_retry)
        self.assertEqual(4, self.test_db_api.error_counter, 'Unexpected retry')

    def test_raise_connection_error_enabled_config(self):
        self.config(group='database', use_db_reconnect=True)
        self.test_db_api.error_counter = 5
        self.assertRaises(exception.DBConnectionError,
                          self.dbapi.api_raise_default)
        self.assertEqual(4, self.test_db_api.error_counter, 'Unexpected retry')

    def test_retry_one(self):
        self.config(group='database', use_db_reconnect=True)
        self.config(group='database', db_retry_interval=1)
        try:
            func = self.dbapi.api_raise_enable_retry
            self.test_db_api.error_counter = 1
            self.assertTrue(func(), 'Single retry did not succeed.')
        except Exception:
            self.fail('Single retry raised an un-wrapped error.')

        self.assertEqual(
            0, self.test_db_api.error_counter,
            'Counter not decremented, retry logic probably failed.')

    def test_retry_two(self):
        self.config(group='database', use_db_reconnect=True)
        self.config(group='database', db_inc_retry_interval=False)
        self.config(group='database', db_retry_interval=1)

        try:
            func = self.dbapi.api_raise_enable_retry
            self.test_db_api.error_counter = 2
            self.assertTrue(func(), 'Multiple retry did not succeed.')
        except Exception:
            self.fail('Multiple retry raised an un-wrapped error.')

        self.assertEqual(
            0, self.test_db_api.error_counter,
            'Counter not decremented, retry logic probably failed.')

    def test_retry_until_failure(self):
        self.config(group='database', use_db_reconnect=True)
        self.config(group='database', db_inc_retry_interval=False)
        self.config(group='database', db_max_retries=3)
        self.config(group='database', db_retry_interval=1)

        func = self.dbapi.api_raise_enable_retry
        self.test_db_api.error_counter = 5
        self.assertRaises(
            exception.DBError, func,
            'Retry of permanent failure did not throw DBError exception.')

        self.assertNotEqual(
            0, self.test_db_api.error_counter,
            'Retry did not stop after sql_max_retries iterations.')
