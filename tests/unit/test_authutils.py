# Copyright 2011 OpenStack Foundation.
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

from openstack.common import authutils
from openstack.common import test


class AuthUtilsTest(test.BaseTestCase):

    def test_auth_str_equal(self):
        self.assertTrue(authutils.auth_str_equal('abc123', 'abc123'))
        self.assertFalse(authutils.auth_str_equal('a', 'aaaaa'))
        self.assertFalse(authutils.auth_str_equal('aaaaa', 'a'))
        self.assertFalse(authutils.auth_str_equal('ABC123', 'abc123'))
