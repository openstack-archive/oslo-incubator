# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 IBM Corp
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
Unit constants
"""

from operator import attrgetter


class ByteUnit(object):
    """Byte unit constant.

    These constants based on powers of 1024, following IEC standard.
    Use these constants like:
       root_disk_gb =  5 * byte.Gi
    """
    def __init__(self):
        self._Ki = 1024
        self._Mi = 1024 ** 2
        self._Gi = 1024 ** 3
        self._Ti = 1024 ** 4
        self._Pi = 1024 ** 5
        self._Ei = 1024 ** 6
        self._Zi = 1024 ** 7
        self._Yi = 1024 ** 8

    Ki = property(attrgetter("_Ki"))
    Mi = property(attrgetter("_Mi"))
    Gi = property(attrgetter("_Gi"))
    Ti = property(attrgetter("_Ti"))
    Pi = property(attrgetter("_Pi"))
    Ei = property(attrgetter("_Ei"))
    Zi = property(attrgetter("_Zi"))
    Yi = property(attrgetter("_Yi"))


byte = ByteUnit()
