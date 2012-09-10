# vim: tabstop=4 shiftwidth=4 softtabstop=4

#    Copyright 2011 OpenStack LLC
#    Copyright 2011 - 2012, Red Hat, Inc.
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
import itertools
import logging
import time
import uuid

import eventlet
import greenlet
import qpid.messaging
import qpid.messaging.exceptions

from openstack.common import cfg
from openstack.common.gettextutils import _
from openstack.common import jsonutils
from openstack.common.rpc import amqp as rpc_amqp
from openstack.common.rpc import common as rpc_common

LOG = logging.getLogger(__name__)

qpid_opts = [
    cfg.StrOpt('qpid_hostname',
               default='localhost',
               help='Qpid broker hostname'),
    cfg.StrOpt('qpid_port',
               default='5672',
               help='Qpid broker port'),
    cfg.StrOpt('qpid_username',
               default='',
               help='Username for qpid connection'),
    cfg.StrOpt('qpid_password',
               default='',
               help='Password for qpid connection'),
    cfg.StrOpt('qpid_sasl_mechanisms',
               default='',
               help='Space separated list of SASL mechanisms to use for auth'),
    cfg.BoolOpt('qpid_reconnect',
                default=True,
                help='Automatically reconnect'),
    cfg.IntOpt('qpid_reconnect_timeout',
               default=0,
               help='Reconnection timeout in seconds'),
    cfg.IntOpt('qpid_reconnect_limit',
               default=0,
               help='Max reconnections before giving up'),
    cfg.IntOpt('qpid_reconnect_interval_min',
               default=0,
               help='Minimum seconds between reconnection attempts'),
    cfg.IntOpt('qpid_reconnect_interval_max',
               default=0,
               help='Maximum seconds between reconnection attempts'),
    cfg.IntOpt('qpid_reconnect_interval',
               default=0,
               help='Equivalent to setting max and min to the same value'),
    cfg.IntOpt('qpid_heartbeat',
               default=5,
               help='Seconds between connection keepalive heartbeats'),
    cfg.StrOpt('qpid_protocol',
               default='tcp',
               help="Transport to use, either 'tcp' or 'ssl'"),
    cfg.BoolOpt('qpid_tcp_nodelay',
                default=True,
                help='Disable Nagle algorithm'),
]

cfg.CONF.register_opts(qpid_opts)


class ConsumerBase(object):
    """Consumer base class."""

    def __init__(self, session, callback, node_name, node_opts,
                 link_name, link_opts):
        """Declare a queue on an amqp session.

        'session' is the amqp session to use
        'callback' is the callback to call when messages are received
        'node_name' is the first part of the Qpid address string, before ';'
        'node_opts' will be applied to the "x-declare" section of "node"
                    in the address string.
        'link_name' goes into the "name" field of the "link" in the address
                    string
        'link_opts' will be applied to the "x-declare" section of "link"
                    in the address string.
        """
        self.callback = callback
        self.receiver = None
        self.session = None

        addr_opts = {
            "create": "always",
            "node": {
                "type": "topic",
                "x-declare": {
                    "durable": True,
                    "auto-delete": True,
                },
            },
            "link": {
                "name": link_name,
                "durable": True,
                "x-declare": {
                    "durable": False,
                    "auto-delete": True,
                    "exclusive": False,
                },
            },
        }
        addr_opts["node"]["x-declare"].update(node_opts)
        addr_opts["link"]["x-declare"].update(link_opts)

        self.address = "%s ; %s" % (node_name, jsonutils.dumps(addr_opts))

        self.reconnect(session)

    def reconnect(self, session):
        """Re-declare the receiver after a qpid reconnect"""
        self.session = session
        self.receiver = session.receiver(self.address)
        self.receiver.capacity = 1

    def consume(self):
        """Fetch the message and pass it to the callback object"""
        message = self.receiver.fetch()
        try:
            self.callback(message.content)
        except Exception:
            LOG.exception(_("Failed to process message... skipping it."))
        finally:
            self.session.acknowledge(message)

    def get_receiver(self):
        return self.receiver


class DirectConsumer(ConsumerBase):
    """Queue/consumer class for 'direct'"""

    def __init__(self, conf, session, msg_id, callback):
        """Init a 'direct' queue.

        'session' is the amqp session to use
        'msg_id' is the msg_id to listen on
        'callback' is the callback to call when messages are received
        """

        super(DirectConsumer, self).__init__(session, callback,
                                             "%s/%s" % (msg_id, msg_id),
                                             {"type": "direct"},
                                             msg_id,
                                             {"exclusive": True})


