# Copyright (c) 2013 OpenStack Foundation
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


import fixtures
from oslo.config import cfg

from openstack.common.db.sqlalchemy import session
from openstack.common.db.sqlalchemy import test_migrations as tm
from tests import utils as test_utils


class DBFixture(fixtures.Fixture):
    """Base database fixture. Allows to use various backend connection uri."""

    CONNECTION = DRIVER = USERNAME = DBNAME = PASSWORD = None

    def __init__(self):
        self.conf = cfg.CONF
        self.conf.import_opt('connection',
                             'openstack.common.db.sqlalchemy.session',
                             group='database')

        if not self.CONNECTION:
            self.CONNECTION = tm._get_connect_string(backend=self.DRIVER,
                                                     user=self.USERNAME,
                                                     passwd=self.PASSWORD,
                                                     database=self.DBNAME)

    def setUp(self):
        super(DBFixture, self).setUp()

        self.conf.set_default('connection', self.CONNECTION, group='database')
        self.addCleanup(self.conf.reset)
        self.addCleanup(session.cleanup)


class SqliteInMemoryFixture(DBFixture):
    """SQLite in-memory DB recreated for each test case."""

    CONNECTION = "sqlite://"


class MySQLFixture(DBFixture):
    """MySQL specific fixture

    The database required to be cleaned after every test runed. The work
    should be done in a DbTestCase subclasses:

    class FooTestCase(DbTestCase):
        def setUp(self):
            ...
            self.test_table.create()
            self.addCleanp(self.test_table.drop)
    """

    DRIVER = 'mysql'
    DBNAME = PASSWORD = USERNAME = 'openstack_citest'


class DbTestCase(test_utils.BaseTestCase):
    """Base class for testing of DB code."""

    FIXTURE = SqliteInMemoryFixture

    def setUp(self):
        super(DbTestCase, self).setUp()

        credentials = (
            self.FIXTURE.DRIVER,
            self.FIXTURE.USERNAME,
            self.FIXTURE.PASSWORD,
            self.FIXTURE.DBNAME)

        # Extra check required to prevent skipping at default connection.
        if self.FIXTURE.DRIVER and not tm._is_backend_avail(*credentials):
            msg = '%s backend is not available.' % self.FIXTURE.DRIVER
            return self.skip(msg)

        self.useFixture(self.FIXTURE())


class MySQLdbTestCase(DbTestCase):
    """Test case to test MySQL specific features."""

    FIXTURE = MySQLFixture
