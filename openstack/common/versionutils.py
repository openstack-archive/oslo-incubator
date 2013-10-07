# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2013 OpenStack Foundation
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
Helpers for comparing version strings.
"""

import itertools


def is_compatible(requested_version, current_version, same_major=True):
    """Determine whether `requested_version` is satisfied by
    `current_version`.

    :param requested_version: Version to check for compatibility
    :param current_version: Version to check against
    :param same_major: If True, the major version must be identical between
        `requested_version` and `current_version`. This is used when a
        major-version difference indicates incompatibility between the two
        versions. Since this is the common-case in practice, the default is
        True.
    :returns: True if compatible, False if not
    """
    requested_parts = requested_version.split('.')
    current_parts = current_version.split('.')

    if same_major and (requested_parts[0] != current_parts[0]):
        return False

    return _cmp_version(current_parts, requested_parts) >= 0


def _cmp_version(a_parts, b_parts):
    """Compare whether two versions are the same.

    :param a_parts: A tuple or list representing first version parts
    :param b_parts: A tuple or list representing second version parts
    :returns: -1 if a < b, 0 if a == b, 1 if a > b
    """
    for va, vb in itertools.izip_longest(a_parts, b_parts, fillvalue='0'):
        ret = int(va) - int(vb)
        if ret > 0:
            return 1
        elif ret < 0:
            return -1
        else:
            pass  # Parts same, keep comparing...

    return 0
