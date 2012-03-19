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

import iso8601
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
        skynet_self_aware_time = datetime.datetime(1997, 8, 29, 6, 14, 0,
                                                   tzinfo=iso8601.iso8601.UTC)
        with mock.patch('datetime.datetime') as datetime_mock:
            datetime_mock.utcnow.return_value = skynet_self_aware_time
            dt = utils.isotime()
            self.assertEqual(dt, skynet_self_aware_time_str)

    def test_parse_isotime(self):
        skynet_self_aware_time_str = '1997-08-29T06:14:00Z'
        skynet_self_aware_time = datetime.datetime(1997, 8, 29, 6, 14, 0,
                                                   tzinfo=iso8601.iso8601.UTC)
        self.assertEqual(skynet_self_aware_time,
                         utils.parse_isotime(skynet_self_aware_time_str))

    def test_utcnow(self):
        utils.set_time_override(mock.sentinel.utcnow)
        self.assertEqual(utils.utcnow(), mock.sentinel.utcnow)

        utils.clear_time_override()
        self.assertFalse(utils.utcnow() == mock.sentinel.utcnow)

        self.assertTrue(utils.utcnow())

    def test_auth_str_equal(self):
        self.assertTrue(utils.auth_str_equal('abc123', 'abc123'))
        self.assertFalse(utils.auth_str_equal('a', 'aaaaa'))
        self.assertFalse(utils.auth_str_equal('aaaaa', 'a'))
        self.assertFalse(utils.auth_str_equal('ABC123', 'abc123'))


class TestIso8601Time(unittest.TestCase):

    def _instaneous(self, timestamp, yr, mon, day, hr, min, sec, micro):
        self.assertEquals(timestamp.year, yr)
        self.assertEquals(timestamp.month, mon)
        self.assertEquals(timestamp.day, day)
        self.assertEquals(timestamp.hour, hr)
        self.assertEquals(timestamp.minute, min)
        self.assertEquals(timestamp.second, sec)
        self.assertEquals(timestamp.microsecond, micro)

    def _do_test(self, str, yr, mon, day, hr, min, sec, micro, shift):
        DAY_SECONDS = 24 * 60 * 60
        timestamp = utils.parse_isotime(str)
        self._instaneous(timestamp, yr, mon, day, hr, min, sec, micro)
        offset = timestamp.tzinfo.utcoffset(None)
        self.assertEqual(offset.seconds + offset.days * DAY_SECONDS, shift)

    def test_zulu(self):
        str = '2012-02-14T20:53:07Z'
        self._do_test(str, 2012, 02, 14, 20, 53, 7, 0, 0)

    def test_zulu_micros(self):
        str = '2012-02-14T20:53:07.123Z'
        self._do_test(str, 2012, 02, 14, 20, 53, 7, 123000, 0)

    def test_offset_east(self):
        str = '2012-02-14T20:53:07+04:30'
        offset = 4.5 * 60 * 60
        self._do_test(str, 2012, 02, 14, 20, 53, 7, 0, offset)

    def test_offset_east_micros(self):
        str = '2012-02-14T20:53:07.42+04:30'
        offset = 4.5 * 60 * 60
        self._do_test(str, 2012, 02, 14, 20, 53, 7, 420000, offset)

    def test_offset_west(self):
        str = '2012-02-14T20:53:07-05:30'
        offset = -5.5 * 60 * 60
        self._do_test(str, 2012, 02, 14, 20, 53, 7, 0, offset)

    def test_offset_west_micros(self):
        str = '2012-02-14T20:53:07.654321-05:30'
        offset = -5.5 * 60 * 60
        self._do_test(str, 2012, 02, 14, 20, 53, 7, 654321, offset)

    def test_compare(self):
        zulu = utils.parse_isotime('2012-02-14T20:53:07')
        east = utils.parse_isotime('2012-02-14T20:53:07-01:00')
        west = utils.parse_isotime('2012-02-14T20:53:07+01:00')
        self.assertTrue(east > west)
        self.assertTrue(east > zulu)
        self.assertTrue(zulu > west)

    def test_compare_micros(self):
        zulu = utils.parse_isotime('2012-02-14T20:53:07.6544')
        east = utils.parse_isotime('2012-02-14T19:53:07.654321-01:00')
        west = utils.parse_isotime('2012-02-14T21:53:07.655+01:00')
        self.assertTrue(east < west)
        self.assertTrue(east < zulu)
        self.assertTrue(zulu < west)

    def test_zulu_roundtrip(self):
        str = '2012-02-14T20:53:07Z'
        zulu = utils.parse_isotime(str)
        self.assertEquals(zulu.tzinfo, iso8601.iso8601.UTC)
        self.assertEquals(utils.isotime(zulu), str)

    def test_east_roundtrip(self):
        str = '2012-02-14T20:53:07-07:00'
        east = utils.parse_isotime(str)
        self.assertEquals(east.tzinfo.tzname(None), '-07:00')
        self.assertEquals(utils.isotime(east), str)

    def test_west_roundtrip(self):
        str = '2012-02-14T20:53:07+11:30'
        west = utils.parse_isotime(str)
        self.assertEquals(west.tzinfo.tzname(None), '+11:30')
        self.assertEquals(utils.isotime(west), str)

    def test_now_roundtrip(self):
        str = utils.isotime()
        now = utils.parse_isotime(str)
        self.assertEquals(now.tzinfo, iso8601.iso8601.UTC)
        self.assertEquals(utils.isotime(now), str)

    def test_zulu_normalize(self):
        str = '2012-02-14T20:53:07Z'
        zulu = utils.parse_isotime(str)
        normed = utils.normalize_time(zulu)
        self._instaneous(normed, 2012, 2, 14, 20, 53, 07, 0)

    def test_east_normalize(self):
        str = '2012-02-14T20:53:07-07:00'
        east = utils.parse_isotime(str)
        normed = utils.normalize_time(east)
        self._instaneous(normed, 2012, 2, 15, 03, 53, 07, 0)

    def test_west_normalize(self):
        str = '2012-02-14T20:53:07+21:00'
        west = utils.parse_isotime(str)
        normed = utils.normalize_time(west)
        self._instaneous(normed, 2012, 2, 13, 23, 53, 07, 0)
