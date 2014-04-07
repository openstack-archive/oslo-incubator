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

"""
Time related utilities and helper functions.
"""

import calendar
import datetime
import logging
import os
import sys
import time

import iso8601
import six


# ISO 8601 extended time format with microseconds
_ISO8601_TIME_FORMAT_SUBSECOND = '%Y-%m-%dT%H:%M:%S.%f'
_ISO8601_TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
PERFECT_TIME_FORMAT = _ISO8601_TIME_FORMAT_SUBSECOND


def isotime(at=None, subsecond=False):
    """Stringify time in ISO 8601 format."""
    if not at:
        at = utcnow()
    st = at.strftime(_ISO8601_TIME_FORMAT
                     if not subsecond
                     else _ISO8601_TIME_FORMAT_SUBSECOND)
    tz = at.tzinfo.tzname(None) if at.tzinfo else 'UTC'
    st += ('Z' if tz == 'UTC' else tz)
    return st


def parse_isotime(timestr):
    """Parse time from ISO 8601 format."""
    try:
        return iso8601.parse_date(timestr)
    except iso8601.ParseError as e:
        raise ValueError(six.text_type(e))
    except TypeError as e:
        raise ValueError(six.text_type(e))


def strtime(at=None, fmt=PERFECT_TIME_FORMAT):
    """Returns formatted utcnow."""
    if not at:
        at = utcnow()
    return at.strftime(fmt)


def parse_strtime(timestr, fmt=PERFECT_TIME_FORMAT):
    """Turn a formatted time back into a datetime."""
    return datetime.datetime.strptime(timestr, fmt)


def normalize_time(timestamp):
    """Normalize time in arbitrary timezone to UTC naive object."""
    offset = timestamp.utcoffset()
    if offset is None:
        return timestamp
    return timestamp.replace(tzinfo=None) - offset


def is_older_than(before, seconds):
    """Return True if before is older than seconds."""
    if isinstance(before, six.string_types):
        before = parse_strtime(before).replace(tzinfo=None)
    else:
        before = before.replace(tzinfo=None)

    return utcnow() - before > datetime.timedelta(seconds=seconds)


def is_newer_than(after, seconds):
    """Return True if after is newer than seconds."""
    if isinstance(after, six.string_types):
        after = parse_strtime(after).replace(tzinfo=None)
    else:
        after = after.replace(tzinfo=None)

    return after - utcnow() > datetime.timedelta(seconds=seconds)


def utcnow_ts():
    """Timestamp version of our utcnow function."""
    if utcnow.override_time is None:
        # NOTE(kgriffs): This is several times faster
        # than going through calendar.timegm(...)
        return int(time.time())

    return calendar.timegm(utcnow().timetuple())


def utcnow():
    """Overridable version of utils.utcnow."""
    if utcnow.override_time:
        try:
            return utcnow.override_time.pop(0)
        except AttributeError:
            return utcnow.override_time
    return datetime.datetime.utcnow()


def iso8601_from_timestamp(timestamp):
    """Returns a iso8601 formatted date from timestamp."""
    return isotime(datetime.datetime.utcfromtimestamp(timestamp))


utcnow.override_time = None


def set_time_override(override_time=None):
    """Overrides utils.utcnow.

    Make it return a constant time or a list thereof, one at a time.

    :param override_time: datetime instance or list thereof. If not
                          given, defaults to the current UTC time.
    """
    utcnow.override_time = override_time or datetime.datetime.utcnow()


def advance_time_delta(timedelta):
    """Advance overridden time using a datetime.timedelta."""
    assert(not utcnow.override_time is None)
    try:
        for dt in utcnow.override_time:
            dt += timedelta
    except TypeError:
        utcnow.override_time += timedelta


def advance_time_seconds(seconds):
    """Advance overridden time by seconds."""
    advance_time_delta(datetime.timedelta(0, seconds))


