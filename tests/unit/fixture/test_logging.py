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


from openstack.common.fixture import logging as logging_fixture
from openstack.common import log as logging
from tests import utils

LOG = logging.getLogger(__name__)


class TestLoggingFixture(utils.BaseTestCase):
    def test_logging_handle_error(self):
        LOG.info('pid of first child is %(foo)s', 1)
        self.useFixture(logging_fixture.get_logging_handle_error_fixture())
        self.assertRaises(TypeError,
                          LOG.info,
                          'pid of first child is %(foo)s',
                          1)
