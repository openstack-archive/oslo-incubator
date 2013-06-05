# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

from openstack.common.first import first
from tests import utils


isbool = lambda x: isinstance(x, bool)
isint = lambda x: isinstance(x, int)
odd = lambda x: isint(x) and x % 2 != 0
even = lambda x: isint(x) and x % 2 == 0
is_meaning_of_life = lambda x: x == 42


class TestFirst(utils.BaseTestCase):
    def test_empty_iterables(self):
        s = set()
        l = []
        self.assertEqual(first(s), None)
        self.assertEqual(first(l), None)

    def test_default_value(self):
        s = set()
        l = []
        self.assertEqual(first(s, default=42), 42)
        self.assertEqual(first(l, default=3.14), 3.14)

        l = [0, False, []]
        self.assertEqual(first(l, default=3.14), 3.14)

    def test_selection(self):
        l = [(), 0, False, 3, []]

        self.assertEqual(first(l, default=42), 3)
        self.assertEqual(first(l, key=isint), 0)
        self.assertEqual(first(l, key=isbool), False)
        self.assertEqual(first(l, key=odd), 3)
        self.assertEqual(first(l, key=even), 0)
        self.assertEqual(first(l, key=is_meaning_of_life), None)
