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
import os

from openstack.common.db.sqlalchemy import session
from oslo.config import cfg
from tests import utils as test_utils


class DBFixture(fixtures.Fixture):
    """Base database fixture."""
    CONNECTION = None

    def __init__(self):
        self.conf = cfg.CONF
        self.conf.import_opt('connection',
                             'openstack.common.db.sqlalchemy.session',
                             group='database')

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


class VariousBackendFixture(DBFixture):
    """Database fixture.
    Allows to run tests on various db backends, such as MySQL and
    PostgreSQL. Be careful and use this fixture to run only engine specific
    tests because create/drop and other actions can take extremly long time.
    Please note, until test database does not dropped all of a tables and an
    entries remain in the database. And database will be dropped only after
    all the test cases will be completed. Those the cleanup process is
    BaseTestCase subclasses business. Use tearDown method to cleanup the
    database:

    class FooTestCase(VariousBackendFixture):
        def setUp(self):
            ...
            self.test_table.create()

        def tearDown(self):
            ...
            self.test_table.create()
    """

    CONNECTION = os.getenv('OS_TEST_DBAPI_CONNECTION', 'sqlite://')


class DbTestCase(test_utils.BaseTestCase):
    """Base class for testing of DB code (uses in-memory SQLite DB fixture)."""

    FIXTURE = SqliteInMemoryFixture

    def setUp(self):
        super(DbTestCase, self).setUp()
        self.useFixture(self.FIXTURE())


class VariousBackendTestCase(DbTestCase):
    """Test case to run engine specific tests with given db backend.
    WARNING: use this test case exclusively only engine specific tests,
    because create/drop and other actions can take extremly long time.
    """

    FIXTURE = VariousBackendFixture
