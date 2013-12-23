# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
test_lvm
----------------------------------

Tests for `lvm` module.
"""
from openstack.common.lvm import lvm
from openstack.common import processutils
from openstack.common import test


class TestLVMWrapper(test.BaseTestCase):
    def setUp(self):
        super(TestLVMWrapper, self).setUp()
        self.output = 'test'
        self.vg_ref = lvm.LVM('test', 'sudo',
                              False, None,
                              'default', self._fake_execute)
        self.root_helper = 'sudo cinder-rootwrap /etc/cinder/rootwrap.conf'

    def _fake_execute(self, _command, *_args, **_kwargs):
        return self.output, None

    def _fake_lvm_version(self, *cmd, **kwargs):
        return 'LVM version:     2.02.95(2) (2012-03-06)', ' '

    def _fake_lvm_version_old(self, *cmd, **kwargs):
        return 'LVM version:     2.02.90(2) (2010-09-16)', ' '

    def _fake_lvs(self, *cmd, **kwargs):
        results =\
            """ precise64 root                                        79.01g
                precise64 swap_1                                       0.75g
                stack-vg2 stack-vg2-pool                               8.56g
                stack-vg2 volume-4164e916-d2ef-4b01-b401-2b8564b3dab1  1.00g"""
        return results, ''

    def _fake_pvs(self, *cmd, **kwargs):
        results =\
            """
            stack-vg:/dev/sdb1:10.01g:5.00g
            stack-vg2:/dev/sdc1:10.01g:1.00g
            precise64:/dev/sda5:79.76g:0g"""
        return results, ''

    def _fake_vgs(self, *cmd, **kwargs):
        results = \
            """
              precise64:79.76g:0g:2:Ble7hc-9RJ7-G3oW-r1y8-FxYg-c40J-GEPM1I
              stack-vg:10.01g:10.01g:0:NBwh2D-qT8V-rYfE-R2z0-GY1q-Wh1R-ndWyRO
              stack-vg2:10.01g:0.43g:2:oJdVoN-rstq-hzjs-qUZ1-Afar-oPv6-bfbbOI
            """
        return results, ''

    def _fake_get_vg2(self, *cmd, **kwargs):
        results = \
            "stack-vg2:10.01g:0.43g:2:oJdVoN-rstq-hzjs-qUZ1-Afar-oPv6-bfbbOI"
        return results, ''

    def test_vg_exists(self):
        self.output = 'test'
        self.assertTrue(self.vg_ref._vg_exists())

        self.output = 'missing'
        self.assertFalse(self.vg_ref._vg_exists())

    def test_get_vg_uuid(self):
        self.output = "NBwh2D-qT8V-rYfE-R2z0-GY1q-Wh1R-ndWyRO"
        expected_result = self.output.split()
        self.assertEquals(self.vg_ref._get_vg_uuid(), expected_result)

    def test_get_thin_pool_free_space(self):
        self.output = "8.56:0.00"
        self.assertEquals(
            self.vg_ref._get_thin_pool_free_space('test-vg',
                                                  'test-vg-pool'), 8.56)

        self.output = "10.00:90.00"
        self.assertEquals(
            self.vg_ref._get_thin_pool_free_space('test-vg',
                                                  'test-vg-pool'), 1.00)

    def test_get_lvm_version(self):
        processutils.execute = self._fake_lvm_version
        self.assertEqual((2, 2, 95),
                         self.vg_ref.get_lvm_version(self.root_helper))

    def test_lvm_thin_support(self):
        processutils.execute = self._fake_lvm_version
        self.assertTrue(
            self.vg_ref.supports_thin_provisioning(self.root_helper))

        processutils.execute = self._fake_lvm_version_old
        self.assertFalse(
            self.vg_ref.supports_thin_provisioning(self.root_helper))

    def test_snapshot_activiation_support(self):
        self.vg_ref._supports_snapshot_lv_activation = None
        processutils.execute = self._fake_lvm_version
        self.assertTrue(self.vg_ref.supports_snapshot_lv_activation)

        processutils.execute = self._fake_lvm_version_old
        self.vg_ref._supports_snapshot_lv_activation = None
        self.assertFalse(self.vg_ref.supports_snapshot_lv_activation)

    def test_get_all_volumes(self):
        processutils.execute = self._fake_lvs

        expected = [{'name': 'root', 'size': '79.01g',
                     'vg': 'precise64'},
                    {'name': 'swap_1', 'size': '0.75g',
                     'vg': 'precise64'},
                    {'name': 'stack-vg2-pool', 'size': '8.56g',
                     'vg': 'stack-vg2'},
                    {'name': 'volume-4164e916-d2ef-4b01-b401-2b8564b3dab1',
                     'size': '1.00g', 'vg': 'stack-vg2'}]

        vols = self.vg_ref.get_all_volumes(self.root_helper)
        self.assertEquals(expected, vols)

    def test_get_volume(self):
        expected =\
            {'name': 'volume-4164e916-d2ef-4b01-b401-2b8564b3dab1',
             'size': '1.00g', 'vg': 'stack-vg2'}

        processutils.execute = self._fake_lvs
        self.assertEquals(expected,
                          self.vg_ref.get_volume(
                              'volume-4164e916-d2ef-4b01-b401-2b8564b3dab1'))

    def test_get_all_volume_groups(self):
        processutils.execute = self._fake_vgs
        expected = [
            {'name': 'precise64',
             'size': '79.76g',
             'available': '0g',
             'lv_count': '2',
             'uuid': 'Ble7hc-9RJ7-G3oW-r1y8-FxYg-c40J-GEPM1I'},
            {'name': 'stack-vg',
             'size': '10.01g',
             'available': '10.01g',
             'lv_count': '0',
             'uuid': 'NBwh2D-qT8V-rYfE-R2z0-GY1q-Wh1R-ndWyRO'},
            {'name': 'stack-vg2',
             'size': '10.01g',
             'available': '0.43g',
             'lv_count': '2',
             'uuid': 'oJdVoN-rstq-hzjs-qUZ1-Afar-oPv6-bfbbOI'}]

        self.assertEquals(
            expected, self.vg_ref.get_all_volume_groups(self.root_helper))

    def test_get_all_physical_volumes(self):
        processutils.execute = self._fake_pvs
        expected = [
            {'vg': 'stack-vg', 'name': '/dev/sdb1',
             'size': '10.01g', 'available': '5.00g'},
            {'vg': 'stack-vg2', 'name': '/dev/sdc1',
             'size': '10.01g', 'available': '1.00g'},
            {'vg': 'precise64', 'name': '/dev/sda5',
             'size': '79.76g', 'available': '0g'}]

        pvs = self.vg_ref.get_all_physical_volumes(self.root_helper)
        self.assertEquals(expected, pvs)

    def test_update_volume_group_info(self):
        processutils.execute = self._fake_get_vg2
        self.vg_ref.vg_name = 'stack-vg2'

        self.vg_ref.vg_free_space = '0.00g'
        self.vg_ref.vg_lv_count = '10'
        self.vg_ref.vg_size = '1000.00g'

        # Verify we modified the object
        self.assertEquals('0.00g', self.vg_ref.vg_free_space)
        self.assertEquals('10', self.vg_ref.vg_lv_count)
        self.assertEquals('1000.00g', self.vg_ref.vg_size)

        # Now run the update and make sure it's reflected correctly
        self.vg_ref.update_volume_group_info()
        self.assertEquals('0.43g', self.vg_ref.vg_free_space)
        self.assertEquals('2', self.vg_ref.vg_lv_count)
        self.assertEquals('10.01g', self.vg_ref.vg_size)

    def test_lv_has_snap(self):
        self.output = "Owi-ao--"
        self.assertTrue(self.vg_ref.lv_has_snapshot('test-vol'))

        self.output = "owi-ao--"
        self.assertTrue(self.vg_ref.lv_has_snapshot('test-vol'))

        self.output = "-wi-ao--"
        self.assertFalse(self.vg_ref.lv_has_snapshot('test-vol'))
