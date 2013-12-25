# Copyright (c) 2013 OpenStack Foundation
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

from testtools import matchers

from openstack.common import test


obj1 = {'id': 1,
        'value': 'value1'}
obj2 = {'id': 2,
        'value': 'value2'}
obj3 = {'id': 3,
        'value': 'value1'}
obj4 = {'id': 4,
        'value': 'value2'}
list_obj1 = [obj1, obj2]
list_obj2 = [obj3, obj4]
host_ips1 = {
    'host1': ['1.1.1.1', '1.1.1.2', '1.1.1.3'],
    'host2': ['1.1.1.4', '1.1.1.5'],
    'host3': ['1.1.1.6']
}


class TestModelsObjectComparatorMixin(test.BaseTestCase,
                                      test.ModelsObjectComparatorMixin):

    def test_equal_objects(self):
        self.assertEqualObjects(obj1=obj1, obj2=obj3, ignored_keys=['id'])

    def test_not_equal_objects(self):
        self.assertRaises(matchers.MismatchError,
                          self.assertEqualObjects, obj1=obj1, obj2=obj2)

    def test_equal_lists_of_objects(self):
        self.assertEqualListsOfObjects(objs1=list_obj1, objs2=list_obj2,
                                       ignored_keys=['id'])

    def test_not_equal_lists_of_objects(self):
        self.assertRaises(matchers.MismatchError,
                          self.assertEqualListsOfObjects,
                          objs1=list_obj1, objs2=list_obj2)

    def test_equal_lists_of_primitives_as_sets(self):
        host_ips2 = {
            'host3': ['1.1.1.6'],
            'host1': ['1.1.1.1', '1.1.1.2', '1.1.1.3'],
            'host2': ['1.1.1.4', '1.1.1.5'],
        }
        self.assertEqualListsOfPrimitivesAsSets(host_ips1, host_ips2)

    def test_not_equal_lists_of_primitives_as_sets(self):
        host_ips3 = {
            'host1': ['1.1.1.1', '1.1.1.2', '1.1.1.3'],
            'host2': ['1.1.1.4', '1.1.1.5']
        }
        self.assertRaises(matchers.MismatchError,
                          self.assertEqualListsOfPrimitivesAsSets,
                          host_ips1, host_ips3)
