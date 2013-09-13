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
from tests import utils as test_utils


class DBFixture(fixtures.Fixture):

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

        conn_tmpl = '%(driver)s://%(usrname)s:%(passwd)s@localhost/%(dbname)s'
        if not self.CONNECTION:
            self.CONNECTION = conn_tmpl % {
                'driver': self.DRIVER,
                'usrname': self.USERNAME,
                'passwd': self.PASSWORD,
                'dbname': self.DBNAME
            }

    def setUp(self):
        super(DBFixture, self).setUp()

        self.conf.set_default('connection', self.CONNECTION, group='database')
        self.addCleanup(self.conf.reset)
        self.addCleanup(session.cleanup)


class SqliteInMemoryFixture(DBFixture):
    """SQLite in-memory DB recreated for each test case."""

    CONNECTION = "sqlite://"


class MySQLFixture(DBFixture):
    """MySQL specific fixture."""

    DRIVER = 'mysql'
    DBNAME = PASSWORD = USERNAME = 'openstack_citest'

    def __init__(self):
        super(MySQLFixture, self).__init__()

        self.conf.import_opt('traditional_mode',
                             'openstack.common.db.sqlalchemy.session',
                             group='database')
        self.conf.set_default('traditional_mode', True, group='database')


class DbTestCase(test_utils.BaseTestCase):
    """Base class for testing of DB code."""

    FIXTURE = SqliteInMemoryFixture

    def setUp(self):
        super(DbTestCase, self).setUp()
        self.useFixture(self.FIXTURE())


class MySQLdbTestCase(DbTestCase):
    """Test case to test MySQL specific features."""

    FIXTURE = MySQLFixture
