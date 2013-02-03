# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

import collections

from openstack.common import cfg


class ConfigFilter(collections.Mapping):

    def __init__(self, conf):
        self._conf = conf
        self._opts = set()
        self._groups = dict()

    def __getattr__(self, name):
        if name in self._groups:
            return self._groups[name]
        if name not in self._opts:
            raise cfg.NoSuchOptError(name)
        return getattr(self._conf, name)

    def __getitem__(self, key):
        return getattr(self, key)

    def __contains__(self, key):
        return key in self._opts or key in self._groups

    def __iter__(self):
        for key in list(self._opts) + self._groups.keys():
            yield key

    def __len__(self):
        return len(self._opts) + len(self._groups)

    def register_opt(self, opt, group=None):
        if not self._conf.register_opt(opt, group):
            return False

        self._register_opt(opt.dest, group)
        return True

    def register_opts(self, opts, group=None):
        for opt in opts:
            self.register_opt(opt, group)

    def register_cli_opt(self, opt, group=None):
        if not self._conf.register_cli_opt(opt, group):
            return False

        self._register_opt(opt.dest, group)
        return True

    def register_cli_opts(self, opts, group=None):
        for opt in opts:
            self.register_cli_opts(opt, group)

    def register_group(self, group):
        self._conf.register_group(group)
        self._get_group(group.name)

    def import_opt(self, opt_name, module_str, group=None):
        self._conf.import_opt(opt_name, module_str, group)
        self._register_opt(opt_name, group)

    def _register_opt(self, opt_name, group):
        if group is None:
            self._opts.add(opt_name)
            return True
        else:
            group = self._get_group(group)
            return group._register_opt(opt_name)

    def _get_group(self, group_or_name):
        if isinstance(group_or_name, cfg.OptGroup):
            group_name = group_or_name.name
        else:
            group_name = group_or_name

        if group_name in self._groups:
            return self._groups[group_name]
        else:
            group = self.GroupAttr(self._conf, group_name)
            self._groups[group_name] = group
            return group

    class GroupAttr(collections.Mapping):

        def __init__(self, conf, group):
            self._conf = conf
            self._group = group
            self._opts = set()

        def __getattr__(self, name):
            if name not in self._opts:
                raise cfg.NoSuchOptError(name)
            return getattr(self._conf[self._group], name)

        def __getitem__(self, key):
            return getattr(self, key)

        def __contains__(self, key):
            return key in self._opts

        def __iter__(self):
            for key in self._opts:
                yield key

        def __len__(self):
            return len(self._opts)

        def _register_opt(self, opt_name):
            self._opts.add(opt_name)
