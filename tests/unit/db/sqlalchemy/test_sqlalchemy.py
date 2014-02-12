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

import _mysql_exceptions
import mock
import sqlalchemy
from sqlalchemy import Column, MetaData, Table, UniqueConstraint
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.engine import reflection
from sqlalchemy.exc import DataError
from sqlalchemy.ext.declarative import declarative_base

from openstack.common.db import exception as db_exc
from openstack.common.db.sqlalchemy import models
from openstack.common.db.sqlalchemy import session
from openstack.common.db.sqlalchemy import test_base
from openstack.common import test


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


class TestDBDisconnected(test.BaseTestCase):

    def _test_ping_listener_disconnected(self, connection):
        engine_args = {
            'pool_recycle': 3600,
            'echo': False,
            'convert_unicode': True}

        engine = sqlalchemy.create_engine(connection, **engine_args)

        self.assertRaises(sqlalchemy.exc.DisconnectionError,
                          session._ping_listener, engine,
                          FakeDBAPIConnection(), FakeConnectionRec(),
                          FakeConnectionProxy())

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


class MySQLTraditionalModeTestCase(test_base.MySQLOpportunisticTestCase):

    def setUp(self):
        super(MySQLTraditionalModeTestCase, self).setUp()

        self.engine = session.create_engine(self.engine.url,
                                            mysql_traditional_mode=True)
        self.connection = self.engine.connect()

        meta = MetaData()
        meta.bind = self.engine
        self.test_table = Table(_TABLE_NAME + "mode", meta,
                                Column('id', Integer, primary_key=True),
                                Column('bar', String(255)))
        self.test_table.create()

        self.addCleanup(self.test_table.drop)
        self.addCleanup(self.connection.close)

    def test_string_too_long(self):
        with self.connection.begin():
            self.assertRaises(DataError, self.connection.execute,
                              self.test_table.insert(), bar='a' * 512)


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


class TestSchemaNamingConventions(test_base.DbTestCase):
    def setUp(self):
        super(TestSchemaNamingConventions, self).setUp()
        self.meta = MetaData()
        self.meta.bind = self.engine
        self.inspector = reflection.Inspector.from_engine(self.meta.bind)

        if not hasattr(self.inspector, 'get_unique_constraints'):
            self.skipTest("Class Inspector doesn't support method "
                          "'get_unique_constraints' in this library version")

    def test_creating_constraint_with_wrong_name_with_force(self):
        session.apply_naming_conventions(force=True)
        test_table = Table(_TABLE_NAME, self.meta,
                           Column('id', Integer, primary_key=True),
                           Column('some_column', Integer),
                           Column('foo', Integer),
                           UniqueConstraint('foo', name='wrong_name'))
        test_table.create()
        self.addCleanup(test_table.drop)

        constraints = self.inspector.get_unique_constraints(_TABLE_NAME)
        self.assertEqual(1, len(constraints))
        self.assertEqual('uniq___tmp__test__tmp__0foo', constraints[0]['name'])

    def test_creating_constraint_without_any_name(self):
        session.apply_naming_conventions(force=False)
        test_table = Table(_TABLE_NAME, self.meta,
                           Column('id', Integer, primary_key=True),
                           Column('some_column', Integer),
                           Column('foo', Integer),
                           UniqueConstraint('some_column'),
                           UniqueConstraint('foo'))
        test_table.create()
        self.addCleanup(test_table.drop)

        constraints = self.inspector.get_unique_constraints(_TABLE_NAME)
        constraints_names = [constraint['name'] for constraint in constraints]
        self.assertEqual(2, len(constraints_names))
        self.assertTrue('uniq___tmp__test__tmp__0some_column' in
                        constraints_names)
        self.assertTrue('uniq___tmp__test__tmp__0foo' in constraints_names)

    def test_creating_constraint_with_wrong_name(self):
        session.apply_naming_conventions(force=False)
        test_table = Table(_TABLE_NAME, self.meta,
                           Column('id', Integer, primary_key=True),
                           Column('some_column', Integer),
                           Column('foo', Integer),
                           UniqueConstraint('foo', name='wrong_name'))
        test_table.create()
        self.addCleanup(test_table.drop)

        constraints = self.inspector.get_unique_constraints(_TABLE_NAME)
        self.assertEqual(1, len(constraints))
        self.assertEqual('wrong_name', constraints[0]['name'])
