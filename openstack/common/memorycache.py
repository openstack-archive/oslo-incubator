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

import heapq

from oslo.config import cfg

from openstack.common import timeutils

memcache_opts = [
    cfg.ListOpt('memcached_servers',
                help='Memcached servers or None for in process cache.'),
]

CONF = cfg.CONF
CONF.register_opts(memcache_opts)


def get_client(memcached_servers=None):
    client_cls = Client

    if not memcached_servers:
        memcached_servers = CONF.memcached_servers
    if memcached_servers:
        import memcache
        client_cls = memcache.Client

    return client_cls(memcached_servers, debug=0)


class Client(object):
    """Replicates a tiny subset of memcached client interface."""

    def __init__(self, *args, **kwargs):
        """Ignores the passed in args."""
        self.cache = {}
        self.priority_queue = []

    def _clean_expired_items(self):
        """Removes items which have passed their timeout."""
        now = timeutils.utcnow_ts()
        while self.priority_queue and self.priority_queue[0][0] <= now:
            (t,k) = heapq.heappop(self.priority_queue)
            del self.cache[k]

    def _remove_from_pq(self, key):
        self.priority_queue = [ (t,k) for (t,k) in self.priority_queue if key != k ]
        heapq.heapify(self.priority_queue)

    def get(self, key):
        """Retrieves the value for a key or None."""
        self._clean_expired_items()
        return self.cache.get(key)

    def set(self, key, value, time=0, min_compress_len=0):
        """Sets the value for a key."""
        timeout = 0
        if key in self.cache:
            self._remove_from_pq(key)
        if time != 0:
            timeout = timeutils.utcnow_ts() + time
            heapq.heappush(self.priority_queue, (timeout, key))
        self.cache[key] = value
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
        self.cache[key] = str(new_value)
        return new_value

    def delete(self, key, time=0):
        """Deletes the value associated with a key."""
        if key in self.cache:
            del self.cache[key]
            self._remove_from_pq(key)
