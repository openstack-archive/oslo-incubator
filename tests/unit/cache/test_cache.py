# Copyright 2013 Red Hat, Inc.
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

from openstack.common.cache._backends import memory
from openstack.common.cache import cache
from tests import utils


class TestCacheModule(utils.BaseTestCase):

    def test_get_cache(self):
        driver = cache.get_cache(cfg.CONF)
        self.assertTrue(isinstance(driver, memory.MemoryBackend))
        self.assertEqual(driver.conf, cfg.CONF.oslo_cache)
