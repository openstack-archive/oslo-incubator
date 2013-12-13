# Copyright 2013 Red Hat, Inc.
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


obj1 = {'id': 1,
        'value': 'value1'}
obj2 = {'id': 2,
        'value': 'value2'}
obj3 = {'id': 3,
        'value': 'value1'}
obj4 = {'id': 4,
        'value': 'value2'}


class TestModelsObjectComparatorMixin(test.BaseTestCase,
                                      test.ModelsObjectComparatorMixin):

    def test_EqualObjects(self):

        self.assertEqualObjects(obj1=obj1, obj2=obj2)
        self.assertEqualObjects(obj1=obj1, obj2=obj3)

    def test_EqualListsOfObjects(self):

        list_obj1 = [obj1, obj2]
        list_obj2 = [obj3, obj4]
        list_obj3 = [obj1, obj3]

        self.assertEqualListsOfObjects(objs1=list_obj1, objs2=list_obj3)
        self.assertEqualListsOfObjects(objs1=list_obj1, objs2=list_obj2)
