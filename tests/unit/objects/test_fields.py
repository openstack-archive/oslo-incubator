#    Copyright 2013 Red Hat, Inc.
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

import datetime
import iso8601
import netaddr
import six

from openstack.common.objects import base as obj_base
from openstack.common.objects import fields
from openstack.common import timeutils
from openstack.common import test


def as_long(v):
    if six.PY2:
        return long(v)
    return v


class FakeFieldType(fields.FieldType):
    def coerce(self, obj, attr, value):
        return '*%s*' % value

    def to_primitive(self, obj, attr, value):
        return '!%s!' % value

    def from_primitive(self, obj, attr, value):
        return value[1:-1]


class TestField(test.BaseTestCase):
    def setUp(self):
        super(TestField, self).setUp()
        self.field = fields.Field(FakeFieldType())
        self.coerce_good_values = [('foo', '*foo*')]
        self.coerce_bad_values = []
        self.to_primitive_values = [('foo', '!foo!')]
        self.from_primitive_values = [('!foo!', 'foo')]

    def test_coerce_good_values(self):
        for in_val, out_val in self.coerce_good_values:
            self.assertEqual(out_val, self.field.coerce('obj', 'attr', in_val))

    def test_coerce_bad_values(self):
        for in_val in self.coerce_bad_values:
            self.assertRaises((TypeError, ValueError),
                              self.field.coerce, 'obj', 'attr', in_val)

    def test_to_primitive(self):
        for in_val, prim_val in self.to_primitive_values:
            self.assertEqual(prim_val, self.field.to_primitive('obj', 'attr',
                                                               in_val))

    def test_from_primitive(self):
        class ObjectLikeThing:
            _context = 'context'

        for prim_val, out_val in self.from_primitive_values:
            self.assertEqual(
                out_val, self.field.from_primitive(
                    ObjectLikeThing,
                    'attr',
                    prim_val
                )
            )


class TestString(TestField):
    def setUp(self):
        super(TestField, self).setUp()
        self.field = fields.StringField()
        self.coerce_good_values = [('foo', 'foo'), (1, '1'), (as_long(1), '1'),
                                   (True, 'True')]
        self.coerce_bad_values = [None]
        self.to_primitive_values = self.coerce_good_values[0:1]
        self.from_primitive_values = self.coerce_good_values[0:1]


class TestInteger(TestField):
    def setUp(self):
        super(TestField, self).setUp()
        self.field = fields.IntegerField()
        self.coerce_good_values = [(1, 1), ('1', 1)]
        self.coerce_bad_values = ['foo', None]
        self.to_primitive_values = self.coerce_good_values[0:1]
        self.from_primitive_values = self.coerce_good_values[0:1]


class TestBoolean(TestField):
    def setUp(self):
        super(TestField, self).setUp()
        self.field = fields.BooleanField()
        self.coerce_good_values = [(True, True), (False, False), (1, True),
                                   ('foo', True), (0, False), ('', False)]
        self.coerce_bad_values = []
        self.to_primitive_values = self.coerce_good_values[0:2]
        self.from_primitive_values = self.coerce_good_values[0:2]


class TestDateTime(TestField):
    def setUp(self):
        super(TestDateTime, self).setUp()
        self.dt = datetime.datetime(1955, 11, 5, tzinfo=iso8601.iso8601.Utc())
        self.field = fields.DateTimeField()
        self.coerce_good_values = [(self.dt, self.dt),
                                   (timeutils.isotime(self.dt), self.dt)]
        self.coerce_bad_values = [1, 'foo']
        self.to_primitive_values = [(
            self.dt,
            timeutils.isotime(self.dt, True)
        )]
        self.from_primitive_values = [(timeutils.isotime(self.dt), self.dt)]


class TestIPAddressV4(TestField):
    def setUp(self):
        super(TestIPAddressV4, self).setUp()
        self.field = fields.IPV4AddressField()
        self.coerce_good_values = [('1.2.3.4', netaddr.IPAddress('1.2.3.4')),
                                   (netaddr.IPAddress('1.2.3.4'),
                                    netaddr.IPAddress('1.2.3.4'))]
        self.coerce_bad_values = ['1-2', 'foo', '::1']
        self.to_primitive_values = [(netaddr.IPAddress('1.2.3.4'), '1.2.3.4')]
        self.from_primitive_values = [('1.2.3.4',
                                       netaddr.IPAddress('1.2.3.4'))]


