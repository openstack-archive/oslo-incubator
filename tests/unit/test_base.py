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

from testtools.matchers import MismatchError

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

    def test_equal_objects(self):

        self.assertEqualObjects(obj1=obj1, obj2=obj3, ignored_keys=['id'])
        try:
            self.assertEqualObjects(obj1=obj1, obj2=obj2)
        except MismatchError:
            resultTest = False
        else:
            resultTest = True
        self.assertFalse(resultTest)

    def test_equal_lists_of_objects(self):

        list_obj1 = [obj1, obj2]
        list_obj2 = [obj3, obj4]

        self.assertEqualListsOfObjects(objs1=list_obj1, objs2=list_obj2,
                                       ignored_keys=['id'])
        try:
            self.assertEqualListsOfObjects(objs1=list_obj1, objs2=list_obj2)
        except MismatchError:
            resultTest = False
        else:
            resultTest = True
        self.assertFalse(resultTest)
