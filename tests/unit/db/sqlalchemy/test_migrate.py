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


from migrate.changeset.constraint import UniqueConstraint
from migrate.changeset.databases import sqlite
import sqlalchemy as sa

from openstack.common.db.sqlalchemy import migration
from openstack.common.db.sqlalchemy import session
from openstack.common.db.sqlalchemy import test_base


def uniques(*constraints):
    """Make a sequence of UniqueConstraint instances easily comparable

        Convert a sequence of UniqueConstraint instances into a set of
        tuples of form (constraint_name, (constraint_columns)) so that
        assertEqual() will be able to compare sets of unique constraints

    """

    return set((uc.name, tuple(uc.columns.keys())) for uc in constraints)


class TestSqliteUniqueConstraints(test_base.DbTestCase):
    def setUp(self):
        super(TestSqliteUniqueConstraints, self).setUp()

        migration.patch_migrate()

        self.helper = sqlite.SQLiteHelper()

        test_table = sa.Table(
            'test_table',
            sa.schema.MetaData(bind=session.get_engine()),
            sa.Column('a', sa.Integer),
            sa.Column('b', sa.String(10)),
            sa.Column('c', sa.Integer),
            sa.UniqueConstraint('a', 'b', name='unique_a_b'),
            sa.UniqueConstraint('b', 'c', name='unique_b_c')
        )
        test_table.create()
        self.addCleanup(test_table.drop)
        # NOTE(rpodolyaka): it's important to use the reflected table here
        #                   rather than original one because this is what
        #                   we actually do in db migrations code
        self.reflected_table = sa.Table(
            'test_table',
            sa.schema.MetaData(bind=session.get_engine()),
            autoload=True
        )

    @test_base.backend_specific('sqlite')
    def test_get_unique_constraints(self):
        table = self.reflected_table

        existing = uniques(*self.helper._get_unique_constraints(table))
        should_be = uniques(
            sa.UniqueConstraint(table.c.a, table.c.b, name='unique_a_b'),
            sa.UniqueConstraint(table.c.b, table.c.c, name='unique_b_c'),
        )
        self.assertEqual(should_be, existing)

    @test_base.backend_specific('sqlite')
    def test_add_unique_constraint(self):
        table = self.reflected_table
        UniqueConstraint(table.c.a, table.c.c, name='unique_a_c').create()

        existing = uniques(*self.helper._get_unique_constraints(table))
        should_be = uniques(
            sa.UniqueConstraint(table.c.a, table.c.b, name='unique_a_b'),
            sa.UniqueConstraint(table.c.b, table.c.c, name='unique_b_c'),
            sa.UniqueConstraint(table.c.a, table.c.c, name='unique_a_c'),
        )
        self.assertEqual(should_be, existing)

    @test_base.backend_specific('sqlite')
    def test_drop_unique_constraint(self):
        table = self.reflected_table
        UniqueConstraint(table.c.a, table.c.b, name='unique_a_b').drop()

        existing = uniques(*self.helper._get_unique_constraints(table))
        should_be = uniques(
            sa.UniqueConstraint(table.c.b, table.c.c, name='unique_b_c'),
        )
        self.assertEqual(should_be, existing)
