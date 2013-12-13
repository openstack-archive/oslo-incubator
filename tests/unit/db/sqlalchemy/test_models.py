# Copyright 2012 Cloudscaling Group, Inc.
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

from sqlalchemy import Column
from sqlalchemy import Integer, String
from sqlalchemy.ext.declarative import declarative_base

from openstack.common.db.sqlalchemy import models
from openstack.common import test
from tests.unit.db.sqlalchemy import base


BASE = declarative_base()


class ModelBaseTest(base.DbTestCase):

    def test_modelbase_has_dict_methods(self):
        dict_methods = ('__getitem__',
                        '__setitem__',
                        '__iter__',
                        'get',
                        'next',
                        'update',
                        'save',
                        'iteritems')
        for method in dict_methods:
            self.assertTrue(hasattr(models.ModelBase, method))

    def test_modelbase_set(self):
        mb = models.ModelBase()
        mb['world'] = 'hello'
        self.assertEqual(mb['world'], 'hello')

    def test_modelbase_update(self):
        mb = models.ModelBase()
        h = {'a': '1', 'b': '2'}
        mb.update(h)
        for key in h.keys():
            self.assertEqual(mb[key], h[key])

    def test_modelbase_iteritems(self):
        self.skipTest("Requires DB")
        mb = models.ModelBase()
        h = {'a': '1', 'b': '2'}
        mb.update(h)
        for key, value in mb.iteritems():
            self.assertEqual(h[key], value)

    def test_modelbase_iter(self):
        self.skipTest("Requires DB")
        mb = models.ModelBase()
        h = {'a': '1', 'b': '2'}
        mb.update(h)
        i = iter(mb)

        min_items = len(h)
        found_items = 0
        while True:
            r = next(i, None)
            if r is None:
                break

            self.assertTrue(r in h)
            found_items += 1

        self.assertEqual(min_items, found_items)

    def test_extra_keys_empty(self):
        """Test verifies that by default extra_keys return empty list."""
        mb = models.ModelBase()
        self.assertEqual(mb._extra_keys, [])

    def test_extra_keys_defined(self):
        """Property _extra_keys will return list with attributes names."""
        ekm = ExtraKeysModel()
        self.assertEqual(ekm._extra_keys, ['name'])

    def test_model_with_extra_keys(self):
        item = ExtraKeysModel()
        data = dict(item)
        self.assertEqual(data, {'smth': None,
                                'id': None,
                                'name': 'NAME'})


class ExtraKeysModel(BASE, models.ModelBase):
    __tablename__ = 'test_model'

    id = Column(Integer, primary_key=True)
    smth = Column(String(255))

    @property
    def name(self):
        return 'NAME'

    @property
    def _extra_keys(self):
        return ['name']


class TimestampMixinTest(test.BaseTestCase):

    def test_timestampmixin_attr(self):

        class TestModel(models.ModelBase, models.TimestampMixin):
            pass

        dict_methods = ('__getitem__',
                        '__setitem__',
                        '__iter__',
                        'get',
                        'next',
                        'update',
                        'save',
                        'iteritems',
                        'created_at',
                        'updated_at')
        for method in dict_methods:
            self.assertTrue(hasattr(TestModel, method))
