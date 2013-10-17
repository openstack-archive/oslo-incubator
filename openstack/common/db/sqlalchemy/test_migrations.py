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
import functools
import io
import os
import urlparse

try:
    from alembic import command
    from alembic import migration
    ALEMBIC_LOADED = True
except ImportError:
    ALEMBIC_LOADED = False
from oslo.config import cfg
import sqlalchemy
import sqlalchemy.dialects.mysql.base as sa_mysql
import sqlalchemy.dialects.postgresql.base as sa_psql
import sqlalchemy.exc
import sqlalchemy.types as sa_types

from openstack.common.db.sqlalchemy import session
from openstack.common.fixture import lockutils as fixtures
from openstack.common import lockutils
from openstack.common import log as logging
from openstack.common import test

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

# In user defined data type case we can get a situation when
# dialect.type_descriptor(SomeType()) can return another type, not SomeType,
# but in database SomeType will be presented. The main reason in sqlalchemy
# logic and actually in colspecs attribute for each dialect. It is very
# limited and will return one of presented types.
# For example, dialect.type_descriptor(DECIMAL()) will return
# sqlalchemy.dialects.mysql.base.NUMERIC but in database
# sqlalchemy.dialects.mysql.base.DECIMAL will be presented.
# This module contains a test comparing expected type with presented in
# database. So, in this situation (sqlalchemy bug) we will get an error.
# We can use a sets of pairs with correct types as a decision of this problem.
DEFAULT_CORRECT_TYPES = set([
    (sa_mysql.NUMERIC, sa_mysql.DECIMAL),
    (sqlalchemy.types.DATETIME, sa_psql.TIMESTAMP),
])


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

    # Base model for project
    # Each component of OpenStack has a models based on
    # sqlalchemy.ext.declarative. Here we should specify this base class.
    # Here inheriting classes should specify this base class.
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
        if self.ALEMBIC_CONFIG is not None and not ALEMBIC_LOADED:
            raise ImportError("alembic")

    def setUp(self):
        # Each test's name ended by name of dialect.
        # We can lock tests by it's name and tests for different dialects
        # can start in parallel mode.
        # It will be done due to one database that using by all tests.
        if hasattr(self, "DIALECT"):
            self.useFixture(fixtures.LockFixture(self.DIALECT))
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
        self.correct_types = DEFAULT_CORRECT_TYPES.copy()

    def tearDown(self):
        # We destroy the test data store between each test case,
        # and recreate it, which ensures that we have no side-effects
        # from the tests
        self._reset_databases()
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

    def _alembic_command(self, alembic_command, engine, *args, **kwargs):
        """Most of alembic command return data into output.
        We should redefine this setting for getting info.
        """
        self.ALEMBIC_CONFIG.stdout = buf = io.StringIO()
        CONF.set_override('connection', str(engine.url), group='database')
        session.cleanup()
        getattr(command, alembic_command)(*args, **kwargs)
        res = buf.getvalue().strip()
        LOG.debug('Alembic command `%s` returns: %s' % (alembic_command, res))
        session.cleanup()
        return res

    def _get_alembic_versions(self, engine):
        """For support of full testing of migrations
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

    def _configure(self, engine, alembic):
        """For each type of repository we should do some of configure steps.
        For migrate_repo we should set under version control our database.
        For alembic we should configure database settings. For this goal we
        should use oslo.config and openstack.commom.db.sqlalchemy.session with
        database functionality (reset default settings and session cleanup).
        """
        if alembic:
            CONF.set_override('connection', str(engine.url), group='database')
            session.cleanup()
            return
        self.MIGRATION_API.version_control(engine, self.REPOSITORY,
                                           self.INIT_VERSION)
        self.assertEqual(self.INIT_VERSION,
                         self.MIGRATION_API.db_version(engine,
                                                       self.REPOSITORY))

        LOG.debug('latest version is %s' % self.REPOSITORY.latest)

    def _migrate_dbsync(self, engine, version_control=True):
        if self.MIGRATION_API is not None and self.REPOSITORY is not None:
            if version_control:
                self.MIGRATION_API.version_control(engine, self.REPOSITORY,
                                                   self.INIT_VERSION)
            self.MIGRATION_API.upgrade(engine, self.REPOSITORY)

    def _alembic_dbsync(self, engine):
        if self.ALEMBIC_CONFIG is not None:
            self._alembic_command('upgrade', engine, self.ALEMBIC_CONFIG,
                                  "head")

    def _up_and_down_versions(self, alembic, engine):
        """Since alembic version has a random algoritm of generation
        (SA-migrate has an ordered autoincrement naming) we should store
        a tuple of versions (version for upgrade and version for downgrade)
        for successfull testing of migrations in up>down>up mode.
        """
        if alembic:
            versions = self._get_alembic_versions(engine)
            return zip(versions, ['-1'] + versions)
        versions = range(self.INIT_VERSION + 1, self.REPOSITORY.latest + 1)
        return [(v, v-1) for v in versions]

    def _walk_versions(self, engine=None, snake_walk=False,
                       downgrade=True, alembic=False):
        # Determine latest version script from the repo, then
        # upgrade from 1 through to the latest, with no data
        # in the databases. This just checks that the schema itself
        # upgrades successfully.

        self._configure(engine, alembic)
        up_and_down_versions = self._up_and_down_versions(alembic, engine)
        for ver_up, ver_down in up_and_down_versions:
            # upgrade -> downgrade -> upgrade
            self._migrate_up(engine, ver_up, with_data=True, alembic=alembic)
            if snake_walk:
                downgraded = self._migrate_down(engine,
                                                ver_down,
                                                with_data=True,
                                                alembic=alembic,
                                                next_version=ver_up)
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
                                                alembic=alembic,
                                                next_version=ver_up)

                if snake_walk and downgraded:
                    self._migrate_up(engine, ver_up, alembic=alembic)
                    self._migrate_down(engine, ver_down, alembic=alembic,
                                       next_version=ver_up)

    def _get_version_from_db(self, engine, alembic):
        """For each type of migrate repo latest version from db
        will be returned.
        """
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
        """Base method for manipulation with migrate repo.
        It will upgrade or downgrade the actual database.
        """
        if alembic:
            self._alembic_command(cmd, engine, self.ALEMBIC_CONFIG, version)
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
            if not alembic:
                next_version = "%03d" % (next_version)
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


class CommonCheckMigrations(BaseMigrationTestCase, WalkVersionsMixin):
    # Tested dialects ('mysql', 'postgres')
    DIALECTS = ['mysql', 'postgres']
    # List of tables that can be presented only in one of places
    # (in models or db). When such is the deliberate creation.
    # Example: backup tables, shadow_tables...
    EXCLUDE_TABLES = []

    def check_dialect(func):
        @functools.wraps(func)
        def _inner(self, dialect):
            if dialect not in self.DIALECTS:
                self.skipTest("%s not presented in self.DIALECTS" % dialect)
            if dialect == 'mysql':
                check_backend = _have_mysql
            elif dialect == 'postgres':
                check_backend = _have_postgresql
            if not check_backend(self.USER, self.PASSWORD, self.DATABASE):
                self.skipTest("%s not available" % dialect)
            func(self, dialect)
        return _inner

    def _get_engine(self, dialect):
        connect_string = _get_connect_string(dialect,
                                             self.USER,
                                             self.PASSWORD,
                                             self.DATABASE)
        engine = sqlalchemy.create_engine(connect_string)
        self.engines[dialect] = engine
        self.test_databases[dialect] = connect_string
        return engine

    @check_dialect
    def _test_walk_versions(self, dialect):
        """Helper method that implements testing of each migration in all ways
        (from up to down and in backward mode). It will work with both types
        of repo.
        """
        engine = self._get_engine(dialect)
        if self.MIGRATION_API is not None and self.REPOSITORY is not None:
            self._walk_versions(engine, snake_walk=True, downgrade=True,
                                alembic=False)
        if self.ALEMBIC_CONFIG is not None:
            self._migrate_dbsync(engine, version_control=False)
            self._walk_versions(engine, snake_walk=True, downgrade=True,
                                alembic=True)

    @check_dialect
    def _test_sync_models(self, dialect):
        """Helper method that implements testing of equality models with
        migrations. All differences will be presented as a list of needed
        changes.
        """
        engine = self._get_engine(dialect)
        self._migrate_dbsync(engine)
        self._alembic_dbsync(engine)
        metadata = sqlalchemy.MetaData(bind=engine)
        metadata.reflect()
        db_tables = metadata.tables
        self.errors = []
        models_tables = self.MODEL_BASE.metadata.tables
        self.EXCLUDE_TABLES.extend(['migrate_version', 'alembic_version'])
        tables = self._check_intersection(models_tables.keys(),
                                          db_tables.keys(),
                                          "Tables",
                                          "models",
                                          exclude=set(self.EXCLUDE_TABLES))
        for table_name in tables:
            table = models_tables[table_name]
            self._check_columns(table, db_tables[table_name],
                                engine.dialect)
            # All checked UniqueConstraints should be excluded from indexes.
            uc = self._check_uniques(table, db_tables[table_name], dialect)
            # All checked ForeignKeys should be excluded from indexes.
            fc = self._check_fkeys(table, db_tables[table_name])
            excluded_indexes = uc | fc
            self._check_indexes(table,
                                db_tables[table_name],
                                excluded_indexes,
                                dialect)
        self.assertEqual(self.errors, [],
                         message="\n".join(self.errors))

    def _check_column_type(self, column_model, column_db, column_name,
                           table_name, dialect):
        """Checking of column's type declared in models with column's type
        existed in database. Also limit of length will be checked.
        """
        _msg = ("Wrong type for column `%(name)s` in `%(table)s`: `%(model)s` "
                "in models, expected `%(db)s`.")
        params = {'name': column_name,
                  'table': table_name,
                  'model': type(column_model.type).__name__,
                  'db': type(column_db.type).__name__}
        msg = _msg % params
        model_column_type_len = getattr(column_model.type, 'length', None)
        model_type = column_model.type
        model_type_cls = type(model_type)
        db_type = column_db.type
        db_type_cls = type(db_type)
        if isinstance(model_type, sa_types.Boolean):
            if not isinstance(db_type, (sa_types.Integer, model_type_cls)):
                self.errors.append(msg)
        elif isinstance(model_type, sa_types.TypeDecorator):
            # This is a special check for redefined types like IPAddress, CIDR,
            # MediumText...
            # For each redefined type we have sqlalchemy.types.Variant
            # instance. But only simple types are present in database model.
            # So we should get one of the base types from each redefined type
            # and compare it with database implementation.
            model_type = model_type.load_dialect_impl(dialect)
            while isinstance(model_type, sa_types.Variant):
                model_type = model_type.load_dialect_impl(dialect)
            model_type_cls = type(model_type)
            if not (issubclass(db_type_cls, model_type_cls) or
                    (model_type_cls, db_type_cls) in self.correct_types):
                params['model'] += ':' + model_type_cls.__name__
                self.errors.append(_msg % params)
            model_column_type_len = getattr(model_type, 'length', None)
        else:
            if not isinstance(db_type, model_type_cls):
                self.errors.append(msg)
        db_column_type_len = getattr(db_type, 'length', None)

        if model_column_type_len != db_column_type_len:
            msg = ("Wrong length for column `%s` in "
                   "`%s` (model: %s, db: %s)" % (column_name,
                                                 table_name,
                                                 model_column_type_len,
                                                 db_column_type_len))
            self.errors.append(msg)

    def _check_columns(self, table_model, table_db, dialect):
        """Checking of equality of columns in table declared in modelas with
        table existed in database.
        Attribute for check:
        - nullable,
        - unique,
        - index,
        - default,
        - primary key.
        """
        table_name = table_model.name
        check_attrs = [
            'nullable',
            'unique',
            'primary_key',
            'index',
        ]
        columns = self._check_intersection(table_db.c.keys(),
                                           table_model.c.keys(),
                                           "Columns",
                                           table_name)
        for column_name in columns:
            column_model = table_model.c[column_name]
            column_db = table_db.c[column_name]
            self._check_column_type(column_model,
                                    column_db,
                                    column_name,
                                    table_name,
                                    dialect)
            # We can not check default attribute like others in `check_attrs`
            # because there are a lot of columns in models with predefined
            # values which skipped in db (created_at, deleted columns).
            # It is not a bug, but without migration that can fix this
            # situation (add default values for this columns in db)
            # we can not check it like other params from `check_attrs`.
            if column_db.default is not None:
                if column_db.default != column_model.default:
                    msg = ("Wrong default value in models for "
                           "`%s.%s`" % (table_name, column_name,))
                    self.errors.append(msg)
            for attr in check_attrs:
                model_attr = getattr(column_model, attr)
                db_attr = getattr(column_db, attr)
                if model_attr != db_attr:
                    msg = ("Wrong value for `%s` attribute in `%s.%s` "
                           "(models:%s, db:%s)" % (attr,
                                                   table_name,
                                                   column_name,
                                                   model_attr,
                                                   db_attr))
                    self.errors.append(msg)

    def _check_indexes(self, table_model, table_db, excluded_indexes, dialect):
        """Base checking of index constraint.
        This test checks name and columns in index.
        For mysql column's order also will be checked.
        """

        db_indexes = dict((index.name, index) for index in
                          table_db.indexes)
        table_name = table_model.name
        model_indexes = dict([(index.name, index) for index in
                             table_model.indexes])
        indexes = self._check_intersection(db_indexes.keys(),
                                           model_indexes.keys(),
                                           "Indexes",
                                           table_name,
                                           exclude=excluded_indexes)
        check_order = self._check_order(dialect)
        for index_name in indexes:
            db_index_c = db_indexes[index_name].columns.keys()
            model_index_c = model_indexes[index_name].columns.keys()
            self._check_intersection(db_index_c,
                                     model_index_c,
                                     "Indexes",
                                     table_name,
                                     index_name,
                                     check_order=check_order)

    def _check_order(self, dialect):
        """Return boolean value for checking of order columns in index.
        In mysql case True will be returned.
        Since before 0.8.2 version columns in indexes have a wrong
        order for postgres False will be returned in this case.
        """
        if dialect == 'mysql':
            return True
        version = map(int, sqlalchemy.__version__.split('.'))
        return dialect == 'postgres' and version >= [0, 8, 2]

    def _check_fkeys(self, table_model, table_db):
        """Checking of equality of foreign keys declared in models
        and existed in database.
        The name for ForeignKey in models is skipped by default.
        We can see it in this kind of creation:
        Column(Integer, ForeignKey('table.column')).
        So, we can only check it by column name.
        Also for each ForeignKey index in table will be created.
        After this step we should remove index for this constraint from
        indexes that we will be checked later (for excluding of duplicate
        check). Removing will be done from temporary list of indexes
        not from table.
        """
        table_name = table_model.name
        db_fkeys = dict((c.parent.name, c.column.name)
                        for c in table_db.foreign_keys)
        model_fkeys = dict((c.parent.name, c.column.name)
                           for c in table_model.foreign_keys)
        fkeys = self._check_intersection(db_fkeys.keys(),
                                         model_fkeys.keys(),
                                         "ForeignKeys",
                                         table_name)
        for k in fkeys:
            self._check_intersection([db_fkeys[k]],
                                     [model_fkeys[k]],
                                     "ForeignKeys",
                                     table_name, k)
        db_fkeys_names = [c.name for c in table_db.foreign_keys
                          if c.parent.name in fkeys]
        db_fkeys_names.extend(fkeys)
        return set(db_fkeys_names)

    def _check_uniques(self, table_model, table_db, dialect):
        """We can check UC only from list of indexes in actual version
        of sqlalchemy.
        If there is a UniqueConstraint in database that skipped
        in models we will get an error from indexes check.
        In missing index case for UC that presented only in database
        mysql check will not give an error, but postgres check will do.
        """
        table_name = table_model.name
        constraint_class = sqlalchemy.schema.UniqueConstraint
        db_indexes = dict((index.name, index) for index in
                          table_db.indexes)
        checked_uniques = []
        check_order = self._check_order(dialect)
        for constraint in table_model.constraints:
            if not isinstance(constraint, constraint_class):
                continue

            # We have a naming convention for UniqueConstraint (UC).
            # (uniq_tablename0columnA0columnB...).
            # But when we use unique=True attribute it can not work
            # because column name will be taken as UC name.
            uniq_fields = ['uniq_' + table_name]
            uniq_fields.extend(constraint.columns.keys())
            check = "0".join(uniq_fields)
            constraint_name = constraint.name
            if constraint_name is None:
                if len(constraint.columns.keys()) > 1:
                    constraint_name = check
                else:
                    constraint_name = constraint.columns.keys()[0]
            if constraint_name not in db_indexes:
                msg = ("%s `%s.%s` declared in models is skipped "
                       "in migrations." % ("UniqueConstraint",
                                           table_name,
                                           constraint_name))
                self.errors.append(msg)
                continue
            checked_uniques.append(constraint_name)
            db_index = db_indexes[constraint_name]
            if not db_index.unique:
                self.errors.append("Index in database `%s.%s` "
                                   "should be unique as it declared "
                                   "in models." % (table_name,
                                                   constraint_name))
            # Checking list and order of columns in UniqueConstraint
            # in models and database at equality.
            self._check_intersection(db_index.columns.keys(),
                                     constraint.columns.keys(),
                                     "UniqueConstraint",
                                     table_name,
                                     constraint_name,
                                     check_order=check_order)
        return set(checked_uniques)

    def _check_intersection(self, db_obj, model_obj, obj_label, table_name,
                            obj_name="", exclude=None, check_order=False):
        """Helper method for checking sets at equality and right order
        of objects in them.
        """
        obj_diff = set(db_obj) ^ set(model_obj)
        full_obj = set(db_obj) & set(model_obj)
        if exclude is not None:
            obj_diff -= exclude
            full_obj -= exclude
        if obj_diff:
            diff_model = obj_diff & set(model_obj)
            diff_db = obj_diff & set(db_obj)
            msg = ("%s have a difference in %s %s: (%s). "
                   "Models: (%s). Database: (%s)." % (obj_label,
                                                      table_name,
                                                      obj_name,
                                                      ",".join(obj_diff),
                                                      ",".join(diff_model),
                                                      ",".join(diff_db)))
            self.errors.append(msg)
        if check_order and db_obj != model_obj:
            msg = ("%s in `%s.%s` have wrong order in models (%s), "
                   "expected in database (%s)" % (obj_label,
                                                  table_name,
                                                  obj_name,
                                                  ",".join(model_obj),
                                                  ",".join(db_obj)))
            self.errors.append(msg)
        return full_obj


class SyncModelsWithMigrations(CommonCheckMigrations):
    # Specific dialect on which migrations will be tested.
    # This name will use as a name for lock of databases resource.
    DIALECT = None

    def test_sync_models(self):
        """Testing of models with migrations to equality on specific dialect.
        """
        self._test_sync_models(self.DIALECT)

    def test_walk_versions_postgres(self):
        """Testing of migrations in up>down>up mode and in down>up>down mode
        on specific dialect.
        """
        self._test_walk_versions(self.DIALECT)
