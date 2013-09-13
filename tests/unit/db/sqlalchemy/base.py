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

from openstack.common.db.sqlalchemy import session
from openstack.common.db.sqlalchemy.test_migrations import _is_backend_avail
from oslo.config import cfg
from tests import utils as test_utils


class DBFixture(fixtures.Fixture):
    """Base database fixture. Allows to use various backend connection uri."""

    CONNECTION = None
    DRIVER = None
    USERNAME = None
    DBNAME = None
    PASSWORD = None

    def __init__(self):
        self.conf = cfg.CONF
        self.conf.import_opt('connection',
                             'openstack.common.db.sqlalchemy.session',
                             group='database')

        conn_tmpl = ('%(driver)s://%(username)s:'
                     '%(passwd)s@localhost/%(dbname)s')
        if not self.CONNECTION:
            self.CONNECTION = conn_tmpl % {
                'driver': self.DRIVER,
                'username': self.USERNAME,
                'passwd': self.PASSWORD,
                'dbname': self.DBNAME
            }

    def setUp(self):
        super(DBFixture, self).setUp()

        # To prevent existance of prepared engine with wrong connection
        session.cleanup()

        self.conf.set_default('connection', self.CONNECTION, group='database')
        self.addCleanup(self.conf.reset)
        self.addCleanup(session.cleanup)


class SqliteInMemoryFixture(DBFixture):
    """SQLite in-memory DB recreated for each test case."""

    CONNECTION = "sqlite://"


class MySQLFixture(DBFixture):
    """MySQL specific fixture

    Be careful and use this fixture to run only MySQL specific
    tests because create/drop and other actions can take extremly long time.
    Please note, until test database does not dropped all of a tables and an
    entries remain in the database. And database will be dropped only after
    all the test cases will be completed. Those the cleanup process is
    BaseTestCase subclasses business:

    class FooTestCase(VariousBackendFixture):
        def setUp(self):
            ...
            self.test_table.create()
            self.sddCleanp(self.test_table.drop)
    """

    DRIVER = 'mysql'
    DBNAME = PASSWORD = USERNAME = 'openstack_citest'


class DbTestCase(test_utils.BaseTestCase):
    """Base class for testing of DB code."""

    FIXTURE = SqliteInMemoryFixture

    def setUp(self):
        super(DbTestCase, self).setUp()

        credantials = (
            self.FIXTURE.DRIVER,
            self.FIXTURE.USERNAME,
            self.FIXTURE.PASSWORD,
            self.FIXTURE.DBNAME)

        if not _is_backend_avail(*credantials):
            msg = '%s backend is not available.' % self.FIXTURE.DRIVER
            return self.skip(msg)

        self.useFixture(self.FIXTURE())


class MySQLdbTestCase(DbTestCase):
    """Test case to test MySQL specific features."""

    FIXTURE = MySQLFixture
