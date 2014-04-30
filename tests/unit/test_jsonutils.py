# Copyright 2011 OpenStack Foundation.
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

import datetime
import inspect
import json

import mock
import netaddr
from oslotest import base as test_base
import simplejson
import six
import six.moves.xmlrpc_client as xmlrpclib

from openstack.common import gettextutils
from openstack.common import jsonutils
from openstack.common import strutils


JSON_IMPLEMENTATIONS = (json, simplejson)


def check_implementations(cls):
    ''' Creates test cases for each json library implementation tested.  '''

    def pred(obj):
        return inspect.ismethod(obj) and obj.__name__.startswith('_test_')

    for name, func in inspect.getmembers(cls, predicate=pred):
        for impl in JSON_IMPLEMENTATIONS:
            case_name = 'test_%s%s' % (impl.__name__, name)
            patched_func = mock.patch.object(jsonutils, 'json', impl)(func)
            setattr(cls, case_name, patched_func)

    return cls


@check_implementations
class JSONUtilsTestCase(test_base.BaseTestCase):

    def _test_dumps(self):
        self.assertEqual(jsonutils.dumps({'a': 'b'}), '{"a": "b"}')

    def _test_loads(self):
        self.assertEqual(jsonutils.loads('{"a": "b"}'), {'a': 'b'})

    def _test_loads_unicode(self):
        self.assertIsInstance(jsonutils.loads('"foo"'), six.text_type)
        self.assertIsInstance(jsonutils.loads(u'"foo"'), six.text_type)

        i18n_str = '"\xd1\x82\xd0\xb5\xd1\x81\xd1\x82"'
        self.assertIsInstance(jsonutils.loads(i18n_str), six.text_type)

        i18n_str_unicode = strutils.safe_decode(i18n_str)
        self.assertIsInstance(jsonutils.loads(i18n_str_unicode), six.text_type)

    def _test_load(self):
        x = six.StringIO('{"a": "b"}')
        json_result = jsonutils.load(x)
        self.assertEqual(json_result, {'a': 'b'})
        for key, val in json_result.iteritems():
            self.assertIsInstance(key, unicode)
            self.assertIsInstance(val, unicode)


class ToPrimitiveTestCase(test_base.BaseTestCase):
    def test_list(self):
        self.assertEqual(jsonutils.to_primitive([1, 2, 3]), [1, 2, 3])

    def test_empty_list(self):
        self.assertEqual(jsonutils.to_primitive([]), [])

    def test_tuple(self):
        self.assertEqual(jsonutils.to_primitive((1, 2, 3)), [1, 2, 3])

    def test_dict(self):
        self.assertEqual(jsonutils.to_primitive(dict(a=1, b=2, c=3)),
                         dict(a=1, b=2, c=3))

    def test_empty_dict(self):
        self.assertEqual(jsonutils.to_primitive({}), {})

    def test_datetime(self):
        x = datetime.datetime(1920, 2, 3, 4, 5, 6, 7)
        self.assertEqual(jsonutils.to_primitive(x),
                         '1920-02-03T04:05:06.000007')

    def test_datetime_preserve(self):
        x = datetime.datetime(1920, 2, 3, 4, 5, 6, 7)
        self.assertEqual(jsonutils.to_primitive(x, convert_datetime=False), x)

    def test_DateTime(self):
        x = xmlrpclib.DateTime()
        x.decode("19710203T04:05:06")
        self.assertEqual(jsonutils.to_primitive(x),
                         '1971-02-03T04:05:06.000000')

    def test_iter(self):
        class IterClass(object):
            def __init__(self):
                self.data = [1, 2, 3, 4, 5]
                self.index = 0

            def __iter__(self):
                return self

            def next(self):
                if self.index == len(self.data):
                    raise StopIteration
                self.index = self.index + 1
                return self.data[self.index - 1]
            __next__ = next

        x = IterClass()
        self.assertEqual(jsonutils.to_primitive(x), [1, 2, 3, 4, 5])

    def test_iteritems(self):
        class IterItemsClass(object):
            def __init__(self):
                self.data = dict(a=1, b=2, c=3).items()
                self.index = 0

            def iteritems(self):
                return self.data

        x = IterItemsClass()
        p = jsonutils.to_primitive(x)
        self.assertEqual(p, {'a': 1, 'b': 2, 'c': 3})

    def test_iteritems_with_cycle(self):
        class IterItemsClass(object):
            def __init__(self):
                self.data = dict(a=1, b=2, c=3)
                self.index = 0

            def iteritems(self):
                return self.data.items()

        x = IterItemsClass()
        x2 = IterItemsClass()
        x.data['other'] = x2
        x2.data['other'] = x

        # If the cycle isn't caught, to_primitive() will eventually result in
        # an exception due to excessive recursion depth.
        jsonutils.to_primitive(x)

    def test_instance(self):
        class MysteryClass(object):
            a = 10

            def __init__(self):
                self.b = 1

        x = MysteryClass()
        self.assertEqual(jsonutils.to_primitive(x, convert_instances=True),
                         dict(b=1))

        self.assertEqual(jsonutils.to_primitive(x), x)

    def test_typeerror(self):
        x = bytearray  # Class, not instance
        if six.PY3:
            self.assertEqual(jsonutils.to_primitive(x), u"<class 'bytearray'>")
        else:
            self.assertEqual(jsonutils.to_primitive(x), u"<type 'bytearray'>")

    def test_nasties(self):
        def foo():
            pass
        x = [datetime, foo, dir]
        ret = jsonutils.to_primitive(x)
        self.assertEqual(len(ret), 3)
        self.assertTrue(ret[0].startswith(u"<module 'datetime' from "))
        if six.PY3:
            self.assertTrue(ret[1].startswith('<function '
                            'ToPrimitiveTestCase.test_nasties.<locals>.foo '
                            'at 0x'))
        else:
            self.assertTrue(ret[1].startswith('<function foo at 0x'))
        self.assertEqual(ret[2], '<built-in function dir>')

    def test_depth(self):
        class LevelsGenerator(object):
            def __init__(self, levels):
                self._levels = levels

            def iteritems(self):
                if self._levels == 0:
                    return iter([])
                else:
                    return iter([(0, LevelsGenerator(self._levels - 1))])

        l4_obj = LevelsGenerator(4)

        json_l2 = {0: {0: '?'}}
        json_l3 = {0: {0: {0: '?'}}}
        json_l4 = {0: {0: {0: {0: '?'}}}}

        ret = jsonutils.to_primitive(l4_obj, max_depth=2)
        self.assertEqual(ret, json_l2)

        ret = jsonutils.to_primitive(l4_obj, max_depth=3)
        self.assertEqual(ret, json_l3)

        ret = jsonutils.to_primitive(l4_obj, max_depth=4)
        self.assertEqual(ret, json_l4)

    def test_ipaddr(self):
        thing = {'ip_addr': netaddr.IPAddress('1.2.3.4')}
        ret = jsonutils.to_primitive(thing)
        self.assertEqual({'ip_addr': '1.2.3.4'}, ret)

    def test_message_with_param(self):
        message_with_params = 'A message with param: %s'
        msg = gettextutils.Message(message_with_params, domain='test_domain')
        msg = msg % 'test_domain'
        ret = jsonutils.to_primitive(msg)
        self.assertEqual(msg, ret)

    def test_message_with_named_param(self):
        message_with_params = 'A message with params: %(param)s'
        msg = gettextutils.Message(message_with_params, domain='test_domain')
        msg = msg % {'param': 'hello'}
        ret = jsonutils.to_primitive(msg)
        self.assertEqual(msg, ret)
