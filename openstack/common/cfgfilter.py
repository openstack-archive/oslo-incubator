# Copyright 2013 Red Hat, Inc.
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

r"""
There are two use cases for the ConfigFilter class:

1. Help enforce that a given module does not access options registered
   by another module, without first declaring those cross-module
   dependencies using import_opt().

2. Prevent private configuration opts from being visible to modules
   other than the one which registered it.

Cross-Module Option Depencies
-----------------------------

When using the global cfg.CONF object, it is quite common for a module
to require the existence of configuration options registered by other
modules.

For example, if module 'foo' registers the 'blaa' option and the module
'bar' uses the 'blaa' option then 'bar' might do:

  import foo

  print(CONF.blaa)

However, it's completely non-obvious why foo is being imported (is it
unused, can we remove the import) and where the 'blaa' option comes from.

The CONF.import_opt() method allows such a dependency to be explicitly
declared:

  CONF.import_opt('blaa', 'foo')
  print(CONF.blaa)

However, import_opt() has a weakness - if 'bar' imports 'foo' using the
import builtin and doesn't use import_opt() to import 'blaa', then 'blaa'
can still be used without problems. Similarly, where multiple options
are registered a module imported via importopt(), a lazy programmer can
get away with only declaring a dependency on a single option.

The ConfigFilter class provides a way to ensure that options are not
available unless they have been registered in the module or imported using
import_opt() e.g. with:

  CONF = ConfigFilter(cfg.CONF)
  CONF.import_opt('blaa', 'foo')
  print(CONF.blaa)

no other options other than 'blaa' are available via CONF.

Private Configuration Options
-----------------------------

Libraries which register configuration options typically do not want
users of the library API to access those configuration options. If
API users do access private configuration options, those users will
be disrupted if and when a configuration option is renamed. In other
words, one does not typically wish for the name of the private config
options to be part of the public API.

The ConfigFilter class provides a way for a library to register
options such that they are not visible via the ConfigOpts instance
which the API user supplies to the library. For example::

  from __future__ import print_function

  from oslo.config.cfg import *
  from openstack.common.cfgfilter import *

  class Widget(object):

      def __init__(self, conf):
          self.conf = conf
          self._private_conf = ConfigFilter(self.conf)
          self._private_conf.register_opt(StrOpt('foo'))

      @property
      def foo(self):
          return self._private_conf.foo

  conf = ConfigOpts()
  widget = Widget(conf)
  print(widget.foo)
  print(conf.foo)  # raises NoSuchOptError

"""

import collections
import itertools

from oslo.config import cfg


