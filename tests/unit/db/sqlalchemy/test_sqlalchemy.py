# encoding=UTF8

# Copyright (c) 2012 Rackspace Hosting
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

"""Unit tests for SQLAlchemy specific code."""

import logging

import _mysql_exceptions
import mock
import sqlalchemy
from sqlalchemy import Column, MetaData, Table, UniqueConstraint
from sqlalchemy import DateTime, Integer, String
from sqlalchemy import exc as sqla_exc
from sqlalchemy.exc import DataError
from sqlalchemy.ext.declarative import declarative_base

from openstack.common.db import exception as db_exc
from openstack.common.db.sqlalchemy import models
from openstack.common.db.sqlalchemy import session
from openstack.common.db.sqlalchemy import test_base
from openstack.common import log
from openstack.common import test
from tests.unit import test_log


BASE = declarative_base()
_TABLE_NAME = '__tmp__test__tmp__'


class TmpTable(BASE, models.ModelBase):
    __tablename__ = _TABLE_NAME
    id = Column(Integer, primary_key=True)
    foo = Column(Integer)


class SessionErrorWrapperTestCase(test_base.DbTestCase):
    def setUp(self):
        super(SessionErrorWrapperTestCase, self).setUp()
        meta = MetaData()
        meta.bind = self.engine
        test_table = Table(_TABLE_NAME, meta,
                           Column('id', Integer, primary_key=True,
                                  nullable=False),
                           Column('deleted', Integer, default=0),
                           Column('deleted_at', DateTime),
                           Column('updated_at', DateTime),
                           Column('created_at', DateTime),
                           Column('foo', Integer),
                           UniqueConstraint('foo', name='uniq_foo'))
        test_table.create()
        self.addCleanup(test_table.drop)

    def test_flush_wrapper(self):
        _session = self.sessionmaker()

        tbl = TmpTable()
        tbl.update({'foo': 10})
        tbl.save(_session)

        tbl2 = TmpTable()
        tbl2.update({'foo': 10})
        self.assertRaises(db_exc.DBDuplicateEntry, tbl2.save, _session)

    def test_execute_wrapper(self):
        _session = self.sessionmaker()
        with _session.begin():
            for i in [10, 20]:
                tbl = TmpTable()
                tbl.update({'foo': i})
                tbl.save(session=_session)

            method = _session.query(TmpTable).\
                filter_by(foo=10).\
                update
            self.assertRaises(db_exc.DBDuplicateEntry,
                              method, {'foo': 20})

    def test_ibm_db_sa_raise_if_duplicate_entry_error_duplicate(self):
        # Tests that the session._raise_if_duplicate_entry_error method
        # translates the duplicate entry integrity error for the DB2 engine.
        statement = ('INSERT INTO key_pairs (created_at, updated_at, '
                     'deleted_at, deleted, name, user_id, fingerprint) VALUES '
                     '(?, ?, ?, ?, ?, ?, ?)')
        params = ['20130918001123627099', None, None, 0, 'keypair-23474772',
                  '974a7c9ffde6419f9811fcf94a917f47',
                  '7d:2c:58:7f:97:66:14:3f:27:c7:09:3c:26:95:66:4d']
        orig = sqla_exc.SQLAlchemyError(
            'SQL0803N  One or more values in the INSERT statement, UPDATE '
            'statement, or foreign key update caused by a DELETE statement are'
            ' not valid because the primary key, unique constraint or unique '
            'index identified by "2" constrains table "NOVA.KEY_PAIRS" from '
            'having duplicate values for the index key.')
        integrity_error = sqla_exc.IntegrityError(statement, params, orig)
        self.assertRaises(db_exc.DBDuplicateEntry,
                          session._raise_if_duplicate_entry_error,
                          integrity_error, 'ibm_db_sa')

    def test_ibm_db_sa_raise_if_duplicate_entry_error_no_match(self):
        # Tests that the session._raise_if_duplicate_entry_error method
        # does not raise a DBDuplicateEntry exception when it's not a matching
        # integrity error.
        statement = ('ALTER TABLE instance_types ADD CONSTRAINT '
                     'uniq_name_x_deleted UNIQUE (name, deleted)')
        params = None
        orig = sqla_exc.SQLAlchemyError(
            'SQL0542N  The column named "NAME" cannot be a column of a '
            'primary key or unique key constraint because it can contain null '
            'values.')
        integrity_error = sqla_exc.IntegrityError(statement, params, orig)
        session._raise_if_duplicate_entry_error(integrity_error, 'ibm_db_sa')


