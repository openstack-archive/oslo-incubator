# vim: tabstop=4 shiftwidth=4 softtabstop=4

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
Provides Openstack-specific models

This module defines classes representing Openstack-specific
data models for use in the Guru Meditation Reports.
"""

import openstack.common.report.models.with_default_views as mwdv
import openstack.common.report.views.text.generic as generic_text_views
import openstack.common.report.views.text.openstack_specific as text_views
import traceback


class StackTraceModel(mwdv.ModelWithDefaultViews):
    """
    A Stack Trace Model

    This model holds data from a python stack trace,
    commonly extracted from running thread information

    :param stack_state: the python stack_state object
    """

    def __init__(self, stack_state):
        super(StackTraceModel, self).__init__(
            text_view=text_views.StackTraceView()
        )

        if (stack_state is not None):
            self['lines'] = [
                {'filename': fn, 'line': ln, 'name': nm, 'code': cd}
                for fn, ln, nm, cd in traceback.extract_stack(stack_state)
            ]

            if stack_state.f_exc_type is not None:
                self['root_exception'] = {
                    'type': stack_state.f_exc_type,
                    'value': stack_state.f_exc_value
                }
            else:
                self['root_exception'] = None
        else:
            self['lines'] = []
            self['root_exception'] = None


class ThreadModel(mwdv.ModelWithDefaultViews):
    """
    A Thread Model

    This model holds data for information about an
    individual thread.  It holds both a thread id,
    as well as a stack trace for the thread

    .. seealso::

        Class :class:`StackTraceModel`

    :param int thread_id: the id of the thread
    :param stack: the python stack state for the current thread
    """

    # threadId, stack in sys._current_frams().items()
    def __init__(self, thread_id, stack):
        super(ThreadModel, self).__init__(text_view=text_views.ThreadView())

        self['thread_id'] = thread_id
        self['stack_trace'] = StackTraceModel(stack)


class GreenThreadModel(mwdv.ModelWithDefaultViews):
    """
    A Green Thread Model

    This model holds data for information about an
    individual thread.  Unlike the thread model,
    it holds just a stack trace, since green threads
    do not have thread ids.

    .. seealso::

        Class :class:`StackTraceModel`

    :param stack: the python stack state for the green thread
    """

    # gr in greenpool.coroutines_running  --> gr.gr_frame
    def __init__(self, stack):
        super(GreenThreadModel, self).__init__(
            {'stack_trace': StackTraceModel(stack)},
            text_view=text_views.GreenThreadView()
        )


class ConfigModel(mwdv.ModelWithDefaultViews):
    """
    A Configuration Options Model

    This model holds data about a set of configuration options
    from :mod:`oslo.config`.  It supports both the default group
    of options and named option groups.

    :param conf_obj: a configuration object
    :type conf_obj: :class:`oslo.config.cfg.ConfigOpts`
    """

    def __init__(self, conf_obj):
        kv_view = generic_text_views.KeyValueView(dict_sep=": ",
                                                  before_dict='')
        super(ConfigModel, self).__init__(text_view=kv_view)

        def opt_title(optname, co):
            return co._opts[optname]['opt'].name

        self['default'] = {
            opt_title(optname, conf_obj): conf_obj[optname]
            for optname in conf_obj._opts
        }

        groups = {}
        for groupname in conf_obj._groups:
            group_obj = conf_obj._groups[groupname]
            curr_group_opts = {
                opt_title(optname, group_obj): conf_obj[groupname][optname]
                for optname in group_obj._opts
            }
            groups[group_obj.name] = curr_group_opts

        self.update(groups)


class OldConfigModel(mwdv.ModelWithDefaultViews):
    """
    A Configuration Options Model

    This model holds data about a set of configuration options
    from :mod:`oslo.config`.  It supports both the default group
    of options and named option groups.

    :param conf_obj: a configuration object
    :type conf_obj: :class:`oslo.config.cfg.ConfigOpts`
    """

    def __init__(self, conf_obj):
        conf_view = text_views.OldConfigView()
        super(OldConfigModel, self).__init__(text_view=conf_view)

        self['default_group'] = [
            [conf_obj._opts[optname]['opt'].name, conf_obj[optname]]
            for optname in conf_obj._opts
        ]

        groups = {}
        for groupname in conf_obj._groups:
            group_obj = conf_obj._groups[groupname]
            curr_group_opts = [
                [
                    group_obj._opts[optname]['opt'].name,
                    conf_obj[groupname][optname]
                ]
                for optname in group_obj._opts
            ]
            groups[group_obj.name] = curr_group_opts

        self['groups'] = [
            [groupname, groups[groupname]] for groupname in groups
        ]


class PackageModel(mwdv.ModelWithDefaultViews):
    """
    A Package Information Model

    This model holds information about the current
    package.  It contains vendor, product, and version
    information.

    :param str vendor: the product vendor
    :param str product: the product name
    :param str version: the product version
    """

    def __init__(self, vendor, product, version):
        super(PackageModel, self).__init__(
            text_view=generic_text_views.KeyValueView()
        )

        self['vendor'] = vendor
        self['product'] = product
        self['version'] = version


class ServicesModel(mwdv.ModelWithDefaultViews):
    """
    A Service Status Model

    This model holds data about a collection
    of Openstack services, their current
    state (alive or dead), and their host machine.

    :param hosts: the various services
    :type hosts: [{'service': str, 'host': str, 'alive': bool}]
    """

    def __init__(self, hosts):
        view = generic_text_views.TableView(
            ['Service', 'Host', 'Alive?'],
            ['service', 'host', 'alive'],
            'services'
        )
        super(ServicesModel, self).__init__(text_view=view)

        self['services'] = hosts