class ConfigFilter(collections.Mapping):

    """A helper class which wraps a ConfigOpts object.

    ConfigFilter enforces the explicit declaration of dependencies on external
    options and allows private options which are not registered with the
    wrapped Configopts object.
    """

    THIS_USES_PRIVATE_CFG_IMPL_DETAILS = object()

    def __init__(self, conf, warning=None):
        """Construct a ConfigFilter object.

        :param conf: a ConfigOpts object
        """
        if warning is not self.THIS_USES_PRIVATE_CFG_IMPL_DETAILS:
            raise Exception("Do not use this API until it has been included "
                            "in oslo.config proper. It uses private "
                            "implementation details of oslo.config that are "
                            "liable to change at any time")

        self._conf = conf
        self._fconf = cfg.ConfigOpts()
        self._sync()

        self._imported_opts = set()
        self._imported_groups = dict()

    def _sync(self):
        if self._fconf._namespace is not self._conf._namespace:
            self._fconf.clear()
            self._fconf._namespace = self._conf._namespace
            self._fconf._args = self._conf._args

    def __getattr__(self, name):
        """Look up an option value.

        :param name: the opt name (or 'dest', more precisely)
        :returns: the option value (after string subsititution) or a GroupAttr
        :raises: NoSuchOptError,ConfigFileValueError,TemplateSubstitutionError
        """
        if name in self._imported_groups:
            return self._imported_groups[name]
        elif name in self._imported_opts:
            return getattr(self._conf, name)
        else:
            self._sync()
            return getattr(self._fconf, name)

    def __getitem__(self, key):
        """Look up an option value."""
        return getattr(self, key)

    def __contains__(self, key):
        """Return True if key is the name of a registered opt or group."""
        return (key in self._fconf or
                key in self._imported_opts or
                key in self._imported_groups)

    def __iter__(self):
        """Iterate over all registered opt and group names."""
        return itertools.chain(self._fconf.keys(),
                               self._imported_opts,
                               self._imported_groups.keys())

    def __len__(self):
        """Return the number of options and option groups."""
        return (len(self._fconf) +
                len(self._imported_opts) +
                len(self._imported_groups))

    def register_opt(self, opt, group=None):
        """Register an option schema.

        :param opt: an instance of an Opt sub-class
        :param group: an optional OptGroup object or group name
        :return: False if the opt was already registered, True otherwise
        :raises: DuplicateOptError
        """
        return self._fconf.register_opt(opt, group)

    def register_opts(self, opts, group=None):
        """Register multiple option schemas at once."""
        return self._fconf.register_opts(opts, group)

    def register_cli_opt(self, opt, group=None):
        """Register a CLI option schema.

        :param opt: an instance of an Opt sub-class
        :param group: an optional OptGroup object or group name
        :return: False if the opt was already register, True otherwise
        :raises: DuplicateOptError, ArgsAlreadyParsedError
        """
        return self._fconf.register_cli_opt(opt, group)

    def register_cli_opts(self, opts, group=None):
        """Register multiple CLI option schemas at once."""
        return self._fconf.register_cli_opts(opts, group)

    def register_group(self, group):
        """Register an option group.

        :param group: an OptGroup object
        """
        self._fconf.register_group(group)

    def import_opt(self, opt_name, module_str, group=None):
        """Import an option definition from a module.

        :param name: the name/dest of the opt
        :param module_str: the name of a module to import
        :param group: an option OptGroup object or group name
        :raises: NoSuchOptError, NoSuchGroupError
        """
        self._conf.import_opt(opt_name, module_str, group)
        self._import_opt(opt_name, group)

    def import_group(self, group, module_str):
        """Import an option group from a module.

        Note that this allows access to all options registered with
        the group whether or not those options were registered by
        the given module.

        :param group: an option OptGroup object or group name
        :param module_str: the name of a module to import
        :raises: ImportError, NoSuchGroupError
        """
        self._conf.import_group(group, module_str)
        group = self._import_group(group)
        group._all_opts = True

    def _import_opt(self, opt_name, group):
        if group is None:
            self._imported_opts.add(opt_name)
            return True
        else:
            group = self._import_group(group)
            return group._import_opt(opt_name)

    def _import_group(self, group_or_name):
        if isinstance(group_or_name, cfg.OptGroup):
            group_name = group_or_name.name
        else:
            group_name = group_or_name

        if group_name in self._imported_groups:
            return self._imported_groups[group_name]
        else:
            group = self.GroupAttr(self._conf, group_name)
            self._imported_groups[group_name] = group
            return group

    class GroupAttr(collections.Mapping):

        """Helper class to wrap a group object.

        Represents the option values of a group as a mapping and attributes.
        """

        def __init__(self, conf, group):
            """Construct a GroupAttr object.

            :param conf: a ConfigOpts object
            :param group: an OptGroup object
            """
            self._conf = conf
            self._group = group
            self._imported_opts = set()
            self._all_opts = False

        def __getattr__(self, name):
            """Look up an option value."""
            if not self._all_opts and name not in self._imported_opts:
                raise cfg.NoSuchOptError(name)
            return getattr(self._conf[self._group], name)

        def __getitem__(self, key):
            """Look up an option value."""
            return getattr(self, key)

        def __contains__(self, key):
            """Return True if key is the name of a registered opt or group."""
            return key in self._imported_opts

        def __iter__(self):
            """Iterate over all registered opt and group names."""
            for key in self._imported_opts:
                yield key

        def __len__(self):
            """Return the number of options and option groups."""
            return len(self._imported_opts)

        def _import_opt(self, opt_name):
            self._imported_opts.add(opt_name)
