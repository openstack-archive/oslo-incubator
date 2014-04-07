# Copyright 2014 OpenStack Foundation.
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

"""Backport of time.monotonic() of Python 3.3 (PEP 418) for Python 2.6
and newer:

- time_monotonic(): Return the value (in fractional seconds) of a monotonic
  clock, i.e. a clock that cannot go backwards. The clock is not affected by
  system clock updates. The reference point of the returned value is undefined,
  so that only the difference between the results of consecutive calls is
  valid.
- time_monotonic_resolution: Resolution of time_monotonic() clock in second

Support Linux, FreeBSD, OpenBSD, Solaris, Windows, Mac OS X, but requires
the ctypes module. The used time function depends on the operating system:

 - Linux, FreeBSD, OpenBSD: clock_gettime(CLOCK_MONOTONIC)
 - Older Windows: GetTickCount()
 - Solaris: clock_gettime(CLOCK_HIGHRES)
 - Windows Vista and newer: GetTickCount64()
 - Mac OS X: mach_absolute_time()

On other platforms, it falls back to system clock: time.time().
"""

__all__ = ('time_monotonic', 'time_monotonic_resolution')

import logging
import os
import sys
import time

# default implementation: system clock (non monotonic!)
time_monotonic = time.time

# the worst resolution is 15.6 ms on Windows
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
