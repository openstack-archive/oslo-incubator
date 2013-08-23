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
import itertools
import os
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
    USER = None
    PASSWD = None
    DATABASE = None
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
        # migrate settings
        self.REPOSITORY = None
        self.INIT_VERSION = 0
        self.migration_api = None

        # alembic settings
        self.alembic_config = None

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

    def _get_alembic_versions(self):
        ret = []
        alembic_history = []
        self.alembic_config.print_stdout = \
            lambda rev: alembic_history.append(str(rev).split("\n")[0])
        command.history(self.alembic_config)
        for rev in alembic_history:
            # 'Rev: 17738166b91 (head)' or 'Rev: 43b1a023dfaa'
            if rev:
                ret.append(rev.split(' ')[1])
        return ret[::-1]

    def _walk_versions_alembic(self, engine=None, snake_walk=False,
                               downgrade=True):
        # Determine latest version script from the repo, then
        # upgrade from 1 through to the latest, with no data
        # in the databases. This just checks that the schema itself
        # upgrades successfully.

        CONF.set_override('connection', str(engine.url), group='database')
        versions = self._get_alembic_versions()
        for num, version in enumerate(versions):
            # upgrade -> downgrade -> upgrade
            self._migrate_up(engine, version, with_data=True, alembic=True)
            if snake_walk:
                if num:
                    version_downgrade = versions[num - 1]
                else:
                    version_downgrade = '-1'
                downgraded = self._migrate_down(engine, version_downgrade,
                                                with_data=True, alembic=True,
                                                next_version=version)
                if downgraded:
                    self._migrate_up(engine, version, alembic=True)

        if downgrade:
            # Now walk it back down to 0 from the latest, testing
            # the downgrade paths.
            versions = versions[::-1]
            for num, version in enumerate(versions):
                try:
                    version_downgrade = versions[num + 1]
                except IndexError:
                    version_downgrade = '-1'
                # downgrade -> upgrade -> downgrade
                downgraded = self._migrate_down(engine,
                                                version_downgrade,
                                                alembic=True,
                                                next_version=version)

                if snake_walk and downgraded:
                    self._migrate_up(engine, version, alembic=True)
                    self._migrate_down(engine, version_downgrade, alembic=True,
                                       next_version=version)

    def _walk_versions(self, engine=None, snake_walk=False, downgrade=True):
        # Determine latest version script from the repo, then
        # upgrade from 1 through to the latest, with no data
        # in the databases. This just checks that the schema itself
        # upgrades successfully.

        # Place the database under version control
        self.migration_api.version_control(engine, self.REPOSITORY,
                                           self.INIT_VERSION)
        self.assertEqual(self.INIT_VERSION,
                         self.migration_api.db_version(engine,
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
        if alembic:
            conn = engine.connect()
            context = migration.MigrationContext.configure(conn)
            version = context.get_current_revision() or '-1'
            conn.close()
        else:
            version = self.migration_api.db_version(engine, self.REPOSITORY)
        return version

    def _migrate(self, engine, alembic, version, cmd):
        if alembic:
            getattr(command, cmd)(self.alembic_config, version)
        else:
            getattr(self.migration_api, cmd)(engine, self.REPOSITORY, version)

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


class SyncModelsWithMigrations(BaseMigrationTestCase, WalkVersionsMixin):

    def _test_list_of_tables(self, dialect, test_mode=False,
                             exclude_tables=None):
        if dialect == 'mysql':
            check_backend = _have_mysql
        elif dialect == 'postgres':
            check_backend = _have_postgresql
        if not check_backend(self.USER,
                             self.PASSWD,
                             self.DATABASE):
            self.skipTest("%s not available" % dialect)
        connect_string = _get_connect_string(dialect, self.USER, self.PASSWD,
                                             self.DATABASE)
        engine = sqlalchemy.create_engine(connect_string)
        self.engines[self.DATABASE] = engine
        self.test_databases[self.DATABASE] = connect_string
        if not test_mode:
            self._reset_databases()
        # run migrations in  migrate repo
        if self.REPOSITORY is not None and self.migration_api is not None:
            self._walk_versions(engine, False, False)
        # run alembic migrations
        if self.alembic_config is not None:
            self._walk_versions_alembic(engine, False, False)
        metadata = sqlalchemy.MetaData(bind=engine)
        metadata.reflect()
        db_tables = metadata.tables
        self.errors = []
        models_tables = self.MODEL_BASE.metadata.tables
        exclude = exclude_tables or []
        exclude.extend(['migrate_version', 'alembic_version'])
        tables = self._get_intersection(models_tables.keys(),
                                        db_tables.keys(),
                                        "Tables",
                                        "models",
                                        exclude=set(exclude))
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
        session.cleanup()
        self.assertEqual(self.errors, [],
                         message="\n".join(self.errors))

    def _check_column_type(self, column_model, column_db, column_name,
                           table_name, dialect):
        msg = ("Wrong type for column `%s` in `%s`: "
               "`%s`, expected: `%s`" % (column_name,
                                         table_name,
                                         column_model.type.__class__.__name__,
                                         column_db.type.__class__.__name__))
        model_column_type_len = getattr(column_model.type, 'length', None)
        if issubclass(column_model.type.__class__,
                      sqlalchemy.types.Boolean):

            if not issubclass(column_db.type.__class__,
                              sqlalchemy.types.Integer) and \
               not issubclass(column_db.type.__class__,
                              column_model.type.__class__):
                self.errors.append(msg)
        elif issubclass(column_model.type.__class__,
                        sqlalchemy.types.TypeDecorator):
            # This is a special check for redefined types like IPAddress, CIDR,
            # MediumText...
            # For each redefined type we have sqlalchemy.types.Variant
            # instance. But only simple types are present in database model.
            # So we should get one of the base types from each redefined type
            # and compare it with database implementation.
            model_type = column_model.type.load_dialect_impl(dialect)
            while issubclass(model_type.__class__, sqlalchemy.types.Variant):
                model_type = model_type.load_dialect_impl(dialect)
            if not issubclass(column_db.type.__class__, model_type.__class__):
                self.errors.append(msg)
            model_column_type_len = getattr(model_type, 'length', None)
        else:
            if not issubclass(column_db.type.__class__,
                              column_model.type.__class__):
                self.errors.append(msg)
        db_column_type_len = getattr(column_db.type, 'length', None)

        if model_column_type_len != db_column_type_len:
            msg = ("Wrong length for column `%s` in "
                   "`%s` (model: %s, db: %s)" % (column_name,
                                                 table_name,
                                                 model_column_type_len,
                                                 db_column_type_len))
            self.errors.append(msg)

    def _check_columns(self, table_model, table_db, dialect):
        table_name = table_model.name
        check_attrs = [
            'nullable',
            'unique',
            'primary_key',
            'index'
        ]
        columns = self._get_intersection(table_db.c.keys(),
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
        """

        db_indexes = dict((index.name, index) for index in
                          table_db.indexes)
        table_name = table_model.name
        model_indexes = dict([(index.name, index) for index in
                             table_model.indexes])
        indexes = self._get_intersection(db_indexes.keys(),
                                         model_indexes.keys(),
                                         "Indexes",
                                         table_name,
                                         "Indexes",
                                         excluded_indexes)
        for index_name in indexes:
            db_index_c = db_indexes[index_name].columns.keys()
            model_index_c = model_indexes[index_name].columns.keys()
            kw = {}
            version = float(sqlalchemy.__version__[2:])
            if dialect == 'postgres' and version >= 8.2 or dialect == 'mysql':
                # Before 0.8.2 version columns in indexes have a wrong
                # order for postgres.
                kw = {'check_order': True}
            self._get_intersection(db_index_c,
                                   model_index_c,
                                   "Indexes",
                                   table_name,
                                   index_name,
                                   **kw)

    def _check_fkeys(self, table_model, table_db):
        table_name = table_model.name
        db_fkeys = dict([(c.parent.name, c.column.name)
                         for c in table_db.foreign_keys])
        # There is no name for ForeignKey in models by default.
        # So, we can only check by column name. But for each
        # ForeignKey index in table will be created.
        # After check we should remove index for this constraint
        # from indexes by its own name in db.
        model_fkeys = dict([(c.parent.name, c.column.name)
                           for c in table_model.foreign_keys])
        fkeys = self._get_intersection(db_fkeys.keys(),
                                       model_fkeys.keys(),
                                       "ForeignKey",
                                       table_name)
        for k in fkeys:
            self._get_intersection([db_fkeys[k]],
                                   [model_fkeys[k]],
                                   "ForeignKey",
                                   table_name, k)
        fkeys_name = [[k, '_'.join(('fk', table_name, k))] for k in fkeys]
        return set(itertools.chain(*fkeys_name))

    def _check_uniques(self, table_model, table_db, dialect):
        table_name = table_model.name
        constraint_class = sqlalchemy.schema.UniqueConstraint
        constraint_label = "UniqueConstraint"
        constraint_keys = [c for c in table_model.constraints
                           if isinstance(c, constraint_class)]
        db_indexes = dict((index.name, index) for index in
                          table_db.indexes)
        checked_uniques = []
        for constraint in constraint_keys:
            # We have a naming convention for UniqueConstraint (UC).
            # (uniq_tablename0columnA0columnB...).
            # But when we use unique=True attribute it can not work
            # Because column name will be taken as UC name.
            # We can check UC only in indexes for mysql dialect.
            # If there is a UniqueConstraint in database that skipped
            # in models we will get an error from indexes check.
            # (in many cases for each UC index will be created).
            # In missing index case for UC that presented only in datbase
            # mysql check will not give an error, but postgres check will do.
            # So, we use this hard magic of creation name and checking
            # keys constraint.
            uniq_fields = ['uniq_' + table_name]
            uniq_fields.extend(constraint.columns.keys())
            check = "0".join(uniq_fields)
            constraint_name = constraint.name
            if constraint_name is not None and constraint_name != check:
                self.errors.append("UniqueConstraint `%s.%s` has a wrong "
                                   "name. Expected:`%s`" % (table_name,
                                                            constraint_name,
                                                            check))
            elif constraint_name is None:
                self.errors.append("UniqueConstraint name in `%s` wrong "
                                   "`None`, expected: %s" % (table_name,
                                                             check))
                if len(constraint.columns.keys()) > 1:
                    constraint_name = check
                else:
                    constraint_name = constraint.columns.keys()[0]
            if constraint_name not in db_indexes:
                msg = ("%s `%s.%s` declared in models is skipped "
                       "in migrations." % (constraint_label,
                                           table_name,
                                           constraint_name))
                self.errors.append(msg)
            else:
                checked_uniques.append(constraint_name)
                db_index = db_indexes[constraint_name]
                if not db_index.unique:
                    self.errors.append("Index `%s.%s` should be "
                                       "unique." % (table_name,
                                                    constraint_name))
                kw = {}
                ver = float(sqlalchemy.__version__[2:])
                if dialect == 'postgres' and ver >= 8.2 or dialect == 'mysql':
                    # Before 0.8.2 version columns in indexes have a wrong
                    # order for postgres.
                    kw = {'check_order': True}
                self._get_intersection(db_index.columns.keys(),
                                       constraint.columns.keys(),
                                       constraint_label,
                                       table_name,
                                       constraint_name,
                                       **kw)
        return set(checked_uniques)

    def _get_intersection(self, db_obj, model_obj, obj_label, table_name,
                          obj_name="", exclude=None, check_order=False):
        obj_diff = set(db_obj).symmetric_difference(set(model_obj))
        full_obj = set(db_obj).intersection(set(model_obj))
        if exclude is not None:
            obj_diff -= exclude
            full_obj -= exclude
        if obj_diff:
            msg = ("%s in `%s` %s have a difference with "
                   "migrations : (%s)." % (obj_label,
                                           table_name,
                                           obj_name,
                                           ",".join(obj_diff)))
            self.errors.append(msg)
        if check_order and db_obj != model_obj:
            msg = ("%s in `%s.%s` have wrong order: (%s): "
                   "expected (%s)" % (obj_label,
                                      table_name,
                                      obj_name,
                                      ",".join(model_obj),
                                      ",".join(db_obj)))
            self.errors.append(msg)
        return full_obj
