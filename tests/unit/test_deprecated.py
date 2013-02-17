# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
#    Copyright 2010 OpenStack LLC
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

from openstack.common import log as logging
from tests import utils as test_utils

LOG = logging.getLogger(__name__)


class DeprecatedConfigTestCase(test_utils.BaseTestCase):
    def setUp(self):
        super(DeprecatedConfigTestCase, self).setUp()
        self.warnbuffer = ""
        self.critbuffer = ""

        def warn_log(msg):
            self.warnbuffer = msg

        def critical_log(msg):
            self.critbuffer = msg

        self.stubs.Set(LOG, 'warn', warn_log)
        self.stubs.Set(LOG, 'critical', critical_log)

    def test_deprecated(self):
        LOG.deprecated('test')
        self.assertEqual(self.warnbuffer, 'Deprecated: test')

    def test_deprecated_fatal(self):
        self.config(fatal_deprecations=True)
        self.assertRaises(logging.DeprecatedConfig,
                          LOG.deprecated, "test2")
        self.assertEqual(self.critbuffer, 'Deprecated: test2')

    def test_deprecated_logs_only_once(self):
        LOG.deprecated('only once!')
        LOG.deprecated('only once!')
        LOG.deprecated('only once!')
        self.assertEqual(self.warnbuffer, 'Deprecated: only once!')
