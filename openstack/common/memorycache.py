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

import copy
import signal
import threading
import time

from oslo_config import cfg
from oslo_utils import timeutils


memcache_opts = [
    cfg.ListOpt('memcached_servers',
                help='Memcached servers or None for in process cache.'),
    cfg.IntOpt('memcache_cleanup_timer',
               default=60,
               help='Time, in seconds, for which the cleanup thread wakes '
                    'up to remove stale items from the cache'),
]

CONF = cfg.CONF
CONF.register_opts(memcache_opts)


def list_opts():
    """Entry point for oslo-config-generator."""
    return [(None, copy.deepcopy(memcache_opts))]


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
    cleanup_thread = None
    sigterm_received = False

    def __init__(self, *args, **kwargs):
        """Ignores the passed in args."""
        self.cache = {}
        signal.signal(signal.SIGHUP, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGQUIT, self._signal_handler)
        signal.signal(signal.SIGALRM, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _init_cleanup_thread(self):
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(target=self._cleanup_worker)
            self.cleanup_thread.start()

    def _signal_handler(self, signum, frame):
        self.sigterm_received = True

    def _cleanup_worker(self):
        while True:
            contains_timed_object = False
            now = timeutils.utcnow_ts()

            for k in list(self.cache):
                (timeout, _value) = self.cache[k]
                if timeout:
                    if now >= timeout:
                        del self.cache[k]
                    else:
                        contains_timed_object = True
            # cache is empty or the cache contains no timed objects
            # kill the thread
            if not len(self.cache) or not contains_timed_object:
                return
            for x in range(CONF.memcache_cleanup_timer):
                # signal was received.  kill the thread
                if self.sigterm_received:
                    return
                # time.sleep doesn't handle SIGTERM.  We're going to loop
                # in short time intervals to kill the thread quicker if a
                # signal is received
                time.sleep(1)

    def get(self, key):
        """Retrieves the value for a key or None.
        """
        if key not in self.cache:
            return None
        now = timeutils.utcnow_ts()
        (timeout, _value) = self.cache[key]
        if timeout and now >= timeout:
            del self.cache[key]

        return self.cache.get(key, (0, None))[1]

    def set(self, key, value, time=0, min_compress_len=0):
        """Sets the value for a key."""
        timeout = 0
        if time != 0:
            timeout = timeutils.utcnow_ts() + time
            self._init_cleanup_thread()

        self.cache[key] = (timeout, value)
        return True

    def add(self, key, value, time=0, min_compress_len=0):
        """Sets the value for a key if it doesn't exist."""
        if self.get(key) is not None:
            return False

        if time != 0:
            self._init_cleanup_thread()

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