class TopicConsumer(ConsumerBase):
    """Consumer class for 'topic'"""

    def __init__(self, conf, session, topic, callback, name=None):
        """Init a 'topic' queue.

        :param session: the amqp session to use
        :param topic: is the topic to listen on
        :paramtype topic: str
        :param callback: the callback to call when messages are received
        :param name: optional queue name, defaults to topic
        """

        super(TopicConsumer, self).__init__(session, callback,
                "%s/%s" % (rpc_amqp.get_control_exchange(conf), topic),
                {}, name or topic, {})


class FanoutConsumer(ConsumerBase):
    """Consumer class for 'fanout'"""

    def __init__(self, conf, session, topic, callback):
        """Init a 'fanout' queue.

        'session' is the amqp session to use
        'topic' is the topic to listen on
        'callback' is the callback to call when messages are received
        """

        super(FanoutConsumer, self).__init__(
            session, callback,
            "%s_fanout" % topic,
            {"durable": False, "type": "fanout"},
            "%s_fanout_%s" % (topic, uuid.uuid4().hex),
            {"exclusive": True})


class Publisher(object):
    """Base Publisher class"""

    def __init__(self, session, node_name, node_opts=None):
        """Init the Publisher class with the exchange_name, routing_key,
        and other options
        """
        self.sender = None
        self.session = session

        addr_opts = {
            "create": "always",
            "node": {
                "type": "topic",
                "x-declare": {
                    "durable": False,
                    # auto-delete isn't implemented for exchanges in qpid,
                    # but put in here anyway
                    "auto-delete": True,
                },
            },
        }
        if node_opts:
            addr_opts["node"]["x-declare"].update(node_opts)

        self.address = "%s ; %s" % (node_name, jsonutils.dumps(addr_opts))

        self.reconnect(session)

    def reconnect(self, session):
        """Re-establish the Sender after a reconnection"""
        self.sender = session.sender(self.address)

    def send(self, msg):
        """Send a message"""
        self.sender.send(msg)


class DirectPublisher(Publisher):
    """Publisher class for 'direct'"""
    def __init__(self, conf, session, msg_id):
        """Init a 'direct' publisher."""
        super(DirectPublisher, self).__init__(session, msg_id,
                                              {"type": "Direct"})


class TopicPublisher(Publisher):
    """Publisher class for 'topic'"""
    def __init__(self, conf, session, topic):
        """init a 'topic' publisher.
        """
        super(TopicPublisher, self).__init__(session,
                "%s/%s" % (rpc_amqp.get_control_exchange(conf), topic))


class FanoutPublisher(Publisher):
    """Publisher class for 'fanout'"""
    def __init__(self, conf, session, topic):
        """init a 'fanout' publisher.
        """
        super(FanoutPublisher, self).__init__(
            session,
            "%s_fanout" % topic, {"type": "fanout"})


class NotifyPublisher(Publisher):
    """Publisher class for notifications"""
    def __init__(self, conf, session, topic):
        """init a 'topic' publisher.
        """
        super(NotifyPublisher, self).__init__(session,
                "%s/%s" % (rpc_amqp.get_control_exchange(conf), topic),
                {"durable": True})


