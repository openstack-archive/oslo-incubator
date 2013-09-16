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
from sqlalchemy.exc import UnboundExecutionError

from openstack.common.db.sqlalchemy import session
from oslo.config import cfg
from tests import utils as test_utils


class DbFixture(fixtures.Fixture):
    """Database fixture.
    Allows to run tests on various db backends, such as SQLite, MySQL and
    PostgreSQL.
    When using real backends please note:
    * Create/drop and other actions can take extremly long time.
    * Until test database does not dropped all of a tables and an
    entries remain in the database.
    * Database will be dropped only after all the test cases will be
    completed.
    * Those the cleanup process is BaseTestCase subclasses business. Use
    tearDown method to cleanup the database:

    class FooTestCase(VariousBackendFixture):
        def setUp(self):
            ...
            self.test_table.create()

        def tearDown(self):
            ...
            self.test_table.drop()
    """

    def __init__(self, use_backend):
        self.conf = cfg.CONF
        self.conf.import_opt('connection',
                             'openstack.common.db.sqlalchemy.session',
                             group='database')

        self.connection = self._get_connection(use_backend)

    def _get_connection(self, use_backend):
        uri = os.getenv('OS_TEST_DBAPI_CONNECTION', 'sqlite://')
        if uri.startswith(use_backend):
            return uri
        raise UnboundExecutionError('%s backend not supported!' % use_backend)

    def setUp(self):
        super(DbFixture, self).setUp()
        # To prevent existance of prepared engine with wrong connection
        session.cleanup()

        self.conf.set_default('connection', self.connection, group='database')
        self.addCleanup(self.conf.reset)
        self.addCleanup(session.cleanup)


class DbTestCase(test_utils.BaseTestCase):
    """Base class for testing of DB code.
    To use backend other than sqlite: override USE_BACKEND attribute
    accordingly to env variable OS_TEST_DBAPI_ADMIN_CONNECTION
    defined in tox.ini file. Can't be used outside of tox.
    """

    USE_BACKEND = 'sqlite'

    def __init__(self, *args):
        super(DbTestCase, self).__init__(*args)
        self.conf = cfg.CONF

    def setUp(self):
        super(DbTestCase, self).setUp()
        try:
            self.useFixture(DbFixture(self.USE_BACKEND))
        except UnboundExecutionError as e:
            self.skip(str(e))
