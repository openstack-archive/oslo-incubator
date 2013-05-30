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

import re

from migrate.changeset.databases import sqlite
from migrate.changeset import ansisql
from sqlalchemy.schema import UniqueConstraint


def _get_unique_constraints(self, table):
    data = table.metadata.bind.execute(
        """
            SELECT sql
            FROM sqlite_master
            WHERE
                type='table' AND
                name='%(table_name)s'
        """ % {"table_name": table.name}
    ).fetchone()[0]

    UNIQUE_PATTERN = "CONSTRAINT (\w+) UNIQUE \(([^\)]+)\)"
    return [
        UniqueConstraint(
            *[getattr(table.columns, c.strip()) for c in cols.split(",")],
            name=name
        )
        for name, cols in re.findall(UNIQUE_PATTERN, data)
    ]


def recreate_table(self, table, column=None, delta=None, omit_uniques=None):
    table_name = self.preparer.format_table(table)

    # we remove all indexes so as not to have
    # problems during copy and re-create
    for index in table.indexes:
        index.drop()

    # reflect existing unique constraints
    for uc in self._get_unique_constraints(table):
        table.append_constraint(uc)
    # omit given unique constraints when creating a new table if required
    table.constraints = set([
        cons for cons in table.constraints
        if omit_uniques is None or cons.name not in omit_uniques
    ])

    self.append('ALTER TABLE %s RENAME TO migration_tmp' % table_name)
    self.execute()

    insertion_string = self._modify_table(table, column, delta)

    table.create(bind=self.connection)
    self.append(insertion_string % {'table_name': table_name})
    self.execute()
    self.append('DROP TABLE migration_tmp')
    self.execute()


def visit_migrate_unique_constraint(self, *p, **k):
    self.recreate_table(p[0].table, omit_uniques=[p[0].name])


def patch_migrate():
    helper_cls = sqlite.SQLiteHelper
    helper_cls.recreate_table = recreate_table
    helper_cls._get_unique_constraints = _get_unique_constraints

    constraint_cls = sqlite.SQLiteConstraintDropper
    constraint_cls.visit_migrate_unique_constraint = \
        visit_migrate_unique_constraint
    constraint_cls.__bases__ = (ansisql.ANSIColumnDropper,
                                sqlite.SQLiteConstraintGenerator)
