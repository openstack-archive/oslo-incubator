# Copyright 2014 VMware
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

import collections
import warnings
import weakref

from openstack.common.cache import backends


class WeakrefBackend(backends.BaseCache):
    """This backend uses Python's weakref API for cache cleaning.

    Normal references increment the reference counter to an object by one. The
    weakref API allows you to hold a reference to an object that does not
    increment the reference counter so that the normal Python GC will collect
    the reference during its pass.

    Because the cache is managed by Python's own GC it will grow as resources
    permit and will shrink as resources are constrained. When the GC runs it
    will sweep the cache clean. That means ttl is ignored since the ttl is
    determined dynamically by the GC itself.
    """

    def __init__(self, parsed_url, options=None):
        super(WeakrefBackend, self).__init__(parsed_url, options)
        self._cache = {}

    def _set(self, key, value, ttl, not_exists=False):

        def collected(ref):
            self.__delitem__(key)

        weak_key = weakref.ref(key, collected)
        # feed the weak reference to the cache
        # the weak reference is actually the key
        # so the GC will collect the key
        self._cache[weak_key] = value

    def _get(self, key, default):
        self._cache.get(key, default)

    def __setitem__(self, key, value):
        self._cache[key] = value

    def __delitem__(self, key):
        try:
            # The key here is from closure, and is calculated later.
            del self.cache[key]
        except KeyError:
            # Some other weak reference might have already removed that
            # key -- in that case we don't need to do anything.
            pass

