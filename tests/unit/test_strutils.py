# -*- coding: utf-8 -*-
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
from openstack.common import test


class StrUtilsTest(test.BaseTestCase):

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
        self.assertTrue(strutils.bool_from_string(c(' 1 ')))
        self.assertTrue(strutils.bool_from_string(c(' true ')))
        self.assertFalse(strutils.bool_from_string(c(' 0 ')))
        self.assertFalse(strutils.bool_from_string(c(' false ')))

    def test_bool_from_string(self):
        self._test_bool_from_string(lambda s: s)

    def test_unicode_bool_from_string(self):
        self._test_bool_from_string(six.text_type)
        self.assertFalse(strutils.bool_from_string(u'使用', strict=False))

        exc = self.assertRaises(ValueError, strutils.bool_from_string,
                                u'使用', strict=True)
        expected_msg = (u"Unrecognized value '使用', acceptable values are:"
                        u" '0', '1', 'f', 'false', 'n', 'no', 'off', 'on',"
                        u" 't', 'true', 'y', 'yes'")
        self.assertEqual(expected_msg, unicode(exc))

    def test_other_bool_from_string(self):
        self.assertFalse(strutils.bool_from_string(None))
        self.assertFalse(strutils.bool_from_string(mock.Mock()))

    def test_int_bool_from_string(self):
        self.assertTrue(strutils.bool_from_string(1))

        self.assertFalse(strutils.bool_from_string(-1))
        self.assertFalse(strutils.bool_from_string(0))
        self.assertFalse(strutils.bool_from_string(2))

    def test_strict_bool_from_string(self):
        # None isn't allowed in strict mode
        exc = self.assertRaises(ValueError, strutils.bool_from_string, None,
                                strict=True)
        expected_msg = ("Unrecognized value 'None', acceptable values are:"
                        " '0', '1', 'f', 'false', 'n', 'no', 'off', 'on',"
                        " 't', 'true', 'y', 'yes'")
        self.assertEqual(expected_msg, str(exc))

        # Unrecognized strings aren't allowed
        self.assertFalse(strutils.bool_from_string('Other', strict=False))
        exc = self.assertRaises(ValueError, strutils.bool_from_string, 'Other',
                                strict=True)
        expected_msg = ("Unrecognized value 'Other', acceptable values are:"
                        " '0', '1', 'f', 'false', 'n', 'no', 'off', 'on',"
                        " 't', 'true', 'y', 'yes'")
        self.assertEqual(expected_msg, str(exc))

        # Unrecognized numbers aren't allowed
        exc = self.assertRaises(ValueError, strutils.bool_from_string, 2,
                                strict=True)
        expected_msg = ("Unrecognized value '2', acceptable values are:"
                        " '0', '1', 'f', 'false', 'n', 'no', 'off', 'on',"
                        " 't', 'true', 'y', 'yes'")
        self.assertEqual(expected_msg, str(exc))

        # False-like values are allowed
        self.assertFalse(strutils.bool_from_string('f', strict=True))
        self.assertFalse(strutils.bool_from_string('false', strict=True))
        self.assertFalse(strutils.bool_from_string('off', strict=True))
        self.assertFalse(strutils.bool_from_string('n', strict=True))
        self.assertFalse(strutils.bool_from_string('no', strict=True))
        self.assertFalse(strutils.bool_from_string('0', strict=True))

        self.assertTrue(strutils.bool_from_string('1', strict=True))

        # Avoid font-similarity issues (one looks like lowercase-el, zero like
        # oh, etc...)
        for char in ('O', 'o', 'L', 'l', 'I', 'i'):
            self.assertRaises(ValueError, strutils.bool_from_string, char,
                              strict=True)

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

    def test_string_conversions(self):
        working_examples = {
            '1024KB': 1048576,
            '1024TB': 1125899906842624,
            '1024K': 1048576,
            '1024T': 1125899906842624,
            '1TB': 1099511627776,
            '1T': 1099511627776,
            '1KB': 1024,
            '1K': 1024,
            '1B': 1,
            '1': 1,
            '1MB': 1048576,
            '7MB': 7340032,
            '0MB': 0,
            '0KB': 0,
            '0TB': 0,
            '': 0,
        }
        for (in_value, expected_value) in working_examples.items():
            b_value = strutils.to_bytes(in_value)
            self.assertEqual(expected_value, b_value)
            if in_value:
                in_value = "-" + in_value
                b_value = strutils.to_bytes(in_value)
                self.assertEqual(expected_value * -1, b_value)
        breaking_examples = [
            'junk1KB', '1023BBBB',
        ]
        for v in breaking_examples:
            self.assertRaises(TypeError, strutils.to_bytes, v)

    def test_slugify(self):
        to_slug = strutils.to_slug
        self.assertRaises(TypeError, to_slug, True)
        self.assertEqual(six.u("hello"), to_slug("hello"))
        self.assertEqual(six.u("two-words"), to_slug("Two Words"))
        self.assertEqual(six.u("ma-any-spa-ce-es"),
                         to_slug("Ma-any\t spa--ce- es"))
        self.assertEqual(six.u("excamation"), to_slug("exc!amation!"))
        self.assertEqual(six.u("ampserand"), to_slug("&ampser$and"))
        self.assertEqual(six.u("ju5tnum8er"), to_slug("ju5tnum8er"))
        self.assertEqual(six.u("strip-"), to_slug(" strip - "))
        self.assertEqual(six.u("perche"), to_slug("perch\xc3\xa9"))
        self.assertEqual(six.u("strange"),
                         to_slug("\x80strange", errors="ignore"))


