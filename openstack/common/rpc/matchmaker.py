# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2011 Cloudscaling Group, Inc
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
"""
The MatchMaker classes should except a Topic or Fanout exchange key and
return keys for direct exchanges, per (approximate) AMQP parlance.
"""

import contextlib
import eventlet
import itertools
import json

from openstack.common import cfg
from openstack.common import importutils
from openstack.common.gettextutils import _
from openstack.common import log as logging

redis = importutils.try_import('redis')


matchmaker_opts = [
    # Matchmaker ring file
    cfg.StrOpt('matchmaker_ringfile',
               default='/etc/nova/matchmaker_ring.json',
               help='Matchmaker ring file (JSON)'),
    cfg.IntOpt('matchmaker_heartbeat_freq',
               default='300',
               help='Heartbeat frequency'),
    cfg.IntOpt('matchmaker_heartbeat_ttl',
               default='600',
               help='Heartbeat time-to-live.'),
    cfg.StrOpt('matchmaker_redis_host',
               default='127.0.0.1',
               help='Host to locate redis'),
    cfg.IntOpt('matchmaker_redis_port',
               default=6379,
               help='Use this port to connect to redis host.'),
]

CONF = cfg.CONF
CONF.register_opts(matchmaker_opts)
LOG = logging.getLogger(__name__)
contextmanager = contextlib.contextmanager


class MatchMakerException(Exception):
    """Signified a match could not be found."""
    message = _("Match not found by MatchMaker.")


class Exchange(object):
    """
    Implements lookups.
    Subclass this to support hashtables, dns, etc.
    """
    def __init__(self):
        pass

    def run(self, key):
        raise NotImplementedError()


class Binding(object):
    """
    A binding on which to perform a lookup.
    """
    def __init__(self):
        pass

    def test(self, key):
        raise NotImplementedError()


class MatchMakerBase(object):
    """
    Match Maker Base Class.
    Build off HeartbeatMatchMakerBase if building a
    heartbeat-capable MatchMaker.
    """
    def __init__(self):
        # Array of tuples. Index [2] toggles negation, [3] is last-if-true
        self.bindings = []

        self.no_heartbeat_msg = _('Matchmaker does not implement '
                                  'registration or heartbeat.')

    def register(self, key, host):
        """
        Register a host on a backend.
        Heartbeats, if applicable, may keepalive registration.
        """
        LOG.warn(self.no_heartbeat_msg)

    def ack_alive(self, key):
        """
        Acknowledge that a host.topic is alive.
        Used internally for updating heartbeats,
        but may also be used publically to acknowledge
        a system is alive (i.e. rpc message successfully
        sent to host)
        """
        LOG.warn(self.no_heartbeat_msg)

    def is_alive(self, topic, host):
        """
        Checks if a host is alive.
        """
        LOG.warn(self.no_heartbeat_msg)

    def expire(self, topic, host):
        """
        Explicitly expire a host's registration.
        """
        LOG.warn(self.no_heartbeat_msg)

    def send_heartbeats(self, topic, host):
        """
        Send all heartbeats.
        Use start_heartbeat to spawn a heartbeat greenthread,
        which loops this method.
        """
        LOG.warn(self.no_heartbeat_msg)

    def unregister(self, key, host):
        """
        Unregister a topic.
        """
        LOG.warn(self.no_heartbeat_msg)

    def start_heartbeat(self):
        """
        Spawn heartbeat greenthread.
        """
        LOG.warn(self.no_heartbeat_msg)

    def stop_heartbeat(self):
        """
        Destroys the heartbeat greenthread.
        """
        LOG.warn(self.no_heartbeat_msg)

    def add_binding(self, binding, rule, last=True):
        self.bindings.append((binding, rule, False, last))

    #NOTE(ewindisch): kept the following method in case we implement the
    #                 underlying support.
    #def add_negate_binding(self, binding, rule, last=True):
    #    self.bindings.append((binding, rule, True, last))

    def queues(self, key):
        workers = []

        # bit is for negate bindings - if we choose to implement it.
        # last stops processing rules if this matches.
        for (binding, exchange, bit, last) in self.bindings:
            if binding.test(key):
                workers.extend(exchange.run(key))

                # Support last.
                if last:
                    return workers
        return workers


