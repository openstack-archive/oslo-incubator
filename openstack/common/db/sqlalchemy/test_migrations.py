# Copyright 2010-2011 OpenStack Foundation
# Copyright 2012-2013 IBM Corp.
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

import functools
import io
import mock
import os
import subprocess

try:
    from alembic import command
    from alembic import migration
    ALEMBIC_LOADED = True
except ImportError:
    ALEMBIC_LOADED = False

import lockfile
from oslo.config import cfg
from six import moves
import sqlalchemy
import sqlalchemy.exc

from openstack.common.gettextutils import _  # noqa
from openstack.common import log as logging
from openstack.common.py3kcompat import urlutils
from openstack.common import test

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


def _get_connect_string(backend, user, passwd, database):
    """Get database connection

    Try to get a connection with a very specific set of values, if we get
    these then we'll run the tests, otherwise they are skipped
    """
    if backend == "postgres":
        backend = "postgresql+psycopg2"
    elif backend == "mysql":
        backend = "mysql+mysqldb"
    else:
        raise Exception("Unrecognized backend: '%s'" % backend)

    return ("%(backend)s://%(user)s:%(passwd)s@localhost/%(database)s"
            % {'backend': backend, 'user': user, 'passwd': passwd,
               'database': database})


def _is_backend_avail(backend, user, passwd, database):
    try:
        connect_uri = _get_connect_string(backend, user, passwd, database)
        engine = sqlalchemy.create_engine(connect_uri)
        connection = engine.connect()
    except Exception:
        # intentionally catch all to handle exceptions even if we don't
        # have any backend code loaded.
        return False
    else:
        connection.close()
        engine.dispose()
        return True


def _have_mysql(user, passwd, database):
    present = os.environ.get('TEST_MYSQL_PRESENT')
    if present is None:
        return _is_backend_avail('mysql', user, passwd, database)
    return present.lower() in ('', 'true')


def _have_postgresql(user, passwd, database):
    present = os.environ.get('TEST_POSTGRESQL_PRESENT')
    if present is None:
        return _is_backend_avail('postgres', user, passwd, database)
    return present.lower() in ('', 'true')


def get_db_connection_info(conn_pieces):
    database = conn_pieces.path.strip('/')
    loc_pieces = conn_pieces.netloc.split('@')
    host = loc_pieces[1]

    auth_pieces = loc_pieces[0].split(':')
    user = auth_pieces[0]
    password = ""
    if len(auth_pieces) > 1:
        password = auth_pieces[1].strip()

    return (user, password, database, host)


def _set_db_lock(lock_path=None, lock_prefix=None):
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            try:
                path = lock_path or os.environ.get("OSLO_LOCK_PATH")
                lock = lockfile.FileLock(os.path.join(path, lock_prefix))
                with lock:
                    LOG.debug(_('Got lock "%s"') % f.__name__)
                    return f(*args, **kwargs)
            finally:
                LOG.debug(_('Lock released "%s"') % f.__name__)
        return wrapper
    return decorator


