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
import random

from openstack.common import heartbeat
from openstack.common.rpc import matchmaker as mm_common


class HeartBeatTopicExchange(mm_common.Exchange):
    def run(self, topic):
        all_hosts = heartbeat.get_heartbeat_api().get_all(topic)
        res = [('%s.%s' % (topic, host), host) for topic, host in all_hosts]
        return [random.choice(res)] if res else []


class HeartBeatFanoutExchange(mm_common.Exchange):
    def run(self, topic):
        topic = topic.split('~', 1)[1]
        all_hosts = heartbeat.get_heartbeat_api().get_all(topic)
        res = [('%s.%s' % (topic, host), host) for topic, host in all_hosts]
        return res


class MatchMakerHeartbeat(mm_common.MatchMakerBase):
    def __init__(self):
        super(MatchMakerHeartbeat, self).__init__()
        self.add_binding(mm_common.FanoutBinding(), HeartBeatFanoutExchange())
        self.add_binding(mm_common.DirectBinding(), mm_common.DirectExchange())
        self.add_binding(mm_common.TopicBinding(), HeartBeatTopicExchange())

    def register(self, key, host):
        heartbeat.get_heartbeat_api().register(key, host)
        # MatchMaker expect the heartbeat is alive after registered.
        heartbeat.get_heartbeat_api().ack_alive(key, host)

    def is_alive(self, topic, host):
        heartbeat.get_heartbeat_api().is_alive(topic, host)

    def unregister(self, key, host):
        heartbeat.get_heartbeat_api().unregister(key, host)

    def start_heartbeat(self):
        heartbeat.get_heartbeat_api().start()

    def stop_heartbeat(self):
        heartbeat.get_heartbeat_api().stop()
