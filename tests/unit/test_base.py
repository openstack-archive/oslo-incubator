from openstack.common.test import ModelsObjectComparatorMixin as MO_Comparator
from openstack.common import test


obj1 = {'id': 1,
        'value': 'value1'}
obj2 = {'id': 2,
        'value': 'value2'}
obj3 = {'id': 3,
        'value': 'value1'}
obj4 = {'id': 4,
        'value': 'value2'}


class TestModelsObjectComparatorMixin(test.BaseTestCase):

    def test_EqualObjects(self):

        self.assertFalse(
            MO_Comparator.assertEqualObjects(obj1=obj1, obj2=obj2))
        self.assertTrue(
            MO_Comparator.assertEqualObjects(obj1=obj1, obj2=obj3))

    def test_EqualListsOfObjects(self):

        list_obj1 = [obj1, obj2]
        list_obj2 = [obj3, obj4]
        list_obj3 = [obj1, obj3]

        self.assertFalse(
            MO_Comparator.assertEqualListsOfObjects(
                objs1=list_obj1, objs2=list_obj3))
        self.assertTrue(
            MO_Comparator.assertEqualListsOfObjects(
                objs1=list_obj1, objs2=list_obj2))