_REGEXP_TABLE_NAME = _TABLE_NAME + "regexp"


class RegexpTable(BASE, models.ModelBase):
    __tablename__ = _REGEXP_TABLE_NAME
    id = Column(Integer, primary_key=True)
    bar = Column(String(255))


class RegexpFilterTestCase(test_base.DbTestCase):

    def setUp(self):
        super(RegexpFilterTestCase, self).setUp()
        meta = MetaData()
        meta.bind = self.engine
        test_table = Table(_REGEXP_TABLE_NAME, meta,
                           Column('id', Integer, primary_key=True,
                                  nullable=False),
                           Column('bar', String(255)))
        test_table.create()
        self.addCleanup(test_table.drop)

    def _test_regexp_filter(self, regexp, expected):
        _session = self.sessionmaker()
        with _session.begin():
            for i in ['10', '20', u'♥']:
                tbl = RegexpTable()
                tbl.update({'bar': i})
                tbl.save(session=_session)

        regexp_op = RegexpTable.bar.op('REGEXP')(regexp)
        result = _session.query(RegexpTable).filter(regexp_op).all()
        self.assertEqual([r.bar for r in result], expected)

    def test_regexp_filter(self):
        self._test_regexp_filter('10', ['10'])

    def test_regexp_filter_nomatch(self):
        self._test_regexp_filter('11', [])

    def test_regexp_filter_unicode(self):
        self._test_regexp_filter(u'♥', [u'♥'])

    def test_regexp_filter_unicode_nomatch(self):
        self._test_regexp_filter(u'♦', [])


class FakeDBAPIConnection():
    def cursor(self):
        return FakeCursor()


class FakeCursor():
    def execute(self, sql):
        pass


class FakeConnectionProxy():
    pass


class FakeConnectionRec():
    pass


class OperationalError(Exception):
    pass


class ProgrammingError(Exception):
    pass


class FakeDB2Engine(object):

    class Dialect():

        def is_disconnect(self, e, *args):
            expected_error = ('SQL30081N: DB2 Server connection is no longer '
                              'active')
            return (str(e) == expected_error)

    dialect = Dialect()
    name = 'ibm_db_sa'

    def dispose(self):
        pass


class TestDBDisconnected(test.BaseTestCase):

    def _test_ping_listener_disconnected(self, connection):
        engine_args = {
            'pool_recycle': 3600,
            'echo': False,
            'convert_unicode': True}

        engine = sqlalchemy.create_engine(connection, **engine_args)
        with mock.patch.object(engine, 'dispose') as dispose_mock:
            self.assertRaises(sqlalchemy.exc.DisconnectionError,
                              session._ping_listener, engine,
                              FakeDBAPIConnection(), FakeConnectionRec(),
                              FakeConnectionProxy())
            dispose_mock.assert_called_once_with()

    def test_mysql_ping_listener_disconnected(self):
        def fake_execute(sql):
            raise _mysql_exceptions.OperationalError(self.mysql_error,
                                                     ('MySQL server has '
                                                      'gone away'))
        with mock.patch.object(FakeCursor, 'execute',
                               side_effect=fake_execute):
            connection = 'mysql://root:password@fakehost/fakedb?charset=utf8'
            for code in [2006, 2013, 2014, 2045, 2055]:
                self.mysql_error = code
                self._test_ping_listener_disconnected(connection)

    def test_db2_ping_listener_disconnected(self):

        def fake_execute(sql):
            raise OperationalError('SQL30081N: DB2 Server '
                                   'connection is no longer active')
        with mock.patch.object(FakeCursor, 'execute',
                               side_effect=fake_execute):
            # TODO(dperaza): Need a fake engine for db2 since ibm_db_sa is not
            # in global requirements. Change this code to use real IBM db2
            # engine as soon as ibm_db_sa is included in global-requirements
            # under openstack/requirements project.
            fake_create_engine = lambda *args, **kargs: FakeDB2Engine()
            with mock.patch.object(sqlalchemy, 'create_engine',
                                   side_effect=fake_create_engine):
                connection = ('ibm_db_sa://db2inst1:openstack@fakehost:50000'
                              '/fakedab')
                self._test_ping_listener_disconnected(connection)


