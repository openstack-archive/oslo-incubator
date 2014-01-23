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

A DB backend module should implement a method named 'get_backend' which
takes no arguments.  The method can return any object that implements DB
API methods.
"""

import functools
import logging
import time

from openstack.common.db import exception
from openstack.common.gettextutils import _
from openstack.common import importutils


LOG = logging.getLogger(__name__)


def safe_for_db_retry(f):
    """Enable db-retry for decorated function, if config option enabled."""
    f.__dict__['enable_retry'] = True
    return f


def _wrap_db_retry(f, retry_interval, inc_retry_interval,
                   max_retry_interval, max_retries):
    """Retry db.api methods, if DBConnectionError() raised

    Retry decorated db.api methods. If we enabled `use_db_reconnect`
    in config, this decorator will be applied to all db.api functions,
    marked with @safe_for_db_retry decorator.
    Decorator catchs DBConnectionError() and retries function in a
    loop until it succeeds, or until maximum retries count will be reached.

    :param f: function to decorate
    :type f: function

    :param next_interval: seconds between db connection retries
    :type next_interval: integer

    :param inc_retry_interval: whether to increase interval between db
                               connection retries, up to db_max_retry_interval
    :type inc_retry_interval: bool

    :param db_max_retry_interval: maximum seconds between db connection
                                  retries, if db_inc_retry_interval is enabled
    :type db_max_retry_interval: integer

    :param db_max_retries: maximum db connection retries before error is raised
                           Setting -1 implies an infinite retry count
    :type db_max_retries: integer

    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        next_retry_interval = retry_interval
        remaining = max_retries

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
                # NOTE(vsergeyev): We are using patched time module, so this
                #                  effectively yields the execution context to
                #                  another green thread.
                time.sleep(next_retry_interval)
                if inc_retry_interval:
                    next_retry_interval = min(
                        next_retry_interval * 2,
                        max_retry_interval
                    )
    return wrapper


class DBAPI(object):
    def __init__(self, backend_name, backend_mapping=None, **kwargs):
        if backend_mapping is None:
            backend_mapping = {}

        # Import the untranslated name if we don't have a
        # mapping.
        backend_path = backend_mapping.get(backend_name, backend_name)
        backend_mod = importutils.import_module(backend_path)
        self.__backend = backend_mod.get_backend()

        self.use_db_reconnect = kwargs.get('use_db_reconnect', False)
        self.db_retry_interval = kwargs.get('db_retry_interval', 1)
        self.db_inc_retry_interval = kwargs.get('db_inc_retry_interval', True)
        self.db_max_retry_interval = kwargs.get('db_max_retry_interval', 10)
        self.db_max_retries = kwargs.get('db_max_retries', 20)

    def __getattr__(self, key):
        attr = getattr(self.__backend, key)

        if not hasattr(attr, '__call__'):
            return attr
        # NOTE(vsergeyev): If `use_db_reconnect` option is set to True, retry
        #                  DB API methods, decorated with @safe_for_db_retry
        #                  on disconnect.
        if self.use_db_reconnect and hasattr(attr, 'enable_retry'):
            attr = _wrap_db_retry(
                attr,
                retry_interval=self.db_retry_interval,
                inc_retry_interval=self.db_inc_retry_interval,
                max_retry_interval=self.db_max_retry_interval,
                max_retries=self.db_max_retries,
            )

        return attr