class MaskPasswordTestCase(test.BaseTestCase):

    def test_json(self):
        # Test 'adminPass' w/o spaces
        payload = """{'adminPass':'mypassword'}"""
        expected = """{'adminPass':'***'}"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'adminPass' with spaces
        payload = """{ 'adminPass' : 'mypassword' }"""
        expected = """{ 'adminPass' : '***' }"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_pass' w/o spaces
        payload = """{'admin_pass':'mypassword'}"""
        expected = """{'admin_pass':'***'}"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_pass' with spaces
        payload = """{ 'admin_pass' : 'mypassword' }"""
        expected = """{ 'admin_pass' : '***' }"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_password' w/o spaces
        payload = """{'admin_password':'mypassword'}"""
        expected = """{'admin_password':'***'}"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_password' with spaces
        payload = """{ 'admin_password' : 'mypassword' }"""
        expected = """{ 'admin_password' : '***' }"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'password' w/o spaces
        payload = """{'password':'mypassword'}"""
        expected = """{'password':'***'}"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'password' with spaces
        payload = """{ 'password' : 'mypassword' }"""
        expected = """{ 'password' : '***' }"""
        self.assertEqual(expected, strutils.mask_password(payload))

    def test_xml(self):
        # Test 'adminPass' w/o spaces
        payload = """<adminPass>mypassword</adminPass>"""
        expected = """<adminPass>***</adminPass>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'adminPass' with spaces
        payload = """<adminPass>
                        mypassword
                     </adminPass>"""
        expected = """<adminPass>***</adminPass>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_pass' w/o spaces
        payload = """<admin_pass>mypassword</admin_pass>"""
        expected = """<admin_pass>***</admin_pass>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_pass' with spaces
        payload = """<admin_pass>
                        mypassword
                     </admin_pass>"""
        expected = """<admin_pass>***</admin_pass>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_password' w/o spaces
        payload = """<admin_password>mypassword</admin_password>"""
        expected = """<admin_password>***</admin_password>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_password' with spaces
        payload = """<admin_password>
                        mypassword
                     </admin_password>"""
        expected = """<admin_password>***</admin_password>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'password' w/o spaces
        payload = """<password>mypassword</password>"""
        expected = """<password>***</password>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'password' with spaces
        payload = """<password>
                        mypassword
                     </password>"""
        expected = """<password>***</password>"""
        self.assertEqual(expected, strutils.mask_password(payload))

    def test_xml_attribute(self):
        # Test 'adminPass' w/o spaces
        payload = """adminPass='mypassword'"""
        expected = """adminPass='***'"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'adminPass' with spaces
        payload = """adminPass = 'mypassword'"""
        expected = """adminPass = '***'"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'adminPass' with double quotes
        payload = """adminPass = "mypassword\""""
        expected = """adminPass = "***\""""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_pass' w/o spaces
        payload = """admin_pass='mypassword'"""
        expected = """admin_pass='***'"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_pass' with spaces
        payload = """admin_pass = 'mypassword'"""
        expected = """admin_pass = '***'"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_pass' with double quotes
        payload = """admin_pass = "mypassword\""""
        expected = """admin_pass = "***\""""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_password' w/o spaces
        payload = """admin_password='mypassword'"""
        expected = """admin_password='***'"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_password' with spaces
        payload = """admin_password = 'mypassword'"""
        expected = """admin_password = '***'"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'admin_password' with double quotes
        payload = """admin_password = "mypassword\""""
        expected = """admin_password = "***\""""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'password' w/o spaces
        payload = """password='mypassword'"""
        expected = """password='***'"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'password' with spaces
        payload = """password = 'mypassword'"""
        expected = """password = '***'"""
        self.assertEqual(expected, strutils.mask_password(payload))
        # Test 'password' with double quotes
        payload = """password = "mypassword\""""
        expected = """password = "***\""""
        self.assertEqual(expected, strutils.mask_password(payload))

    def test_json_message(self):
        payload = """body: {"changePassword": {"adminPass": "1234567"}}"""
        expected = """body: {"changePassword": {"adminPass": "***"}}"""
        self.assertEqual(expected, strutils.mask_password(payload))
        payload = """body: {"rescue": {"admin_pass": "1234567"}}"""
        expected = """body: {"rescue": {"admin_pass": "***"}}"""
        self.assertEqual(expected, strutils.mask_password(payload))
        payload = """body: {"rescue": {"admin_password": "1234567"}}"""
        expected = """body: {"rescue": {"admin_password": "***"}}"""
        self.assertEqual(expected, strutils.mask_password(payload))
        payload = """body: {"rescue": {"password": "1234567"}}"""
        expected = """body: {"rescue": {"password": "***"}}"""
        self.assertEqual(expected, strutils.mask_password(payload))

    def test_xml_message(self):
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<rebuild
    xmlns="http://docs.openstack.org/compute/api/v1.1"
    name="foobar"
    imageRef="http://openstack.example.com/v1.1/32278/images/70a599e0-31e7"
    accessIPv4="1.2.3.4"
    accessIPv6="fe80::100"
    adminPass="seekr3t">
  <metadata>
    <meta key="My Server Name">Apache1</meta>
  </metadata>