class BaseMigrationTestCase(test.BaseTestCase):
    """Base class for testing of migration utils.

    It contains constants that can be redefined for each component
    of OpenStack. By these settings we can configure migration repo
    (SA-migrate and alembic at the same time).
    """
    # Database settings
    # It will be used for each tested dialect.
    USER = 'openstack_citest'
    PASSWORD = 'openstack_citest'
    DATABASE = 'openstack_citest'

    # Migrate repo settings
    # Path to migrations repo in python style.
    REPOSITORY = None
    # Number of first migration in repo minus one.
    INIT_VERSION = 0
    # API for migrate repo for getting version from db
    # and run of upgrade/downgrade.
    MIGRATION_API = None

    # Alembic repo settings
    # Since  alembic config is used by all alembic commands
    # it should be declared for alembic repo here.
    ALEMBIC_CONFIG = None

    def __init__(self, *args, **kwargs):
        super(BaseMigrationTestCase, self).__init__(*args, **kwargs)

        self.DEFAULT_CONFIG_FILE = os.path.join(os.path.dirname(__file__),
                                                'test_migrations.conf')
        # Test machines can set the TEST_MIGRATIONS_CONF variable
        # to override the location of the config file for migration testing
        self.CONFIG_FILE_PATH = os.environ.get('TEST_MIGRATIONS_CONF',
                                               self.DEFAULT_CONFIG_FILE)
        self.test_databases = {}
        if self.ALEMBIC_CONFIG is not None and not ALEMBIC_LOADED:
            raise ImportError("alembic")

    def setUp(self):
        super(BaseMigrationTestCase, self).setUp()

        # Load test databases from the config file. Only do this
        # once. No need to re-run this on each test...
        LOG.debug('config_path is %s' % self.CONFIG_FILE_PATH)
        if os.path.exists(self.CONFIG_FILE_PATH):
            cp = moves.configparser.RawConfigParser()
            try:
                cp.read(self.CONFIG_FILE_PATH)
                defaults = cp.defaults()
                for key, value in defaults.items():
                    self.test_databases[key] = value
            except moves.configparser.ParsingError as e:
                self.fail("Failed to read test_migrations.conf config "
                          "file. Got error: %s" % e)
        else:
            self.fail("Failed to find test_migrations.conf config "
                      "file.")

        self.engines = {}
        for key, value in self.test_databases.items():
            self.engines[key] = sqlalchemy.create_engine(value)

        # We start each test case with a completely blank slate.
        self._reset_databases()

    def tearDown(self):
        # We destroy the test data store between each test case,
        # and recreate it, which ensures that we have no side-effects
        # from the tests
        self._reset_databases()
        super(BaseMigrationTestCase, self).tearDown()

    def execute_cmd(self, cmd=None):
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
        output = process.communicate()[0]
        LOG.debug(output)
        self.assertEqual(0, process.returncode,
                         "Failed to run: %s\n%s" % (cmd, output))

    def _reset_pg(self, conn_pieces):
        (user, password, database, host) = get_db_connection_info(conn_pieces)
        os.environ['PGPASSWORD'] = password
        os.environ['PGUSER'] = user
        # note(boris-42): We must create and drop database, we can't
        # drop database which we have connected to, so for such
        # operations there is a special database template1.
        sqlcmd = ("psql -w -U %(user)s -h %(host)s -c"
                  " '%(sql)s' -d template1")

        sql = ("drop database if exists %s;") % database
        droptable = sqlcmd % {'user': user, 'host': host, 'sql': sql}
        self.execute_cmd(droptable)

        sql = ("create database %s;") % database
        createtable = sqlcmd % {'user': user, 'host': host, 'sql': sql}
        self.execute_cmd(createtable)

        os.unsetenv('PGPASSWORD')
        os.unsetenv('PGUSER')

    @_set_db_lock(lock_prefix='migration_tests-')
    def _reset_databases(self):
        for key, engine in self.engines.items():
            conn_string = self.test_databases[key]
            conn_pieces = urlutils.urlparse(conn_string)
            engine.dispose()
            if conn_string.startswith('sqlite'):
                # We can just delete the SQLite database, which is
                # the easiest and cleanest solution
                db_path = conn_pieces.path.strip('/')
                if os.path.exists(db_path):
                    os.unlink(db_path)
                # No need to recreate the SQLite DB. SQLite will
                # create it for us if it's not there...
            elif conn_string.startswith('mysql'):
                # We can execute the MySQL client to destroy and re-create
                # the MYSQL database, which is easier and less error-prone
                # than using SQLAlchemy to do this via MetaData...trust me.
                (user, password, database, host) = \
                    get_db_connection_info(conn_pieces)
                sql = ("drop database if exists %(db)s; "
                       "create database %(db)s;") % {'db': database}
                cmd = ("mysql -u \"%(user)s\" -p\"%(password)s\" -h %(host)s "
                       "-e \"%(sql)s\"") % {'user': user, 'password': password,
                                            'host': host, 'sql': sql}
                self.execute_cmd(cmd)
            elif conn_string.startswith('postgresql'):
                self._reset_pg(conn_pieces)


