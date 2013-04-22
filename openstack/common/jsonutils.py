# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
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

'''
JSON related utilities.

This module provides a few things:

    1) A handy function for getting an object down to something that can be
    JSON serialized.  See to_primitive().

    2) Wrappers around loads() and dumps().  The dumps() wrapper will
    automatically use to_primitive() for you if needed.

    3) This sets up anyjson to use the loads() and dumps() wrappers if anyjson
    is available.
'''


import datetime
import functools
import inspect
import itertools
import json
import types
import xmlrpclib

from openstack.common.gettextutils import _

from openstack.common import timeutils

_simple_type_tests = (types.NoneType, int, basestring, bool, float, long)
_nasty_type_tests = (inspect.ismodule, inspect.isclass, inspect.ismethod,
                     inspect.isfunction, inspect.isgeneratorfunction,
                     inspect.isgenerator, inspect.istraceback, inspect.isframe,
                     inspect.iscode, inspect.isbuiltin, inspect.isroutine,
                     inspect.isabstract)


class NotSerializableException(Exception):
    pass


def _get_object_id(value):
    # From python docs:
    #
    # This is an integer (or long integer) which is guaranteed to be unique
    # and constant for this object during its lifetime.
    return id(value)


def _simple_helper(value, **kwargs):
    """
    # handle obvious types first - order of basic types determined by running
    # full tests on nova project, resulting in the following counts:
    # 572754 <type 'NoneType'>
    # 460353 <type 'int'>
    # 379632 <type 'unicode'>
    # 274610 <type 'str'>
    # 199918 <type 'dict'>
    # 114200 <type 'datetime.datetime'>
    #  51817 <type 'bool'>
    #  26164 <type 'list'>
    #   6491 <type 'float'>
    #    283 <type 'tuple'>
    #     19 <type 'long'>
    """

    if isinstance(value, _simple_type_tests):
        return value
    if isinstance(value, datetime.datetime):
        if kwargs.get('convert_datetime'):
            return timeutils.strtime(value)
        else:
            return value
    raise NotSerializableException()


def _nasty_helper(value, **kwargs):
    for functor in _nasty_type_tests:
        if functor(value):
            return unicode(value)
    # Note: value of itertools.count doesn't get caught by _nasty_type_tests
    # above and results in infinite loop when list(value) is called.
    if type(value) == itertools.count:
        return unicode(value)
    raise NotSerializableException()


def _mock_helper(value, **kwargs):
    # FIXME(vish): Workaround for LP bug 852095. Without this workaround,
    #              tests that raise an exception in a mocked method that
    #              has a @wrap_exception with a notifier will fail. If
    #              we up the dependency to 0.5.4 (when it is released) we
    #              can remove this workaround.
    if getattr(value, '__module__', None) == 'mox':
        return 'mock'
    raise NotSerializableException()


def _recursive_helper(value, convert_instances, convert_datetime, level,
                      max_depth, in_progress):
    try:
        recursive = functools.partial(_to_primitive_helper,
                                      convert_instances=convert_instances,
                                      convert_datetime=convert_datetime,
                                      level=level,
                                      max_depth=max_depth,
                                      in_progress=in_progress)

        if isinstance(value, dict):
            return dict((k, recursive(v)) for k, v in value.iteritems())
        elif isinstance(value, (list, tuple)):
            return [recursive(lv) for lv in value]

        # It's not clear why xmlrpclib created their own DateTime type, but
        # for our purposes, make it a datetime type which is explicitly
        # handled
        if isinstance(value, xmlrpclib.DateTime):
            value = datetime.datetime(*tuple(value.timetuple())[:6])

        if convert_datetime and isinstance(value, datetime.datetime):
            return timeutils.strtime(value)
        elif hasattr(value, 'iteritems'):
            return recursive(dict(value.iteritems()), level=level + 1)
        elif hasattr(value, '__iter__'):
            return recursive(list(value))
        elif convert_instances and hasattr(value, '__dict__'):
            # Likely an instance of something. Watch for cycles.
            # Ignore class member vars.
            return recursive(value.__dict__, level=level + 1)
        else:
            return value
    except TypeError:
        # Class objects are tricky since they may define something like
        # __iter__ defined but it isn't callable as list().
        return unicode(value)


def _to_primitive_helper(value, in_progress,
                         convert_instances, convert_datetime,
                         level, max_depth):
    """Convert a complex object into primitives.

    Handy for JSON serialization. We can optionally handle instances,
    but since this is a recursive function, we could have cyclical
    data structures.

    Therefore, convert_instances=True is lossy ... be aware.
    """

    if level > max_depth:
        raise RuntimeError(_('Maximum to_primitive recursion depth of %s '
                             'exceeded') % (max_depth))

    value_id = _get_object_id(value)
    if value_id in in_progress:
        raise RuntimeError(_("Cycle found for object: %s") % value)

    # The function order matters here since we want to activate the recursive
    # helper as the last one that will get called, and not the first...
    for func in (_simple_helper, _nasty_helper, _mock_helper,
                 _recursive_helper):
        in_progress[value_id] = True
        try:
            return func(value,
                        convert_instances=convert_instances,
                        convert_datetime=convert_datetime,
                        level=level,
                        in_progress=in_progress,
                        max_depth=max_depth)
        except NotSerializableException:
            pass
        finally:
            in_progress.pop(value_id)

    raise NotSerializableException(("Unable to convert: %s") % type(value))


def to_primitive(value, convert_instances=False, convert_datetime=True,
                 max_depth=3):
    max_depth = max(0, max_depth)
    return _to_primitive_helper(value,
                                convert_instances=convert_instances,
                                convert_datetime=convert_datetime,
                                level=0,
                                max_depth=max_depth,
                                in_progress={})


def dumps(value, default=to_primitive, **kwargs):
    return json.dumps(value, default=default, **kwargs)


def loads(s):
    return json.loads(s)


def load(s):
    return json.load(s)


try:
    import anyjson
except ImportError:
    pass
else:
    anyjson._modules.append((__name__, 'dumps', TypeError,
                                       'loads', ValueError, 'load'))
    anyjson.force_implementation(__name__)
