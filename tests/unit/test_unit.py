# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 IBM Corp
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

from openstack.common import unit
from openstack.common import test


class UnitTest(test.BaseTestCase):
    def test_byteunit(self):
        self.assertEqual(unit.byte.Ki, 1024)
        self.assertEqual(unit.byte.Mi, 1024 ** 2)
        self.assertEqual(unit.byte.Gi, 1024 ** 3)
        self.assertEqual(unit.byte.Ti, 1024 ** 4)
        self.assertEqual(unit.byte.Pi, 1024 ** 5)

    def test_byteunit_readonly(self):

        def set_readonly_Ki():
            unit.byte.Ki = 10

        def set_readonly_Mi():
            unit.byte.Mi = 10

        def set_readonly_Gi():
            unit.byte.Gi = 10

        def set_readonly_Ti():
            unit.byte.Ti = 10

        def set_readonly_Pi():
            unit.byte.Pi = 10

        self.assertRaises(AttributeError, set_readonly_Ki)
        self.assertRaises(AttributeError, set_readonly_Mi)
        self.assertRaises(AttributeError, set_readonly_Gi)
        self.assertRaises(AttributeError, set_readonly_Ti)
        self.assertRaises(AttributeError, set_readonly_Pi)
