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
from openstack.common.fixture import config
from openstack.common import test


class SqliteInMemoryFixture(fixtures.Fixture):
    """SQLite in-memory DB recreated for each test case."""

    def setUp(self):
        super(SqliteInMemoryFixture, self).setUp()
        config_fixture = self.useFixture(config.Config())
        self.conf = config_fixture.conf
        self.conf.import_opt('connection',
                             'openstack.common.db.sqlalchemy.session',
                             group='database')

        self.conf.set_default('connection', "sqlite://", group='database')
        self.addCleanup(session.cleanup)


class DbTestCase(test.BaseTestCase):
    """Base class for testing of DB code (uses in-memory SQLite DB fixture)."""

    def setUp(self):
        super(DbTestCase, self).setUp()

        self.useFixture(SqliteInMemoryFixture())
