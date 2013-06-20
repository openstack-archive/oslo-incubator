# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 Rackspace Hosting
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

"""Multiple DB API backend support.

Supported configuration options:

The following two parameters are in the 'database' group:
`backend`: DB backend name or full module path to DB backend module.
`use_tpool`: Enable thread pooling of DB API calls.

A DB backend module should implement a method named 'get_backend' which
takes no arguments.  The method can return any object that implements DB
API methods.

*NOTE*: There are bugs in eventlet when using tpool combined with
threading locks. The python logging module happens to use such locks.  To
work around this issue, be sure to specify thread=False with
eventlet.monkey_patch().

A bug for eventlet has been filed here:

https://bitbucket.org/eventlet/eventlet/issue/137/
"""
import functools
import time

from oslo.config import cfg

from openstack.common.db import exception
from openstack.common.gettextutils import _  # noqa
from openstack.common import importutils
from openstack.common import lockutils
from openstack.common import log as logging

db_opts = [
    cfg.StrOpt('backend',
               default='sqlalchemy',
               deprecated_name='db_backend',
               deprecated_group='DEFAULT',
               help='The backend to use for db'),
    cfg.BoolOpt('use_tpool',
                default=False,
                deprecated_name='dbapi_use_tpool',
                deprecated_group='DEFAULT',
                help='Enable the experimental use of thread pooling for '
                     'all DB API calls'),
    cfg.BoolOpt('use_db_reconnect',
                default=False,
                help='Enable the experimental use of database reconnect '
                     'on connection lost'),
    cfg.IntOpt('db_retry_interval',
               default=1,
               help='seconds between db connection retries'),
    cfg.BoolOpt('db_inc_retry_interval',
                default=True,
                help='Whether to increase interval between db connection '
                     'retries, up to db_max_retry_interval'),
    cfg.IntOpt('db_max_retry_interval',
               default=10,
               help='max seconds between db connection retries, if '
                    'db_inc_retry_interval is enabled'),
    cfg.IntOpt('db_max_retries',
               default=20,
               help='maximum db connection retries before error is raised. '
                    '(setting -1 implies an infinite retry count)'),
]

CONF = cfg.CONF
CONF.register_opts(db_opts, 'database')

LOG = logging.getLogger(__name__)


def disable_db_retry(f):
    f.skip_retry = True
    return f


def enable_db_retry(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        next_interval = CONF.database.db_retry_interval
        remaining = CONF.database.db_max_retries

        while True:
            try:
                return f(*args, **kwargs)
            except exception.DBConnectionError as e:
                if remaining == 0:
                    LOG.exception(_('DB exceeded retry limit.'))
                    raise exception.DBError(e)
                if remaining != -1:
                    remaining -= 1
                    LOG.exception(_('DB connection error.'))
                # NOTE(vsergeyev): We are using patched time module, so this is
                #                  effectively yields the execution context to
                #                  another green thread.
                time.sleep(next_interval)
                if CONF.database.db_inc_retry_interval:
                    next_interval = min(
                        next_interval * 2,
                        CONF.database.db_max_retry_interval
                    )

    return wrapper


def wrap_tpool(f, thread_pool):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        return thread_pool.execute(f, *args, **kwargs)
    return wrapper


class DBAPI(object):
    def __init__(self, backend_mapping=None):
        if backend_mapping is None:
            backend_mapping = {}
        self.__backend = None
        self.__backend_mapping = backend_mapping

    @lockutils.synchronized('dbapi_backend', 'oslo-')
    def __get_backend(self):
        """Get the actual backend.  May be a module or an instance of
        a class.  Doesn't matter to us.  We do this synchronized as it's
        possible multiple greenthreads started very quickly trying to do
        DB calls and eventlet can switch threads before self.__backend gets
        assigned.
        """
        if self.__backend:
            # Another thread assigned it
            return self.__backend
        backend_name = CONF.database.backend
        self.__use_tpool = CONF.database.use_tpool
        if self.__use_tpool:
            from eventlet import tpool
            self.__tpool = tpool
        # Import the untranslated name if we don't have a
        # mapping.
        backend_path = self.__backend_mapping.get(backend_name,
                                                  backend_name)
        backend_mod = importutils.import_module(backend_path)
        self.__backend = backend_mod.get_backend()
        return self.__backend

    def __getattr__(self, key):
        backend = self.__backend or self.__get_backend()
        attr = getattr(backend, key)

        if not hasattr(attr, '__call__'):
            return attr
        # NOTE(vsergeyev): we should decorate db-api methods to provide
        #                  db-retry feature if there are:
        #                  - enabled `use_db_reconnect` flag in config
        #                  - function db-retry feature  doesen't ddisabled by
        #                    disable_db_retry() decorator.
        if CONF.database.use_db_reconnect and not getattr(attr,
                                                          'skip_retry', False):
            attr = enable_db_retry(attr)
        if self.__use_tpool:
            attr = wrap_tpool(attr, self.__tpool)

        return attr
