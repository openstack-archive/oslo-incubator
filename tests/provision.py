# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010-2013 OpenStack Foundation
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

"""Provision test environment for specific DB backends"""

import os
import random
import string
import sys

import sqlalchemy

from openstack.common.db.sqlalchemy import test_migrations as tm


SQL_CONNECTION = os.getenv('OS_TEST_DBAPI_ADMIN_CONNECTION', 'sqlite://')


def _gen_credentials(*names):
    """Generate credantials."""
    auth_dict = {}
    for name in names:
        val = ''.join(random.choice(string.lowercase) for i in xrange(10))
        auth_dict[name] = val
    return auth_dict


def _get_engine(uri=SQL_CONNECTION):
    """Engine creation

    By default the uri is SQL_CONNECTION which is admin credantials.
    Call the function without arguments to get admin connection. Admin
    connection required to create temporary user and database for each
    particular test. Othervice use existing connection to recreate connection
    to the temporary database.
    """
    return sqlalchemy.create_engine(uri, poolclass=sqlalchemy.pool.NullPool)


def _execute_sql(engine, sql, driver):
    """Initialize connection, execute sql query and close it."""
    with engine.connect() as conn:
        if driver == 'postgresql':
            conn.connection.set_isolation_level(0)
        for s in sql:
            conn.execute(s)


def create_database(engine):
    """Provide temporary user and database for each particular test."""
    driver = engine.url.drivername

    auth = _gen_credentials('database', 'user', 'passwd')

    sqls = {
        'mysql': [
            'drop database if exists %(database)s;',
            'grant all on %(database)s.* to \'%(user)s\'@\'localhost\''
            ' identified by \'%(passwd)s\';',
            'create database %(database)s;',
        ],
        'postgresql': [
            'drop database if exists %(database)s;',
            'drop user if exists %(user)s;',
            'create user %(user)s with password \'%(passwd)s\';',
            'create database %(database)s owner %(user)s;',
        ]
    }

    if driver == 'sqlite':
        return 'sqlite:////tmp/%s' % auth['database']

    try:
        sql = map(lambda x: x % auth, sqls[driver])
    except KeyError:
        raise ValueError('Unsupported RDBMS %s' % driver)

    _execute_sql(engine, sql, driver)

    params = auth.copy()
    params['backend'] = driver
    return tm._get_connect_string(**params)


def drop_database(engine, current_uri):
    """Drop temporary database and user after each particular test."""
    engine = _get_engine(current_uri)
    admin_engine = _get_engine()
    driver = engine.url.drivername
    auth = {'database': engine.url.database, 'user': engine.url.username}

    if driver == 'sqlite':
        try:
            os.remove(auth['database'])
        except OSError:
            pass
        return

    sqls = {
        'mysql+mysqldb': [
            'drop database if exists %(database)s;',
            'drop user \'%(user)s\'@\'localhost\';',
        ],
        'postgresql+psycopg2': [
            'drop database if exists %(database)s;',
            'drop user if exists %(user)s;',
        ]
    }

    try:
        sql = map(lambda x: x % auth, sqls[driver])
    except KeyError:
        raise ValueError('Unsupported RDBMS %s' % driver)

    _execute_sql(admin_engine, sql, driver)


def main():
    engine = _get_engine()
    command, args = sys.argv[1], sys.argv[2:]
    if command == "create":
        for i in range(int(args[0])):
            print(create_database(engine))
    elif command == "drop":
        for db in args:
            drop_database(engine, db)
    else:
        raise ValueError("Unknown command: %s" % command)


if __name__ == "__main__":
    main()