</rebuild>"""
        expected = """<?xml version="1.0" encoding="UTF-8"?>
<rebuild
    xmlns="http://docs.openstack.org/compute/api/v1.1"
    name="foobar"
    imageRef="http://openstack.example.com/v1.1/32278/images/70a599e0-31e7"
    accessIPv4="1.2.3.4"
    accessIPv6="fe80::100"
    adminPass="***">
  <metadata>
    <meta key="My Server Name">Apache1</meta>
  </metadata>
</rebuild>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    admin_pass="MySecretPass"/>"""
        expected = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    admin_pass="***"/>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    admin_password="MySecretPass"/>"""
        expected = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    admin_password="***"/>"""
        self.assertEqual(expected, strutils.mask_password(payload))
        payload = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    password="MySecretPass"/>"""
        expected = """<?xml version="1.0" encoding="UTF-8"?>
<rescue xmlns="http://docs.openstack.org/compute/api/v1.1"
    password="***"/>"""
        self.assertEqual(expected, strutils.mask_password(payload))

    def test_mask_password(self):
        payload = "test = 'password'  :   'aaaaaa'"
        expected = "test = 'password'  :   '111'"
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='111'))

        payload = 'mysqld --password "aaaaaa"'
        expected = 'mysqld --password "****"'
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='****'))

        payload = 'mysqld --password aaaaaa'
        expected = 'mysqld --password ???'
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='???'))

        payload = 'mysqld --password = "aaaaaa"'
        expected = 'mysqld --password = "****"'
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='****'))

        payload = "mysqld --password = 'aaaaaa'"
        expected = "mysqld --password = '****'"
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='****'))

        payload = "mysqld --password = aaaaaa"
        expected = "mysqld --password = ****"
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='****'))

        payload = "test = password =   aaaaaa"
        expected = "test = password =   111"
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='111'))

        payload = "test = password=   aaaaaa"
        expected = "test = password=   111"
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='111'))

        payload = "test = password =aaaaaa"
        expected = "test = password =111"
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='111'))

        payload = "test = password=aaaaaa"
        expected = "test = password=111"
        self.assertEqual(expected,
                         strutils.mask_password(payload, secret='111'))

        payload = 'test = "original_password" : "aaaaaaaaa"'
        expected = 'test = "original_password" : "***"'
        self.assertEqual(expected, strutils.mask_password(payload))

        payload = 'test = "param1" : "value"'
        expected = 'test = "param1" : "value"'
        self.assertEqual(expected, strutils.mask_password(payload))

        payload = """{'adminPass':'mypassword'}"""
        payload = six.text_type(payload)
        expected = """{'adminPass':'***'}"""
        self.assertEqual(expected, strutils.mask_password(payload))

        payload = ("test = 'node.session.auth.password','-v','mypassword',"
                   "'nomask'")
        expected = ("test = 'node.session.auth.password','-v','***',"
                    "'nomask'")
        self.assertEqual(expected, strutils.mask_password(payload))

        payload = ("test = 'node.session.auth.password', '--password', "
                   "'mypassword', 'nomask'")
        expected = ("test = 'node.session.auth.password', '--password', "
                    "'***', 'nomask'")
        self.assertEqual(expected, strutils.mask_password(payload))

        payload = ("test = 'node.session.auth.password', '--password', "
                   "'mypassword'")
        expected = ("test = 'node.session.auth.password', '--password', "
                    "'***'")
        self.assertEqual(expected, strutils.mask_password(payload))

        payload = "test = node.session.auth.password -v mypassword nomask"
        expected = "test = node.session.auth.password -v *** nomask"
        self.assertEqual(expected, strutils.mask_password(payload))

        payload = ("test = node.session.auth.password --password mypassword "
                   "nomask")
        expected = ("test = node.session.auth.password --password *** "
                    "nomask")
        self.assertEqual(expected, strutils.mask_password(payload))

        payload = ("test = node.session.auth.password --password mypassword")
        expected = ("test = node.session.auth.password --password ***")
        self.assertEqual(expected, strutils.mask_password(payload))
