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

from openstack.common import test
from openstack.common import units


class UnitTest(test.BaseTestCase):
    def test_binary_unit(self):
        self.assertEqual(units.Ki, 1024)
        self.assertEqual(units.Mi, 1024 ** 2)
        self.assertEqual(units.Gi, 1024 ** 3)
        self.assertEqual(units.Ti, 1024 ** 4)
        self.assertEqual(units.Pi, 1024 ** 5)
        self.assertEqual(units.Ei, 1024 ** 6)
        self.assertEqual(units.Zi, 1024 ** 7)
        self.assertEqual(units.Yi, 1024 ** 8)

    def test_decimal_unit(self):
        self.assertEqual(units.k, 1000)
        self.assertEqual(units.M, 1000 ** 2)
        self.assertEqual(units.G, 1000 ** 3)
        self.assertEqual(units.T, 1000 ** 4)
        self.assertEqual(units.P, 1000 ** 5)
        self.assertEqual(units.E, 1000 ** 6)
        self.assertEqual(units.Z, 1000 ** 7)
        self.assertEqual(units.Y, 1000 ** 8)