class Connection(object):
    """Connection object."""

    pool = None

    def __init__(self, conf, server_params=None):
        self.session = None
        self.consumers = {}
        self.consumer_thread = None
        self.conf = conf

        if server_params is None:
            server_params = {}

        default_params = dict(hostname=self.conf.qpid_hostname,
                              port=self.conf.qpid_port,
                              username=self.conf.qpid_username,
                              password=self.conf.qpid_password)

        params = server_params
        for key in default_params.keys():
            params.setdefault(key, default_params[key])

        self.broker = params['hostname'] + ":" + str(params['port'])
        # Create the connection - this does not open the connection
        self.connection = qpid.messaging.Connection(self.broker)

        # Check if flags are set and if so set them for the connection
        # before we call open
        self.connection.username = params['username']
        self.connection.password = params['password']
        self.connection.sasl_mechanisms = self.conf.qpid_sasl_mechanisms
        self.connection.reconnect = self.conf.qpid_reconnect
        if self.conf.qpid_reconnect_timeout:
            self.connection.reconnect_timeout = (
                self.conf.qpid_reconnect_timeout)
        if self.conf.qpid_reconnect_limit:
            self.connection.reconnect_limit = self.conf.qpid_reconnect_limit
        if self.conf.qpid_reconnect_interval_max:
            self.connection.reconnect_interval_max = (
                self.conf.qpid_reconnect_interval_max)
        if self.conf.qpid_reconnect_interval_min:
            self.connection.reconnect_interval_min = (
                self.conf.qpid_reconnect_interval_min)
        if self.conf.qpid_reconnect_interval:
            self.connection.reconnect_interval = (
                self.conf.qpid_reconnect_interval)
        self.connection.heartbeat = self.conf.qpid_heartbeat
        self.connection.protocol = self.conf.qpid_protocol
        self.connection.tcp_nodelay = self.conf.qpid_tcp_nodelay

        # Open is part of reconnect -
        # NOTE(WGH) not sure we need this with the reconnect flags
        self.reconnect()

    def _register_consumer(self, consumer):
        self.consumers[str(consumer.get_receiver())] = consumer

    def _lookup_consumer(self, receiver):
        return self.consumers[str(receiver)]

    def reconnect(self):
        """Handles reconnecting and re-establishing sessions and queues"""
        if self.connection.opened():
            try:
                self.connection.close()
            except qpid.messaging.exceptions.ConnectionError:
                pass

        while True:
            try:
                self.connection.open()
            except qpid.messaging.exceptions.ConnectionError, e:
                LOG.error(_('Unable to connect to AMQP server: %s'), e)
                time.sleep(self.conf.qpid_reconnect_interval or 1)
            else:
                break

        LOG.info(_('Connected to AMQP server on %s'), self.broker)

        self.session = self.connection.session()

        for consumer in self.consumers.itervalues():
            consumer.reconnect(self.session)

        if self.consumers:
            LOG.debug(_("Re-established AMQP queues"))

    def ensure(self, error_callback, method, *args, **kwargs):
        while True:
            try:
                return method(*args, **kwargs)
            except (qpid.messaging.exceptions.Empty,
                    qpid.messaging.exceptions.ConnectionError), e:
                if error_callback:
                    error_callback(e)
                self.reconnect()

    def close(self):
        """Close/release this connection"""
        self.cancel_consumer_thread()
        self.connection.close()
        self.connection = None

    def reset(self):
        """Reset a connection so it can be used again"""
        self.cancel_consumer_thread()
        self.session.close()
        self.session = self.connection.session()
        self.consumers = {}

    def declare_consumer(self, consumer_cls, topic, callback):
        """Create a Consumer using the class that was passed in and
        add it to our list of consumers
        """
        def _connect_error(exc):
            log_info = {'topic': topic, 'err_str': str(exc)}
            LOG.error(_("Failed to declare consumer for topic '%(topic)s': "
                      "%(err_str)s") % log_info)

        def _declare_consumer():
            consumer = consumer_cls(self.conf, self.session, topic, callback)
            self._register_consumer(consumer)
            return consumer

        return self.ensure(_connect_error, _declare_consumer)

    def iterconsume(self, limit=None, timeout=None):
        """Return an iterator that will consume from all queues/consumers"""

        def _error_callback(exc):
            if isinstance(exc, qpid.messaging.exceptions.Empty):
                LOG.exception(_('Timed out waiting for RPC response: %s') %
                              str(exc))
                raise rpc_common.Timeout()
            else:
                LOG.exception(_('Failed to consume message from queue: %s') %
                              str(exc))

        def _consume():
            nxt_receiver = self.session.next_receiver(timeout=timeout)
            try:
                self._lookup_consumer(nxt_receiver).consume()
            except Exception:
                LOG.exception(_("Error processing message.  Skipping it."))

        for iteration in itertools.count(0):
            if limit and iteration >= limit:
                raise StopIteration
            yield self.ensure(_error_callback, _consume)

    def cancel_consumer_thread(self):
        """Cancel a consumer thread"""
        if self.consumer_thread is not None:
            self.consumer_thread.kill()
            try:
                self.consumer_thread.wait()
            except greenlet.GreenletExit:
                pass
            self.consumer_thread = None

    def publisher_send(self, cls, topic, msg):
        """Send to a publisher based on the publisher class"""

        def _connect_error(exc):
            log_info = {'topic': topic, 'err_str': str(exc)}
            LOG.exception(_("Failed to publish message to topic "
                          "'%(topic)s': %(err_str)s") % log_info)

        def _publisher_send():
            publisher = cls(self.conf, self.session, topic)
            publisher.send(msg)

        return self.ensure(_connect_error, _publisher_send)

    def declare_direct_consumer(self, topic, callback):
        """Create a 'direct' queue.
        In nova's use, this is generally a msg_id queue used for
        responses for call/multicall
        """
        self.declare_consumer(DirectConsumer, topic, callback)

    def declare_topic_consumer(self, topic, callback=None, queue_name=None):
        """Create a 'topic' consumer."""
        self.declare_consumer(functools.partial(TopicConsumer,
                                                name=queue_name,
                                                ),
                              topic, callback)

    def declare_fanout_consumer(self, topic, callback):
        """Create a 'fanout' consumer"""
        self.declare_consumer(FanoutConsumer, topic, callback)

    def direct_send(self, msg_id, msg):
        """Send a 'direct' message"""
        self.publisher_send(DirectPublisher, msg_id, msg)

    def topic_send(self, topic, msg):
        """Send a 'topic' message"""
        self.publisher_send(TopicPublisher, topic, msg)

    def fanout_send(self, topic, msg):
        """Send a 'fanout' message"""
        self.publisher_send(FanoutPublisher, topic, msg)

    def notify_send(self, topic, msg, **kwargs):
        """Send a notify message on a topic"""
        self.publisher_send(NotifyPublisher, topic, msg)

    def consume(self, limit=None):
        """Consume from all queues/consumers"""
        it = self.iterconsume(limit=limit)
        while True:
            try:
                it.next()
            except StopIteration:
                return

    def consume_in_thread(self):
        """Consumer from all queues/consumers in a greenthread"""
        def _consumer_thread():
            try:
                self.consume()
            except greenlet.GreenletExit:
                return
        if self.consumer_thread is None:
            self.consumer_thread = eventlet.spawn(_consumer_thread)
        return self.consumer_thread

    def create_consumer(self, topic, proxy, fanout=False):
        """Create a consumer that calls a method in a proxy object"""
        proxy_cb = rpc_amqp.ProxyCallback(
            self.conf, proxy,
            rpc_amqp.get_connection_pool(self.conf, Connection))

        if fanout:
            consumer = FanoutConsumer(self.conf, self.session, topic, proxy_cb)
        else:
            consumer = TopicConsumer(self.conf, self.session, topic, proxy_cb)

        self._register_consumer(consumer)

        return consumer

    def create_worker(self, topic, proxy, pool_name):
        """Create a worker that calls a method in a proxy object"""
        proxy_cb = rpc_amqp.ProxyCallback(
            self.conf, proxy,
            rpc_amqp.get_connection_pool(self.conf, Connection))

        consumer = TopicConsumer(self.conf, self.session, topic, proxy_cb,
                                 name=pool_name)

        self._register_consumer(consumer)

        return consumer


