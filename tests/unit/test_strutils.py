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
import six

from openstack.common import strutils
from tests import utils


class StrUtilsTest(utils.BaseTestCase):

    def test_bool_bool_from_string(self):
        self.assertTrue(strutils.bool_from_string(True))
        self.assertFalse(strutils.bool_from_string(False))

    def _test_bool_from_string(self, c):
        self.assertTrue(strutils.bool_from_string(c('true')))
        self.assertTrue(strutils.bool_from_string(c('TRUE')))
        self.assertTrue(strutils.bool_from_string(c('on')))
        self.assertTrue(strutils.bool_from_string(c('On')))
        self.assertTrue(strutils.bool_from_string(c('yes')))
        self.assertTrue(strutils.bool_from_string(c('YES')))
        self.assertTrue(strutils.bool_from_string(c('yEs')))
        self.assertTrue(strutils.bool_from_string(c('1')))
        self.assertTrue(strutils.bool_from_string(c('T')))
        self.assertTrue(strutils.bool_from_string(c('t')))
        self.assertTrue(strutils.bool_from_string(c('Y')))
        self.assertTrue(strutils.bool_from_string(c('y')))

        self.assertFalse(strutils.bool_from_string(c('false')))
        self.assertFalse(strutils.bool_from_string(c('FALSE')))
        self.assertFalse(strutils.bool_from_string(c('off')))
        self.assertFalse(strutils.bool_from_string(c('OFF')))
        self.assertFalse(strutils.bool_from_string(c('no')))
        self.assertFalse(strutils.bool_from_string(c('0')))
        self.assertFalse(strutils.bool_from_string(c('42')))
        self.assertFalse(strutils.bool_from_string(c(
                         'This should not be True')))
        self.assertFalse(strutils.bool_from_string(c('F')))
        self.assertFalse(strutils.bool_from_string(c('f')))
        self.assertFalse(strutils.bool_from_string(c('N')))
        self.assertFalse(strutils.bool_from_string(c('n')))

        # Whitespace should be stripped
        self.assertTrue(strutils.bool_from_string(c(' true ')))
        self.assertFalse(strutils.bool_from_string(c(' false ')))

    def test_bool_from_string(self):
        self._test_bool_from_string(lambda s: s)

    def test_unicode_bool_from_string(self):
        self._test_bool_from_string(six.text_type)

    def test_other_bool_from_string(self):
        self.assertFalse(strutils.bool_from_string(None))
        self.assertFalse(strutils.bool_from_string(mock.Mock()))

    def test_int_bool_from_string(self):
        self.assertTrue(strutils.bool_from_string(1))

        self.assertFalse(strutils.bool_from_string(-1))
        self.assertFalse(strutils.bool_from_string(0))
        self.assertFalse(strutils.bool_from_string(2))

    def test_strict_bool_from_string(self):
        self.assertFalse(strutils.bool_from_string('other', strict=False))
        self.assertRaises(ValueError, strutils.bool_from_string, 'other',
                          strict=True)

        self.assertFalse(strutils.bool_from_string('f', strict=True))
        self.assertFalse(strutils.bool_from_string('false', strict=True))
        self.assertFalse(strutils.bool_from_string('off', strict=True))
        self.assertFalse(strutils.bool_from_string('n', strict=True))
        self.assertFalse(strutils.bool_from_string('no', strict=True))

    def test_int_from_bool_as_string(self):
        self.assertEqual(1, strutils.int_from_bool_as_string(True))
        self.assertEqual(0, strutils.int_from_bool_as_string(False))

    def test_safe_decode(self):
        safe_decode = strutils.safe_decode
        self.assertRaises(TypeError, safe_decode, True)
        self.assertEqual(six.u('ni\xf1o'), safe_decode("ni\xc3\xb1o",
                         incoming="utf-8"))
        self.assertEqual(six.u("test"), safe_decode("dGVzdA==",
                         incoming='base64'))

        self.assertEqual(six.u("strange"), safe_decode('\x80strange',
                         errors='ignore'))

        self.assertEqual(six.u('\xc0'), safe_decode('\xc0',
                         incoming='iso-8859-1'))

        # Forcing incoming to ascii so it falls back to utf-8
        self.assertEqual(six.u('ni\xf1o'), safe_decode('ni\xc3\xb1o',
                         incoming='ascii'))

    def test_safe_encode(self):
        safe_encode = strutils.safe_encode
        self.assertRaises(TypeError, safe_encode, True)
        self.assertEqual("ni\xc3\xb1o", safe_encode(six.u('ni\xf1o'),
                                                    encoding="utf-8"))
        self.assertEqual("dGVzdA==\n", safe_encode("test",
                                                   encoding='base64'))
        self.assertEqual('ni\xf1o', safe_encode("ni\xc3\xb1o",
                                                encoding="iso-8859-1",
                                                incoming="utf-8"))

        # Forcing incoming to ascii so it falls back to utf-8
        self.assertEqual('ni\xc3\xb1o', safe_encode('ni\xc3\xb1o',
                                                    incoming='ascii'))
