# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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

import unittest

import mock

from openstack.common import exception
from openstack.common import utils


class UtilsTest(unittest.TestCase):

    def test_bool_bool_from_string(self):
        self.assertTrue(utils.bool_from_string(True))
        self.assertFalse(utils.bool_from_string(False))

    def test_str_bool_from_string(self):
        self.assertTrue(utils.bool_from_string('true'))
        self.assertTrue(utils.bool_from_string('TRUE'))
        self.assertTrue(utils.bool_from_string('on'))
        self.assertTrue(utils.bool_from_string('On'))
        self.assertTrue(utils.bool_from_string('yes'))
        self.assertTrue(utils.bool_from_string('YES'))
        self.assertTrue(utils.bool_from_string('yEs'))
        self.assertTrue(utils.bool_from_string('1'))

        self.assertFalse(utils.bool_from_string('false'))
        self.assertFalse(utils.bool_from_string('FALSE'))
        self.assertFalse(utils.bool_from_string('off'))
        self.assertFalse(utils.bool_from_string('OFF'))
        self.assertFalse(utils.bool_from_string('no'))
        self.assertFalse(utils.bool_from_string('0'))
        self.assertFalse(utils.bool_from_string('42'))
        self.assertFalse(utils.bool_from_string('This should not be True'))

    def test_unicode_bool_from_string(self):
        self.assertTrue(utils.bool_from_string(u'true'))
        self.assertTrue(utils.bool_from_string(u'TRUE'))
        self.assertTrue(utils.bool_from_string(u'on'))
        self.assertTrue(utils.bool_from_string(u'On'))
        self.assertTrue(utils.bool_from_string(u'yes'))
        self.assertTrue(utils.bool_from_string(u'YES'))
        self.assertTrue(utils.bool_from_string(u'yEs'))
        self.assertTrue(utils.bool_from_string(u'1'))

        self.assertFalse(utils.bool_from_string(u'false'))
        self.assertFalse(utils.bool_from_string(u'FALSE'))
        self.assertFalse(utils.bool_from_string(u'off'))
        self.assertFalse(utils.bool_from_string(u'OFF'))
        self.assertFalse(utils.bool_from_string(u'no'))
        self.assertFalse(utils.bool_from_string(u'NO'))
        self.assertFalse(utils.bool_from_string(u'0'))
        self.assertFalse(utils.bool_from_string(u'42'))
        self.assertFalse(utils.bool_from_string(u'This should not be True'))

    def test_other_bool_from_string(self):
        self.assertFalse(utils.bool_from_string(mock.Mock()))

    def test_int_from_bool_as_string(self):
        self.assertEqual(1, utils.int_from_bool_as_string(True))
        self.assertEqual(0, utils.int_from_bool_as_string(False))

    # NOTE(jkoelker) Moar tests from nova need to be ported. But they
    #                need to be mock'd out. Currently they requre actually
    #                running code.
    def test_execute_unknown_kwargs(self):
        self.assertRaises(exception.Error, utils.execute, hozer=True)

    def test_parse_host_port(self):
        self.assertEqual(('server01', 80), utils.parse_host_port('server01:80'))
        self.assertEqual(('server01', None), utils.parse_host_port('server01'))
        self.assertEqual(('server01', 1234), utils.parse_host_port('server01', default_port=1234))
        self.assertEqual(('[::1]', 80), utils.parse_host_port('[::1]:80'))
        self.assertEqual(('[::1]', None), utils.parse_host_port('[::1]'))
        self.assertEqual(('[::1]', 1234), utils.parse_host_port('[::1]', default_port=1234))