class MySQLModeTestCase(test_base.MySQLOpportunisticTestCase):

    def __init__(self, *args, **kwargs):
        super(MySQLModeTestCase, self).__init__(*args, **kwargs)
        # By default, run in empty SQL mode.
        # Subclasses override this with specific modes.
        self.mysql_mode = ''

    def setUp(self):
        super(MySQLModeTestCase, self).setUp()

        self.engine = session.create_engine(self.engine.url,
                                            mysql_sql_mode=self.mysql_mode)
        self.connection = self.engine.connect()

        meta = MetaData()
        meta.bind = self.engine
        self.test_table = Table(_TABLE_NAME + "mode", meta,
                                Column('id', Integer, primary_key=True),
                                Column('bar', String(255)))
        self.test_table.create()

        self.addCleanup(self.test_table.drop)
        self.addCleanup(self.connection.close)

    def _test_string_too_long(self, value):
        with self.connection.begin():
            self.connection.execute(self.test_table.insert(),
                                    bar=value)
            result = self.connection.execute(self.test_table.select())
            return result.fetchone()['bar']

    def test_string_too_long(self):
        value = 'a' * 512
        # String is too long.
        # With no SQL mode set, this gets truncated.
        self.assertNotEqual(value,
                            self._test_string_too_long(value))


class MySQLStrictAllTablesModeTestCase(MySQLModeTestCase):
    "Test data integrity enforcement in MySQL STRICT_ALL_TABLES mode."

    def __init__(self, *args, **kwargs):
        super(MySQLStrictAllTablesModeTestCase, self).__init__(*args, **kwargs)
        self.mysql_mode = 'STRICT_ALL_TABLES'

    def test_string_too_long(self):
        value = 'a' * 512
        # String is too long.
        # With STRICT_ALL_TABLES or TRADITIONAL mode set, this is an error.
        self.assertRaises(DataError,
                          self._test_string_too_long, value)


class MySQLTraditionalModeTestCase(MySQLStrictAllTablesModeTestCase):
    """Test data integrity enforcement in MySQL TRADITIONAL mode.
    Since TRADITIONAL includes STRICT_ALL_TABLES, this inherits all
    STRICT_ALL_TABLES mode tests.
    """

    def __init__(self, *args, **kwargs):
        super(MySQLTraditionalModeTestCase, self).__init__(*args, **kwargs)
        self.mysql_mode = 'TRADITIONAL'


class EngineFacadeTestCase(test.BaseTestCase):
    def setUp(self):
        super(EngineFacadeTestCase, self).setUp()

        self.facade = session.EngineFacade('sqlite://')

    def test_get_engine(self):
        eng1 = self.facade.get_engine()
        eng2 = self.facade.get_engine()

        self.assertIs(eng1, eng2)

    def test_get_session(self):
        ses1 = self.facade.get_session()
        ses2 = self.facade.get_session()

        self.assertIsNot(ses1, ses2)

    def test_get_session_arguments_override_default_settings(self):
        ses = self.facade.get_session(autocommit=False, expire_on_commit=True)

        self.assertFalse(ses.autocommit)
        self.assertTrue(ses.expire_on_commit)

    @mock.patch('openstack.common.db.sqlalchemy.session.get_maker')
    @mock.patch('openstack.common.db.sqlalchemy.session.create_engine')
    def test_creation_from_config(self, create_engine, get_maker):
        conf = mock.MagicMock()
        conf.database.items.return_value = [
            ('connection_debug', 100),
            ('max_pool_size', 10),
            ('mysql_sql_mode', 'TRADITIONAL'),
        ]

        session.EngineFacade.from_config('sqlite:///:memory:', conf,
                                         autocommit=False,
                                         expire_on_commit=True)

        conf.database.items.assert_called_once_with()
        create_engine.assert_called_once_with(
            sql_connection='sqlite:///:memory:',
            connection_debug=100,
            max_pool_size=10,
            mysql_sql_mode='TRADITIONAL',
            sqlite_fk=False,
            idle_timeout=mock.ANY,
            retry_interval=mock.ANY,
            max_retries=mock.ANY,
            max_overflow=mock.ANY,
            connection_trace=mock.ANY,
            sqlite_synchronous=mock.ANY,
            pool_timeout=mock.ANY,
        )
        get_maker.assert_called_once_with(engine=create_engine(),
                                          autocommit=False,
                                          expire_on_commit=True)


