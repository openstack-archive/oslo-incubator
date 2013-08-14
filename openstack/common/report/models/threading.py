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

"""Provides threading and stack-trace models

This module defines classes representing thread, green
thread, and stack trace data models
"""

import openstack.common.report.models.with_default_views as mwdv
import openstack.common.report.views.text.threading as text_views
import traceback


class StackTraceModel(mwdv.ModelWithDefaultViews):
    """A Stack Trace Model

    This model holds data from a python stack trace,
    commonly extracted from running thread information

    :param stack_state: the python stack_state object
    """

    def __init__(self, stack_state):
        super(StackTraceModel, self).__init__(
            text_view=text_views.StackTraceView())

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
    """A Thread Model

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
    """A Green Thread Model

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
            text_view=text_views.GreenThreadView())
