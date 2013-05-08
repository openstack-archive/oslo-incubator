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

import six


@six.add_metaclass(abc.ABCMeta)
class BaseCache(object):
    """Base Cache Abstraction

    :params parsed_url: Parsed url object.
    :params options: A dictionary with configuration parameters
        for the cache. For example:
            - default_ttl: An integer defining the default ttl
            for keys.
    """

    def __init__(self, parsed_url, options=None):
        self._parsed_url = parsed_url
        self._options = options or {}
        self._default_ttl = int(self._options.get('default_ttl', 0))

    @abc.abstractmethod
    def set(self, key, value, ttl=0, not_exists=False):
        """Sets or updates a cache entry

        NOTE: Thread-safety is required and has to be
        guaranteed by the backend implementation.

        :params key: Item key as string.
        :type key: `unicode string`
        :params value: Value to assign to the key. This
                       can be anything that is handled
                       by the current backend.
        :params ttl: Key's timeout in seconds. 0 means
                     no timeout.
        :type ttl: int
        :params not_exists: If True, the key will be set
                            if it doesn't exist. Otherwise,
                            it'll always be set.
        :type not_exists: bool

        :returns: True if the operation succeeds, False otherwise.
        """

    def __setitem__(self, key, value):
        self.set(key, value, self._default_ttl)

    @abc.abstractmethod
    def get(self, key, default=None):
        """Gets one item from the cache

        NOTE: Thread-safety is required and it has to be
        guaranteed by the backend implementation.

        :params key: Key for the item to retrieve
                     from the cache.
        :params default: The default value to return.

        :returns: `key`'s value in the cache if it exists,
                  otherwise `default` should be returned.
        """

    def __getitem__(self, key):
        # NOTE(flaper87): Should this raise
        # KeyError? The difficult bit would
        # be 'knowing' when the key was not
        # set. None is not a valid reference
        # because values can indeed be None.
        return self.get(key)

    @abc.abstractmethod
    def unset(self, key):
        """Removes an item from cache.

        NOTE: Thread-safety is required and it has to be
        guaranteed by the backend implementation.

        :params key: The key to remove.

        :returns: The key value if there's one
        """

    def __delitem__(self, key):
        return self.unset(key)

    @abc.abstractmethod
    def clear(self):
        """Removes all items from the cache.

        NOTE: Thread-safety is required and it has to be
        guaranteed by the backend implementation.
        """

    @abc.abstractmethod
    def incr(self, key, delta=1):
        """Increments the value for a key

        :params key: The key for the value to be incremented
        :params delta: Number of units by which to increment
                       the value. Pass a negative number to
                       decrement the value.

        :returns: The new value
        """

    @abc.abstractmethod
    def append(self, key, tail):
        """Appends `value` to `key`'s value.

        :params key: The key of the value to which
                     `tail` should be appended.
        :params tail: The value to append to the
                      original.

        :returns: The new value
        """

    @abc.abstractmethod
    def exists(self, key):
        """Verifies that a key exists.

        :params key: The key to verify.

        :returns: True if the key exists,
                  otherwise False.
        """

    def __contains__(self, key):
        return self.exists(key)

    @abc.abstractmethod
    def get_many(self, keys, default=None):
        """Gets keys' value from cache

        :params keys: List of keys to retrieve.
        :params default: The default value to return
                         for each key that is not in
                         the cache.

        :returns: A  generator of (key, value)
        """
        for k in keys:
            val = self.get(k, default=default)
            yield (k, val)

    @abc.abstractmethod
    def set_many(self, data, ttl=0):
        """Puts several items into the cache at once

        Depending on the backend, this operation may or may
        not be efficient. The default implementation calls
        set for each (key, value) pair passed, other backends
        support set_many operations as part of their protocols.

        :params data: A dictionary like {key: val} to store
                      in the cache.
        :params ttl: Key's timeout in seconds.
        """
        for key, value in data.items():
            self.set(key, value, ttl=ttl)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            self.set(key, value, self._default_ttl)

    @abc.abstractmethod
    def unset_many(self, keys):
        """Removes several keys from the cache at once

        :params keys: List of keys to unset.
        """
        for key in keys:
            self.unset(key)