def clear_time_override():
    """Remove the overridden time."""
    utcnow.override_time = None


def marshall_now(now=None):
    """Make an rpc-safe datetime with microseconds.

    Note: tzinfo is stripped, but not required for relative times.
    """
    if not now:
        now = utcnow()
    return dict(day=now.day, month=now.month, year=now.year, hour=now.hour,
                minute=now.minute, second=now.second,
                microsecond=now.microsecond)


def unmarshall_time(tyme):
    """Unmarshall a datetime dict."""
    return datetime.datetime(day=tyme['day'],
                             month=tyme['month'],
                             year=tyme['year'],
                             hour=tyme['hour'],
                             minute=tyme['minute'],
                             second=tyme['second'],
                             microsecond=tyme['microsecond'])


def delta_seconds(before, after):
    """Return the difference between two timing objects.

    Compute the difference in seconds between two date, time, or
    datetime objects (as a float, to microsecond resolution).
    """
    delta = after - before
    return total_seconds(delta)


def total_seconds(delta):
    """Return the total seconds of datetime.timedelta object.

    Compute total seconds of datetime.timedelta, datetime.timedelta
    doesn't have method total_seconds in Python2.6, calculate it manually.
    """
    try:
        return delta.total_seconds()
    except AttributeError:
        return ((delta.days * 24 * 3600) + delta.seconds +
                float(delta.microseconds) / (10 ** 6))


def is_soon(dt, window):
    """Determines if time is going to happen in the next window seconds.

    :param dt: the time
    :param window: minimum seconds to remain to consider the time not soon

    :return: True if expiration is within the given duration
    """
    soon = (utcnow() + datetime.timedelta(seconds=window))
    return normalize_time(dt) <= soon


# default implementation of time_monotonic(): system clock (may go backward!)
time_monotonic = time.time

# the worst resolution of time.time() is 15.6 ms on Windows
time_monotonic_resolution = 0.050

if sys.version_info >= (3, 3):
    # On Python 3.3, reuse the builtin time.monotonic()
    time_monotonic = time.monotonic
    time_monotonic_resolution = time.get_clock_info('monotonic').resolution

elif sys.platform.startswith(("linux", "freebsd", "openbsd", "sunos")):
    # Linux, FreeBSD, OpenBSD: use clock_gettime(CLOCK_MONOTONIC),
    # Solaris: use clock_gettime(CLOCK_HIGHRES).
    import ctypes
    import ctypes.util

    if sys.platform.startswith(("freebsd", "openbsd")):
        libraries = ('c',)
    elif sys.platform.startswith("linux"):
        # Linux: in glibc 2.17+, clock_gettime() is provided by the libc,
        # on older versions, it is provided by librt
        libraries = ('c', 'rt')
    else:
        # Solaris
        libraries = ('rt',)

    library = None
    for name in libraries:
        filename = ctypes.util.find_library(name)
        if not filename:
            continue
        library = ctypes.CDLL(filename, use_errno=True)
        if not hasattr(library, 'clock_gettime'):
            library = None

    if library is not None:
        time_t = ctypes.c_long
        clockid_t = ctypes.c_int

        class timespec(ctypes.Structure):
            _fields_ = (
                ('tv_sec', time_t),
                ('tv_nsec', ctypes.c_long),
            )
        timespec_p = ctypes.POINTER(timespec)

        clock_gettime = library.clock_gettime
        clock_gettime.argtypes = (clockid_t, timespec_p)
        clock_gettime.restype = ctypes.c_int

        def ctypes_oserror():
            errno = ctypes.get_errno()
            message = os.strerror(errno)
            return OSError(errno, message)

        def time_monotonic():
            ts = timespec()
            err = clock_gettime(time_monotonic.clk_id, ctypes.byref(ts))
            if err:
                raise ctypes_oserror()
            return ts.tv_sec + ts.tv_nsec * 1e-9

        if sys.platform.startswith("linux"):
            time_monotonic.clk_id = 1   # CLOCK_MONOTONIC
        elif sys.platform.startswith("freebsd"):
            time_monotonic.clk_id = 4   # CLOCK_MONOTONIC
        elif sys.platform.startswith("openbsd"):
            time_monotonic.clk_id = 3   # CLOCK_MONOTONIC
        else:
            assert sys.platform.startswith("sunos")
            time_monotonic.clk_id = 4   # CLOCK_HIGHRES

        def get_resolution():
            _clock_getres = library.clock_getres
            _clock_getres.argtypes = (clockid_t, timespec_p)
            _clock_getres.restype = ctypes.c_int

            ts = timespec()
            err = _clock_getres(time_monotonic.clk_id, ctypes.byref(ts))
            if err:
                raise ctypes_oserror()
            return ts.tv_sec + ts.tv_nsec * 1e-9
        time_monotonic_resolution = get_resolution()
        del get_resolution
    else:
        logging.error("time_monotonic: clock_gettime() function was not found")

