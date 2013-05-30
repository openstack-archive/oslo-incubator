import os
import os.path

import eventlet
import mock
from oslo.config import cfg
import tempfile

from openstack.common import heartbeat
from openstack.common.heartbeat import heartbeat_local
from tests import utils


class TestHeartbeatAPI(utils.BaseTestCase):
    def setUp(self):
        super(TestHeartbeatAPI, self).setUp()
        cfg.CONF.set_override('heartbeat_driver',
                         'openstack.common.heartbeat.HeartbeatDriverBase')
        driver_patcher = mock.patch('openstack.common.heartbeat.HeartbeatDriverBase',
                                    autospec=True)
        self.driver_mock = driver_patcher.start()
        self.driver = self.driver_mock.return_value
        self.addCleanup(cfg.CONF.reset)
        self.addCleanup(driver_patcher.stop)

    def test_heartbeat_register(self):
        api = heartbeat.HeartbeatAPI(1, 1)
        api.register('topic1', 'host1')
        self.assertEqual(self.driver.register.call_count, 1)
        api.register('topic1', 'host1')
        api.register('topic2', 'host1')
        self.assertEqual(self.driver.register.call_count, 2)
        expected_call = [mock.call('topic1', 'host1'),
                         mock.call('topic2', 'host1')]
        self.driver.register.assert_has_calls(self.driver.register.call_args_list, expected_call)

    def test_heartbeat_unregister(self):
        api = heartbeat.HeartbeatAPI(1, 1)
        self.driver.unregister.return_value = None
        api.unregister('topic3', 'host1')
        self.assertEqual(self.driver.unregister.call_count, 0)
        api.register('topic4', 'host1')
        api.register('topic4', 'host1')
        api.unregister('topic4', 'host1')
        self.assertEqual(self.driver.unregister.call_count, 0)
        api.unregister('topic4', 'host1')
        self.driver.unregister.assert_called_once_with('topic4', 'host1')
        self.assertEqual(self.driver.unregister.call_count, 1)


class TestHeartbeatLocal(utils.BaseTestCase):
    def setUp(self):
        super(TestHeartbeatLocal, self).setUp()
        self.ttl = 3
        self.freq = 1
        if os.path.exists(heartbeat_local.MAPPING_FILE):
            os.remove(heartbeat_local.MAPPING_FILE)
        self.driver = heartbeat_local.HeartbeatLocal(1, 2)

    def test_ack_alive(self):
        topic = 'topic1'
        host = 'host1'
        self.driver.register(topic, host)
        self.driver.ack_alive(topic, host)
        eventlet.sleep(self.freq)
        self.assertTrue(self.driver.is_alive(topic, host))

    def test_is_alive_without_reigster(self):
        topic = 'topic1'
        host = 'host1'
        self.assertFalse(self.driver.is_alive(topic, host))

    def test_ack_alive_without_register(self):
        topic = 'topic1'
        host = 'host1'
        self.driver.ack_alive(topic, host)
        self.assertTrue(self.driver.is_alive(topic, host))

    def test_ack_alive_all(self):
        topic_hosts = [('topic1', 'host1'), ('topic1', 'host2'),
                       ('topic2', 'host1')]
        self.driver.ack_alive_all(topic_hosts)
        for topic, host in topic_hosts:
            self.assertTrue(self.driver.is_alive(topic, host))

    def test_expire(self):
        topic = 'topic1'
        host = 'host1'
        self.driver.register(topic, host)
        self.driver.ack_alive(topic, host)
        eventlet.sleep(self.ttl + 1)
        self.assertFalse(self.driver.is_alive(topic, host))

    def test_get_all(self):
        topic_hosts = [('topic1', 'host1'), ('topic1', 'host2'),
                       ('topic2', 'host2')]
        for topic, host in topic_hosts:
            self.driver.register(topic, host)
        for topic, host in topic_hosts[1:]:
            self.driver.ack_alive(topic, host)
        res = self.driver.get_all()
        expected_res = [('topic1', 'host2'), ('topic2', 'host2')]
        self.assertEqual(res, expected_res)

    def test_get_all_by_topic(self):
        topic_hosts = [('topic1', 'host1'), ('topic1', 'host2'),
                       ('topic2', 'host2')]
        for topic, host in topic_hosts:
            self.driver.register(topic, host)
        for topic, host in topic_hosts[1:]:
            self.driver.ack_alive(topic, host)
        res = self.driver.get_all('topic1')
        expected_res = [('topic1', 'host2')]
        self.assertEqual(res, expected_res)
