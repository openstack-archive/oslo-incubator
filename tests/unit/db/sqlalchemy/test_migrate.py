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


import fixtures
from migrate.changeset.constraint import UniqueConstraint
from migrate.changeset.databases import sqlite
from oslo.config import cfg
import sqlalchemy as sa

from openstack.common.db.sqlalchemy import migration
from openstack.common.db.sqlalchemy import session
from tests import utils as test_utils


migration.patch_migrate()


def uniques(*constraints):
    """Make a sequence of UniqueConstraint instances easily comparable

        Convert a sequence of UniqueConstraint instances into a set of
        tuples of form (constraint_name, (constraint_columns)) so that
        assertEquals() will be able to compare sets of unique constraints

    """

    return set((uc.name, tuple(uc.columns.keys())) for uc in constraints)


class SqliteInMemoryFixture(fixtures.Fixture):
    """SQLite in-memory DB recreated for each test case"""

    def __init__(self):
        self.conf = cfg.CONF
        self.conf.import_opt('connection',
                             'openstack.common.db.sqlalchemy.session',
                             group='database')

    def setUp(self):
        super(SqliteInMemoryFixture, self).setUp()

        self.conf.set_default('connection', "sqlite://", group='database')
        self.addCleanup(self.conf.reset)

        engine = session.get_engine()
        self.addCleanup(engine.dispose)


class TestSqliteUniqueConstraints(test_utils.BaseTestCase):
    def setUp(self):
        super(TestSqliteUniqueConstraints, self).setUp()

        self.useFixture(SqliteInMemoryFixture())
        self.helper = sqlite.SQLiteHelper()

        sa.Table(
            'test_table',
            sa.schema.MetaData(bind=session.get_engine()),
            sa.Column('a', sa.Integer),
            sa.Column('b', sa.String(10)),
            sa.Column('c', sa.Integer),
            sa.UniqueConstraint('a', 'b', name='unique_a_b'),
            sa.UniqueConstraint('b', 'c', name='unique_b_c')
        ).create()

        # NOTE(rpodolyaka): it's important to use the reflected table here
        #                   rather than original one because this is what
        #                   we actually do in db migrations code
        self.reflected_table = sa.Table(
            'test_table',
            sa.schema.MetaData(bind=session.get_engine()),
            autoload=True
        )

    def test_get_unique_constraints(self):
        table = self.reflected_table

        existing = uniques(*self.helper._get_unique_constraints(table))
        should_be = uniques(
            sa.UniqueConstraint(table.c.a, table.c.b, name='unique_a_b'),
            sa.UniqueConstraint(table.c.b, table.c.c, name='unique_b_c'),
        )
        self.assertEquals(should_be, existing)

    def test_add_unique_constraint(self):
        table = self.reflected_table
        UniqueConstraint(table.c.a, table.c.c, name='unique_a_c').create()

        existing = uniques(*self.helper._get_unique_constraints(table))
        should_be = uniques(
            sa.UniqueConstraint(table.c.a, table.c.b, name='unique_a_b'),
            sa.UniqueConstraint(table.c.b, table.c.c, name='unique_b_c'),
            sa.UniqueConstraint(table.c.a, table.c.c, name='unique_a_c'),
        )
        self.assertEquals(should_be, existing)

    def test_drop_unique_constraint(self):
        table = self.reflected_table
        UniqueConstraint(table.c.a, table.c.b, name='unique_a_b').drop()

        existing = uniques(*self.helper._get_unique_constraints(table))
        should_be = uniques(
            sa.UniqueConstraint(table.c.b, table.c.c, name='unique_b_c'),
        )
        self.assertEquals(should_be, existing)
