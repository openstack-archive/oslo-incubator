# -*- coding: utf-8 -*-

# Copyright 2013 Metacloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import functools

from dogpile.cache import compat

from openstack.common.cache import core


__all__ = ['memoize']


def memoize(cache_region_name, namespace=None, expiration_time=None,
            should_cache_fn=None, to_str=compat.string_type):
    """Memoization decorator that leverages dogpile.cache as the store.


    ..NOTE::
        Unless a new `function_key_generator` and
        `function_multi_key_generator` are configured on the cache region
        when `.configure()` is called, this decorator cannot be utilized on
        methods with keyword arguments. Maintaining cache coherency
        and supporting proper cache invalidation when working with optional
        arguments is very difficult to do correctly. Due to this extreme
        difficulty, the default behavior is to not allow memoization of
        methods with keyword arguments. (An exception will be
        raised when the decorator attempts to generate the cache-key on
        method invocation).

    See ``dogpile.cache.region.CacheRegion.cache_on_arguments`` for more
    information. This decorator is mostly a wrapper for the dogpile native
    decorator.

    :param cache_region_name: The string value of the "CacheRegion" name,
                              primarily used to group caching of values to
                              the same Cache Backend/Cache Configuration
    :param namespace: A value that can be used to disambiguate between two
                      methods (on different classes) with the same name.
    :param expiration_time: If passed as an Int, this is the time-to-live of
                            the memoized value for the decorated method (in
                            seconds). If this is a callable, it will be called
                            with no parameters and the returned value will be
                            used as the time-to-live of the memoized value
                            for the decorated method (in seconds).
    :param should_cache_fn: A callable function that will be passed the
                            resulting value from the decorated method. The
                            function should return True if the result is to be
                            cached and False if the result should not be
                            cached.
    :param: to_str: callable, will be called on each function argument
                    in order to convert to a string, defaults to `str()`
    """
    # NOTE(morganfainberg): If the cache region has not been configured, a
    # memoized function will raise an exception. This decorator goes through
    # extra work to ensure that the actual wrapped function/method from the
    # cache region `cache_on_arguments` wrapper will not be executed unless
    # the cache region has been configured. In the case that the cache
    # region is not configured, an un-wrapped version of the method is
    # executed instead.
    #
    # It should be noted that the memoize decorator use will preclude the
    # ability to get rid of all of the references to the WeakRefValue that
    # could allow for a new CacheController and configuration to be loaded for
    # the `cache_region_name` used.

    cache_region = core.get_cache_region(cache_region_name)
    cache_on_args_fn = cache_region.cache_on_arguments(
        namespace=namespace, expiration_time=expiration_time,
        should_cache_fn=should_cache_fn, to_str=to_str)

    def decorator(fn):
        memoized_function = cache_on_args_fn(fn)

        def invalidate(*args, **kwargs):
            if cache_region.is_configured:
                memoized_function.invalidate(*args, **kwargs)

        def set_(*args, **kwargs):
            if cache_region.is_configured:
                memoized_function.set(*args, **kwargs)

        def refresh(*args, **kwargs):
            if cache_region.is_configured:
                memoized_function.refresh(*args, **kwargs)

        @functools.wraps(fn)
        def decorate(*args, **kwargs):
            if cache_region.is_configured:
                memoized_function(*args, **kwargs)
            return fn(*args, **kwargs)

        decorate.invalidate = invalidate
        decorate.set = set_
        decorate.refresh = refresh

        return decorate
    return decorator
