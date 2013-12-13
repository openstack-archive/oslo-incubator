# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
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

"""Common utilities used in testing"""

import abc
import functools
import os
import tempfile

import fixtures
from oslo.config import cfg
import six
import testtools

from openstack.common.db.sqlalchemy import session
from openstack.common.db.sqlalchemy import utils
from openstack.common.fixture import moxstubout

_TRUE_VALUES = ('True', 'true', '1', 'yes')


class BaseTestCase(testtools.TestCase):

    def setUp(self, conf=cfg.CONF):
        super(BaseTestCase, self).setUp()
        moxfixture = self.useFixture(moxstubout.MoxStubout())
        self._set_timeout()
        self._fake_output()
        self.useFixture(fixtures.FakeLogger('openstack.common'))
        self.useFixture(fixtures.NestedTempfile())
        self.useFixture(fixtures.TempHomeDir())
        self.mox = moxfixture.mox
        self.stubs = moxfixture.stubs
        self.conf = conf
        self.addCleanup(self.conf.reset)
        self.useFixture(fixtures.FakeLogger('openstack.common'))

        test_timeout = os.environ.get('OS_TEST_TIMEOUT', 0)
        try:
            test_timeout = int(test_timeout)
        except ValueError:
            # If timeout value is invalid do not set a timeout.
            test_timeout = 0
        if test_timeout > 0:
            self.useFixture(fixtures.Timeout(test_timeout, gentle=True))
        if os.environ.get('OS_STDOUT_CAPTURE') in _TRUE_VALUES:
            stdout = self.useFixture(fixtures.StringStream('stdout')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stdout', stdout))
        if os.environ.get('OS_STDERR_CAPTURE') in _TRUE_VALUES:
            stderr = self.useFixture(fixtures.StringStream('stderr')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stderr', stderr))

        self.useFixture(fixtures.NestedTempfile())
        self.tempdirs = []

    def tearDown(self):
        super(BaseTestCase, self).tearDown()
        self.conf.reset()
        self.stubs.UnsetAll()
        self.stubs.SmartUnsetAll()

    def _set_timeout(self):
        test_timeout = os.environ.get('OS_TEST_TIMEOUT', 0)
        try:
            test_timeout = int(test_timeout)
        except ValueError:
            # If timeout value is invalid do not set a timeout.
            test_timeout = 0
        if test_timeout > 0:
            self.useFixture(fixtures.Timeout(test_timeout, gentle=True))

    def _fake_output(self):
        if os.environ.get('OS_STDOUT_CAPTURE') in _TRUE_VALUES:
            stdout = self.useFixture(fixtures.StringStream('stdout')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stdout', stdout))
        if os.environ.get('OS_STDERR_CAPTURE') in _TRUE_VALUES:
            stderr = self.useFixture(fixtures.StringStream('stderr')).stream
            self.useFixture(fixtures.MonkeyPatch('sys.stderr', stderr))

    def create_tempfiles(self, files, ext='.conf'):
        tempfiles = []
        for (basename, contents) in files:
            if not os.path.isabs(basename):
                (fd, path) = tempfile.mkstemp(prefix=basename, suffix=ext)
            else:
                path = basename + ext
                fd = os.open(path, os.O_CREAT | os.O_WRONLY)
            tempfiles.append(path)
            try:
                os.write(fd, contents)
            finally:
                os.close(fd)
        return tempfiles

    def config(self, **kw):
        """Override some configuration values.

        The keyword arguments are the names of configuration options to
        override and their values.

        If a group argument is supplied, the overrides are applied to
        the specified configuration option group.

        All overrides are automatically cleared at the end of the current
        test by the tearDown() method.
        """
        group = kw.pop('group', None)
        for k, v in six.iteritems(kw):
            self.conf.set_override(k, v, group)


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

        self.conf.set_default('connection', self._get_uri(), group='database')
        self.addCleanup(self.conf.reset)


class DbTestCase(BaseTestCase):
    """Base class for testing of DB code.

    Using `DbFixture`. Intended to be the main database test case to use all
    the tests on a given backend with user defined uri. Backend specific
    tests should be decorated with `backend_specific` decorator.
    """

    FIXTURE = DbFixture

    def setUp(self):
        super(DbTestCase, self).setUp()
        self.useFixture(self.FIXTURE())

        self.addCleanup(session.cleanup)


ALLOWED_DIALECTS = ['sqlite', 'mysql', 'postgresql']


def backend_specific(*dialects):
    """Decorator to skip backend specific tests on inappropriate engines.

    ::dialects: list of dialects names under which the test will be launched.
    """
    def wrap(f):
        @functools.wraps(f)
        def ins_wrap(self):
            if not set(dialects).issubset(ALLOWED_DIALECTS):
                raise ValueError(
                    "Please use allowed dialects: %s" % ALLOWED_DIALECTS)
            engine = session.get_engine()
            if engine.name not in dialects:
                msg = ('The test "%s" can be run '
                       'only on %s. Current engine is %s.')
                args = (f.__name__, ' '.join(dialects), engine.name)
                self.skip(msg % args)
            else:
                return f(self)
        return ins_wrap
    return wrap


@six.add_metaclass(abc.ABCMeta)
class OpportunisticFixture(DbFixture):
    """Base fixture to use default CI databases.

    The databases exist in OpenStack CI infrastructure. But for the
    correct functioning in local environment the databases must be
    created manually.
    """

    DRIVER = abc.abstractproperty(lambda: None)
    DBNAME = PASSWORD = USERNAME = 'openstack_citest'

    def _get_uri(self):
        return utils._get_connect_string(backend=self.DRIVER,
                                         user=self.USERNAME,
                                         passwd=self.PASSWORD,
                                         database=self.DBNAME)


@six.add_metaclass(abc.ABCMeta)
class OpportunisticTestCase(DbTestCase):
    """Base test case to use default CI databases.

    The subclasses of the test case are running only when openstack_citest
    database is available otherwise a tests will be skipped.
    """

    FIXTURE = abc.abstractproperty(lambda: None)

    def setUp(self):
        credentials = (
            self.FIXTURE.DRIVER,
            self.FIXTURE.USERNAME,
            self.FIXTURE.PASSWORD,
            self.FIXTURE.DBNAME)

        if self.FIXTURE.DRIVER and not utils._is_backend_avail(*credentials):
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
