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

from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from testtools import matchers

from openstack.common.db.sqlalchemy import models
from openstack.common import test


BASE = declarative_base()


class FakeModel(BASE, models.ModelBase):

    __tablename__ = 'fake'

    id = Column(Integer, primary_key=True)
    value = Column(String(255))


class TestModelsObjectComparatorMixin(test.BaseTestCase,
                                      test.ModelsObjectComparatorMixin):

    def setUp(self):
        super(TestModelsObjectComparatorMixin, self).setUp()
        self.obj1 = FakeModel(**{'id': 1, 'value': 'value1'})
        self.obj2 = FakeModel(**{'id': 2, 'value': 'value2'})
        self.obj3 = FakeModel(**{'id': 3, 'value': 'value1'})
        self.obj4 = FakeModel(**{'id': 4, 'value': 'value2'})
        self.list_obj1 = [self.obj1, self.obj2]
        self.list_obj2 = [self.obj3, self.obj4]

    def test_equal_objects(self):
        self.assertEqualObjects(obj1=self.obj1, obj2=self.obj3,
                                ignored_keys=['id'])

    def test_not_equal_objects(self):
        self.assertRaises(matchers.MismatchError,
                          self.assertEqualObjects,
                          obj1=self.obj1, obj2=self.obj2)

    def test_equal_lists_of_objects(self):
        self.assertEqualListsOfObjects(objs1=self.list_obj1,
                                       objs2=self.list_obj2,
                                       ignored_keys=['id'])

    def test_not_equal_lists_of_objects(self):
        self.assertRaises(matchers.MismatchError,
                          self.assertEqualListsOfObjects,
                          objs1=self.list_obj1,
                          objs2=self.list_obj2)

    def test_equal_lists_of_primitives_as_sets(self):
        ip = ['10.0.0.3', '10.0.0.2', '10.0.0.1']
        host_ip = ['10.0.0.1', '10.0.0.2', '10.0.0.3']
        self.assertEqualListsOfPrimitivesAsSets(ip, host_ip)

    def test_not_equal_lists_of_primitives_as_sets(self):
        ip = ['10.0.0.3', '10.0.0.2', '10.0.0.1']
        host_ip = ['10.0.0.1', '10.0.0.5', '10.0.0.3']
        self.assertRaises(matchers.MismatchError,
                          self.assertEqualListsOfPrimitivesAsSets,
                          ip, host_ip)
