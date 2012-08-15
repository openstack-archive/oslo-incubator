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

import pkg_resources
import sys
import traceback

from openstack.common import log as logging

LOG = logging.getLogger(__name__)


def import_class(import_str):
    """Returns a class from a string including module and class"""
    mod_str, _sep, class_str = import_str.rpartition('.')
    try:
        __import__(mod_str)
        return getattr(sys.modules[mod_str], class_str)
    except (ValueError, AttributeError), exc:
        raise ImportError('Class %s cannot be found (%s)' %
                          (class_str,
                           traceback.format_exception(*sys.exc_info())))


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


def check_isinstance(obj, cls):
    """Checks that obj is of type cls, and lets PyLint infer types."""
    if isinstance(obj, cls):
        return obj
    raise Exception(_('Expected object of type: %s') % (str(cls)))


def import_entrypoint(name_space, ep_name, *args, **kwargs):
    """
    Import a driver via pkg_resources entrypoints.
    """
    for ep in pkg_resources.iter_entry_points(name_space, ep_name):
        return ep.load()(*args, **kwargs)
    return None


def import_driver(name_space, driver_name, cls, *args, **kwargs):
    """
    Try to load the compute driver from entrypoints. Fall back
    to old-style importutils.
    """

    LOG.info(_("Loading driver '%s:%s'") % (name_space, driver_name))
    driver_obj = import_entrypoint(name_space, driver_name, *args, **kwargs)
    if driver_obj is None:
        driver_obj = import_object_ns(name_space, driver_name, *args, **kwargs)
        LOG.warn(_('Library import of drivers is deprecated. Entry points '
                   'should be used instead'))

    return check_isinstance(driver_obj, cls)


def import_module(import_str):
    """Import a module."""
    __import__(import_str)
    return sys.modules[import_str]
