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

`db_backend`: DB backend name or full module path to DB backend module.
`dbapi_use_tpool`: Enable thread pooling of DB API calls.

A DB backend module should implement a class named 'API' that will be
instatiated once by the backend loader.  For backwards compatibility with
the sqlalchemy backend in nova, support methods defined within the
module outside of a class.
"""

from openstack.common import cfg
from openstack.common import lockutils
from openstack.common import importutils


db_opts = [
    cfg.StrOpt('db_backend',
               default='sqlalchemy',
               help='The backend to use for db'),
    cfg.BoolOpt('dbapi_use_tpool',
                default=False,
                help='Enable the experimental use of thread pooling for '
                     'all DB API calls')
]

CONF = cfg.CONF
CONF.register_opts(db_opts)


class DBAPI(object):
    def __init__(self, known_backends=None):
        if known_backends is None:
            known_backends = {}
        self.__backend = None
        self.__known_backends = known_backends

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
        backend_name = CONF.db_backend
        self.__use_tpool = CONF.dbapi_use_tpool
        if self.__use_tpool:
            from eventlet import tpool
            self.__tpool = tpool
        # Import the untranslated name if we don't have a
        # mapping.
        backend_path = self.__known_backends.get(backend_name,
                                                 backend_name)
        backend_mod = importutils.import_module(backend_path)
        self.__backend = backend_mod.get_backend()
        return self.__backend

    def __getattr__(self, key):
        backend = self.__backend or self.__get_backend()
        attr = getattr(backend, key)
        if not self.__use_tpool or not hasattr(attr, '__call__'):
            return attr

        def tpool_wrapper(*args, **kwargs):
            return self.__tpool.execute(attr, *args, **kwargs)

        tpool_wrapper.__name__ = attr.__name__
        return tpool_wrapper
