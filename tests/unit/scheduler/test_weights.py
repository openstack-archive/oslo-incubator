# Copyright 2011-2012 OpenStack Foundation.
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

"""
Tests For Scheduler weights.
"""

from openstack.common.scheduler import base_weight
from openstack.common import test
from tests.unit import fakes


class TestWeightHandler(test.BaseTestCase):
    def test_get_all_classes(self):
        namespace = "openstack.common.tests.fakes.weights"
        handler = base_weight.BaseWeightHandler(
            base_weight.BaseWeigher, namespace)
        classes = handler.get_all_classes()
        self.assertTrue(fakes.FakeWeigher1 in classes)
        self.assertTrue(fakes.FakeWeigher2 in classes)
        self.assertFalse(fakes.FakeClass in classes)
