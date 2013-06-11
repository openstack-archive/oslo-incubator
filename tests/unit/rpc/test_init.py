# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 Mirantis Inc.
# All Rights Reserved
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


import fixtures
from oslo.config import cfg

from openstack.common.rpc import set_defaults
from tests import utils


class ConfigFixture(fixtures.Fixture):
    """Config recreated for each test case."""

    def __init__(self):
        super(ConfigFixture, self).__init__()

        self.conf = cfg.CONF
        self.conf.import_opt('control_exchange', 'openstack')

    def setUp(self):
        super(ConfigFixture, self).setUp()

        self.addCleanup(self.conf.reset)


class SetDefaultsTestCase(utils.BaseTestCase):

    def setUp(self):
        super(SetDefaultsTestCase, self).setUp()
        self.useFixture(ConfigFixture())

    def test_set_defaults(self):
        control_exchange_name = "test_name_123"
        set_defaults(control_exchange_name)
        self.assertEqual(
            cfg.CONF.control_exchange, control_exchange_name)

    def test_set_defaults_get_walue_before(self):
        default_name = 'openstack'
        self.assertEqual(cfg.CONF.control_exchange, default_name)
        control_exchange_name = "test_name_345"
        set_defaults(control_exchange_name)
        self.assertEqual(
            cfg.CONF.control_exchange, control_exchange_name)

    def test_set_defaults_few_times(self):
        control_exchange_name_1 = "test_name_1"
        control_exchange_name_2 = "test_name_2"

        set_defaults(control_exchange_name_1)
        self.assertEqual(
            cfg.CONF.control_exchange, control_exchange_name_1)

        set_defaults(control_exchange_name_2)
        self.assertEqual(
            cfg.CONF.control_exchange, control_exchange_name_2)
