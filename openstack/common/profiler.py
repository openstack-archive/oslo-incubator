# Copyright 2013 OpenStack Foundation.
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

import functools
import uuid

from openstack.common import context
from openstack.common.notifier import api as notifier_api


class Profiler:

    def __init__(self, base_id=None, service='generic'):
        self._context = context.get_admin_context()
        self._service = service
        if not base_id:
            base_id = str(uuid.uuid4())
        self._trace_stack = [base_id]
        self._name = None

    def __call__(self, name):
        """This method simplifies usage of profiler object as a guard
        > profiler = Profiler(service='nova')
        > with profiler('some long running code'):
        >     do_some_stuff()
        """
        self._name = name
        return self

    def __enter__(self):
        if self._name:
            self.start(self._name)

    def __exit__(self, etype, value, traceback):
        if self._name:
            self.stop(self._name)
        self._name = None

    def start(self, name, info=None):
        """Currently time measurement itself is delegated to
        notification.api. Every message is marked with a unix
        timestamp and for now it should be sufficient.
        Later more precise measurements can be added here.
        """
        self._trace_stack.append(str(uuid.uuid4()))
        self._notify('%s-start' % name, info)

    def stop(self, name, info=None):
        self._notify('%s-stop' % name, info)
        self._trace_stack.pop()

    def _notify(self, name, info):
        payload = {
            'name': name,
            'base_id': self._trace_stack[0],
            'trace_id': self._trace_stack[-1],
            'parent_id': self._trace_stack[-2]
        }
        if info:
            payload['info'] = info

        publisher_id = notifier_api.publisher_id(self._service)
        notifier_api.notify(self._context, publisher_id,
                            'profiler.%s' % self._service,
                            notifier_api.INFO, payload)


def traced(name, profiler=None):
    if profiler:
        assert(isinstance(profiler, Profiler))
    else:
        profiler = Profiler()

    def wrapper(func):
        @functools.wraps(func)
        def decorator(*args, **kwargs):
            with profiler(name):
                return func(*args, **kwargs)
        return decorator
    return wrapper
