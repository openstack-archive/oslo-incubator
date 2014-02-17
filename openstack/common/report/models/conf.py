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

"""Provides Openstack Configuration Model

This module defines a class representing the data
model for :mod:`oslo.config` configuration options
"""

import re

import openstack.common.report.models.with_default_views as mwdv
import openstack.common.report.views.text.generic as generic_text_views


class ConfigModel(mwdv.ModelWithDefaultViews):
    """A Configuration Options Model

    This model holds data about a set of configuration options
    from :mod:`oslo.config`.  It supports both the default group
    of options and named option groups.

    :param conf_obj: a configuration object
    :type conf_obj: :class:`oslo.config.cfg.ConfigOpts`
    :param bool scrub_passwords: redact passwords? (default: True)
    """

    def __init__(self, conf_obj, scrub_passwords=True):
        kv_view = generic_text_views.KeyValueView(dict_sep=": ",
                                                  before_dict='')
        super(ConfigModel, self).__init__(text_view=kv_view)

        def opt_title(optname, co):
            return co._opts[optname]['opt'].name

        scrub_pass = lambda k, v: v

        if scrub_passwords:
            PASS_RE = re.compile('^\w+_(password|key|token)$')

            def scrub(k, v):
                if PASS_RE.match(k) is not None:
                    return '*' * len(v)
                else:
                    return v

            scrub_pass = scrub

        self['default'] = {}
        for optname in conf_obj._opts:
            k = opt_title(optname, conf_obj)
            self['default'][k] = scrub_pass(k, conf_obj[optname])

        groups = {}
        for groupname in conf_obj._groups:
            group_obj = conf_obj._groups[groupname]
            group_opts = {}
            for optname in group_obj._opts:
                k = opt_title(optname, group_obj)
                group_opts[k] = scrub_pass(k, conf_obj[groupname][optname])

            groups[group_obj.name] = group_opts

        self.update(groups)
