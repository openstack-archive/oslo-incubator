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

from functools import wraps
import os

import fixtures
from oslo.config import cfg

from openstack.common.db.sqlalchemy import session
from openstack.common.db.sqlalchemy import test_migrations as tm
from tests import utils as test_utils


class DbFixture(fixtures.Fixture):
    """Basic database fixture.

    Allows to run tests on various db backends, such as SQLite, MySQL and
    PostgreSQL. By default use sqlite backend. To override default backend
    uri set env variable OS_TEST_DBAPI_CONNECTION with database admin
    credentials for specific backend.
    """

    def _get_uri(self):
        return os.getenv('OS_TEST_DBAPI_CONNECTION', 'sqlite://')

    def __init__(self):
        super(DbFixture, self).__init__()
        self.conf = cfg.CONF
        self.conf.import_opt('connection',
                             'openstack.common.db.sqlalchemy.session',
                             group='database')

    def setUp(self):
        super(DbFixture, self).setUp()

        # To prevent existance of prepared engine with wrong connection
        session.cleanup()

        self.conf.set_default('connection', self._get_uri(), group='database')
        self.addCleanup(self.conf.reset)


class DbTestCase(test_utils.BaseTestCase):
    """Base class for testing of DB code.

    Using `DbFixture`. Intended to be the main database test case to use all
    the tests on a given backend with user defined uri. Backend specific
    tests should be decorated with `backend_specific` decorator.
    """

    FIXTURE = DbFixture

    def setUp(self):
        super(DbTestCase, self).setUp()
        self.useFixture(self.FIXTURE())


ALLOWED_DIALECTS = ['sqlite', 'mysql', 'postgresql']


def backend_specific(*dialects):
    """Decorator to skip backend specific tests on inappropriate engines.

    ::dialects: list of dialects names under which the test will be launched.
    """
    def wrap(f):
        @wraps(f)
        def ins_wrap(self):
            if not set(dialects).issubset(ALLOWED_DIALECTS):
                raise ValueError(
                    "Please use allowed dialects: %s" % ALLOWED_DIALECTS)
            engine = session.get_engine()
            if engine.name not in dialects:
                msg = 'The test "%s" can be run '
                'only on %s. Current engine is %s.'
                args = (f.__name__, ' '.join(dialects), engine.name)
                self.skip(msg % args)
            else:
                return f(self)
        return ins_wrap
    return wrap


class OpportunisticFixture(DbFixture):
    """Base fixture to use default CI databases.

    The databases exists in OpenStack CI infrastructure. But for the
    correct functioning in local environment the databases must be
    created manually.
    """

    DRIVER = None
    DBNAME = PASSWORD = USERNAME = 'openstack_citest'

    def _get_uri(self):
        return tm._get_connect_string(backend=self.DRIVER,
                                      user=self.USERNAME,
                                      passwd=self.PASSWORD,
                                      database=self.DBNAME)


class OpportunisticTestCase(DbTestCase):
    """Base test case to use default CI databases.

    The subclasses of the test case are running only when openstack_citest
    database is available otherwise a tests will be skipped.
    """

    def setUp(self):
        credentials = (
            self.FIXTURE.DRIVER,
            self.FIXTURE.USERNAME,
            self.FIXTURE.PASSWORD,
            self.FIXTURE.DBNAME)

        if (self.FIXTURE.DRIVER and not tm._is_backend_avail(*credentials)):
            msg = '%s backend is not available.' % self.FIXTURE.DRIVER
            return self.skip(msg)

        super(OpportunisticTestCase, self).setUp()


class MySQLOpportunisticFixture(OpportunisticFixture):
    DRIVER = 'mysql'


class PostgreSQLOpportunisticFixture(OpportunisticFixture):
    DRIVER = 'postgresql'


class MySQLOpportunisticTestCase(OpportunisticTestCase):
    FIXTURE = MySQLOpportunisticFixture


class PostgreSQLOpportunisticTestCase(OpportunisticTestCase):
    FIXTURE = PostgreSQLOpportunisticFixture
