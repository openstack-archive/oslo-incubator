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

"""Unit tests for SQLAlchemy specific code."""

from eventlet import db_pool
try:
    import MySQLdb
    HAS_MYSQLDB = True
except ImportError:
    HAS_MYSQLDB = False

from openstack.common import context
from openstack.common import exception
from openstack.common.db.sqlalchemy import session
from tests import utils as test_utils


class TestException(exception.OpenstackException):
    pass


class DbPoolTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(DbPoolTestCase, self).setUp()
        if not HAS_MYSQLDB:
            self.skipTest("Required module MySQLdb missing.")
        self.config(sql_dbpool_enable=True)
        self.user_id = 'fake'
        self.project_id = 'fake'
        self.context = context.RequestContext(self.user_id, self.project_id)

    def test_db_pool_option(self):
        self.config(sql_idle_timeout=11, sql_min_pool_size=21,
                    sql_max_pool_size=42)

        info = {}

        class FakeConnectionPool(db_pool.ConnectionPool):
            def __init__(self, mod_name, **kwargs):
                info['module'] = mod_name
                info['kwargs'] = kwargs
                super(FakeConnectionPool, self).__init__(mod_name,
                                                         **kwargs)

            def connect(self, *args, **kwargs):
                raise TestException()

        self.stubs.Set(db_pool, 'ConnectionPool',
                       FakeConnectionPool)

        sql_connection = 'mysql://user:pass@127.0.0.1/nova'
        self.assertRaises(TestException, session.create_engine,
                          sql_connection)

        self.assertEqual(info['module'], MySQLdb)
        self.assertEqual(info['kwargs']['max_idle'], 11)
        self.assertEqual(info['kwargs']['min_size'], 21)
        self.assertEqual(info['kwargs']['max_size'], 42)
