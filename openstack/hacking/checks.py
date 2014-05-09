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


def no_import_from(logical_line):
    """Check import style.

    O101: Don't use import style 'import openstack.common.*'
    Need use 'from openstack.common.*'

    Okay: from openstack.common.apiclient import exceptions
    Okay: from openstack.common import log as logging
    Okay: from openstack.common.gettextutils import _LE
    O101: import openstack.common.report.generators.conf as cgen
    O101:      import openstack.common.report
    """
    msg = ("O101: Do not use import style 'import openstack.common.*', use "
           "'from openstack.common.*'")
    if import_style_re.match(logical_line):
        yield (0, msg)


def check_longest_base_name(physical_line):
    """Check import style.

    O102: Make sure the line length won't exceed 80 characters while replacing
    oslo with longest base name.
    """
    # Note(gcb): update longgest_base_name if we have in the future.
    longest_base_name = "openstack_dashboard"
    msg = ("O102: 'the line will exceed 80 characters while replacing oslo "
           "with base name %s " % longest_base_name)
    exceptions = ['oslotest']
    find_exceptions = [physical_line.find(item) == -1 for item in exceptions]
    if physical_line.find('oslo') != -1 and all(find_exceptions):
        length = len(physical_line) + len(longest_base_name) + 2 - len('oslo')
        if length > 79:
            yield (0, msg)


def factory(register):
    register(no_import_from)
