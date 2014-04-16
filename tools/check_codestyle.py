#!/usr/bin/env python

# Copyright 2014(c) EasyStack, Inc.
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

import os
import re
import sys


return_value = 0
IMPORT_RE = re.compile(r'^( *)import openstack.common')


def _check_import_style(path, line, num):
    """Check import style

    Should import module like from openstack.common.* import,
    not import openstack.common.

    :param patch: the file path
    :param line: the current line to handle
    :param num: the current line number
    """

    global return_value

    if IMPORT_RE.match(line):
        return_value = 1
        print("ERROR: Should import module like 'from openstack.common.* "
              " import': in file %s line %d" % (path, num + 1))


def check_file(path):
    with open(path, "r") as f:
        for index, line in enumerate(f):
            # Any check function can be applied here works as pipeline
            _check_import_style(path, line, index)


def check_directory(path):
    for i in os.listdir(path):
        new_path = os.path.join(path, i)
        if os.path.isdir(new_path):
            check_directory(new_path)
        elif os.path.isfile(new_path) and i.endswith('.py'):
            check_file(new_path)


check_directory('openstack/common')

sys.exit(return_value)
