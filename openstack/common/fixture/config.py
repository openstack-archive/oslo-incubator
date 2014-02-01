#
# Copyright 2013 Mirantis, Inc.
# Copyright 2013 OpenStack Foundation
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

import fixtures
from oslo.config import cfg
import six


class Config(fixtures.Fixture):
    """Override some configuration values.

    The keyword arguments are the names of configuration options to
    override and their values.

    If a group argument is supplied, the overrides are applied to
    the specified configuration option group.

    All overrides are automatically cleared at the end of the current
    test by the reset() method, which is registered by addCleanup().

    Options can be registered using the register_opt() method.  All
    options registered in this way will be automatically unregistered at the
    end of the current test by the _unregister_config_opts() method, which is
    registered by addCleanup().  Multiple options can be registered with the
    register_opts() method.
    """

    def __init__(self, conf=cfg.CONF):
        self.conf = conf

    def setUp(self):
        super(Config, self).setUp()
        self.addCleanup(self._unregister_config_opts)
        self.addCleanup(self.conf.reset)
        self._registered_config_opts = {}

    def config(self, **kw):
        group = kw.pop('group', None)
        for k, v in six.iteritems(kw):
            self.conf.set_override(k, v, group)

    def _unregister_config_opts(self):
        for group in self._registered_config_opts:
            self.conf.unregister_opts(self._registered_config_opts[group],
                                      group=group)

    def register_opt(self, opt, group=None):
        self.conf.register_opt(opt, group=group)
        self._registered_config_opts.setdefault(group, set()).add(opt)

    def register_opts(self, opts, group=None):
        for opt in opts:
            self.register_opt(opt, group=group)
