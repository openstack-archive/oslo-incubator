# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack Foundation.
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
from openstack.common import passwordutils
from openstack.common import test


class TestPasswordUtils(test.BaseTestCase):

    def test_generate_password(self):
        password = passwordutils.generate_password()
        self.assertTrue(password is not None)
        self.assertTrue(len(password) == passwordutils.DEFAULT_PASSWORD_LENGTH)

    def test_generate_password_length(self):
        password = passwordutils.generate_password(16)
        self.assertTrue(password is not None)
        self.assertTrue(len(password) == 16)

    def test_generate_password_uniqueness(self):
        password_list = []
        for i in xrange(20):
            password_list.append(passwordutils.generate_password())
            self.assertTrue(password_list[i] is not None)
            self.assertTrue(len(password_list[i]) ==
                            passwordutils.DEFAULT_PASSWORD_LENGTH)

        self.assertEqual(len(password_list), len(set(password_list)))
