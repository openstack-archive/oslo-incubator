#
# Copyright 2013 Mirantis, Inc.
# Copyright 2013 OpenStack Foundation
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
from oslo.config import cfg

from openstack.common.db.sqlalchemy import test_base
from openstack.common.fixture import config

conf = cfg.CONF


class ConfigTestCase(test_base.DbTestCase):
    def setUp(self):
        super(ConfigTestCase, self).setUp()
        self.config = self.useFixture(config.Config(conf)).config
        self.config_fixture = config.Config(conf)
        conf.register_opt(cfg.StrOpt(
            'testing_option', default='initial_value'))

    def test_overriden_value(self):
        self.assertEqual(conf.get('testing_option'), 'initial_value')
        self.config(testing_option='changed_value')
        self.assertEqual(conf.get('testing_option'),
                         self.config_fixture.conf.get('testing_option'))

    def test_cleanup(self):
        self.config(testing_option='changed_value')
        self.assertEqual(self.config_fixture.conf.get('testing_option'),
                         'changed_value')
        self.config_fixture.conf.reset()
        self.assertEqual(conf.get('testing_option'), 'initial_value')
