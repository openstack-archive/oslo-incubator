#!/usr/bin/env python

# Copyright 2014 Red Hat, Inc.
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

import copy
import os
import sys

# Parse MAINTAINERS file
maintainers = {}
module_template = {'maintainers': [],
                   'status': '',
                   'files': [],
                   }
with open('MAINTAINERS', 'r') as maintainers_file:
    for line in maintainers_file:
        if line.startswith('=='):
            module_name = line[3:-4]
            maintainers[module_name] = copy.deepcopy(module_template)
        elif line.startswith('M:'):
            maintainer_name = line[3:]
            maintainers[module_name]['maintainers'] = maintainer_name
        elif line.startswith('S:'):
            status = line[3:]
            maintainers[module_name]['status'] = status
        elif line.startswith('F:'):
            filename = line[3:-1]
            maintainers[module_name]['files'].append(filename)

# Check that all files in the tree are covered in MAINTAINERS
return_value = 0


def find_directory(directory):
    for module, values in maintainers.items():
        if (directory + '/') in values['files']:
            return
    print('Directory %s not found in MAINTAINERS' % directory)
    global return_value
    return_value = 1


def find_file(filename):
    for module, values in maintainers.items():
        if filename in values['files']:
            return
    print('File %s not found in MAINTAINERS' % filename)
    global return_value
    return_value = 1


def check_directory(path):
    skipped_entries = ['__init__.py', 'deprecated', '__pycache__']
    for i in os.listdir(path):
        if i.endswith('.pyc') or i in skipped_entries:
            continue
        if os.path.isdir(os.path.join(path, i)):
            find_directory(i)
        elif os.path.isfile(os.path.join(path, i)):
            find_file(i)


check_directory('openstack/common')

sys.exit(return_value)