class HeartbeatMatchMakerBase(MatchMakerBase):
    """
    Base for a heart-beat capable MatchMaker.
    Provides common methods for registering,
    unregistering, and maintaining heartbeats.
    """
    def __init__(self):
        self.hosts = set([])
        self._heart = None
        self.host_topic = {}

        super(HeartbeatMatchMakerBase, self).__init__()

    """Base for a heart-beat capable MatchMaker"""
    def send_heartbeats(self, topic, host):
        for htp in self.host_topic:
            key, host = htp
            success = self.ack_alive(key + '.' + host)
            if not success:
                self.register(self.host_topic[host], host)

    def backend_register(self, key, host):
        """
        Implements registration logic.
        Called by register(self,key,host)
        """
        raise NotImplementedError("Must implement backend_register")

    def backend_unregister(self, key, key_host):
        """
        Implements de-registration logic.
        Called by unregister(self,key,host)
        """
        raise NotImplementedError("Must implement backend_unregister")

    def register(self, key, host):
        self.hosts.add(host)
        self.host_topic[(key, host)] = host
        key_host = '.'.join((key, host))

        self.backend_register(key, key_host)

        self.ack_alive(key_host)

    def unregister(self, key, host):
        if (key, host) in self.host_topic:
            del self.host_topic[(key, host)]

        if host in self.hosts:
            self.hosts.remove(host)

        self.backend_unregister(key, '.'.join((key, host)))

        LOG.info(_("Matchmaker unregistered: %s, %s" % (key, host)))

    def start_heartbeat(self):
        """
        Implementation of MatchMakerBase.start_heartbeat
        Launches greenthread looping send_heartbeats(),
        yielding for CONF.matchmaker_heartbeat_freq seconds
        between iterations.
        """
        if len(self.hosts) == 0:
            raise MatchMakerException(
                _("Register before starting heartbeat."))

        def do_heartbeat():
            while True:
                self.send_heartbeats()
                eventlet.sleep(CONF.matchmaker_heartbeat_freq)

        self._heart = eventlet.spawn(do_heartbeat)

    def stop_heartbeat(self):
        if self._heart:
            self._heart.kill()


class DirectBinding(Binding):
    """
    Specifies a host in the key via a '.' character
    Although dots are used in the key, the behavior here is
    that it maps directly to a host, thus direct.
    """
    def test(self, key):
        if '.' in key:
            return True
        return False


class TopicBinding(Binding):
    """
    Where a 'bare' key without dots.
    AMQP generally considers topic exchanges to be those *with* dots,
    but we deviate here in terminology as the behavior here matches
    that of a topic exchange (whereas where there are dots, behavior
    matches that of a direct exchange.
    """
    def test(self, key):
        if '.' not in key:
            return True
        return False


class FanoutBinding(Binding):
    """Match on fanout keys, where key starts with 'fanout.' string."""
    def test(self, key):
        if key.startswith('fanout~'):
            return True
        return False


class StubExchange(Exchange):
    """Exchange that does nothing."""
    def run(self, key):
        return [(key, None)]


class RingExchange(Exchange):
    """
    Match Maker where hosts are loaded from a static file containing
    a hashmap (JSON formatted).

    __init__ takes optional ring dictionary argument, otherwise
    loads the ringfile from CONF.mathcmaker_ringfile.
    """
    def __init__(self, ring=None):
        super(RingExchange, self).__init__()

        if ring:
            self.ring = ring
        else:
            fh = open(CONF.matchmaker_ringfile, 'r')
            self.ring = json.load(fh)
            fh.close()

        self.ring0 = {}
        for k in self.ring.keys():
            self.ring0[k] = itertools.cycle(self.ring[k])

    def _ring_has(self, key):
        if key in self.ring0:
            return True
        return False


class RoundRobinRingExchange(RingExchange):
    """A Topic Exchange based on a hashmap."""
    def __init__(self, ring=None):
        super(RoundRobinRingExchange, self).__init__(ring)

    def run(self, key):
        if not self._ring_has(key):
            LOG.warn(
                _("No key defining hosts for topic '%s', "
                  "see ringfile") % (key, )
            )
            return []
        host = next(self.ring0[key])
        return [(key + '.' + host, host)]


class FanoutRingExchange(RingExchange):
    """Fanout Exchange based on a hashmap."""
    def __init__(self, ring=None):
        super(FanoutRingExchange, self).__init__(ring)

    def run(self, key):
        # Assume starts with "fanout~", strip it for lookup.
        nkey = key.split('fanout~')[1:][0]
        if not self._ring_has(nkey):
            LOG.warn(
                _("No key defining hosts for topic '%s', "
                  "see ringfile") % (nkey, )
            )
            return []
        return map(lambda x: (key + '.' + x, x), self.ring[nkey])


class LocalhostExchange(Exchange):
    """Exchange where all direct topics are local."""
    def __init__(self):
        super(Exchange, self).__init__()

    def run(self, key):
        return [(key.split('.')[0] + '.localhost', 'localhost')]