class MysqlSetCallbackTest(test_log.LogTestBase):

    class FakeCursor(object):
        def __init__(self, execs):
            self._execs = execs

        def execute(self, sql, arg):
            self._execs.append(sql % arg)

    class FakeDbapiCon(object):
        def __init__(self, execs):
            self._execs = execs

        def cursor(self):
            return MysqlSetCallbackTest.FakeCursor(self._execs)

    class FakeResultSet(object):
        def __init__(self, realmode):
            self._realmode = realmode

        def fetchone(self):
            return ['ignored', self._realmode]

    class FakeEngine(object):
        def __init__(self, realmode=None):
            self._cbs = {}
            self._execs = []
            self._realmode = realmode

        def set_callback(self, name, cb):
            self._cbs[name] = cb

        def execute(self, sql):
            cb = self._cbs.get('checkout', lambda *x, **y: None)
            dbapi_con = MysqlSetCallbackTest.FakeDbapiCon(self._execs)
            connection_rec = None  # Not used.
            connection_proxy = None  # Not used.
            cb(dbapi_con, connection_rec, connection_proxy)
            self._execs.append(sql)
            return MysqlSetCallbackTest.FakeResultSet(self._realmode)

    def stub_listen(engine, name, cb):
        engine.set_callback(name, cb)

    @mock.patch.object(sqlalchemy.event, 'listen', side_effect=stub_listen)
    def _call_set_callback(self, listen_mock, sql_mode=None, realmode=None):
        engine = self.FakeEngine(realmode=realmode)

        logger = log.getLogger('openstack.common.db.sqlalchemy.session')
        self._set_log_level_with_cleanup(logger, logging.DEBUG)
        self._add_handler_with_cleanup(logger)

        session._mysql_set_mode_callback(engine, sql_mode=sql_mode)
        return engine

    def test_set_mode_traditional(self):
        # If _mysql_set_mode_callback is called with an sql_mode, then the SQL
        # mode is set on the connection.

        engine = self._call_set_callback(sql_mode='TRADITIONAL')

        exp_calls = [
            "SET SESSION sql_mode = ['TRADITIONAL']",
            "SHOW VARIABLES LIKE 'sql_mode'"
        ]
        self.assertEqual(exp_calls, engine._execs)

    def test_set_mode_ansi(self):
        # If _mysql_set_mode_callback is called with an sql_mode, then the SQL
        # mode is set on the connection.

        engine = self._call_set_callback(sql_mode='ANSI')

        exp_calls = [
            "SET SESSION sql_mode = ['ANSI']",
            "SHOW VARIABLES LIKE 'sql_mode'"
        ]
        self.assertEqual(exp_calls, engine._execs)

    def test_set_mode_no_mode(self):
        # If _mysql_set_mode_callback is called with sql_mode=None, then
        # the SQL mode is NOT set on the connection.

        engine = self._call_set_callback()

        exp_calls = [
            "SHOW VARIABLES LIKE 'sql_mode'"
        ]
        self.assertEqual(exp_calls, engine._execs)

    def test_fail_detect_mode(self):
        # If "SHOW VARIABLES LIKE 'sql_mode'" results in no row, then
        # we get a log indicating can't detect the mode.

        self._call_set_callback()

        self.assertIn('Unable to detect effective SQL mode',
                      self.stream.getvalue())

    def test_logs_real_mode(self):
        # If "SHOW VARIABLES LIKE 'sql_mode'" results in a value, then
        # we get a log with the value.

        self._call_set_callback(realmode='SOMETHING')

        self.assertIn('MySQL server mode set to SOMETHING',
                      self.stream.getvalue())

    def test_warning_when_not_traditional(self):
        # If "SHOW VARIABLES LIKE 'sql_mode'" results in a value that doesn't
        # include 'TRADITIONAL', then a warning is logged.

        self._call_set_callback(realmode='NOT_TRADIT')

        self.assertIn("consider enabling TRADITIONAL or STRICT_ALL_TABLES",
                      self.stream.getvalue())

    def test_no_warning_when_traditional(self):
        # If "SHOW VARIABLES LIKE 'sql_mode'" results in a value that includes
        # 'TRADITIONAL', then no warning is logged.

        self._call_set_callback(realmode='TRADITIONAL')

        self.assertNotIn("consider enabling TRADITIONAL or STRICT_ALL_TABLES",
                         self.stream.getvalue())

    def test_no_warning_when_strict_all_tables(self):
        # If "SHOW VARIABLES LIKE 'sql_mode'" results in a value that includes
        # 'STRICT_ALL_TABLES', then no warning is logged.

        self._call_set_callback(realmode='STRICT_ALL_TABLES')

        self.assertNotIn("consider enabling TRADITIONAL or STRICT_ALL_TABLES",
                         self.stream.getvalue())
