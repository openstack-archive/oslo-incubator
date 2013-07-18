# Copyright (c) 2013 Openstack Foundation.
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
import abc
import unittest

from openstack.common import abcutils


@abcutils.abstractbase
class MetaX(object):
    @abc.abstractproperty
    def x(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def morex(self):
        raise NotImplementedError()


class GoodX(MetaX):
    def __init__(self, x):
        self._x = x

    @property
    def x(self):
        return self._x

    def morex(self):
        self._x += 1


class BadX(MetaX):
    pass


class AbcUtilsGoodClassTest(unittest.TestCase):
    def setUp(self):
        super(AbcUtilsGoodClassTest, self).setUp()
        self.obj = GoodX(1)

    def test_object_type_matches_base_class(self):
        self.assertTrue(type(self.obj) is GoodX)

    def test_derived_class_is_subclass_of_abc(self):
        self.assertTrue(issubclass(GoodX, MetaX))

    def test_object_is_instance_of_derived_class(self):
        self.assertTrue(isinstance(self.obj, GoodX))

    def test_derived_class_hasattr_register(self):
        self.assertTrue(hasattr(GoodX, 'register'))


class AbcUtilsBadClassTest(unittest.TestCase):
    def test_non_conforming_child_raises_type_error(self):
        self.assertRaises(TypeError, BadX)
