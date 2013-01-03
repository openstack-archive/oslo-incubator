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
import unittest

import iso8601
import mock

from openstack.common import timeutils


class TimeUtilsTest(unittest.TestCase):

    def setUp(self):
        self.skynet_self_aware_time_str = '1997-08-29T06:14:00Z'
        self.skynet_self_aware_time = datetime.datetime(1997, 8, 29, 6, 14, 0)
        self.one_minute_before = datetime.datetime(1997, 8, 29, 6, 13, 0)
        self.one_minute_after = datetime.datetime(1997, 8, 29, 6, 15, 0)
        self.skynet_self_aware_time_perfect_str = '1997-08-29T06:14:00.000000'
        self.skynet_self_aware_time_perfect = datetime.datetime(1997, 8, 29,
                                                                6, 14, 0)

    def tearDown(self):
        timeutils.clear_time_override()

    def test_isotime(self):
        with mock.patch('datetime.datetime') as datetime_mock:
            datetime_mock.utcnow.return_value = self.skynet_self_aware_time
            dt = timeutils.isotime()
            self.assertEqual(dt, self.skynet_self_aware_time_str)

    def test_parse_isotime(self):
        expect = timeutils.parse_isotime(self.skynet_self_aware_time_str)
        skynet_self_aware_time_utc = self.skynet_self_aware_time.replace(
            tzinfo=iso8601.iso8601.UTC)
        self.assertEqual(skynet_self_aware_time_utc, expect)

    def test_strtime(self):
        expect = timeutils.strtime(self.skynet_self_aware_time_perfect)
        self.assertEqual(self.skynet_self_aware_time_perfect_str, expect)

    def test_parse_strtime(self):
        perfect_time_format = self.skynet_self_aware_time_perfect_str
        expect = timeutils.parse_strtime(perfect_time_format)
        self.assertEqual(self.skynet_self_aware_time_perfect, expect)

    def test_strtime_and_back(self):
        orig_t = datetime.datetime(1997, 8, 29, 6, 14, 0)
        s = timeutils.strtime(orig_t)
        t = timeutils.parse_strtime(s)
        self.assertEqual(orig_t, t)

    def _test_is_older_than(self, fn):
        strptime = datetime.datetime.strptime
        with mock.patch('datetime.datetime') as datetime_mock:
            datetime_mock.utcnow.return_value = self.skynet_self_aware_time
            datetime_mock.strptime = strptime
            expect_true = timeutils.is_older_than(fn(self.one_minute_before),
                                                  59)
            self.assertTrue(expect_true)
            expect_false = timeutils.is_older_than(fn(self.one_minute_before),
                                                   60)
            self.assertFalse(expect_false)
            expect_false = timeutils.is_older_than(fn(self.one_minute_before),
                                                   61)
            self.assertFalse(expect_false)

    def test_is_older_than_datetime(self):
        self._test_is_older_than(lambda x: x)

    def test_is_older_than_str(self):
        self._test_is_older_than(timeutils.strtime)

    def _test_is_newer_than(self, fn):
        strptime = datetime.datetime.strptime
        with mock.patch('datetime.datetime') as datetime_mock:
            datetime_mock.utcnow.return_value = self.skynet_self_aware_time
            datetime_mock.strptime = strptime
            expect_true = timeutils.is_newer_than(fn(self.one_minute_after),
                                                  59)
            self.assertTrue(expect_true)
            expect_false = timeutils.is_newer_than(fn(self.one_minute_after),
                                                   60)
            self.assertFalse(expect_false)
            expect_false = timeutils.is_newer_than(fn(self.one_minute_after),
                                                   61)
            self.assertFalse(expect_false)

    def test_is_newer_than_datetime(self):
        self._test_is_newer_than(lambda x: x)

    def test_is_newer_than_str(self):
        self._test_is_newer_than(timeutils.strtime)

    def test_utcnow_ts(self):
        skynet_self_aware_timestamp = 872835240
        dt = datetime.datetime.utcfromtimestamp(skynet_self_aware_timestamp)
        self.assertEqual(self.skynet_self_aware_time, dt)
        with mock.patch('datetime.datetime') as datetime_mock:
            datetime_mock.utcnow.return_value = self.skynet_self_aware_time
            ts = timeutils.utcnow_ts()
            self.assertEqual(ts, skynet_self_aware_timestamp)

    def test_utcnow(self):
        timeutils.set_time_override(mock.sentinel.utcnow)
        self.assertEqual(timeutils.utcnow(), mock.sentinel.utcnow)

        timeutils.clear_time_override()
        self.assertFalse(timeutils.utcnow() == mock.sentinel.utcnow)

        self.assertTrue(timeutils.utcnow())

    def test_advance_time_delta(self):
        timeutils.set_time_override(self.one_minute_before)
        timeutils.advance_time_delta(datetime.timedelta(seconds=60))
        self.assertEqual(timeutils.utcnow(), self.skynet_self_aware_time)

    def test_advance_time_seconds(self):
        timeutils.set_time_override(self.one_minute_before)
        timeutils.advance_time_seconds(60)
        self.assertEqual(timeutils.utcnow(), self.skynet_self_aware_time)

    def test_marshall_time(self):
        now = timeutils.utcnow()
        binary = timeutils.marshall_now(now)
        backagain = timeutils.unmarshall_time(binary)
        self.assertEqual(now, backagain)

    def test_delta_seconds(self):
        before = timeutils.utcnow()
        after = before + datetime.timedelta(days=7, seconds=59,
                                            microseconds=123456)
        self.assertAlmostEquals(604859.123456,
                                timeutils.delta_seconds(before, after))


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
        timestamp = timeutils.parse_isotime(str)
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
        zulu = timeutils.parse_isotime('2012-02-14T20:53:07')
        east = timeutils.parse_isotime('2012-02-14T20:53:07-01:00')
        west = timeutils.parse_isotime('2012-02-14T20:53:07+01:00')
        self.assertTrue(east > west)
        self.assertTrue(east > zulu)
        self.assertTrue(zulu > west)

    def test_compare_micros(self):
        zulu = timeutils.parse_isotime('2012-02-14T20:53:07.6544')
        east = timeutils.parse_isotime('2012-02-14T19:53:07.654321-01:00')
        west = timeutils.parse_isotime('2012-02-14T21:53:07.655+01:00')
        self.assertTrue(east < west)
        self.assertTrue(east < zulu)
        self.assertTrue(zulu < west)

    def test_zulu_roundtrip(self):
        str = '2012-02-14T20:53:07Z'
        zulu = timeutils.parse_isotime(str)
        self.assertEquals(zulu.tzinfo, iso8601.iso8601.UTC)
        self.assertEquals(timeutils.isotime(zulu), str)

    def test_east_roundtrip(self):
        str = '2012-02-14T20:53:07-07:00'
        east = timeutils.parse_isotime(str)
        self.assertEquals(east.tzinfo.tzname(None), '-07:00')
        self.assertEquals(timeutils.isotime(east), str)

    def test_west_roundtrip(self):
        str = '2012-02-14T20:53:07+11:30'
        west = timeutils.parse_isotime(str)
        self.assertEquals(west.tzinfo.tzname(None), '+11:30')
        self.assertEquals(timeutils.isotime(west), str)

    def test_now_roundtrip(self):
        str = timeutils.isotime()
        now = timeutils.parse_isotime(str)
        self.assertEquals(now.tzinfo, iso8601.iso8601.UTC)
        self.assertEquals(timeutils.isotime(now), str)

    def test_zulu_normalize(self):
        str = '2012-02-14T20:53:07Z'
        zulu = timeutils.parse_isotime(str)
        normed = timeutils.normalize_time(zulu)
        self._instaneous(normed, 2012, 2, 14, 20, 53, 07, 0)

    def test_east_normalize(self):
        str = '2012-02-14T20:53:07-07:00'
        east = timeutils.parse_isotime(str)
        normed = timeutils.normalize_time(east)
        self._instaneous(normed, 2012, 2, 15, 03, 53, 07, 0)

    def test_west_normalize(self):
        str = '2012-02-14T20:53:07+21:00'
        west = timeutils.parse_isotime(str)
        normed = timeutils.normalize_time(west)
        self._instaneous(normed, 2012, 2, 13, 23, 53, 07, 0)

    def test_normalize_aware_to_naive(self):
        dt = datetime.datetime(2011, 2, 14, 20, 53, 07)
        str = '2011-02-14T20:53:07+21:00'
        aware = timeutils.parse_isotime(str)
        naive = timeutils.normalize_time(aware)
        self.assertTrue(naive < dt)

    def test_normalize_zulu_aware_to_naive(self):
        dt = datetime.datetime(2011, 2, 14, 20, 53, 07)
        str = '2011-02-14T19:53:07Z'
        aware = timeutils.parse_isotime(str)
        naive = timeutils.normalize_time(aware)
        self.assertTrue(naive < dt)

    def test_normalize_naive(self):
        dt = datetime.datetime(2011, 2, 14, 20, 53, 07)
        dtn = datetime.datetime(2011, 2, 14, 19, 53, 07)
        naive = timeutils.normalize_time(dtn)
        self.assertTrue(naive < dt)
