#!/usr/bin/env python

# Copyright (c) 2014 EasyStack Co., Ltd.
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
from sets import Set
import sys

# module list in openstack-common.conf
module_list = []
# module list in directory openstack/common
actual_list = []
return_value = 0
code_name = sys.argv[1]


# Extract module list in openstack-common.conf
def get_module_list_in_conf():
    with open('openstack-common.conf', 'r') as module_file:
        for line in module_file:
            if line.startswith('module='):
                module_name = line[7:-1]
                module_list.append(module_name)


# Get modules which is not signle file in openstack/common directly.
def get_modules_in_directory(path):
    global actual_list

    if os.path.isfile(path):
        return
    for i in os.listdir(path):
        # Assume every module not a single file includes __init__.py
        if i == '__init__.py':
            module_directory = path.split('/openstack/common/')[1]
            module_name = '.'.join(module_directory.split('/'))
            actual_list.append(module_name)
        if os.path.isdir(os.path.join(path, i)):
            get_modules_in_directory(os.path.join(path, i))


# Get actual modules in directory openstack/common
def list_actual_modules(path):
    global actual_list
    skipped_entries = ['__init__.py', 'deprecated', '__pycache__']

    for i in os.listdir(path):
        if i.endswith('.pyc') or i in skipped_entries:
            continue
        # For single file module
        if i.endswith('.py'):
            actual_list.append(i[:-3])
        # For not single file module
        if os.path.isdir(os.path.join(path, i)):
            get_modules_in_directory(os.path.join(path, i))


def check_modules():
    global return_value

    get_module_list_in_conf()

    list_actual_modules('%s/openstack/common' % code_name)

    sorted_list = sorted(module_list)

    delta = [module_list[i] for i in range(len(module_list))
             if module_list[i] != sorted_list[i]]
    if len(delta) != 0:
        print('Please list modules  in alphabetical order.')
        print('Modules in openstack-common.conf not in order: %s' % delta)
        return_value = 1

    tracked_set = Set(module_list)
    actual_set = Set(actual_list)
    diff_set = tracked_set ^ actual_set
    if len(diff_set) != 0:
        print('Please track actual modules in openstack-common.conf.')
        print("TrackedSet ^ ActualSet = %s" % diff_set)
        return_value = 1

check_modules()

sys.exit(return_value)