class DirectExchange(Exchange):
    """
    Exchange where all topic keys are split, sending to second half.
    i.e. "compute.host" sends a message to "compute" running on "host"
    """
    def __init__(self):
        super(Exchange, self).__init__()

    def run(self, key):
        b, e = key.split('.', 1)
        return [(b, e)]


class RedisExchange(Exchange):
    def __init__(self, matchmaker):
        self.matchmaker = matchmaker
        self.redis = matchmaker.redis
        super(RedisExchange, self).__init__()


class RedisTopicExchange(RedisExchange):
    """
    Exchange where all topic keys are split, sending to second half.
    i.e. "compute.host" sends a message to "compute" running on "host"
    """
    def run(self, topic):
        while True:
            member_name = self.redis.srandmember(topic)

            if not member_name:
                # If this happens, there are no
                # longer any members.
                break

            if not self.matchmaker.is_alive(topic, member_name):
                continue

            host = member_name.split('.', 1)[1]
            return [(member_name, host)]
        return []


class RedisFanoutExchange(RedisExchange):
    """
    Exchange where all topic keys are split, sending to second half.
    i.e. "compute.host" sends a message to "compute" running on "host"
    """
    def run(self, topic):
        topic = topic.split('~', 1)[1]
        hosts = set(self.redis.smembers(topic))
        good_hosts = set(filter(
            lambda host: self.matchmaker.is_alive(topic, host), hosts))

        addresses = map(lambda x: x.split('.', 1)[1], good_hosts)
        return zip(hosts, addresses)


class MatchMakerRedis(HeartbeatMatchMakerBase):
    """
    Match Maker where hosts are loaded from a static hashmap.
    """
    def __init__(self):
        super(MatchMakerRedis, self).__init__()

        self.redis = redis.StrictRedis(
            host=CONF.matchmaker_redis_host,
            port=CONF.matchmaker_redis_port)

        self.add_binding(FanoutBinding(), RedisFanoutExchange(self))
        self.add_binding(DirectBinding(), DirectExchange())
        self.add_binding(TopicBinding(), RedisTopicExchange(self))

    def ack_alive(self, key):
        return self.redis.expire(key, CONF.matchmaker_heartbeat_ttl)

    def is_alive(self, topic, host):
        if self.redis.ttl(host) == -1:
            self.expire(topic, host)
            return False
        return True

    def expire(self, topic, host):
        with self.redis.pipeline() as pipe:
            pipe.multi()
            pipe.delete(host)
            pipe.srem(topic, host)
            pipe.execute()

    def send_heartbeats(self):
        for htp in self.host_topic:
            key, host = htp
            success = self.ack_alive(key + '.' + host)
            if not success:
                self.register(self.host_topic[host], host)

    def backend_register(self, key, key_host):
        with self.redis.pipeline() as pipe:
            pipe.multi()
            pipe.sadd(key, key_host)

            # No value is needed, we just
            # care if it exists. Sets aren't viable
            # because only keys can expire.
            pipe.set(key_host, '')

            pipe.execute()

    def backend_unregister(self, key, key_host):
        with self.redis.pipeline() as pipe:
            pipe.multi()
            pipe.srem(key, key_host)
            pipe.delete(key_host)
            pipe.execute()


class MatchMakerRing(MatchMakerBase):
    """
    Match Maker where hosts are loaded from a static hashmap.
    """
    def __init__(self, ring=None):
        super(MatchMakerRing, self).__init__()
        self.add_binding(FanoutBinding(), FanoutRingExchange(ring))
        self.add_binding(DirectBinding(), DirectExchange())
        self.add_binding(TopicBinding(), RoundRobinRingExchange(ring))


class MatchMakerLocalhost(MatchMakerBase):
    """
    Match Maker where all bare topics resolve to localhost.
    Useful for testing.
    """
    def __init__(self):
        super(MatchMakerLocalhost, self).__init__()
        self.add_binding(FanoutBinding(), LocalhostExchange())
        self.add_binding(DirectBinding(), DirectExchange())
        self.add_binding(TopicBinding(), LocalhostExchange())


class MatchMakerStub(MatchMakerBase):
    """
    Match Maker where topics are untouched.
    Useful for testing, or for AMQP/brokered queues.
    Will not work where knowledge of hosts is known (i.e. zeromq)
    """
    def __init__(self):
        super(MatchMakerLocalhost, self).__init__()

        self.add_binding(FanoutBinding(), StubExchange())
        self.add_binding(DirectBinding(), StubExchange())
        self.add_binding(TopicBinding(), StubExchange())
