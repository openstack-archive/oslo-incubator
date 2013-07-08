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

"""Provides Openstack-Specific Views

This module provides a collection of Openstack-specific
views for use in the Guru Meditation Reports.
"""

from openstack.common.report.views.jinja_view import JinjaView


class StackTraceView(JinjaView):
    """A Stack Trace View

    This view displays stack trace models defined by
    :class:`openstack.common.report.models.openstack_specific.StackTraceModel`
    """

    VIEW_TEXT = (
        "{% if root_exception is not none %}"
        "Exception: {{ root_exception }}\n"
        "------------------------------------\n"
        "\n"
        "{% endif %}"
        "{% for line in lines %}\n"
        "{{ line.filename }}:{{ line.line }} in {{ line.name }}\n"
        "    {% if line.code is not none %}"
        "`{{ line.code }}`"
        "{% else %}"
        "(source not found)"
        "{% endif %}\n"
        "{% else %}\n"
        "No Traceback!\n"
        "{% endfor %}"
    )


class GreenThreadView(object):
    """A Green Thread View

    This view displays a green thread provided by the data
    model :class:`openstack.common.report.models.openstack_specific.GreenThreadModel`  # noqa
    """

    FORMAT_STR = "------{thread_str: ^60}------" + "\n" + "{stack_trace}"

    def __call__(self, model):
        return self.FORMAT_STR.format(
            thread_str=" Green Thread ",
            stack_trace=model.stack_trace
        )


class ThreadView(object):
    """A Thread Collection View

    This view displays a python thread provided by the data
    model :class:`openstack.common.report.models.openstack_specific.ThreadModel`  # noqa
    """

    FORMAT_STR = "------{thread_str: ^60}------" + "\n" + "{stack_trace}"

    def __call__(self, model):
        return self.FORMAT_STR.format(
            thread_str=" Thread #{0} ".format(model.thread_id),
            stack_trace=model.stack_trace
        )


class OldConfigView(JinjaView):
    """A Configuration Options View

    This view is designed to display configuration options
    structured in the general manner of those from
    :mod:`oslo.config`.  The data is provided by the data model
    :class:`openstack.common.report.models.openstack_specific.ConfigModel` .
    """

    VIEW_TEXT = """
    [DEFAULT]{% for optname, optval in default_group %}
        {{ optname }} = {{ optval }}{% endfor %}
    {% for groupname, groupopts in groups %}
    {{ groupname }}:{% for optname, optval in groupopts %}
        {{ optname }} = {{ optval }}{% endfor %}
    {% endfor %}
    """
