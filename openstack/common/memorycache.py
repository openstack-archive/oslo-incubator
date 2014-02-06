# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
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

"""Super simple fake memcache client."""

from oslo.config import cfg

from openstack.common import timeutils

memcache_opts = [
    cfg.ListOpt('memcached_servers',
                default=None,
                help='Memcached servers or None for in process cache.'),
]

CONF = cfg.CONF
CONF.register_opts(memcache_opts)


def get_client(memcached_servers=None):
    client_cls = Client

    if not memcached_servers:
        memcached_servers = CONF.memcached_servers
    if memcached_servers:
        try:
            import memcache
            client_cls = memcache.Client
        except ImportError:
            pass

    return client_cls(memcached_servers, debug=0)


class Client(object):
    """Replicates a tiny subset of memcached client interface."""

    def __init__(self, _servers, cache_clean_period=60, *args, **kwargs):
        """Ignores the passed in args, except for cache_clean_period."""
        self.cache_clean_period = cache_clean_period
        self.last_cache_clean = timeutils.utcnow_ts()
        self.cache = {}

    def _clean_expired_items_if_necessary(self):
        """Calls the clean method if it hasn't been called
        recently enough.
        """
        if timeutils.utcnow_ts() > (self.last_cache_clean +
                                    self.cache_clean_period):
            self.clean_expired_items()

    def clean_expired_items(self):
        """Removes items which have passed their timeout.  This will
        happen automatically every cache_clean_period seconds,
        but clients may wish to call this method more frequently for
        a busy cache.  Returns the number of evicted items.
        """
        now = timeutils.utcnow_ts()
        for k in list(self.cache):
            (timeout, _value) = self.cache[k]
            if timeout and timeout <= now:
                del self.cache[k]
        self.last_cache_clean = now

    def get(self, key):
        """Retrieves the value for a key or None."""
        self._clean_expired_items_if_necessary()
        (timeout, value) = self.cache.get(key, (0, None))
        expired = timeout and timeout <= timeutils.utcnow_ts()
        return value if not expired else None

    def set(self, key, value, time=0, min_compress_len=0):
        """Sets the value for a key."""
        timeout = 0
        if time != 0:
            timeout = timeutils.utcnow_ts() + time
        self.cache[key] = (timeout, value)
        return True

    def add(self, key, value, time=0, min_compress_len=0):
        """Sets the value for a key if it doesn't exist."""
        if self.get(key) is not None:
            return False
        return self.set(key, value, time, min_compress_len)

    def incr(self, key, delta=1):
        """Increments the value for a key."""
        value = self.get(key)
        if value is None:
            return None
        new_value = int(value) + delta
        self.cache[key] = (self.cache[key][0], str(new_value))
        return new_value

    def delete(self, key, time=0):
        """Deletes the value associated with a key."""
        if key in self.cache:
            del self.cache[key]
