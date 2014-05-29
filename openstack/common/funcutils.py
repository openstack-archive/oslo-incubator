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

"""Utility methods for working with functions/decorators."""

import inspect

import six


def get_wrapped_function(function):
    """Get the method at the bottom of a stack of decorators."""

    if not hasattr(function, six._func_closure) or \
       not six.get_function_closure(function):
        return function

    def _get_wrapped_function(function):
        if not hasattr(function, six._func_closure):
            return None

        func_closure = six.get_function_closure(function)
        if not func_closure:
            return None

        for closure in func_closure:
            func = closure.cell_contents

            deeper_func = _get_wrapped_function(func)
            if deeper_func:
                return deeper_func
            elif hasattr(closure.cell_contents, '__call__'):
                return closure.cell_contents

    return _get_wrapped_function(function)


def getcallargs(function, *args, **kwargs):
    """This is a simplified inspect.getcallargs (2.7+).

    It should be replaced when python >= 2.7 is standard.
    """

    keyed_args = {}
    argnames, varargs, keywords, defaults = inspect.getargspec(function)

    keyed_args.update(kwargs)

    # NOTE(alaski) the implicit 'self' or 'cls' argument shows up in
    # argnames but not in args or kwargs.  Uses 'in' rather than '==' because
    # some tests use 'self2'.
    if 'self' in argnames[0] or 'cls' == argnames[0]:
        # The function may not actually be a method or have __self__.
        # Typically seen when it's stubbed with mox.
        if inspect.ismethod(function) and hasattr(function, '__self__'):
            keyed_args[argnames[0]] = function.__self__
        else:
            keyed_args[argnames[0]] = None

    remaining_argnames = filter(lambda x: x not in keyed_args, argnames)
    keyed_args.update(dict(zip(remaining_argnames, args)))

    if defaults:
        num_defaults = len(defaults)
        for argname, value in zip(argnames[-num_defaults:], defaults):
            if argname not in keyed_args:
                keyed_args[argname] = value

    return keyed_args
