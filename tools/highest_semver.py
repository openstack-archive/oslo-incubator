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
    # Ignore versions where the beginning doesn't look like a number,
    # such as 'havana-eol'
    if not isinstance(v[0], int):
        continue
    # Ignore date-based entries
    if v[0] > 100:
        continue
    tags.append(v)

print('.'.join(str(t) for t in max(tags)))
