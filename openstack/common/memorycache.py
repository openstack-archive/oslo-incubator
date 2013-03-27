# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

from openstack.common.gettextutils import _
from openstack.common import log as logging
from openstack.common import timeutils

memcache_opts = [
    cfg.ListOpt('memcached_servers',
                default=None,
                help='Memcached servers or None for in process cache.'),
]

CONF = cfg.CONF
CONF.register_opts(memcache_opts)
LOG = logging.getLogger(__name__)


try:
    import memcache
    has_memcache = True
except ImportError:
    has_memcache = False


def get_client(memcached_servers=None):
    if memcached_servers is None:
        memcached_servers = CONF.memcached_servers

    if memcached_servers and has_memcache:
        return SafeMemcacheClient(memcached_servers, debug=0)
    else:
        return SafeClient()


class Client(object):
    """Replicates a tiny subset of memcached client interface."""

    def __init__(self, *args, **kwargs):
        """Ignores the passed in args."""
        self.cache = {}

    def get(self, key):
        """Retrieves the value for a key or None.

        this expunges expired keys during each get"""

        now = timeutils.utcnow_ts()
        for k in self.cache.keys():
            (timeout, _value) = self.cache[k]
            if timeout and now >= timeout:
                del self.cache[k]

        return self.cache.get(key, (0, None))[1]

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


def fallback_wrapper(default=None):
    """This wrapper calls super on a class which doesn't really have a parent,
    but due to MRO will work like a mixin and resolve to the actual client
    class as long as SafeClient uses the right parent class order.
    """
    def wrapper(f):
        def func(self, key, *args, **kwargs):
            try:
                actual_func = getattr(super(SafeClientMixin, self),
                                      f.__name__)
                return actual_func(key, *args, **kwargs)
            except Exception:
                LOG.exception(_("Cache failure while performing %s on key %s"),
                              f.__name__, key)
                return default_return
        return func
    return wrapper


class SafeClientMixin(object):
    @fallback_wrapper()
    def get(*args, **kwargs):
        pass

    @fallback_wrapper(False)
    def set(*args, **kwargs):
        pass

    @fallback_wrapper(False)
    def add(*args, **kwargs):
        pass

    @fallback_wrapper()
    def incr(*args, **kwargs):
        pass

    @fallback_wrapper(False)
    def delete(*args, **kwargs):
        pass


class SafeClient(SafeClientMixin, Client):
    pass


if has_memcache:
    class SafeMemcacheClient(SafeClientMixin, memcache.Client):
        pass
