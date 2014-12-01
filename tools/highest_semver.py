#!/usr/bin/env python
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

"""Read a list of version tags from stdin and pick the one with the
highest semver value.
"""

from __future__ import print_function

import fileinput
import sys


def try_int(val):
    try:
        return int(val)
    except ValueError:
        return val


tags = []
for line in fileinput.input(sys.argv[1:]):
    line = line.strip()
    if not line:
        continue
    parts = line.split('.')
    v = tuple(try_int(val) for val in parts)
    if len(v) == 3:
        v = v + ('zzz',)  # artifically sort the value higher than alphas
    # Ignore versions where the beginning doesn't look like a number,
    # such as 'havana-eol'
    if not isinstance(v[0], int):
        continue
    # Ignore date-based entries
    if v[0] > 100:
        continue
    tags.append(v)

if tags:
    # We only want to print something if we actually have any tags to
    # pick from. Otherwise we probably have a library that has never
    # been released, so there is no valid version.
    version = max(tags)
    if version[-1] == 'zzz':
        version = version[:-1]
    print('.'.join(str(t) for t in version))