class TestIPAddressV6(TestField):
    def setUp(self):
        super(TestIPAddressV6, self).setUp()
        self.field = fields.IPV6AddressField()
        self.coerce_good_values = [('::1', netaddr.IPAddress('::1')),
                                   (netaddr.IPAddress('::1'),
                                    netaddr.IPAddress('::1'))]
        self.coerce_bad_values = ['1.2', 'foo', '1.2.3.4']
        self.to_primitive_values = [(netaddr.IPAddress('::1'), '::1')]
        self.from_primitive_values = [('::1',
                                       netaddr.IPAddress('::1'))]


class TestDict(TestField):
    def setUp(self):
        super(TestDict, self).setUp()
        self.field = fields.Field(fields.Dict(FakeFieldType()))
        self.coerce_good_values = [({'foo': 'bar'}, {'foo': '*bar*'}),
                                   ({'foo': 1}, {'foo': '*1*'})]
        self.coerce_bad_values = [{1: 'bar'}, 'foo']
        self.to_primitive_values = [({'foo': 'bar'}, {'foo': '!bar!'})]
        self.from_primitive_values = [({'foo': '!bar!'}, {'foo': 'bar'})]


class TestDictOfStrings(TestField):
    def setUp(self):
        super(TestDictOfStrings, self).setUp()
        self.field = fields.DictOfStringsField()
        self.coerce_good_values = [({'foo': 'bar'}, {'foo': 'bar'}),
                                   ({'foo': 1}, {'foo': '1'})]
        self.coerce_bad_values = [{1: 'bar'}, {'foo': None}, 'foo']
        self.to_primitive_values = [({'foo': 'bar'}, {'foo': 'bar'})]
        self.from_primitive_values = [({'foo': 'bar'}, {'foo': 'bar'})]


class TestDictOfStringsNone(TestField):
    def setUp(self):
        super(TestDictOfStringsNone, self).setUp()
        self.field = fields.DictOfNullableStringsField()
        self.coerce_good_values = [({'foo': 'bar'}, {'foo': 'bar'}),
                                   ({'foo': 1}, {'foo': '1'}),
                                   ({'foo': None}, {'foo': None})]
        self.coerce_bad_values = [{1: 'bar'}, 'foo']
        self.to_primitive_values = [({'foo': 'bar'}, {'foo': 'bar'})]
        self.from_primitive_values = [({'foo': 'bar'}, {'foo': 'bar'})]


class TestList(TestField):
    def setUp(self):
        super(TestList, self).setUp()
        self.field = fields.Field(fields.List(FakeFieldType()))
        self.coerce_good_values = [(['foo', 'bar'], ['*foo*', '*bar*'])]
        self.coerce_bad_values = ['foo']
        self.to_primitive_values = [(['foo'], ['!foo!'])]
        self.from_primitive_values = [(['!foo!'], ['foo'])]


class TestObject(TestField):
    def setUp(self):
        class TestableObject(obj_base.AbstractDomainObject):
            def __eq__(self, value):
                # NOTE(danms): Be rather lax about this equality thing to
                # satisfy the assertEqual() in test_from_primitive(). We
                # just want to make sure the right type of object is re-created
                return value.__class__.__name__ == TestableObject.__name__

        class OtherTestableObject(obj_base.AbstractDomainObject):
            pass

        obj_base.reset_obj_classes()
        obj_base.register_obj_class(TestableObject)
        obj_base.register_obj_class(OtherTestableObject)

        test_inst = TestableObject()
        super(TestObject, self).setUp()
        self.field = fields.Field(fields.Object('TestableObject'))
        self.coerce_good_values = [(test_inst, test_inst)]
        self.coerce_bad_values = [OtherTestableObject(), 1, 'foo']
        self.to_primitive_values = [(test_inst, test_inst.obj_to_primitive())]
        self.from_primitive_values = [(test_inst.obj_to_primitive(),
                                       test_inst)]
