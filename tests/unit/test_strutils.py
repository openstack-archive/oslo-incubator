# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import mock

from openstack.common import strutils
from tests import utils


class StrUtilsTest(utils.BaseTestCase):

    def test_bool_bool_from_string(self):
        self.assertTrue(strutils.bool_from_string(True))
        self.assertFalse(strutils.bool_from_string(False))

    def test_str_bool_from_string(self):
        self.assertTrue(strutils.bool_from_string('true'))
        self.assertTrue(strutils.bool_from_string('TRUE'))
        self.assertTrue(strutils.bool_from_string('on'))
        self.assertTrue(strutils.bool_from_string('On'))
        self.assertTrue(strutils.bool_from_string('yes'))
        self.assertTrue(strutils.bool_from_string('YES'))
        self.assertTrue(strutils.bool_from_string('yEs'))
        self.assertTrue(strutils.bool_from_string('1'))

        self.assertFalse(strutils.bool_from_string('false'))
        self.assertFalse(strutils.bool_from_string('FALSE'))
        self.assertFalse(strutils.bool_from_string('off'))
        self.assertFalse(strutils.bool_from_string('OFF'))
        self.assertFalse(strutils.bool_from_string('no'))
        self.assertFalse(strutils.bool_from_string('0'))
        self.assertFalse(strutils.bool_from_string('42'))
        self.assertFalse(strutils.bool_from_string('This should not be True'))

    def test_unicode_bool_from_string(self):
        self.assertTrue(strutils.bool_from_string(u'true'))
        self.assertTrue(strutils.bool_from_string(u'TRUE'))
        self.assertTrue(strutils.bool_from_string(u'on'))
        self.assertTrue(strutils.bool_from_string(u'On'))
        self.assertTrue(strutils.bool_from_string(u'yes'))
        self.assertTrue(strutils.bool_from_string(u'YES'))
        self.assertTrue(strutils.bool_from_string(u'yEs'))
        self.assertTrue(strutils.bool_from_string(u'1'))

        self.assertFalse(strutils.bool_from_string(u'false'))
        self.assertFalse(strutils.bool_from_string(u'FALSE'))
        self.assertFalse(strutils.bool_from_string(u'off'))
        self.assertFalse(strutils.bool_from_string(u'OFF'))
        self.assertFalse(strutils.bool_from_string(u'no'))
        self.assertFalse(strutils.bool_from_string(u'NO'))
        self.assertFalse(strutils.bool_from_string(u'0'))
        self.assertFalse(strutils.bool_from_string(u'42'))
        self.assertFalse(strutils.bool_from_string(u'This should not be True'))

    def test_other_bool_from_string(self):
        self.assertFalse(strutils.bool_from_string(mock.Mock()))

    def test_int_from_bool_as_string(self):
        self.assertEqual(1, strutils.int_from_bool_as_string(True))
        self.assertEqual(0, strutils.int_from_bool_as_string(False))

    def test_safe_decode(self):
        safe_decode = strutils.safe_decode
        self.assertRaises(TypeError, safe_decode, True)
        self.assertEqual(u'ni\xf1o', safe_decode("ni\xc3\xb1o",
                                                 incoming="utf-8"))
        self.assertEqual(u"test", safe_decode("dGVzdA==",
                                              incoming='base64'))

        self.assertEqual(u"strange", safe_decode('\x80strange',
                                                 errors='ignore'))

        self.assertEqual(u'\xc0', safe_decode('\xc0',
                                              incoming='iso-8859-1'))

        # Forcing incoming to ascii so it falls back to utf-8
        self.assertEqual(u'ni\xf1o', safe_decode('ni\xc3\xb1o',
                                                 incoming='ascii'))

    def test_safe_encode(self):
        safe_encode = strutils.safe_encode
        self.assertRaises(TypeError, safe_encode, True)
        self.assertEqual("ni\xc3\xb1o", safe_encode(u'ni\xf1o',
                                                    encoding="utf-8"))
        self.assertEqual("dGVzdA==\n", safe_encode("test",
                                                   encoding='base64'))
        self.assertEqual('ni\xf1o', safe_encode("ni\xc3\xb1o",
                                                encoding="iso-8859-1",
                                                incoming="utf-8"))

        # Forcing incoming to ascii so it falls back to utf-8
        self.assertEqual('ni\xc3\xb1o', safe_encode('ni\xc3\xb1o',
                                                    incoming='ascii'))
