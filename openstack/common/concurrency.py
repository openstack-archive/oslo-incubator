# Copyright 2014 Mirantis.inc
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

from eventlet import tpool
from oslo.config import cfg

from openstack.common.db import api as common_db_api

tpool_opts = [
    cfg.BoolOpt('use_tpool',
                default=False,
                deprecated_name='dbapi_use_tpool',
                deprecated_group='DEFAULT',
                help='Enable the experimental use of thread pooling for '
                     'all DB API calls'),
]

CONF = cfg.CONF
CONF.register_opts(tpool_opts, 'database')
CONF.import_opt('backend', 'openstack.common.db.options',
                group='database')


class DBAPI(object):
    """DB API wrapper class.

    This wraps the oslo DB API with an option to be able to use eventlet's
    thread pooling. Since the CONF variable may not be loaded at the time
    this class is instantiated, we must look at it on the first DB API call.
    """

    def __init__(self, backend_mapping):
        self.__db_api = None
        self.__backend_mapping = backend_mapping

    @property
    def _db_api(self):
        if not self.__db_api:
            db_api = common_db_api.DBAPI(
                CONF.database.backend, backend_mapping=self.__backend_mapping)
            if CONF.database.use_tpool:
                self.__db_api = tpool.Proxy(db_api)
            else:
                self.__db_api = db_api
        return self.__db_api

    def __getattr__(self, key):
        return getattr(self._db_api, key)