def create_connection(conf, new=True):
    """Create a connection"""
    return rpc_amqp.create_connection(
        conf, new,
        rpc_amqp.get_connection_pool(conf, Connection))


def multicall(conf, context, topic, msg, timeout=None):
    """Make a call that returns multiple times."""
    return rpc_amqp.multicall(
        conf, context, topic, msg, timeout,
        rpc_amqp.get_connection_pool(conf, Connection))


def call(conf, context, topic, msg, timeout=None):
    """Sends a message on a topic and wait for a response."""
    return rpc_amqp.call(
        conf, context, topic, msg, timeout,
        rpc_amqp.get_connection_pool(conf, Connection))


def cast(conf, context, topic, msg):
    """Sends a message on a topic without waiting for a response."""
    return rpc_amqp.cast(
        conf, context, topic, msg,
        rpc_amqp.get_connection_pool(conf, Connection))


def fanout_cast(conf, context, topic, msg):
    """Sends a message on a fanout exchange without waiting for a response."""
    return rpc_amqp.fanout_cast(
        conf, context, topic, msg,
        rpc_amqp.get_connection_pool(conf, Connection))


def cast_to_server(conf, context, server_params, topic, msg):
    """Sends a message on a topic to a specific server."""
    return rpc_amqp.cast_to_server(
        conf, context, server_params, topic, msg,
        rpc_amqp.get_connection_pool(conf, Connection))


def fanout_cast_to_server(conf, context, server_params, topic, msg):
    """Sends a message on a fanout exchange to a specific server."""
    return rpc_amqp.fanout_cast_to_server(
        conf, context, server_params, topic, msg,
        rpc_amqp.get_connection_pool(conf, Connection))


def notify(conf, context, topic, msg):
    """Sends a notification event on a topic."""
    return rpc_amqp.notify(conf, context, topic, msg,
                           rpc_amqp.get_connection_pool(conf, Connection))


def cleanup():
    return rpc_amqp.cleanup(Connection.pool)
