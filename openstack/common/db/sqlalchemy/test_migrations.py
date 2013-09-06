# vim: tabstop=4 shiftwidth=4 softtabstop=4

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


import commands
import ConfigParser
import os
import tempfile
import urlparse

from alembic import command
from alembic import migration
from oslo.config import cfg
import sqlalchemy
import sqlalchemy.exc

from openstack.common.db.sqlalchemy import session
from openstack.common import lockutils
from openstack.common import log as logging
from openstack.common import test

LOG = logging.getLogger(__name__)
CONF = cfg.CONF
lockutils.set_defaults(tempfile.mkdtemp())


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


class BaseMigrationTestCase(test.BaseTestCase):
    """Base class fort testing of migration utils."""
    # Database settings
    USER = 'openstack_citest'
    PASSWD = 'openstack_citest'
    DATABASE = 'openstack_citest'

    # Migrate repo settings
    REPOSITORY = None
    INIT_VERSION = 0
    MIGRATION_API = None

    # Alembic repo settings
    ALEMBIC_CONFIG = None

    # Base model for project
    MODEL_BASE = None

    def __init__(self, *args, **kwargs):
        super(BaseMigrationTestCase, self).__init__(*args, **kwargs)

        self.DEFAULT_CONFIG_FILE = os.path.join(os.path.dirname(__file__),
                                                'test_migrations.conf')
        # Test machines can set the TEST_MIGRATIONS_CONF variable
        # to override the location of the config file for migration testing
        self.CONFIG_FILE_PATH = os.environ.get('TEST_MIGRATIONS_CONF',
                                               self.DEFAULT_CONFIG_FILE)
        self.test_databases = {}

    def setUp(self):
        super(BaseMigrationTestCase, self).setUp()

        # Load test databases from the config file. Only do this
        # once. No need to re-run this on each test...
        LOG.debug('config_path is %s' % self.CONFIG_FILE_PATH)
        if os.path.exists(self.CONFIG_FILE_PATH):
            cp = ConfigParser.RawConfigParser()
            try:
                cp.read(self.CONFIG_FILE_PATH)
                defaults = cp.defaults()
                for key, value in defaults.items():
                    self.test_databases[key] = value
            except ConfigParser.ParsingError as e:
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
        session.cleanup()
        super(BaseMigrationTestCase, self).tearDown()

    def execute_cmd(self, cmd=None):
        status, output = commands.getstatusoutput(cmd)
        LOG.debug(output)
        self.assertEqual(0, status,
                         "Failed to run: %s\n%s" % (cmd, output))

    @lockutils.synchronized('pgadmin', 'tests-', external=True)
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

    def _reset_databases(self):
        for key, engine in self.engines.items():
            conn_string = self.test_databases[key]
            conn_pieces = urlparse.urlparse(conn_string)
            engine.dispose()
            session.cleanup()
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

    def _get_alembic_versions(self):
        ret = []
        alembic_history = []
        self.ALEMBIC_CONFIG.print_stdout = \
            lambda rev: alembic_history.append(str(rev).split("\n")[0])
        command.history(self.ALEMBIC_CONFIG)
        del self.ALEMBIC_CONFIG.print_stdout
        for rev in alembic_history:
            # 'Rev: 17738166b91 (head)' or 'Rev: 43b1a023dfaa'
            if rev:
                ret.append(rev.split(' ')[1])
        ret.reverse()
        return ret

    def _walk_versions_alembic(self, engine=None, snake_walk=False,
                               downgrade=True):
        # Determine latest version script from the repo, then
        # upgrade from 1 through to the latest, with no data
        # in the databases. This just checks that the schema itself
        # upgrades successfully.

        CONF.set_override('connection', str(engine.url), group='database')
        session.cleanup()
        versions = self._get_alembic_versions()
        up_and_down_versions = zip(versions, ['-1'] + versions)
        for ver_up, ver_down in up_and_down_versions:
            # upgrade -> downgrade -> upgrade
            self._migrate_up(engine, ver_up, with_data=True, alembic=True)
            if snake_walk:
                downgraded = self._migrate_down(engine, ver_down,
                                                with_data=True, alembic=True,
                                                next_version=ver_up)
                if downgraded:
                    self._migrate_up(engine, ver_up, alembic=True)

        if downgrade:
            # Now walk it back down to 0 from the latest, testing
            # the downgrade paths.
            up_and_down_versions.reverse()
            for ver_up, ver_down in up_and_down_versions:
                # downgrade -> upgrade -> downgrade
                downgraded = self._migrate_down(engine,
                                                ver_down,
                                                alembic=True,
                                                next_version=ver_up)

                if snake_walk and downgraded:
                    self._migrate_up(engine, ver_up, alembic=True)
                    self._migrate_down(engine, ver_down, alembic=True,
                                       next_version=ver_up)

    def _walk_versions(self, engine=None, snake_walk=False, downgrade=True):
        # Determine latest version script from the repo, then
        # upgrade from 1 through to the latest, with no data
        # in the databases. This just checks that the schema itself
        # upgrades successfully.

        # Place the database under version control
        self.MIGRATION_API.version_control(engine, self.REPOSITORY,
                                           self.INIT_VERSION)
        self.assertEqual(self.INIT_VERSION,
                         self.MIGRATION_API.db_version(engine,
                                                       self.REPOSITORY))

        LOG.debug('latest version is %s' % self.REPOSITORY.latest)
        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)

        for version in versions:
            # upgrade -> downgrade -> upgrade
            self._migrate_up(engine, version, with_data=True)
            if snake_walk:
                downgraded = self._migrate_down(
                    engine, version - 1, with_data=True)
                if downgraded:
                    self._migrate_up(engine, version)

        if downgrade:
            # Now walk it back down to 0 from the latest, testing
            # the downgrade paths.
            for version in reversed(versions):
                # downgrade -> upgrade -> downgrade
                downgraded = self._migrate_down(engine, version - 1)

                if snake_walk and downgraded:
                    self._migrate_up(engine, version)
                    self._migrate_down(engine, version - 1)

    def _get_version_from_db(self, engine, alembic):
        if not alembic:
            return self.MIGRATION_API.db_version(engine, self.REPOSITORY)
        conn = engine.connect()
        try:
            context = migration.MigrationContext.configure(conn)
            version = context.get_current_revision() or '-1'
        finally:
            conn.close()
        return version

    def _migrate(self, engine, alembic, version, cmd):
        if alembic:
            getattr(command, cmd)(self.ALEMBIC_CONFIG, version)
        else:
            getattr(self.MIGRATION_API, cmd)(engine, self.REPOSITORY, version)

    def _migrate_down(self, engine, version, with_data=False,
                      alembic=False, next_version=None):
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
            if next_version is None:
                next_version = "%03d" % (version + 1)
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
        # NOTE(sdague): try block is here because it's impossible to debug
        # where a failed data migration happens otherwise
        check_version = version if alembic else '%03d' % version
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