class WalkVersionsMixin(object):

    @mock.patch('openstack.common.db.sqlalchemy.session.get_engine')
    @mock.patch('openstack.common.db.sqlalchemy.session.get_session')
    def _alembic_command(self, alembic_command, engine, *args, **kwargs):
        """Runs alembic command.

        Most of alembic command return data into output.
        We should redefine this setting for getting info.
        """
        # A lot of pieces of code use oslo session for getting of engine
        # and session. These settings are based on config's options.
        # For sucessful testing in concurrency mode we can redefine these
        # engine and session by mock.
        mock_get_session, mock_get_engine = args[-2:]
        mock_get_engine.return_value = engine
        mock_get_session.return_value.get_bind.return_value = engine

        self.ALEMBIC_CONFIG.stdout = buf = io.StringIO()
        getattr(command, alembic_command)(*args[:-2], **kwargs)
        res = buf.getvalue().strip()
        LOG.debug('Alembic command `%s` returns: %s' % (alembic_command, res))
        return res

    def _get_alembic_versions(self, engine):
        """Returns alembic versions.

        For support of full testing of migrations
        we should have an opportunity to run command step by step for each
        version in repo. This method returns list of alembic_versions by
        historical order.
        """
        full_history = self._alembic_command('history',
                                             engine, self.ALEMBIC_CONFIG)
        # The piece of output data with version can looked as:
        # 'Rev: 17738166b91 (head)' or 'Rev: 43b1a023dfaa'
        alembic_history = [r.split(' ')[1] for r in full_history.split("\n")
                           if r.startswith("Rev")]
        alembic_history.reverse()
        return alembic_history

    def _configure(self, engine, alembic=False):
        """Configuration of repo.

        For each type of repository we should do some of configure steps.
        For migrate_repo we should set under version control our database.
        For alembic we should configure database settings. For this goal we
        should use oslo.config and openstack.commom.db.sqlalchemy.session with
        database functionality (reset default settings and session cleanup).
        """
        if alembic:
            return
        self.MIGRATION_API.version_control(engine, self.REPOSITORY,
                                           self.INIT_VERSION)
        self.assertEqual(self.INIT_VERSION,
                         self.MIGRATION_API.db_version(engine,
                                                       self.REPOSITORY))

        LOG.debug(_('latest version is %s') % self.REPOSITORY.latest)

    def _up_and_down_versions(self, alembic, engine):
        """List of versions for up>down>up mode.

        Since alembic version has a random algoritm of generation
        (SA-migrate has an ordered autoincrement naming) we should store
        a tuple of versions (version for upgrade and version for downgrade)
        for successfull testing of migrations in up>down>up mode.
        """
        if alembic:
            versions = self._get_alembic_versions(engine)
            return zip(versions, ['-1'] + versions)
        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)
        return [(v, v - 1) for v in versions]

    def _walk_versions(self, engine=None, snake_walk=False,
                       downgrade=True, alembic=False):
        # Determine latest version script from the repo, then
        # upgrade from 1 through to the latest, with no data
        # in the databases. This just checks that the schema itself
        # upgrades successfully.

        self._configure(engine, alembic=alembic)
        up_and_down_versions = self._up_and_down_versions(alembic, engine)
        for ver_up, ver_down in up_and_down_versions:
            # upgrade -> downgrade -> upgrade
            self._migrate_up(engine, ver_up, with_data=True, alembic=alembic)
            if snake_walk:
                downgraded = self._migrate_down(engine,
                                                ver_down,
                                                ver_up,
                                                with_data=True,
                                                alembic=alembic)
                if downgraded:
                    self._migrate_up(engine, ver_up, alembic=alembic)

        if downgrade:
            # Now walk it back down to 0 from the latest, testing
            # the downgrade paths.
            up_and_down_versions.reverse()
            for ver_up, ver_down in up_and_down_versions:
                # downgrade -> upgrade -> downgrade
                downgraded = self._migrate_down(engine,
                                                ver_down,
                                                ver_up,
                                                alembic=alembic)

                if snake_walk and downgraded:
                    self._migrate_up(engine, ver_up, alembic=alembic)
                    self._migrate_down(engine, ver_down, ver_up,
                                       alembic=alembic)

    def _get_version_from_db(self, engine, alembic):
        """Returns actual version from database.

        For each type of migrate repo latest version from db
        will be returned.
        """
        if not alembic:
            return self.MIGRATION_API.db_version(engine, self.REPOSITORY)
        with engine.begin() as conn:
            context = migration.MigrationContext.configure(conn)
            version = context.get_current_revision() or '-1'
        return version

    def _migrate(self, engine, alembic, version, cmd):
        """Runs migrate command.

        Base method for manipulation with migrate repo.
        It will upgrade or downgrade the actual database.
        """
        if alembic:
            self._alembic_command(cmd, engine, self.ALEMBIC_CONFIG, version)
        else:
            getattr(self.MIGRATION_API, cmd)(engine, self.REPOSITORY, version)

    def _migrate_down(self, engine, version, next_version, with_data=False,
                      alembic=False):
        try:
            self._migrate(engine, alembic, version, 'downgrade')
        except NotImplementedError:
            # NOTE(sirp): some migrations, namely release-level
            # migrations, don't support a downgrade.
            return False
        self.assertEqual(version, self._get_version_from_db(engine,
                                                            alembic))

        # NOTE(sirp): `version` is what we're downgrading to (i.e. the 'target'
        # version). So if we have any downgrade checks, they need to be run for
        # the previous (higher numbered) migration.
        if with_data:
            next_version = next_version if alembic else '%03d' % next_version
            post_downgrade = getattr(
                self, "_post_downgrade_%s" % next_version, None)
            if post_downgrade:
                post_downgrade(engine)

        return True

    def _migrate_up(self, engine, version, with_data=False, alembic=False):
        """migrate up to a new version of the db.

        We allow for data insertion and post checks at every
        migration version with special _pre_upgrade_### and
        _check_### functions in the main test.
        """
        check_version = version if alembic else '%03d' % version
        # NOTE(sdague): try block is here because it's impossible to debug
        # where a failed data migration happens otherwise
        try:
            if with_data:
                data = None
                pre_upgrade = getattr(
                    self, "_pre_upgrade_%s" % check_version, None)
                if pre_upgrade:
                    data = pre_upgrade(engine)
            self._migrate(engine, alembic, version, 'upgrade')
            self.assertEqual(version, self._get_version_from_db(engine,
                                                                alembic))
            if with_data:
                check = getattr(self, "_check_%s" % check_version, None)
                if check:
                    check(engine, data)
        except Exception:
            LOG.error("Failed to migrate to version %s on engine %s" %
                      (version, engine))
            raise
