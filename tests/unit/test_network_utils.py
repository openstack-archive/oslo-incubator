# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack Foundation.
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

from openstack.common import network_utils
from tests import utils


class NetworkUtilsTest(utils.BaseTestCase):

    def test_parse_host_port(self):
        self.assertEqual(('server01', 80),
                         network_utils.parse_host_port('server01:80'))
        self.assertEqual(('server01', None),
                         network_utils.parse_host_port('server01'))
        self.assertEqual(('server01', 1234),
                         network_utils.parse_host_port('server01',
                         default_port=1234))
        self.assertEqual(('::1', 80),
                         network_utils.parse_host_port('[::1]:80'))
        self.assertEqual(('::1', None),
                         network_utils.parse_host_port('[::1]'))
        self.assertEqual(('::1', 1234),
                         network_utils.parse_host_port('[::1]',
                         default_port=1234))
        self.assertEqual(('2001:db8:85a3::8a2e:370:7334', 1234),
                         network_utils.parse_host_port(
                             '2001:db8:85a3::8a2e:370:7334',
                             default_port=1234))
