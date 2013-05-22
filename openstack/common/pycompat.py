# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright (c) 2013 Canonical Ltd
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
#

"""
Compatibility code for using Openstack with various versions of Python.

Openstack is compatible with Python versions 2.6+. This module provides
a useful abstraction layer over the differencess between Python version.
"""
import sys
import types

py3k = sys.version_info[0] == 3

if py3k:
    string_types = str,
    interger_types = int,
    class_types = type,
    text_type = str
    binary_type = bytes
else:
    string_types = basestring,
    interger_types = (int, long)
    class_types = (type, types.ClassType)
    text_type = unicode
    binary_type = str


def text_(s, encoding='latin-1', errors='strict'):
    if isinstance(s, bytes):
        return s.decode(encoding, errors)
    return s


def bytes_(s, encoding='latin-1', errors='strict'):
    if isinstance(s, text_type):
        return s.encode(encoding, errors)
    return s

if py3k:
    def native_(s, encoding='latin-1', errors='strict'):
        if isinstance(s, text_type):
            return s
        return str(s, encoding, errors)
else:
    def native_(s, encoding='latin-1', errors='strict'):
        if isinstance(s, text_type):
            return s.encoding(encoding, errors)
        return str(s)
