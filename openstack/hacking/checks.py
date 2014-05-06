# Copyright (c) 2014 EasyStack, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import re


import_style_re = re.compile(r"^( *)import openstack.common")
assert_equal_end_with_none_re = re.compile(
    r"(.)*assertEqual\((\w|\.|\'|\"|\[|\])+, None\)")
assert_equal_start_with_none_re = re.compile(
    r"(.)*assertEqual\(None, (\w|\.|\'|\"|\[|\])+\)")


def no_import_from(logical_line):
    """Check import style.

    O101: Don't use import style 'import openstack.common.*'
    Need use 'from openstack.common.*'
    """
    msg = ("O101: Do not use import style 'import openstack.common.*', use "
           "from openstack.common.*")
    if import_style_re.match(logical_line):
        yield (0, msg)


def assert_equal_none(logical_line):
    """Check for assertEqual(A, None) or assertEqual(None, A) sentences

    O102: assertEqual(A, None) or assertEqual(None, A)sentences not allowed.
    """

    res = (assert_equal_start_with_none_re.match(logical_line) or
           assert_equal_end_with_none_re.match(logical_line))
    if res:
        yield (0, "N102: assertEqual(A, None) or assertEqual(None, A) "
               "sentences not allowed")


def factory(register):
    register(no_import_from)
    register(assert_equal_none)
