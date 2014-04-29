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

from oslotest import base as oslo_test
from sqlalchemy import Column
from sqlalchemy import Integer, String
from sqlalchemy.ext.declarative import declarative_base

from openstack.common.db.sqlalchemy import models
from openstack.common.db.sqlalchemy import test_base


BASE = declarative_base()


class ModelBaseTest(test_base.DbTestCase):
    def setUp(self):
        super(ModelBaseTest, self).setUp()
        self.mb = models.ModelBase()
        self.ekm = ExtraKeysModel()

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
        self.mb['world'] = 'hello'
        self.assertEqual(self.mb['world'], 'hello')

    def test_modelbase_update(self):
        h = {'a': '1', 'b': '2'}
        self.mb.update(h)
        for key in h.keys():
            self.assertEqual(self.mb[key], h[key])

    def test_modelbase_iteritems(self):
        h = {'a': '1', 'b': '2'}
        expected = {
            'id': None,
            'smth': None,
            'name': 'NAME',
            'a': '1',
            'b': '2',
        }
        self.ekm.update(h)
        found_items = 0
        for key, value in self.ekm.iteritems():
            self.assertEqual(expected[key], value)
            found_items += 1

        self.assertEqual(len(expected), found_items)

    def test_modelbase_iter(self):
        expected = {
            'id': None,
            'smth': None,
            'name': 'NAME',
        }
        i = iter(self.ekm)
        found_items = 0
        while True:
            r = next(i, None)
            if r is None:
                break
            self.assertEqual(expected[r[0]], r[1])
            found_items += 1

        self.assertEqual(len(expected), found_items)

    def test_extra_keys_empty(self):
        """Test verifies that by default extra_keys return empty list."""
        self.assertEqual(self.mb._extra_keys, [])

    def test_extra_keys_defined(self):
        """Property _extra_keys will return list with attributes names."""
        self.assertEqual(self.ekm._extra_keys, ['name'])

    def test_model_with_extra_keys(self):
        data = dict(self.ekm)
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


class TimestampMixinTest(oslo_test.BaseTestCase):

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
