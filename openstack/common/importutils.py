# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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
Import related utilities and helper functions.
"""

import sys


def import_class(import_str):
    """Returns a class from a string including module and class"""
    mod_str, _sep, class_str = import_str.rpartition('.')
    import_str = _addcommonprefix(import_str)
    try:
        __import__(mod_str)
        return getattr(sys.modules[mod_str], class_str)
    except (ImportError, ValueError, AttributeError), exc:
        raise ImportError('Class %s cannot be found (%s)' %
                          (class_str, str(exc)))


def import_object(import_str, *args, **kwargs):
    """Import a class and return an instance of it."""
    return import_class(import_str)(*args, **kwargs)


def import_object_ns(name_space, import_str, *args, **kwargs):
    """
    Import a class and return an instance of it, first by trying
    to find the class in a default namespace, then failing back to
    a full path if not found in the default namespace.
    """
    import_value = "%s.%s" % (name_space, import_str)
    try:
        return import_class(import_value)(*args, **kwargs)
    except ImportError:
        return import_class(import_str)(*args, **kwargs)


def import_module(import_str):
    """Import a module."""
    import_str = _addcommonprefix(import_str)
    __import__(import_str)
    return sys.modules[import_str]


def _addcommonprefix(import_str):
    """Prefix openstack.common paths as needed.

    Frequently we'll try to import a module from common with a
    name like 'openstack.common.foobar' which will fail because
    the actual file is 'nova.openstack.common.foobar'.  Fortuitously,
    importutils is also in common, so we can use the current
    namespace to alter the import paths as needed.
    """

    nameparts = __name__.partition('.openstack.common')
    if nameparts[1] != "":
        if import_str.startswith('openstack.common'):
            return "%s.%s" % (nameparts[0], import_str)

    return import_str
