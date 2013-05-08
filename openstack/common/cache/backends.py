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

import abc


class BaseCache(object):

    __metaclas__ = abc.ABCMeta

    def __init__(self, conf, cache_prefix):
        self.conf = conf
        self._cache_prefix = cache_prefix

    @abc.abstractmethod
    def set(self, key, value, ttl=0):
        """Sets a key to the cache

        :params key: Key to create as string.
        :params value: Value to assign to the key. This
                       can be anything that is handled
                       by current back-end.
        :params ttl: Key's timeout in seconds.
        """

    @abc.abstractmethod
    def get(self, key, default=None):
        """Gets one or many keys from the cache

        :params key: Key to lookup in the cache.
        :params default: The default value to return.

        :returns: `key`'s value in the cache if it exists,
                  otherwise `default` should be returned.
        """

    @abc.abstractmethod
    def unset(self, key):
        """Removes key from cache.

        :params key: The key to remove.

        :returns: The key value if there's one
        """

    def _prefix_key(self, key):
        """Prepares the key

        This method concatenates the cache_prefix
        and the key so it can be used in the cache.

        NOTE: All cache backends have to call it
        explicitly where needed.

        :param key: The key to be prefixed
        """
        if self._cache_prefix:
            return ("%(prefix)s-%(key)s" %
                    {'prefix': self._cache_prefix, 'key': key})
        return key

    def add(self, key, value, ttl=0):
        """Sets the value for a key if it doesn't exist

        :params key: Key to create as string.
        :params value: Value to assign to the key. This
                       can be anything that is handled
                       by current back-end.
        :params ttl: Key's timeout in seconds.
        """
        if self.get(key) is not None:
            return False
        return self.set(key, value, ttl)

    def get_many(self, keys, default=None):
        """Gets key's value from cache

        :params keys: List of keys to retrieve.
        :params default: The default value to return.

        :returns: A  generator of (key, value)
        """
        for k in keys:
            val = self.get(k, default=default)
            if val is not None:
                yield (k, val)

    def has_key(self, key):
        """Verifies if a key exists.

        :params key: The key which existence should
                     be verified.

        :returns: True if the key exists, otherwise
                  False.
        """
        return self.get(key) is not None

    def set_many(self, data, ttl=0):
        """Sets many keys in the cache

        :params data: A dictionary like {key: val} to store
                      in the cache.
        :params ttl: Key's timeout in seconds.
        """
        for key, value in data.items():
            self.set(key, value, ttl=ttl)

    def incr(self, key, delta=1):
        """Increments the value for a key

        :params key: The key to add the value to.
        :params delta: Units to increment. Use negative
                       numbers to decrement `key`

        :returns: The new value
        """
        value = self.get(key)
        if value is None:
            return None
        new_value = value + delta
        self.set(key, new_value)
        return new_value

    def append(self, key, tail):
        """Appends `value` to `key`'s value.

        :params key: The key to append value to.
        :params tail: The value to append to `key`

        :returns: The new value
        """
        value = self.get(key)
        if value is None:
            return None
        new_value = value + tail
        self.set(key, new_value)
        return new_value
