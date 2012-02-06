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

import datetime
import sys
import unittest

import mock

from openstack.common import exception
from openstack.common import utils
from openstack.common import setuputils


class UtilsTest(unittest.TestCase):

    def test_bool_bool_from_string(self):
        self.assertTrue(utils.bool_from_string(True))
        self.assertFalse(utils.bool_from_string(False))

    def test_str_bool_from_string(self):
        self.assertTrue(utils.bool_from_string('true'))
        self.assertTrue(utils.bool_from_string('TRUE'))
        self.assertTrue(utils.bool_from_string('on'))
        self.assertTrue(utils.bool_from_string('on'))
        self.assertTrue(utils.bool_from_string('1'))

        self.assertFalse(utils.bool_from_string('false'))
        self.assertFalse(utils.bool_from_string('FALSE'))
        self.assertFalse(utils.bool_from_string('off'))
        self.assertFalse(utils.bool_from_string('OFF'))
        self.assertFalse(utils.bool_from_string('0'))
        self.assertFalse(utils.bool_from_string('42'))
        self.assertFalse(utils.bool_from_string('This should not be True'))

    def test_unicode_bool_from_string(self):
        self.assertTrue(utils.bool_from_string(u'true'))
        self.assertTrue(utils.bool_from_string(u'TRUE'))
        self.assertTrue(utils.bool_from_string(u'on'))
        self.assertTrue(utils.bool_from_string(u'on'))
        self.assertTrue(utils.bool_from_string(u'1'))

        self.assertFalse(utils.bool_from_string(u'false'))
        self.assertFalse(utils.bool_from_string(u'FALSE'))
        self.assertFalse(utils.bool_from_string(u'off'))
        self.assertFalse(utils.bool_from_string(u'OFF'))
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

    # NOTE(jkoelker) There has GOT to be a way to test this. But mocking
    #                __import__ is the devil. Right now we just make
    #               sure we can import something from the stdlib
    def test_import_class(self):
        dt = utils.import_class('datetime.datetime')
        self.assertEqual(sys.modules['datetime'].datetime, dt)

    def test_import_bad_class(self):
        self.assertRaises(exception.NotFound, utils.import_class,
                          'lol.u_mad.brah')

    def test_import_object(self):
        dt = utils.import_object('datetime')
        self.assertEqual(sys.modules['datetime'], dt)

    def test_import_object_class(self):
        dt = utils.import_object('datetime.datetime')
        self.assertEqual(sys.modules['datetime'].datetime, dt)

    def test_isotime(self):
        skynet_self_aware_time_str = '1997-08-29T06:14:00Z'
        skynet_self_aware_time = datetime.datetime(1997, 8, 29, 6, 14, 0)
        with mock.patch('datetime.datetime') as datetime_mock:
            datetime_mock.utcnow.return_value = skynet_self_aware_time
            dt = utils.isotime()
            self.assertEqual(dt, skynet_self_aware_time_str)

    def test_parse_isotime(self):
        skynet_self_aware_time_str = '1997-08-29T06:14:00Z'
        skynet_self_aware_time = datetime.datetime(1997, 8, 29, 6, 14, 0)
        self.assertEqual(skynet_self_aware_time,
                         utils.parse_isotime(skynet_self_aware_time_str))

    def test_str_dict_replace(self):
        string = 'Johnnie T. Hozer'
        mapping = {'T.': 'The'}
        self.assertEqual('Johnnie The Hozer',
                         setuputils.str_dict_replace(string, mapping))

    def test_utcnow(self):
        utils.set_time_override(mock.sentinel.utcnow)
        self.assertEqual(utils.utcnow(), mock.sentinel.utcnow)

        utils.clear_time_override()
        self.assertFalse(utils.utcnow() == mock.sentinel.utcnow)

        self.assertTrue(utils.utcnow())
