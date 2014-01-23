#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

import os

from oslo.config import cfg

from openstack.common.db.sqlalchemy import session


sqlite_db_opts = [
    cfg.StrOpt('sqlite_db',
               default='oslo.sqlite',
               help='The file name to use with SQLite'),
    cfg.BoolOpt('sqlite_synchronous',
                default=True,
                help='If True, SQLite uses synchronous mode'),
]

database_opts = [
    cfg.StrOpt('backend',
               default='sqlalchemy',
               deprecated_name='db_backend',
               deprecated_group='DEFAULT',
               help='The backend to use for db'),
    cfg.StrOpt('connection',
               default='sqlite:///' +
                       os.path.abspath(os.path.join(os.path.dirname(__file__),
                       '../', '$sqlite_db')),
               help='The SQLAlchemy connection string used to connect to the '
                    'database',
               secret=True,
               deprecated_opts=[cfg.DeprecatedOpt('sql_connection',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_connection',
                                                  group='DATABASE'),
                                cfg.DeprecatedOpt('connection',
                                                  group='sql'), ]),
    cfg.StrOpt('slave_connection',
               default='',
               secret=True,
               help='The SQLAlchemy connection string used to connect to the '
                    'slave database'),
    cfg.IntOpt('idle_timeout',
               default=3600,
               deprecated_opts=[cfg.DeprecatedOpt('sql_idle_timeout',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_idle_timeout',
                                                  group='DATABASE'),
                                cfg.DeprecatedOpt('idle_timeout',
                                                  group='sql')],
               help='Timeout before idle sql connections are reaped'),
    cfg.IntOpt('min_pool_size',
               default=1,
               deprecated_opts=[cfg.DeprecatedOpt('sql_min_pool_size',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_min_pool_size',
                                                  group='DATABASE')],
               help='Minimum number of SQL connections to keep open in a '
                    'pool'),
    cfg.IntOpt('max_pool_size',
               default=None,
               deprecated_opts=[cfg.DeprecatedOpt('sql_max_pool_size',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_max_pool_size',
                                                  group='DATABASE')],
               help='Maximum number of SQL connections to keep open in a '
                    'pool'),
    cfg.IntOpt('max_retries',
               default=10,
               deprecated_opts=[cfg.DeprecatedOpt('sql_max_retries',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sql_max_retries',
                                                  group='DATABASE')],
               help='Maximum db connection retries during startup. '
                    '(setting -1 implies an infinite retry count)'),
    cfg.IntOpt('retry_interval',
               default=10,
               deprecated_opts=[cfg.DeprecatedOpt('sql_retry_interval',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('reconnect_interval',
                                                  group='DATABASE')],
               help='Interval between retries of opening a sql connection'),
    cfg.IntOpt('max_overflow',
               default=None,
               deprecated_opts=[cfg.DeprecatedOpt('sql_max_overflow',
                                                  group='DEFAULT'),
                                cfg.DeprecatedOpt('sqlalchemy_max_overflow',
                                                  group='DATABASE')],
               help='If set, use this value for max_overflow with sqlalchemy'),
    cfg.IntOpt('connection_debug',
               default=0,
               deprecated_opts=[cfg.DeprecatedOpt('sql_connection_debug',
                                                  group='DEFAULT')],
               help='Verbosity of SQL debugging information. 0=None, '
                    '100=Everything'),
    cfg.BoolOpt('connection_trace',
                default=False,
                deprecated_opts=[cfg.DeprecatedOpt('sql_connection_trace',
                                                   group='DEFAULT')],
                help='Add python stack traces to SQL as comment strings'),
    cfg.IntOpt('pool_timeout',
               default=None,
               deprecated_opts=[cfg.DeprecatedOpt('sqlalchemy_pool_timeout',
                                                  group='DATABASE')],
               help='If set, use this value for pool_timeout with sqlalchemy'),
]

CONF = cfg.CONF
CONF.register_opts(sqlite_db_opts)
CONF.register_opts(database_opts, 'database')


def set_defaults(sql_connection, sqlite_db, max_pool_size=None,
                 max_overflow=None, pool_timeout=None):
    """Set defaults for configuration variables."""
    cfg.set_defaults(database_opts,
                     connection=sql_connection)
    cfg.set_defaults(sqlite_db_opts,
                     sqlite_db=sqlite_db)
    # Update the QueuePool defaults
    if max_pool_size is not None:
        cfg.set_defaults(database_opts,
                         max_pool_size=max_pool_size)
    if max_overflow is not None:
        cfg.set_defaults(database_opts,
                         max_overflow=max_overflow)
    if pool_timeout is not None:
        cfg.set_defaults(database_opts,
                         pool_timeout=pool_timeout)


def create_engine(cfg, sqlite_fk=False, mysql_traditional_mode=False):
    return session.create_engine(
        cfg.database.connection,
        sqlite_fk=sqlite_fk,
        mysql_traditional_mode=mysql_traditional_mode,
        idle_timeout=cfg.database.idle_timeout,
        connection_debug=cfg.databse.connection_debug,
        max_pool_size=cfg.database.max_pool_size,
        max_overflow=cfg.database.max_overflow,
        pool_timeout=cfg.database.pool_timeout,
        sqlite_synchronous=cfg.database.sqlite_synchronous,
        connection_trace=cfg.database.connection_trace,
        max_retries=cfg.database.max_retries,
        retry_internval=cfg.database.retry_interval)
