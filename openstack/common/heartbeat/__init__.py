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
import functools

from oslo.config import cfg

from openstack.common.gettextutils import _
from openstack.common import importutils
from openstack.common import log as logging
from openstack.common import loopingcall


heartbeat_opts = [
    cfg.StrOpt('heartbeat_freq',
               default=3,
               help='Heartbeat frequency'),
    cfg.StrOpt('heartbeat_ttl',
               default=4,
               help='Heartbeat time-to-live'),
    cfg.StrOpt('heartbeat_driver',
               default=None,
               help='Heartbeat driver')
]

CONF = cfg.CONF
CONF.register_opts(heartbeat_opts)
LOG = logging.getLogger(__name__)

_heartbeat_api = None


def get_heartbeat_api():
    global _heartbeat_api
    if not _heartbeat_api:
        if CONF.heartbeat_ttl < CONF.heartbeat_freq:
            LOG.warn(_("heartbeat_ttl should greater than heartbeat_freq: "
                       "heartbeat_ttl=%s, heartbeat_freq=%s"),
                     {'heartbeat_ttl': CONF.heartbeat_ttl,
                      'heartbeat_freq': CONF.heartbeat_freq})
        _heartbeat_api = HeartbeatAPI(CONF.heartbeat_freq, CONF.heartbeat_ttl)
    return _heartbeat_api


class HeartbeatAPI(object):
    """"Interface of Heartbeat. It is a singleton. Only one instance
    in one process.
    """
    def __init__(self, freq, ttl):
        self.freq = freq
        self.ttl = ttl
        self.heartbeats = {}
        self.loopingcall = None
        self.driver = importutils.import_class(
            CONF.heartbeat_driver)(freq, ttl)

    def register(self, topic, host, **kwargs):
        """Register an heartbeat that identify uniquely by 'topic' and 'host'.

        :param kwargs: Receive more params that used by implement existed db
        based heartbeat for bw compatibility.
        """
        if not self.heartbeats.has_key((topic, host)):
            self.heartbeats[(topic, host)] = 0
            self.driver.register(topic, host, **kwargs)
        self.heartbeats[(topic, host)] += 1

    def unregister(self, topic, host, **kwargs):
        """Un-register an heartbeat.
        
        :param kwargs: Receive more params that used by implement existed db
        based heartbeat for bw compatibility.
        """
        if self.heartbeats.has_key((topic, host)):
            self.heartbeats[(topic, host)] -= 1
            if not self.heartbeats[(topic, host)]:
                self.driver.unregister(topic, host, **kwargs)
                del self.heartbeats[(topic, host)]

    def ack_alive(self, topic, host):
        """Acknowledge (topic, host) is alive"""
        return self.driver.ack_alive(topic, host)

    def is_alive(self, topic, host, **kwargs):
        """Check if an heartbeat is alive that unique identity by topic and 'host'

        :param kwargs: Receive more params that used by implement existed db
        based heartbeat for bw compatibility.
        """
        return self.driver.is_alive(topic, host, **kwargs)

    def get_all(self, topic=None):
        """Obtain all (topic, host) that alived

        :returns: Return a list (topic, host) that alived.
        Example: [('topic1', 'host1'), ('topic1', 'host2'), ...]
        """

        return self.driver.get_all(topic)

    def start(self):
        """Run all the heartbeats that registered in the current process.

        MatchMaker may register many heartbeats, and those heartbeat run
        in same process. So we can run those heatbeat in same timer for
        more effective.
        """
        if not self.loopingcall:
            self.loopingcall = loopingcall.FixedIntervalLoopingCall(
                functools.partial(self.driver.ack_alive_all,
                                  self.heartbeats.keys()))
            self.loopingcall.start(
                interval=self.freq)

    def stop(self):
        """Stop heartbeats"""
        if self.loopingcall:
            self.loopingcall.stop()


class HeartbeatDriverBase(object):
    """Base class for Heartbeat Driver"""

    def __init__(self, freq, ttl):
        self.freq = freq
        self.ttl = ttl

    def register(self, topic, host, **kwargs):
        """Register an heartbeat that identify uniquely by 'topic' and 'host'.

        :param kwargs: Receive more params that used by implement existed db
        based heartbeat for bw compatibility.
        """
        pass

    def unregister(self, topic, host, **kwargs):
        """Un-register an heartbeat.
        
        :param kwargs: Receive more params that used by implement existed db
        based heartbeat for bw compatibility.
        """
        pass

    def ack_alive(self, topic, host, **kwargs):
        """Acknowledge (topic, host) is alive

        :param kwargs: Receive more params that used by implement existed db
        based heartbeat for bw compatibility.
        """
        pass

    def ack_alive_all(self, topic_hosts):
        """Ackownledge a list of (topc, host).
        :topic_hosts: The format as
        [('topic1', 'host1'), ('topic1', 'host2'), ...]
        """
        pass

    def is_alive(self, topic, host, **kwargs):
        """Check if an heartbeat is alive that unique identity by topic and 'host'

        :param kwargs: Receive more params that used by implement existed db
        based heartbeat for bw compatibility.
        """
        pass

    def get_all(self, topic=None):
        """Obtain all (topic, host) that alived

        :returns: Return a list (topic, host) that alived.
        Example: [('topic1', 'host1'), ('topic1', 'host2'), ...]
        """
        pass
