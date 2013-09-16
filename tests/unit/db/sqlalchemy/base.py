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
from tests import utils as test_utils


class DbFixture(fixtures.Fixture):
    """Database fixture.
    Allows to run tests on various db backends, such as SQLite, MySQL and
    PostgreSQL.
    When using real backends please note: Create/drop and other actions can
    take extremly long time.
    """

    def __init__(self):
        self.conf = cfg.CONF
        self.conf.import_opt('connection',
                             'openstack.common.db.sqlalchemy.session',
                             group='database')
        self.uri = os.getenv('OS_TEST_DBAPI_CONNECTION', 'sqlite://')

    def setUp(self):
        super(DbFixture, self).setUp()
        # To prevent existance of prepared engine with wrong connection
        session.cleanup()

        self.conf.set_default('connection', self.uri, group='database')
        self.addCleanup(self.conf.reset)
        self.addCleanup(session.cleanup)


class DbTestCase(test_utils.BaseTestCase):
    """Base class for testing of DB code.
    To use backend other than sqlite: override env variable
    OS_TEST_DBAPI_ADMIN_CONNECTION defined in tox.ini file.
    Can't be used outside of tox.
    """

    def setUp(self):
        super(DbTestCase, self).setUp()
        self.useFixture(DbFixture())


ALLOWED_DIALECTS = ['sqlite', 'mysql', 'postgres']


def backend_specific(*dialects):
    """Decorator to skip backend specific tests on inappropriate engines

    ::dialects: list of dialects names under which the test will be launched.
    """
    def wrap(f):
        @wraps(f)
        def ins_wrap(self):
            if not set(dialects).issubset(ALLOWED_DIALECTS):
                raise NameError(
                    "Please use allowed dialects: %s" % ALLOWED_DIALECTS)
            engine = session.get_engine()
            if engine.name not in dialects:
                msg = ' '.join(('The test "%s" can be run only on %s.',
                                'Current engine is %s.'))
                args = (f.__name__, ' '.join(dialects), engine.name)
                self.skip(msg % args)
            else:
                return f(self)
        return ins_wrap
    return wrap
