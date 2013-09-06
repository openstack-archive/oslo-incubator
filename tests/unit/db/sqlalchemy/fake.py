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


from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy import ForeignKeyConstraint, Index, types, schema
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.declarative import declarative_base


# Will be used as models state.
BASE = declarative_base()


class CIDR(types.TypeDecorator):
    """An SQLAlchemy type representing a CIDR definition."""

    impl = types.String

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(postgresql.INET())
        else:
            return dialect.type_descriptor(types.String(43))


class _FakeRefTable(object):
    __tablename__ = 'fake_ref_table'
    __table_args__ = {'mysql_engine': 'Innodb'}
    id = Column(Integer, primary_key=True)


class FakeRefTable(BASE, _FakeRefTable):
    pass


class _FakeTable():
    """Base model for fake table.
    For negative tests columns or constraints will be overwriten.
    """
    __tablename__ = 'fake_table'
    __table_args__ = (
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(CIDR)
    col_fk = Column(Integer)
    col_bool = Column(Boolean)


class FakeTable(_FakeTable, BASE):
    pass


BASE_EXTRA_TABLES = declarative_base()


class ExtraTable(BASE_EXTRA_TABLES):
    __tablename__ = 'extra_table'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    id = Column(Integer, primary_key=True)


class FakeTableExtra(BASE_EXTRA_TABLES, _FakeRefTable):
    pass


BASE_INDEXES_DIFF = declarative_base()


class IndexesDiffTable(BASE_INDEXES_DIFF, _FakeTable):
    __table_args__ = (
        # Extra index.
        Index("col_str_idx", "col_str"),
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )


class FakeRefTableIndexesDiff(BASE_INDEXES_DIFF, _FakeRefTable):
    pass


BASE_UNIQ_DIFF = declarative_base()


class UniqDiffTable(BASE_UNIQ_DIFF, _FakeTable):
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        # Wrong name for UniqueConstraint.
        schema.UniqueConstraint("col_fk", "id",
                                name="UNIQ_col_fk0id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )


class FakeRefTableUniqDiff(BASE_UNIQ_DIFF, _FakeRefTable):
    pass


BASE_EXTRA_COLUMN = declarative_base()


class ExtraColumnTable(BASE_EXTRA_COLUMN, _FakeTable):
    __table_args__ = (
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )
    # Extra column.
    col_fk3 = Column(Integer)


class FakeRefTableExtraColumn(BASE_EXTRA_COLUMN, _FakeRefTable):
    pass


BASE_FK_DIFF = declarative_base()


class FKDiffTable(BASE_FK_DIFF, _FakeTable):
    __tablename__ = 'fake_table'
    __table_args__ = (
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        # ForeignKey should be declared for `col_fk` column.
        ForeignKeyConstraint(['col_fk2'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )

    # Extra column.
    col_fk2 = Column(Integer)


class FakeRefTableFKDiff(BASE_FK_DIFF, _FakeRefTable):
    pass


BASE_WRONG_TYPE = declarative_base()


class WrongTypeTable(BASE_WRONG_TYPE, _FakeTable):
    __table_args__ = (
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )

    # Column's type should be CIDR.
    col_cidr = Column(Integer)


class FakeRefTableWrongType(BASE_WRONG_TYPE, _FakeRefTable):
    pass


BASE_WRONG_INDEX_ORDER = declarative_base()


class WrongIndexOrderTypeTable(BASE_WRONG_INDEX_ORDER, _FakeTable):
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        # Wrong columns order in index.
        Index("col_cidr_idx", "col_fk", "col_cidr"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )


class FakeRefTableWrongIndexOrder(BASE_WRONG_INDEX_ORDER, _FakeRefTable):
    pass

BASE_EXTRA_NULLABLE = declarative_base()


class ExtraNullableTable(BASE_EXTRA_NULLABLE, _FakeTable):
    __table_args__ = (
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )
    # Nullable is missing.
    col_str = Column(String(255))


class FakeRefTableExtraNullable(BASE_EXTRA_NULLABLE, _FakeRefTable):
    pass

BASE_WRONG_UNIQ_INDEX = declarative_base()


class WrongUniqIndexTable(BASE_WRONG_UNIQ_INDEX, _FakeTable):
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        # Extra index.
        Index("uniq_fake_table0col_fk0id", "col_fk", "id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )


class FakeRefTableWrongUniqIndex(BASE_WRONG_UNIQ_INDEX, _FakeRefTable):
    pass


BASE_WRONG_UNIQ_NAME = declarative_base()


class WrongUniqNameTable(BASE_WRONG_UNIQ_NAME, _FakeTable):
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        # Wrong name for UniqueKey.
        schema.UniqueConstraint("col_fk", "id",
                                name="fake_table0col_fk0id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id']),
        {'mysql_engine': 'InnoDB'}
    )


class FakeRefTableWrongUniqName(BASE_WRONG_UNIQ_NAME, _FakeRefTable):
    pass
