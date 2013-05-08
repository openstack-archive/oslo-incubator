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


from openstack.common.cache import backends
from openstack.common import lockutils
from openstack.common import timeutils


class MemoryBackend(backends.BaseCache):

    def __init__(self, conf, cache_prefix):
        super(MemoryBackend, self).__init__(conf, cache_prefix)
        self._cache = {}
        self._cache_ttl = {}
        self._lock = lockutils.DynamicRWLock()

    def set(self, key, value, ttl=0):
        with self._lock.write(key):
            key = self._prefix_key(key)
            if ttl != 0:
                ttl = timeutils.utcnow_ts() + ttl
            self._cache[key] = (ttl, value)

            if ttl:
                self._cache_ttl.setdefault(ttl, set()).add(key)

            return True

    def get(self, key, default=None):
        with self._lock.read(key):
            key = self._prefix_key(key)
            now = timeutils.utcnow_ts()

            try:
                timeout, value = self._cache[key]

                if timeout and now >= timeout:
                    del self._cache[key]
                    return default

                return value
            except KeyError:
                return default

    def unset(self, key):
        with self._lock.write(key):
            now = timeutils.utcnow_ts()
            for timeout in sorted(self._cache_ttl.keys()):

                # NOTE(flaper87): If timeout is greater
                # than `now`, stop the iteration, other
                # keys are have not expired.
                if now < timeout:
                    break

                # NOTE(flaper87): Unset every key in
                # this set from the cache if its timeout
                # is equal to `timeout`. (They key might
                # have been updated)
                for subkey in self._cache_ttl.pop(timeout):
                    if self._cache[subkey][0] == timeout:
                        del self._cache[subkey]

            # NOTE(flaper87): Delete the key. Using pop
            # since it could have been deleted already
            self._cache.pop(self._prefix_key(key), None)
