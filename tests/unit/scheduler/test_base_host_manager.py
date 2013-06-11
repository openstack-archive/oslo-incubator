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
"""
Tests For Scheduler
"""
from oslo.config import cfg

from openstack.common import exception
from openstack.common import timeutils
from openstack.common.scheduler import base_host_manager
from openstack.common.scheduler import filters
from tests import utils

CONF = cfg.CONF


class FakeFilterClass1(filters.BaseHostFilter):
    def host_passes(self, host_state, filter_properties):
        pass


class FakeFilterClass2(filters.BaseHostFilter):
    def host_passes(self, host_state, filter_properties):
        pass


class BaseHostManagerTestCase(utils.BaseTestCase):
    """Test case for base host manager."""

    def setUp(self):
        super(BaseHostManagerTestCase, self).setUp()
        self.host_manager = base_host_manager.BaseHostManager()
        self.host_manager.service_name = 'fake_service'

        self.fake_hosts = [base_host_manager.BaseHostState('fake_host%s' % x,
                                                           'fake-node')
                           for x in xrange(1, 5)]
        self.fake_hosts += [base_host_manager.BaseHostState('fake_multihost',
                                                            'fake-node%s' % x)
                            for x in xrange(1, 5)]
        self.addCleanup(timeutils.clear_time_override)

    def test_choose_host_filters_not_found(self):
        self.config(scheduler_default_filters='FakeFilterClass3')
        self.host_manager.filter_classes = [FakeFilterClass1,
                                            FakeFilterClass2]
        self.assertRaises(exception.SchedulerHostFilterNotFound,
                          self.host_manager._choose_host_filters, None)

    def test_choose_host_filters(self):
        self.config(scheduler_default_filters=['FakeFilterClass2'])
        self.host_manager.filter_classes = [FakeFilterClass1,
                                            FakeFilterClass2]

        # Test we returns 1 correct function
        filter_classes = self.host_manager._choose_host_filters(None)
        self.assertEqual(len(filter_classes), 1)
        self.assertEqual(filter_classes[0].__name__, 'FakeFilterClass2')

    def _mock_get_filtered_hosts(self, info, specified_filters=None):
        self.mox.StubOutWithMock(self.host_manager, '_choose_host_filters')

        info['got_objs'] = []
        info['got_fprops'] = []

        def fake_filter_one(_self, obj, filter_props):
            info['got_objs'].append(obj)
            info['got_fprops'].append(filter_props)
            return True

        self.stubs.Set(FakeFilterClass1, '_filter_one', fake_filter_one)
        self.host_manager._choose_host_filters(specified_filters).\
            AndReturn([FakeFilterClass1])

    def _verify_result(self, info, result, filters=True):
        for x in info['got_fprops']:
            self.assertEqual(x, info['expected_fprops'])
        if filters:
            self.assertEqual(set(info['expected_objs']), set(info['got_objs']))
        self.assertEqual(set(info['expected_objs']), set(result))

    def test_get_filtered_hosts(self):
        fake_properties = {'moo': 1, 'cow': 2}

        info = {'expected_objs': self.fake_hosts,
                'expected_fprops': fake_properties}

        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()
        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result)

    def test_get_filtered_hosts_with_specificed_filters(self):
        fake_properties = {'moo': 1, 'cow': 2}

        specified_filters = ['FakeFilterClass1', 'FakeFilterClass2']
        info = {'expected_objs': self.fake_hosts,
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info, specified_filters)

        self.mox.ReplayAll()

        args = [self.fake_hosts, fake_properties]
        kwargs = {'filter_class_names': specified_filters}
        result = self.host_manager.get_filtered_hosts(*args, **kwargs)
        self._verify_result(info, result)

    def test_get_filtered_hosts_with_ignore(self):
        fake_properties = {'ignore_hosts': ['fake_host1', 'fake_host3',
                                            'fake_host5', 'fake_multihost']}

        # [1] and [3] are host2 and host4
        info = {'expected_objs': [self.fake_hosts[1], self.fake_hosts[3]],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result)

    def test_get_filtered_hosts_with_force_hosts(self):
        fake_properties = {'force_hosts': ['fake_host1', 'fake_host3',
                                           'fake_host5']}

        # [0] and [2] are host1 and host3
        info = {'expected_objs': [self.fake_hosts[0], self.fake_hosts[2]],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result, False)

    def test_get_filtered_hosts_with_no_matching_force_hosts(self):
        fake_properties = {'force_hosts': ['fake_host5', 'fake_host6']}

        info = {'expected_objs': [],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        self.host_manager.get_filtered_hosts(self.fake_hosts,
                                             fake_properties)

    def test_get_filtered_hosts_with_ignore_and_force_hosts(self):
        # Ensure ignore_hosts processed before force_hosts in host filters.
        fake_properties = {'force_hosts': ['fake_host3', 'fake_host1'],
                           'ignore_hosts': ['fake_host1']}

        # only fake_host3 should be left.
        info = {'expected_objs': [self.fake_hosts[2]],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result, False)

    def test_get_filtered_hosts_with_force_host_and_many_nodes(self):
        # Ensure all nodes returned for a host with many nodes
        fake_properties = {'force_hosts': ['fake_multihost']}

        info = {'expected_objs': [self.fake_hosts[4], self.fake_hosts[5],
                                  self.fake_hosts[6], self.fake_hosts[7]],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result, False)

    def test_get_filtered_hosts_with_force_nodes(self):
        fake_properties = {'force_nodes': ['fake-node2', 'fake-node4',
                                           'fake-node9']}

        # [5] is fake-node2, [7] is fake-node4
        info = {'expected_objs': [self.fake_hosts[5], self.fake_hosts[7]],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result, False)

    def test_get_filtered_hosts_with_force_hosts_and_nodes(self):
        # Ensure only overlapping results if both force host and node
        fake_properties = {'force_hosts': ['fake_host1', 'fake_multihost'],
                           'force_nodes': ['fake-node2', 'fake-node9']}

        # [5] is fake-node2
        info = {'expected_objs': [self.fake_hosts[5]],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result, False)

    def test_get_filtered_hosts_with_force_hosts_and_wrong_nodes(self):
        # Ensure non-overlapping force_node and force_host yield no result
        fake_properties = {'force_hosts': ['fake_multihost'],
                           'force_nodes': ['fake-node']}

        info = {'expected_objs': [],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result, False)

    def test_get_filtered_hosts_with_ignore_hosts_and_force_nodes(self):
        # Ensure ignore_hosts can coexist with force_nodes
        fake_properties = {'force_nodes': ['fake-node4', 'fake-node2'],
                           'ignore_hosts': ['fake_host1', 'fake_host2']}

        info = {'expected_objs': [self.fake_hosts[5], self.fake_hosts[7]],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result, False)

    def test_get_filtered_hosts_with_ignore_hosts_and_force_same_nodes(self):
        # Ensure ignore_hosts is processed before force_nodes
        fake_properties = {'force_nodes': ['fake_node4', 'fake_node2'],
                           'ignore_hosts': ['fake_multihost']}

        info = {'expected_objs': [],
                'expected_fprops': fake_properties}
        self._mock_get_filtered_hosts(info)

        self.mox.ReplayAll()

        result = self.host_manager.get_filtered_hosts(self.fake_hosts,
                                                      fake_properties)
        self._verify_result(info, result, False)

    def test_update_service_capabilities(self):
        service_states = self.host_manager.service_states
        self.assertEqual(len(service_states.keys()), 0)
        self.mox.StubOutWithMock(timeutils, 'utcnow')
        timeutils.utcnow().AndReturn(31337)
        timeutils.utcnow().AndReturn(31339)

        host1_capabs = dict(free_memory=1234, host_memory=5678,
                            timestamp=1, hypervisor_hostname='node1')
        host2_capabs = dict(free_memory=8756, timestamp=1,
                            hypervisor_hostname='node2')

        self.mox.ReplayAll()
        self.host_manager.update_service_capabilities('fake_service', 'host1',
                                                      host1_capabs)
        self.host_manager.update_service_capabilities('fake_service', 'host2',
                                                      host2_capabs)

        # Make sure original dictionary wasn't copied
        self.assertEqual(host1_capabs['timestamp'], 1)

        host1_capabs['timestamp'] = 31337
        host2_capabs['timestamp'] = 31339

        expected = {'host1': host1_capabs,
                    'host2': host2_capabs}
        self.assertEqual(service_states, expected)
