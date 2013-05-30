import logging
import os
import os.path

import eventlet
from oslo.config import cfg

from openstack.common import importutils
from openstack.common import heartbeat
from openstack.common.heartbeat import heartbeat_local
from openstack.common.rpc import matchmaker_heartbeat as matchmaker
from tests.unit.rpc import matchmaker_common as common
from tests import utils


LOG = logging.getLogger(__name__)


class MatchMakerHeartbeatLookupTestCase(utils.BaseTestCase,
                                        common._MatchMakerTestCase):
    def setUp(self):
        super(MatchMakerHeartbeatLookupTestCase, self).setUp()

        cfg.CONF.set_override(
            'heartbeat_driver',
            'openstack.common.heartbeat.heartbeat_local.HeartbeatLocal')

        self.topic = "test"
        self.hosts = map(lambda x: 'mockhost-' + str(x), range(1, 10))

        if os.path.exists(heartbeat_local.MAPPING_FILE):
            os.remove(heartbeat_local.MAPPING_FILE)

        self.driver = matchmaker.MatchMakerHeartbeat()

        for h in self.hosts:
            self.driver.register(self.topic, h)

        self.driver.start_heartbeat()

    def tearDown(self):
        super(MatchMakerHeartbeatLookupTestCase, self).tearDown()
        self.driver.stop_heartbeat()


class MatchMakerHeartbeatTestCase(utils.BaseTestCase,
                                  common._MatchMakerDynRegTestCase):
    def setUp(self):
        super(MatchMakerHeartbeatTestCase, self).setUp()

        cfg.CONF.set_override(
            'heartbeat_driver',
            'openstack.common.heartbeat.heartbeat_local.HeartbeatLocal')

        if os.path.exists(heartbeat_local.MAPPING_FILE):
            os.remove(heartbeat_local.MAPPING_FILE)
        heartbeat._heartbeat_api = None
        self.driver = matchmaker.MatchMakerHeartbeat()
        self.topic = "test"
        self.hosts = map(lambda x: 'mockhost-' + str(x), range(1, 10))
