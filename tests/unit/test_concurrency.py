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

import eventlet
import mock

from oslo.config import cfg
from oslotest import base as test_base

from openstack.common import concurrency

CONF = cfg.CONF
FAKE_BACKEND_MAPPING = {'sqlalchemy': 'fake.db.sqlalchemy.api'}


class DBAPITestCase(test_base.BaseTestCase):

    def setUp(self):
        super(DBAPITestCase, self).setUp()
        self.db_api = concurrency.DBAPI(FAKE_BACKEND_MAPPING)

    @mock.patch('openstack.common.concurrency.common_db_api')
    def test_db_api_common(self, mock_db_api):
        # get access to some db-api method
        self.db_api.fake

        # CONF.database.use_tpool is False, so we have no proxy in this case
        self.assertIsInstance(self.db_api._db_api, mock.Mock)

    @mock.patch('openstack.common.concurrency.common_db_api')
    def test_db_api_config_change(self, mock_db_api):
        CONF.set_override('use_tpool', True, group='database')
        self.addCleanup(CONF.reset)

        # get access to some db-api method
        self.db_api.fake

        # CONF.database.use_tpool is True, so we get tpool proxy in this case
        self.assertIsInstance(self.db_api._db_api, eventlet.tpool.Proxy)