elif os.name == "nt":
    # Windows: use GetTickCount64() or GetTickCount()
    import ctypes.wintypes

    # GetTickCount64() requires Windows Vista, Server 2008 or later
    if hasattr(ctypes.windll.kernel32, 'GetTickCount64'):
        ULONGLONG = ctypes.c_uint64

        GetTickCount64 = ctypes.windll.kernel32.GetTickCount64
        GetTickCount64.restype = ULONGLONG
        GetTickCount64.argtypes = ()

        def time_monotonic():
            return GetTickCount64() * 1e-3
        time_monotonic_resolution = 1e-3
    else:
        GetTickCount = ctypes.windll.kernel32.GetTickCount
        GetTickCount.restype = ctypes.wintypes.DWORD
        GetTickCount.argtypes = ()

        # Detect GetTickCount() integer overflow (32 bits, roll-over after
        # 49.7 days). It increases an internal epoch (reference time) by
        # 2^32 each time that an overflow is detected. The epoch is stored
        # in the process-local state and so the value of time_monotonic()
        # may be different in two Python processes running for more than
        # 49 days.
        def time_monotonic(use_info):
            ticks = GetTickCount()
            if ticks < time_monotonic.last:
                # Integer overflow detected
                time_monotonic.delta += 2 ** 32
            time_monotonic.last = ticks
            return (ticks + time_monotonic.delta) * 1e-3
        time_monotonic.last = 0
        time_monotonic.delta = 0
        time_monotonic_resolution = 1e-3

elif sys.platform == 'darwin':
    # Mac OS X: use mach_absolute_time() and mach_timebase_info()
    import ctypes
    import ctypes.util

    libc_name = ctypes.util.find_library('c')
    if libc_name:
        libc = ctypes.CDLL(libc_name, use_errno=True)

        mach_absolute_time = libc.mach_absolute_time
        mach_absolute_time.argtypes = ()
        mach_absolute_time.restype = ctypes.c_uint64

        class mach_timebase_info_data_t(ctypes.Structure):
            _fields_ = (
                ('numer', ctypes.c_uint32),
                ('denom', ctypes.c_uint32),
            )
        mach_timebase_info_data_p = ctypes.POINTER(mach_timebase_info_data_t)

        mach_timebase_info = libc.mach_timebase_info
        mach_timebase_info.argtypes = (mach_timebase_info_data_p,)
        mach_timebase_info.restype = ctypes.c_int

        def time_monotonic():
            return mach_absolute_time() * time_monotonic.factor

        timebase = mach_timebase_info_data_t()
        mach_timebase_info(ctypes.byref(timebase))
        time_monotonic.factor = float(timebase.numer) / timebase.denom * 1e-9
        time_monotonic_resolution = time_monotonic.factor
        del timebase
    else:
        logging.error("time_monotonic: the C library cannot be found")

else:
    logging.error("time_monotonic: unsupported platform %r", sys.platform)
