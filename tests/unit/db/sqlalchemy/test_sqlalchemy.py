# vim: tabstop=4 shiftwidth=4 softtabstop=4
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

import sqlalchemy
from sqlalchemy import Column, MetaData, Table, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import DateTime, Integer

from openstack.common.db.sqlalchemy import models
from openstack.common.db.sqlalchemy import session
from openstack.common import importutils
from tests import utils as test_utils

MySQLdb = importutils.try_import('MySQLdb')


class TestException(Exception):
    pass


class DbPoolTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(DbPoolTestCase, self).setUp()
        if MySQLdb is None:
            self.skipTest("Required module MySQLdb missing.")
        self.config(sql_dbpool_enable=True)
        self.user_id = 'fake'
        self.project_id = 'fake'

    def test_db_pool_option(self):
        # test that pool options are passed to engine creation
        self.config(sql_idle_timeout=11, sql_max_pool_size=42,
                    sql_max_overflow=5)

        def _create_engine(*args, **kwargs):
            e = test_utils.TestingException("engine")
            e.engine_args = args
            e.engine_kwargs = kwargs
            raise e

        self.stubs.Set(sqlalchemy, 'create_engine', _create_engine)

        sql_connection = 'mysql://user:pass@127.0.0.1/nova'

        try:
            session.create_engine(sql_connection)
            self.fail("no test exception")
        except test_utils.TestingException as e:
            self.assertEqual(sql_connection, e.engine_args[0])
            self.assertEqual(42, e.engine_kwargs['pool_size'])
            self.assertEqual(5, e.engine_kwargs['max_overflow'])
            self.assertEqual(11, e.engine_kwargs['pool_recycle'])

    def test_conn_options(self):
        def fake_connect(**kwargs):
            e = test_utils.TestingException("connect")
            e.conn_args = kwargs
            raise e

        self.stubs.Set(MySQLdb, 'connect', fake_connect)

        sql_connection = 'mysql://user:pass@127.0.0.1/nova'

        try:
            session.create_engine(sql_connection)
            self.fail("no test exception")
        except test_utils.TestingException as e:
            self.assertEqual('pass', e.conn_args['passwd'])
            self.assertEqual('127.0.0.1', e.conn_args['host'])
            self.assertEqual('nova', e.conn_args['db'])
            self.assertEqual('user', e.conn_args['user'])


BASE = declarative_base()
_TABLE_NAME = '__tmp__test__tmp__'


class TmpTable(BASE, models.ModelBase):
    __tablename__ = _TABLE_NAME
    id = Column(Integer, primary_key=True)
    foo = Column(Integer)


class SessionErrorWrapperTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(SessionErrorWrapperTestCase, self).setUp()
        meta = MetaData()
        meta.bind = session.get_engine()
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

    def tearDown(self):
        super(SessionErrorWrapperTestCase, self).tearDown()
        meta = MetaData()
        meta.bind = session.get_engine()
        test_table = Table(_TABLE_NAME, meta, autoload=True)
        test_table.drop()

    def test_flush_wrapper(self):
        tbl = TmpTable()
        tbl.update({'foo': 10})
        tbl.save()

        tbl2 = TmpTable()
        tbl2.update({'foo': 10})
        self.assertRaises(session.DBDuplicateEntry, tbl2.save)

    def test_execute_wrapper(self):
        _session = session.get_session()
        with _session.begin():
            for i in [10, 20]:
                tbl = TmpTable()
                tbl.update({'foo': i})
                tbl.save(session=_session)

            method = _session.query(TmpTable).\
                filter_by(foo=10).\
                update
            self.assertRaises(session.DBDuplicateEntry,
                              method, {'foo': 20})
