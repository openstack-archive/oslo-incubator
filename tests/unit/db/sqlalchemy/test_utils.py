# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 Boris Pavlovic (boris@pavlovic.me).
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

from sqlalchemy.dialects import mysql
from sqlalchemy import Boolean, Index, Integer, DateTime, String
from sqlalchemy import MetaData, Table, Column
from sqlalchemy.engine import reflection
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.sql import select
from sqlalchemy.types import UserDefinedType, NullType

from openstack.common.db.sqlalchemy import utils
from openstack.common import exception
import test_migrations

_SHADOW_TABLE_PREFIX = "shadow_"


class CustomType(UserDefinedType):
    """Dummy column type for testing unsupported types."""
    def get_col_spec(self):
        return "CustomType"


class TestMigrationUtils(test_migrations.BaseMigrationTestCase):
    """Class for testing utils that are used in db migrations."""

    def _populate_db_for_drop_duplicate_entries(self, engine, meta,
                                                table_name):
        values = [
            {'id': 11, 'a': 3, 'b': 10, 'c': 'abcdef'},
            {'id': 12, 'a': 5, 'b': 10, 'c': 'abcdef'},
            {'id': 13, 'a': 6, 'b': 10, 'c': 'abcdef'},
            {'id': 14, 'a': 7, 'b': 10, 'c': 'abcdef'},
            {'id': 21, 'a': 1, 'b': 20, 'c': 'aa'},
            {'id': 31, 'a': 1, 'b': 20, 'c': 'bb'},
            {'id': 41, 'a': 1, 'b': 30, 'c': 'aef'},
            {'id': 42, 'a': 2, 'b': 30, 'c': 'aef'},
            {'id': 43, 'a': 3, 'b': 30, 'c': 'aef'}
        ]

        test_table = Table(table_name, meta,
                           Column('id', Integer, primary_key=True,
                                  nullable=False),
                           Column('a', Integer),
                           Column('b', Integer),
                           Column('c', String(255)),
                           Column('deleted', Integer, default=0),
                           Column('deleted_at', DateTime),
                           Column('updated_at', DateTime))

        test_table.create()
        engine.execute(test_table.insert(), values)
        return test_table, values

    def test_drop_old_duplicate_entries_from_table(self):
        table_name = "__test_tmp_table__"

        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            test_table, values = self._populate_db_for_drop_duplicate_entries(
                engine, meta, table_name)
            utils.drop_old_duplicate_entries_from_table(
                engine, table_name, False, 'b', 'c')

            uniq_values = set()
            expected_ids = []
            for value in sorted(values, key=lambda x: x['id'], reverse=True):
                uniq_value = (('b', value['b']), ('c', value['c']))
                if uniq_value in uniq_values:
                    continue
                uniq_values.add(uniq_value)
                expected_ids.append(value['id'])

            real_ids = [row[0] for row in
                        engine.execute(select([test_table.c.id])).fetchall()]

            self.assertEqual(len(real_ids), len(expected_ids))
            for id_ in expected_ids:
                self.assertTrue(id_ in real_ids)

    def test_drop_old_duplicate_entries_from_table_soft_delete(self):
        table_name = "__test_tmp_table__"

        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table, values = self._populate_db_for_drop_duplicate_entries(
                engine, meta, table_name)
            utils.drop_old_duplicate_entries_from_table(engine, table_name,
                                                        True, 'b', 'c')
            uniq_values = set()
            expected_values = []
            soft_deleted_values = []

            for value in sorted(values, key=lambda x: x['id'], reverse=True):
                uniq_value = (('b', value['b']), ('c', value['c']))
                if uniq_value in uniq_values:
                    soft_deleted_values.append(value)
                    continue
                uniq_values.add(uniq_value)
                expected_values.append(value)

            base_select = table.select()

            rows_select = base_select.where(table.c.deleted != table.c.id)
            row_ids = [row['id'] for row in
                       engine.execute(rows_select).fetchall()]
            self.assertEqual(len(row_ids), len(expected_values))
            for value in expected_values:
                self.assertTrue(value['id'] in row_ids)

            deleted_rows_select = base_select.where(
                table.c.deleted == table.c.id)
            deleted_rows_ids = [row['id'] for row in
                                engine.execute(deleted_rows_select).fetchall()]
            self.assertEqual(len(deleted_rows_ids),
                             len(values) - len(row_ids))
            for value in soft_deleted_values:
                self.assertTrue(value['id'] in deleted_rows_ids)

    def test_check_shadow_table(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine

            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('a', Integer),
                          Column('c', String(256)))
            table.create()

            #check missing shadow table
            self.assertRaises(NoSuchTableError,
                              utils.check_shadow_table, engine, table_name)

            shadow_table = Table(_SHADOW_TABLE_PREFIX + table_name, meta,
                                 Column('id', Integer),
                                 Column('a', Integer))
            shadow_table.create()

            # check missing column
            self.assertRaises(exception.OpenstackException,
                              utils.check_shadow_table, engine, table_name)

            # check when all is ok
            c = Column('c', String(256))
            shadow_table.create_column(c)
            self.assertTrue(utils.check_shadow_table(engine, table_name))

            # check extra column
            d = Column('d', Integer)
            shadow_table.create_column(d)
            self.assertRaises(exception.OpenstackException,
                              utils.check_shadow_table, engine, table_name)

    def test_check_shadow_table_different_types(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine

            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('a', Integer))
            table.create()

            shadow_table = Table(_SHADOW_TABLE_PREFIX + table_name, meta,
                                 Column('id', Integer, primary_key=True),
                                 Column('a', String(256)))
            shadow_table.create()
            self.assertRaises(exception.OpenstackException,
                              utils.check_shadow_table, engine, table_name)

    def test_check_shadow_table_with_unsupported_type(self):
        table_name = 'abc'
        engine = self.engines['sqlite']
        meta = MetaData(bind=engine)

        table = Table(table_name, meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', Integer),
                      Column('c', CustomType))
        table.create()

        shadow_table = Table(_SHADOW_TABLE_PREFIX + table_name, meta,
                             Column('id', Integer, primary_key=True),
                             Column('a', Integer),
                             Column('c', CustomType))
        shadow_table.create()
        self.assertTrue(utils.check_shadow_table(engine, table_name))

    def test_create_shadow_table_by_table_instance(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('a', Integer),
                          Column('b', String(256)))
            table.create()
            utils.create_shadow_table(engine, table=table)
            self.assertTrue(utils.check_shadow_table(engine, table_name))

    def test_create_shadow_table_by_name(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine

            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('a', Integer),
                          Column('b', String(256)))
            table.create()
            utils.create_shadow_table(engine, table_name=table_name)
            self.assertTrue(utils.check_shadow_table(engine, table_name))

    def test_create_shadow_table_not_supported_type(self):
        table_name = 'abc'
        engine = self.engines['sqlite']
        meta = MetaData()
        meta.bind = engine
        table = Table(table_name, meta,
                      Column('id', Integer, primary_key=True),
                      Column('a', CustomType))
        table.create()
        self.assertRaises(exception.OpenstackException,
                          utils.create_shadow_table,
                          engine, table_name=table_name)

        utils.create_shadow_table(engine, table_name=table_name,
                                  a=Column('a', CustomType()))
        self.assertTrue(utils.check_shadow_table(engine, table_name))

    def test_create_shadow_both_table_and_table_name_are_none(self):
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            self.assertRaises(exception.OpenstackException,
                              utils.create_shadow_table, engine)

    def test_create_shadow_both_table_and_table_name_are_specified(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('a', Integer))
            table.create()
            self.assertRaises(exception.OpenstackException,
                              utils.create_shadow_table,
                              engine, table=table, table_name=table_name)

    def test_create_duplicate_shadow_table(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('a', Integer))
            table.create()
            utils.create_shadow_table(engine, table_name=table_name)
            self.assertRaises(exception.ShadowTableExists,
                              utils.create_shadow_table,
                              engine, table_name=table_name)

    def test_change_deleted_column_type_doesnt_drop_index(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData(bind=engine)

            indexes = {
                'idx_a_deleted': ['a', 'deleted'],
                'idx_b_deleted': ['b', 'deleted'],
                'idx_a': ['a']
            }

            index_instances = [Index(name, *columns)
                               for name, columns in indexes.iteritems()]

            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('a', String(255)),
                          Column('b', String(255)),
                          Column('deleted', Boolean),
                          *index_instances)
            table.create()
            utils.change_deleted_column_type_to_id_type(engine, table_name)
            utils.change_deleted_column_type_to_boolean(engine, table_name)

            insp = reflection.Inspector.from_engine(engine)
            real_indexes = insp.get_indexes(table_name)
            self.assertEqual(len(real_indexes), 3)
            for index in real_indexes:
                name = index['name']
                self.assertIn(name, indexes)
                self.assertEqual(set(index['column_names']),
                                 set(indexes[name]))

    def test_change_deleted_column_type_to_id_type_integer(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('deleted', Boolean))
            table.create()
            utils.change_deleted_column_type_to_id_type(engine, table_name)

            table = utils.get_table(engine, table_name)
            self.assertTrue(isinstance(table.c.deleted.type, Integer))

    def test_change_deleted_column_type_to_id_type_string(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table = Table(table_name, meta,
                          Column('id', String(255), primary_key=True),
                          Column('deleted', Boolean))
            table.create()
            utils.change_deleted_column_type_to_id_type(engine, table_name)

            table = utils.get_table(engine, table_name)
            self.assertTrue(isinstance(table.c.deleted.type, String))

    def test_change_deleted_column_type_to_id_type_custom(self):
        table_name = 'abc'
        engine = self.engines['sqlite']
        meta = MetaData()
        meta.bind = engine
        table = Table(table_name, meta,
                      Column('id', Integer, primary_key=True),
                      Column('foo', CustomType),
                      Column('deleted', Boolean))
        table.create()

        self.assertRaises(exception.OpenstackException,
                          utils.change_deleted_column_type_to_id_type,
                          engine, table_name)

        fooColumn = Column('foo', CustomType())
        utils.change_deleted_column_type_to_id_type(engine, table_name,
                                                    foo=fooColumn)

        table = utils.get_table(engine, table_name)
        # NOTE(boris-42): There is no way to check has foo type CustomType.
        #                 but sqlalchemy will set it to NullType.
        self.assertTrue(isinstance(table.c.foo.type, NullType))
        self.assertTrue(isinstance(table.c.deleted.type, Integer))

    def test_change_deleted_column_type_to_boolean(self):
        table_name = 'abc'
        for key, engine in self.engines.items():
            meta = MetaData()
            meta.bind = engine
            table = Table(table_name, meta,
                          Column('id', Integer, primary_key=True),
                          Column('deleted', Integer))
            table.create()

            utils.change_deleted_column_type_to_boolean(engine, table_name)

            table = utils.get_table(engine, table_name)
            expected_type = Boolean if key != "mysql" else mysql.TINYINT
            self.assertTrue(isinstance(table.c.deleted.type, expected_type))

    def test_change_deleted_column_type_to_boolean_type_custom(self):
        table_name = 'abc'
        engine = self.engines['sqlite']
        meta = MetaData()
        meta.bind = engine
        table = Table(table_name, meta,
                      Column('id', Integer, primary_key=True),
                      Column('foo', CustomType),
                      Column('deleted', Integer))
        table.create()

        self.assertRaises(exception.OpenstackException,
                          utils.change_deleted_column_type_to_boolean,
                          engine, table_name)

        fooColumn = Column('foo', CustomType())
        utils.change_deleted_column_type_to_boolean(engine, table_name,
                                                    foo=fooColumn)

        table = utils.get_table(engine, table_name)
        # NOTE(boris-42): There is no way to check has foo type CustomType.
        #                 but sqlalchemy will set it to NullType.
        self.assertTrue(isinstance(table.c.foo.type, NullType))
        self.assertTrue(isinstance(table.c.deleted.type, Boolean))
