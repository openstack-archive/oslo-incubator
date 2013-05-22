# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 Red Hat, Inc.
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

# W0102: Dangerous default value %s as argument
# W0603: Using the global statement
# W0621: Redefining name %s from outer scope
# pylint: disable=W0102,W0603,W0621

import getpass
import inspect
import os
import sys
import textwrap
import uuid

import prettytable

from openstack.common.apiclient import exceptions
from openstack.common import strutils


MAX_PASSWORD_PROMTS = 3


def validate_args(fn, *args, **kwargs):
    """Check that the supplied args are sufficient for calling a function.

    >>> validate_args(lambda a: None)
    Traceback (most recent call last):
        ...
    MissingArgs: An argument is missing
    >>> validate_args(lambda a, b, c, d: None, 0, c=1)
    Traceback (most recent call last):
        ...
    MissingArgs: 2 arguments are missing

    :param fn: the function to check
    :param arg: the positional arguments supplied
    :param kwargs: the keyword arguments supplied
    """
    argspec = inspect.getargspec(fn)

    num_defaults = len(argspec.defaults or [])
    required_args = argspec.args[:len(argspec.args) - num_defaults]

    def isbound(method):
        return getattr(method, 'im_self', None) is not None

    if isbound(fn):
        required_args.pop(0)

    missing = [arg for arg in required_args if arg not in kwargs]
    missing = missing[len(args):]
    if missing:
        raise exceptions.MissingArgs(missing)


def arg(*args, **kwargs):
    """Decorator for CLI args."""
    def _decorator(func):
        add_arg(func, *args, **kwargs)
        return func
    return _decorator


def env(*args, **kwargs):
    """Returns the first environment variable set.

    If all are empty, defaults to '' or keyword arg `default`.
    """
    for arg in args:
        value = os.environ.get(arg, None)
        if value:
            return value
    return kwargs.get('default', '')


def add_arg(func, *args, **kwargs):
    """Bind CLI arguments to a shell.py `do_foo` function."""

    if not hasattr(func, 'arguments'):
        func.arguments = []

    # NOTE(sirp): avoid dups that can occur when the module is shared across
    # tests.
    if (args, kwargs) not in func.arguments:
        # Because of the sematics of decorator composition if we just append
        # to the options list positional options will appear to be backwards.
        func.arguments.insert(0, (args, kwargs))


def unauthenticated(func):
    """Adds 'unauthenticated' attribute to decorated function.

    Usage:

    >>> @unauthenticated
    ... def mymethod(f):
    ...     pass
    """
    func.unauthenticated = True
    return func


def isunauthenticated(func):
    """Checks if the function does not require authentication.

    Mark such functions with the `@unauthenticated` decorator.

    :returns: bool
    """
    return getattr(func, 'unauthenticated', False)


def print_list(objs, fields, formatters={}, sortby_index=0):
    if sortby_index is None:
        sortby = None
    else:
        sortby = fields[sortby_index]
    mixed_case_fields = ['serverId']
    pt = prettytable.PrettyTable([f for f in fields], caching=False)
    pt.align = 'l'

    for o in objs:
        row = []
        for field in fields:
            if field in formatters:
                row.append(formatters[field](o))
            else:
                if field in mixed_case_fields:
                    field_name = field.replace(' ', '_')
                else:
                    field_name = field.lower().replace(' ', '_')
                data = getattr(o, field_name, '')
                row.append(data)
        pt.add_row(row)

    if sortby is not None:
        print(strutils.safe_encode(pt.get_string(sortby=sortby)))
    else:
        print(strutils.safe_encode(pt.get_string()))


def print_dict(dct, dict_property="Property", wrap=0):
    pt = prettytable.PrettyTable([dict_property, 'Value'], caching=False)
    pt.align = 'l'
    for k, v in dct.iteritems():
        # convert dict to str to check length
        if isinstance(v, dict):
            v = str(v)
        if wrap > 0:
            v = textwrap.fill(str(v), wrap)
        # if value has a newline, add in multiple rows
        # e.g. fault with stacktrace
        if v and isinstance(v, basestring) and r'\n' in v:
            lines = v.strip().split(r'\n')
            col1 = k
            for line in lines:
                pt.add_row([col1, line])
                col1 = ''
        else:
            pt.add_row([k, v])
    print(strutils.safe_encode(pt.get_string()))


def find_resource(manager, name_or_id):
    """Helper for the _find_* methods."""
    # first try to get entity as integer id
    try:
        is_intid = isinstance(name_or_id, int) or name_or_id.isdigit()
    except AttributeError:
        is_intid = False

    if is_intid:
        try:
            return manager.get(int(name_or_id))
        except exceptions.NotFound:
            pass

    # now try to get entity as uuid
    try:
        uuid.UUID(strutils.safe_encode(name_or_id))
        return manager.get(name_or_id)
    except (TypeError, ValueError, exceptions.NotFound):
        pass

    # for str id which is not uuid (for Flavor search currently)
    if getattr(manager, 'is_alphanum_id_allowed', False):
        try:
            return manager.get(name_or_id)
        except exceptions.NotFound:
            pass

    try:
        try:
            return manager.find(human_id=name_or_id)
        except exceptions.NotFound:
            pass

        # finally try to find entity by name
        try:
            resource = getattr(manager, 'resource_class', None)
            name_attr = resource.NAME_ATTR if resource else 'name'
            kwargs = {name_attr: name_or_id}
            return manager.find(**kwargs)
        except exceptions.NotFound:
            msg = "No %s with a name or ID of '%s' exists." % \
                (manager.resource_class.__name__.lower(), name_or_id)
            raise exceptions.CommandError(msg)
    except exceptions.NoUniqueMatch:
        msg = ("Multiple %s matches found for '%s', use an ID to be more"
               " specific." % (manager.resource_class.__name__.lower(),
                               name_or_id))
        raise exceptions.CommandError(msg)


def get_password():
    verify = strutils.bool_from_string(env("OS_VERIFY_PASSWORD"))
    pw = None
    if hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
        # Check for Ctl-D
        try:
            for _ in xrange(MAX_PASSWORD_PROMTS):
                pw1 = getpass.getpass('OS Password: ')
                if verify:
                    pw2 = getpass.getpass('Please verify: ')
                else:
                    pw2 = pw1
                if pw1 == pw2 and pw1:
                    pw = pw1
                    break
        except EOFError:
            pass
    return pw
