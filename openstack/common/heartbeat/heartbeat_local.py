# Copyright 2013 IBM Corp.
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
import fcntl
import json
import mmap
import os.path
import time

from openstack.common import heartbeat
from openstack.common import log as logging

LOG = logging.getLogger(__name__)
MAPPING_FILE = '/tmp/test.mmap'
CACHE_SIZE = 4096
PADDING = '\n'


class HeartbeatLocal(heartbeat.HeartbeatDriverBase):
    """Local heartbeat based on mmap. Only used for
    all component run on same node. Useful for test.
    """
    def __init__(self, freq, ttl):
        super(HeartbeatLocal, self).__init__(freq, ttl)
        if not os.path.exists(MAPPING_FILE):
            self.f = open(MAPPING_FILE, 'w+')
        else:
            self.f = open(MAPPING_FILE, 'rw+')
        self.f.seek(CACHE_SIZE)
        self.f.write('\n')
        self.f.flush()
        self.m = mmap.mmap(self.f.fileno(), 0)

    def _update_cache(self, key_values={}):
        """key_values = {} means just load the cache.
        If the value was 'None' means delete this item.
        """
        fcntl.flock(self.f.fileno(), fcntl.LOCK_EX)
        try:
            # update the cache
            try:
                self.cache = json.loads(self.m[:CACHE_SIZE])
            except:
                self.cache = {}
            if key_values:
                self.cache.update(key_values)
                for key, val in key_values.iteritems():
                    if not val:
                        if self.cache.has_key(key):
                            del self.cache[key]
            else:
                return
            # write the updated cache back to file
            s = json.dumps(self.cache)
            if len(s) > CACHE_SIZE:
                LOG.warn("Cache size: %(cache_size)s was overflow,"
                         "defined cache size: %(defined_cache_size)s!",
                         {'cache_size': len(s),
                          'defined_cache_size': CACHE_SIZE})
            blank = PADDING * (CACHE_SIZE - len(s))
            self.m[:CACHE_SIZE] = s + blank
        finally:
            fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)

    def unregister(self, topic, host, **kwargs):
        topic_host = '%s.%s' % (topic, host)
        self._update_cache({topic_host: None})

    def ack_alive(self, topic, host):
        topic_host = '%s.%s' % (topic, host)
        self._update_cache({topic_host: str(time.time())})

    def ack_alive_all(self, topic_hosts):
        args = {}
        for topic_host in topic_hosts:
            args['%s.%s' % topic_host] = str(time.time())
        self._update_cache(args)

    def is_alive(self, topic, host, **kwargs):
        self._update_cache()
        if self.cache.has_key('%s.%s' % (topic, host)):
            delta = time.time() - float(self.cache['%s.%s' % (topic, host)])
            return delta <= self.ttl
        self.unregister(topic, host)
        return False

    def get_all(self, topic=None):
        self._update_cache()
        res = []
        for topic_host in self.cache.keys():
            t, h = topic_host.split('.', 1)
            if topic and topic != t:
                continue
            if self.is_alive(t, h):
                res.append((t, h))
        return res
