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
from sqlalchemy import ForeignKey, Index, types, schema, ForeignKeyConstraint
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

    def process_bind_param(self, value, dialect):
        """Process/Formats the value before insert it into the db."""
        # NOTE(sdague): normalize all the inserts
        return value


class _FakeRefTable():
    __tablename__ = 'fake_ref_table'
    __table_args__ = {'mysql_engine': 'Innodb'}
    id = Column(Integer, primary_key=True)


class FakeRefTable(BASE, _FakeRefTable):
    pass


class FakeTable(BASE):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        ForeignKeyConstraint(['col_fk'], ['fake_ref_table.id'])
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(CIDR)
    col_fk = Column(Integer)
    col_fk2 = Column(Integer)
    col_bool = Column(Boolean)


BASE_EXTRA_TABLES = declarative_base()


class ExtraTable(BASE_EXTRA_TABLES):
    __tablename__ = 'extra_table'
    __table_args__ = {'mysql_engine': 'InnoDB'}
    id = Column(Integer, primary_key=True)


BASE_INDEXES_DIFF = declarative_base()


class IndexesDiffTable(BASE_INDEXES_DIFF):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        Index("col_str_idx", "col_str"),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(CIDR)
    col_fk = Column(Integer, ForeignKey('fake_ref_table.id'))
    col_fk2 = Column(Integer)
    col_bool = Column(Boolean)


BASE_UNIQ_DIFF = declarative_base()


class UniqDiffTable(BASE_UNIQ_DIFF):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="UNIQ_col_fk0id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(CIDR)
    col_fk = Column(Integer, ForeignKey('fake_ref_table.id'))
    col_fk2 = Column(Integer)
    col_bool = Column(Boolean)


BASE_EXTRA_COLUMN = declarative_base()


class ExtraColumnTable(BASE_EXTRA_COLUMN):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(CIDR)
    col_fk = Column(Integer, ForeignKey('fake_ref_table.id'))
    col_fk3 = Column(Integer)
    col_bool = Column(Boolean)


BASE_FK_DIFF = declarative_base()


class FKDiffTable(BASE_FK_DIFF):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(CIDR)
    col_fk2 = Column(Integer, ForeignKey('fake_ref_table.id'))
    col_fk = Column(Integer)
    col_bool = Column(Boolean)


BASE_WRONG_TYPE = declarative_base()


class WrongTypeTable(BASE_WRONG_TYPE):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(Integer)
    col_fk = Column(Integer, ForeignKey('fake_ref_table.id'))
    col_fk2 = Column(Integer)
    col_bool = Column(Boolean)


BASE_WRONG_INDEX_ORDER = declarative_base()


class WrongIndexOrderTypeTable(BASE_WRONG_INDEX_ORDER):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        Index("col_cidr_idx", "col_fk", "col_cidr"),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(CIDR)
    col_fk = Column(Integer, ForeignKey('fake_ref_table.id'))
    col_fk2 = Column(Integer)
    col_bool = Column(Boolean)


BASE_EXTRA_NULLABLE = declarative_base()


class ExtraNullableTable(BASE_EXTRA_NULLABLE):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="uniq_fake_table0col_fk0id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255))
    col_cidr = Column(CIDR)
    col_fk = Column(Integer, ForeignKey('fake_ref_table.id'))
    col_fk2 = Column(Integer)
    col_bool = Column(Boolean)


BASE_WRONG_UNIQ_INDEX = declarative_base()


class WrongUniqIndexTable(BASE_WRONG_UNIQ_INDEX):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        Index("uniq_fake_table0col_fk0id", "col_fk", "id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(CIDR)
    col_fk = Column(Integer, ForeignKey('fake_ref_table.id'))
    col_fk2 = Column(Integer)
    col_bool = Column(Boolean)


BASE_WRONG_UNIQ_NAME = declarative_base()


class WrongUniqNameTable(BASE_WRONG_UNIQ_NAME):
    __tablename__ = 'fake_table'
    __table_args__ = (
        schema.UniqueConstraint("col_str", "col_cidr",
                                name="uniq_fake_table0col_str0col_cidr"),
        schema.UniqueConstraint("col_fk", "id",
                                name="fake_table0col_fk0id"),
        Index("col_cidr_idx", "col_cidr", "col_fk"),
        {'mysql_engine': 'InnoDB'}
    )

    id = Column(Integer, primary_key=True)
    col_str = Column(String(255), nullable=False)
    col_cidr = Column(CIDR)
    col_fk = Column(Integer, ForeignKey('fake_ref_table.id'))
    col_fk2 = Column(Integer)
    col_bool = Column(Boolean)
