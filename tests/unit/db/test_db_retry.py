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
#
# vim: tabstop=4 shiftwidth=4 softtabstop=4


from openstack.common.db import api
from openstack.common.db import exception
from openstack.common.db.sqlalchemy import session
from openstack.common import importutils

from tests import utils as test_utils

sqla = importutils.import_module('sqlalchemy')
exc = sqla.exc


class TestDBAPI(object):
    def api_raise(self, *args, **kwargs):
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
            orig = exc.DBAPIError(False, False, False)
            orig.args = [2006, 'Test raise operational error']
            e = exception.DBConnectionError(orig)
            raise e
        else:
            return True


test_db_api = TestDBAPI()


def get_backend():
    return test_db_api


class DBReconnectTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(DBReconnectTestCase, self).setUp()
        self.error_counter = 0
        self.dbapi = api.DBAPI(
            backend_mapping={'sqlalchemy': 'tests.unit.db.test_db_retry'})

    def mysql_raise(self):
        """Simulate raising a database-has-gone-away error for mysql."""
        orig = exc.DBAPIError(False, False, False)
        orig.args = [2006, 'Test raise operational error']
        e = exc.OperationalError(False, False, orig)
        raise e

    def postgresql_raise(self):
        """Simulate raising a database-has-gone-away error for postgresql."""
        orig = exc.DBAPIError(False, False, False)
        orig.pgcode = '57P02'
        e = exc.OperationalError(False, False, orig)
        raise e

    def test_raise_db_conn_error_mysql(self):
        is_db_conn_error = False
        try:
            self.mysql_raise()
        except Exception as e:
            is_db_conn_error = session._is_db_connection_lost(e, "mysql")
        self.assertTrue(is_db_conn_error)

    def test_raise_db_conn_error_postgresql(self):
        is_db_conn_error = False
        try:
            self.postgresql_raise()
        except Exception as e:
            is_db_conn_error = session._is_db_connection_lost(e, "postgresql")
        self.assertTrue(is_db_conn_error)

    def test_retry_one(self):
        self.config(group='database', db_retry_interval=1)
        try:
            func = self.dbapi.api_raise
            test_db_api.error_counter = 1
            self.assertEqual(True, func(), 'Single retry did not succeed.')
        except Exception:
            self.fail('Single retry raised an un-wrapped error.')

        self.assertEqual(
            0, test_db_api.error_counter,
            'Counter not decremented, retry logic probably failed.')

    def test_retry_two(self):
        self.config(group='database', db_inc_retry_interval=False)
        self.config(group='database', db_retry_interval=1)

        try:
            func = self.dbapi.api_raise
            test_db_api.error_counter = 2
            self.assertEqual(True, func(), 'Multiple retry did not succeed.')
        except Exception:
            self.fail('Multiple retry raised an un-wrapped error.')

        self.assertEqual(
            0, test_db_api.error_counter,
            'Counter not decremented, retry logic probably failed.')

    def test_retry_until_failure(self):
        self.config(group='database', db_inc_retry_interval=False)
        self.config(group='database', db_max_retries=3)
        self.config(group='database', db_retry_interval=1)

        func = self.dbapi.api_raise
        test_db_api.error_counter = 5
        self.assertRaises(
            exception.DBError, func,
            'Retry of permanent failure did not throw DBError exception.')

        self.assertNotEqual(
            0, test_db_api.error_counter,
            'Retry did not stop after sql_max_retries iterations.')
