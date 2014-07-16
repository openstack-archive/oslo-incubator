# Copyright 2011 OpenStack Foundation.
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
import traceback


def import_class(import_str):
    """Returns a class from a string including module and class."""
    mod_str, _sep, class_str = import_str.rpartition('.')
    __import__(mod_str)
    try:
        return getattr(sys.modules[mod_str], class_str)
    except AttributeError:
        raise ImportError('Class %s cannot be found (%s)' %
                          (class_str,
                           traceback.format_exception(*sys.exc_info())))


def import_object(import_str, *args, **kwargs):
    """Import a class and return an instance of it."""
    return import_class(import_str)(*args, **kwargs)


def import_object_ns(name_space, import_str, *args, **kwargs):
    """Tries to import object from default namespace.

    Imports a class and return an instance of it, first by trying
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
    __import__(import_str)
    return sys.modules[import_str]


def import_versioned_module(version, submodule=None):
    module = 'oslo.v%s' % version
    if submodule:
        module = '.'.join((module, submodule))
    return import_module(module)


def try_import(import_str, default=None):
    """Try to import a module and if it fails return default."""
    try:
        return import_module(import_str)
    except ImportError:
        return default


class LazyPluggable(object):
    """A pluggable backend loaded lazily based on some value.

    Here is example of how this class can be used

    1. Registration of option in config::

        ipv6_backend_opt = cfg.StrOpt('ipv6_backend',
                                      default='rfc2462',
                                      help='Backend to use for IPv6 generation')
        CONF = cfg.CONF
        CONF.register_opt(ipv6_backend_opt)

    2. Creating IMPL - object of class LazyPluggable::

        IMPL = utils.LazyPluggable('ipv6_backend',
                                   CONF,
                                   rfc2462='nova.ipv6.rfc2462',
                                   account_identifier
                                   ='nova.ipv6.account_identifier')
    """

    def __init__(self, conf, pivot, config_group=None, **backends):
        """Given instance of config, get backend depending on pivot.

        The backend will be loaded on the first attribute access
        to the class instance. If the backend specified in the config file
        is not found, PluginLoadError will be raised.
        :param conf: instance of config
        :param pivot: name of option in config, which responsible
            for the selection of backend in runtime
        :param config_group: group of config, if None is passed, search
            will be done in [DEFAULT] config group
        :param backends: supported backends, which must be a mapping
            where keys are the names of supported backends and
            values are the names of modules implementing those backends
        """

        self._conf = conf
        self._backends = backends
        self._pivot = pivot
        self._backend = None
        self._config_group = config_group

    def _get_backend(self):
        if not self._backend:
            if self._config_group is None:
                backend_name = self._conf[self._pivot]
            else:
                backend_name = self._conf[self._config_group][self._pivot]
            if backend_name not in self._backends:
                msg = ('Invalid backend: %s') % backend_name
                raise PluginLoadError(msg)

            backend = self._backends[backend_name]
            if isinstance(backend, tuple):
                name = backend[0]
                fromlist = backend[1]
            else:
                name = backend
                fromlist = backend

            self._backend = __import__(name, None, None, fromlist)
        return self._backend

    def __getattr__(self, key):
        backend = self._get_backend()
        return getattr(backend, key)


class PluginLoadError(Exception):
    pass
