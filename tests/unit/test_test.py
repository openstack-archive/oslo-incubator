# Copyright 2012 OpenStack LLC.
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

from openstack.common import cfg
from tests import utils as test_utils

testconfigdefault = 'grosmichel'
testconfigset = 'cavendish'
testconfigoverride = 'goldfinger'

test_opts = [
    cfg.StrOpt('testconfigopt',
               default=testconfigdefault,
               help='Arbitrary test config option')
    ]

CONF = cfg.CONF
CONF.register_opts(test_opts)


class cfgOverrideTestCase(test_utils.BaseTestCase):

    def test_cfg_override(self):
        self.assertEqual(cfg.CONF.get('testconfigopt'), testconfigdefault)
        self.assertEqual(cfg.CONF.testconfigopt, testconfigdefault)

        cfg.CONF.testconfigopt = testconfigset
        self.assertEqual(cfg.CONF.testconfigopt, testconfigset)
        self.assertEqual(cfg.CONF.get('testconfigopt'), testconfigset)

        self.config(testconfigopt=testconfigoverride)
        self.assertEqual(cfg.CONF.get('testconfigopt'), testconfigoverride)
        self.assertEqual(cfg.CONF.testconfigopt, testconfigoverride)
